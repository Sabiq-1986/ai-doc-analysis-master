#!/usr/bin/env python3
"""
Migration Script: Vector(768) -> Vector(384)

Migrates the embedding column from 768-dim DPR to 384-dim multilingual MiniLM.
All existing chunks are deleted and documents are re-embedded from saved files.

Usage:
    python migrate_embeddings.py

This script is idempotent — safe to run multiple times.
"""
import sys
import psycopg2
from pathlib import Path


def main():
    from app.config import get_settings
    settings = get_settings()

    print("=" * 60)
    print("  Embedding Migration: 768-dim -> 384-dim")
    print("  Model: paraphrase-multilingual-MiniLM-L12-v2")
    print("=" * 60)
    print()

    # Connect to database
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            dbname=settings.DB_NAME,
        )
        conn.autocommit = False
        cur = conn.cursor()
        print("[DB] Connected to PostgreSQL")
    except Exception as e:
        print(f"[DB] Cannot connect: {e}")
        sys.exit(1)

    # Check current embedding dimension
    try:
        cur.execute("""
            SELECT atttypmod FROM pg_attribute
            WHERE attrelid = 'document_chunks'::regclass
            AND attname = 'embedding'
        """)
        row = cur.fetchone()
        if row:
            current_dim = row[0]
            print(f"[DB] Current embedding column dimension: {current_dim}")
            if current_dim == 384:
                print("[DB] Already at 384 dimensions. Checking if re-embedding needed...")
        else:
            print("[DB] Embedding column not found — will be created on next startup.")
            conn.close()
            sys.exit(0)
    except Exception:
        print("[DB] Could not detect current dimension — proceeding with migration.")

    # Count existing chunks
    cur.execute("SELECT COUNT(*) FROM document_chunks")
    chunk_count = cur.fetchone()[0]
    print(f"[DB] Existing chunks: {chunk_count}")

    # Count documents
    cur.execute("SELECT COUNT(*) FROM documents")
    doc_count = cur.fetchone()[0]
    print(f"[DB] Existing documents: {doc_count}")

    if chunk_count > 0:
        print()
        print(f"[MIGRATE] Deleting {chunk_count} old chunks...")
        cur.execute("DELETE FROM document_chunks")
        print("[MIGRATE] Old chunks deleted.")

    # Reset chunk counts on documents
    cur.execute("UPDATE documents SET chunk_count = 0")

    # Alter the embedding column to 384 dimensions
    print("[MIGRATE] Altering embedding column: Vector(768) -> Vector(384)...")
    try:
        cur.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(384)")
        print("[MIGRATE] Column altered successfully.")
    except Exception as e:
        # If the column is already 384, this may fail; that's OK
        conn.rollback()
        print(f"[MIGRATE] Column alter note: {e}")
        # Reconnect after rollback
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            dbname=settings.DB_NAME,
        )
        conn.autocommit = False
        cur = conn.cursor()

    # Drop old IVFFlat index if exists (it's bound to old dimension)
    try:
        cur.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat")
        print("[MIGRATE] Dropped old IVFFlat index.")
    except Exception:
        pass

    conn.commit()
    print()
    print("[MIGRATE] Schema migration complete!")
    print()

    if doc_count == 0:
        print("[MIGRATE] No documents to re-embed. Done!")
        conn.close()
        return

    # Re-embed all documents
    print(f"[MIGRATE] Re-embedding {doc_count} documents with multilingual model...")
    print()

    # Get all documents
    cur.execute("SELECT id, user_id, filename, file_path, file_type FROM documents ORDER BY created_at")
    documents = cur.fetchall()
    conn.close()

    # Now use the application services to re-embed
    from app.parsers.document_processor import DocumentProcessor
    from app.services.vector_service import vector_service
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    processor = DocumentProcessor()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    success_count = 0
    error_count = 0

    for doc_id, user_id, filename, file_path, file_type in documents:
        try:
            if not Path(file_path).exists():
                print(f"  [{error_count + success_count + 1}/{doc_count}] SKIP: {filename} (file not found)")
                error_count += 1
                continue

            # Parse
            chunks = processor.parse(file_path, file_type)

            # Chunk if needed
            if not processor.is_already_chunked(file_type):
                chunks = text_splitter.split_documents(chunks) if chunks else []

            # Set metadata
            for c in chunks:
                c.metadata["source"] = filename
                c.metadata["filename"] = filename

            # Add to vector store
            if chunks:
                vector_service.add_documents(user_id, doc_id, chunks)

            # Update chunk count
            conn2 = psycopg2.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                dbname=settings.DB_NAME,
            )
            cur2 = conn2.cursor()
            cur2.execute("UPDATE documents SET chunk_count = %s WHERE id = %s", (len(chunks), doc_id))
            conn2.commit()
            conn2.close()

            success_count += 1
            print(f"  [{success_count + error_count}/{doc_count}] OK: {filename} ({len(chunks)} chunks)")

        except Exception as e:
            error_count += 1
            print(f"  [{success_count + error_count}/{doc_count}] ERROR: {filename}: {e}")

    print()
    print("=" * 60)
    print(f"  Migration complete!")
    print(f"  Success: {success_count}/{doc_count}")
    if error_count:
        print(f"  Errors: {error_count}/{doc_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
