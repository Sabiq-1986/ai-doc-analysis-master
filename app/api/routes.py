# app/api/routes.py
"""API Routes with STREAMING support."""
import json
import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.services.document_service import document_service
from app.services.chat_service import chat_service
from app.schemas.schemas import (
    DocumentUploadResponse, DocumentResponse,
    ChatSessionCreate, ChatSessionResponse,
    MessageCreate, ChatResponse
)

router = APIRouter()
DEFAULT_USER_ID = "default"


def format_sources(sources):
    """Convert sources to list of dicts."""
    if not sources:
        return []
    return [{"filename": s} if isinstance(s, str) else s for s in sources]


# ============ Document Endpoints ============

@router.post("/documents/upload", response_model=DocumentUploadResponse, tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        content = await file.read()
        doc = await document_service.process_document(db=db, user_id=DEFAULT_USER_ID, filename=file.filename, content=content)

        # Link document to session if session_id provided
        if session_id:
            await chat_service.add_documents_to_session(db, session_id, DEFAULT_USER_ID, [doc.id])

        return DocumentUploadResponse(id=doc.id, filename=doc.filename, file_type=doc.file_type, chunk_count=doc.chunk_count, message=f"Processed with {doc.chunk_count} chunks")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents", response_model=list[DocumentResponse], tags=["Documents"])
async def list_documents(db: AsyncSession = Depends(get_db)):
    docs = await document_service.get_user_documents(db, DEFAULT_USER_ID)
    return [DocumentResponse(id=doc.id, filename=doc.filename, file_type=doc.file_type, chunk_count=doc.chunk_count, created_at=doc.created_at) for doc in docs]

@router.delete("/documents/{document_id}", tags=["Documents"])
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    if not await document_service.delete_document(db, DEFAULT_USER_ID, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Deleted"}


# ============ Chat Session Endpoints ============

@router.post("/chat/sessions", response_model=ChatSessionResponse, tags=["Chat"])
async def create_chat_session(session_data: ChatSessionCreate, db: AsyncSession = Depends(get_db)):
    session = await chat_service.create_session(db=db, user_id=DEFAULT_USER_ID, title=session_data.title, document_ids=session_data.document_ids)
    return ChatSessionResponse(id=session.id, title=session.title, document_ids=session.document_ids or [], created_at=session.created_at)

@router.get("/chat/sessions", response_model=list[ChatSessionResponse], tags=["Chat"])
async def list_chat_sessions(db: AsyncSession = Depends(get_db)):
    sessions = await chat_service.get_user_sessions(db, DEFAULT_USER_ID)
    return [ChatSessionResponse(id=s.id, title=s.title, document_ids=s.document_ids or [], created_at=s.created_at) for s in sessions]

@router.get("/chat/sessions/{session_id}", tags=["Chat"])
async def get_chat_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session, messages = await chat_service.get_session(db, session_id, DEFAULT_USER_ID)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "id": session.id,
        "title": session.title,
        "document_ids": session.document_ids or [],
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": format_sources(m.sources),
                "created_at": m.created_at
            }
            for m in messages
        ],
        "created_at": session.created_at,
        "updated_at": session.updated_at
    }

@router.patch("/chat/sessions/{session_id}", response_model=ChatSessionResponse, tags=["Chat"])
async def update_chat_session(session_id: str, title: str = Query(...), db: AsyncSession = Depends(get_db)):
    session = await chat_service.update_session_title(db, session_id, DEFAULT_USER_ID, title)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionResponse(id=session.id, title=session.title, document_ids=session.document_ids or [], created_at=session.created_at)

@router.delete("/chat/sessions/{session_id}", tags=["Chat"])
async def delete_chat_session(session_id: str, db: AsyncSession = Depends(get_db)):
    if not await chat_service.delete_session(db, session_id, DEFAULT_USER_ID):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Deleted"}

@router.post("/chat/sessions/{session_id}/documents", tags=["Chat"])
async def set_session_documents(session_id: str, document_ids: list[str], db: AsyncSession = Depends(get_db)):
    try:
        session = await chat_service.add_documents_to_session(db, session_id, DEFAULT_USER_ID, document_ids)
        return {"message": "Updated", "document_ids": session.document_ids}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============ STREAMING Chat Endpoint ============

@router.post("/chat/sessions/{session_id}/messages/stream", tags=["Chat"])
async def stream_message(session_id: str, message: MessageCreate, db: AsyncSession = Depends(get_db)):
    """Stream chat response using Server-Sent Events."""
    
    async def event_generator():
        try:
            async for chunk in chat_service.stream_chat(
                db=db,
                user_id=DEFAULT_USER_ID,
                session_id=session_id,
                question=message.content
            ):
                # Format as SSE
                yield f"data: {chunk}\n\n"
                # Force flush by yielding empty string
                await asyncio.sleep(0)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Content-Type": "text/event-stream",
        }
    )


# ============ Non-streaming endpoint ============

@router.post("/chat/sessions/{session_id}/messages", response_model=ChatResponse, tags=["Chat"])
async def send_message(session_id: str, message: MessageCreate, db: AsyncSession = Depends(get_db)):
    """Non-streaming message endpoint."""
    try:
        result = await chat_service.chat(db=db, user_id=DEFAULT_USER_ID, session_id=session_id, question=message.content)
        return ChatResponse(
            answer=result["response"],
            sources=result["sources"],
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Test endpoint to verify streaming ============

@router.get("/test/stream", tags=["Test"])
async def test_stream():
    """Test streaming without Ollama - sends numbers 1-10 with delay."""
    async def generate():
        for i in range(1, 11):
            yield f"data: {json.dumps({'type': 'token', 'content': f' {i}'})}\n\n"
            await asyncio.sleep(0.3)  # 300ms delay between numbers
        yield f"data: {json.dumps({'type': 'done', 'content': ' 1 2 3 4 5 6 7 8 9 10'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )