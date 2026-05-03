#!/usr/bin/env python3
"""
Database Setup Script - Creates/Recreates all tables with correct schema.

Run this to:
1. Drop all existing tables
2. Install pgvector extension  
3. Create all tables matching the SQLAlchemy models
4. Create indexes for fast search

Usage:
    python create_database.py
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'docqa')
DB_USER = os.getenv('DB_USER', 'docqa')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'docqa_password')
EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '768'))


def create_database():
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        print("ERROR: psycopg2 not installed!")
        print("Run: pip install psycopg2-binary")
        sys.exit(1)
    
    print("=" * 60)
    print("  DATABASE SETUP")
    print("=" * 60)
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print(f"Database: {DB_NAME}")
    print(f"Embedding Dimension: {EMBEDDING_DIMENSION}")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        print("✓ Connected to PostgreSQL")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    
    try:
        # Step 1: Install pgvector
        print("\n[1/6] Installing pgvector extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✓ pgvector ready")
        
        # Step 2: Drop all tables
        print("\n[2/6] Dropping existing tables...")
        cursor.execute("DROP TABLE IF EXISTS chat_messages CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS chat_sessions CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS document_chunks CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS documents CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
        print("✓ Old tables dropped")
        
        # Step 3: Create users table
        print("\n[3/6] Creating users table...")
        cursor.execute("""
            CREATE TABLE users (
                id VARCHAR(255) PRIMARY KEY,
                email VARCHAR(255) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            INSERT INTO users (id, email) VALUES ('default', 'default@local');
        """)
        print("✓ users table created (default user added)")
        
        # Step 4: Create documents table
        print("\n[4/6] Creating documents table...")
        cursor.execute("""
            CREATE TABLE documents (
                id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255) REFERENCES users(id),
                filename VARCHAR(500) NOT NULL,
                file_type VARCHAR(50) NOT NULL,
                file_path VARCHAR(1000) NOT NULL,
                file_size INTEGER,
                chunk_count INTEGER DEFAULT 0,
                doc_metadata JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX idx_documents_user ON documents(user_id);
            CREATE INDEX idx_documents_filename ON documents(filename);
        """)
        print("✓ documents table created")
        
        # Step 5: Create document_chunks table
        print(f"\n[5/6] Creating document_chunks table (vector({EMBEDDING_DIMENSION}))...")
        cursor.execute(f"""
            CREATE TABLE document_chunks (
                id VARCHAR(255) PRIMARY KEY,
                document_id VARCHAR(255) REFERENCES documents(id) ON DELETE CASCADE,
                user_id VARCHAR(255),
                content TEXT NOT NULL,
                embedding vector({EMBEDDING_DIMENSION}),
                chunk_index INTEGER,
                chunk_metadata JSON DEFAULT '{{}}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX idx_chunks_document ON document_chunks(document_id);
            CREATE INDEX idx_chunks_user ON document_chunks(user_id);
        """)
        print(f"✓ document_chunks table created ({EMBEDDING_DIMENSION} dimensions)")
        
        # Step 6: Create chat tables
        print("\n[6/6] Creating chat tables...")
        cursor.execute("""
            CREATE TABLE chat_sessions (
                id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255) REFERENCES users(id),
                title VARCHAR(500) DEFAULT 'New Chat',
                document_ids JSON DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX idx_sessions_user ON chat_sessions(user_id);
            
            CREATE TABLE chat_messages (
                id VARCHAR(255) PRIMARY KEY,
                session_id VARCHAR(255) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                sources JSON DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX idx_messages_session ON chat_messages(session_id);
        """)
        print("✓ chat tables created")
        
        # Create vector index
        print("\n[+] Creating vector index...")
        try:
            cursor.execute(f"""
                CREATE INDEX idx_chunks_embedding 
                ON document_chunks 
                USING hnsw (embedding vector_cosine_ops);
            """)
            print("✓ HNSW index created")
        except Exception as e:
            print(f"  Index will be created after data insert: {e}")
        
        # Verify
        print("\n" + "=" * 60)
        print("  VERIFICATION")
        print("=" * 60)
        
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        print("Tables:")
        for t in tables:
            print(f"  ✓ {t[0]}")
        
        # Check chat_sessions columns
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'chat_sessions' ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        print("\nchat_sessions columns:")
        for c in columns:
            print(f"  ✓ {c[0]}")
        
        print("\n" + "=" * 60)
        print("  ✓ DATABASE SETUP COMPLETE!")
        print("=" * 60)
        print("\nRun: python run.py")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    create_database()
