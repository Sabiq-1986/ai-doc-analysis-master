# app/services/document_service.py
"""
Document Service - Upload, process, store, and manage documents.
Uses the modular DocumentProcessor for parsing all file types.
"""
import os
from pathlib import Path
from typing import Optional, List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.database import Document as DBDocument
from app.services.vector_service import vector_service
from app.parsers.document_processor import DocumentProcessor

settings = get_settings()


class DocumentService:
    """Document service using modular parsers with local OCR and AI Vision."""

    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        self.processor = DocumentProcessor()
        print(f"[DOC] Document service initialized (local OCR + AI Vision)")

    async def process_document(self, db: AsyncSession, user_id: str, filename: str, content: bytes) -> DBDocument:
        """Process any document using modular parsers."""
        print(f"[DOC] Processing: {filename}")

        file_ext = Path(filename).suffix.lower()

        # Validate file type
        supported = self.processor.get_supported_types()
        if file_ext not in supported:
            raise ValueError(f"Unsupported: {file_ext}. Supported: {', '.join(supported)}")

        # Save file
        user_dir = self.upload_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / filename

        with open(file_path, 'wb') as f:
            f.write(content)

        # Parse using DocumentProcessor
        documents = self.processor.parse(str(file_path), file_ext)

        # Chunk long-text documents; pre-chunked formats (Excel rows, slides, etc.) pass through
        if self.processor.is_already_chunked(file_ext):
            chunks = documents
        else:
            chunks = self.text_splitter.split_documents(documents) if documents else []

        # Ensure metadata
        for c in chunks:
            c.metadata["source"] = filename
            c.metadata["filename"] = filename

        print(f"[DOC] Total chunks: {len(chunks)}")

        # Save to database
        doc = DBDocument(
            user_id=user_id, filename=filename, file_type=file_ext,
            file_path=str(file_path), file_size=len(content), chunk_count=len(chunks),
            doc_metadata={"source": filename, "type": file_ext}
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Add to vector store
        if chunks:
            vector_service.add_documents(user_id, doc.id, chunks)

        return doc

    async def get_user_documents(self, db: AsyncSession, user_id: str) -> list[DBDocument]:
        result = await db.execute(select(DBDocument).where(DBDocument.user_id == user_id).order_by(DBDocument.created_at.desc()))
        return list(result.scalars().all())

    async def get_document(self, db: AsyncSession, document_id: str, user_id: str) -> Optional[DBDocument]:
        result = await db.execute(select(DBDocument).where(DBDocument.id == document_id, DBDocument.user_id == user_id))
        return result.scalar_one_or_none()

    async def delete_document(self, db: AsyncSession, document_id: str, user_id: str) -> bool:
        doc = await self.get_document(db, document_id, user_id)
        if not doc:
            return False
        vector_service.delete_document(user_id, document_id)
        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except Exception:
            pass
        await db.delete(doc)
        await db.commit()
        return True


document_service = DocumentService()
