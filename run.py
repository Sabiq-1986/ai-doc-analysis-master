#!/usr/bin/env python3
# run.py - Main entry point for the Document Q&A application

import torch
import uvicorn
import sys
import time
import platform


def check_tesseract():
    """Check if Tesseract OCR is installed."""
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages()
        return True, str(version), langs
    except Exception:
        return False, None, []


def check_ollama():
    """Check if Ollama is running."""
    try:
        import requests
        from app.config import get_settings
        settings = get_settings()
        ollama_url = settings.OLLAMA_BASE_URL.rstrip('/')
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def check_postgres():
    """Check if PostgreSQL is running and accessible."""
    try:
        import psycopg2
        from app.config import get_settings
        settings = get_settings()
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            dbname=settings.DB_NAME
        )
        
        # Check if pgvector extension is available
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        has_vector = cur.fetchone() is not None
        
        cur.close()
        conn.close()
        
        return True, has_vector
    except Exception as e:
        return False, False


def print_banner():
    """Print application banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║        📄 Document Q&A System with RAG                        ║
    ║        PostgreSQL + pgvector + Ollama                         ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def main():
    print_banner()
    
    # Check PostgreSQL
    print("🔍 Checking PostgreSQL...")
    pg_running, has_pgvector = check_postgres()
    
    if not pg_running:
        print("❌ PostgreSQL is not running or not accessible!")
        print("")
        print("   To fix this, choose ONE of these options:")
        print("")
        print("   Option A: Use Docker (easiest)")
        print("   $ docker-compose up -d")
        print("")
        print("   Option B: Run the setup script")
        print("   $ python create_database.py")
        print("")
        print("   Option C: Manual setup (see setup_database.sql)")
        print("")
        print("   Current settings (edit in app/config.py or .env file):")
        try:
            from app.config import get_settings
            s = get_settings()
            print(f"   - Host: {s.DB_HOST}")
            print(f"   - Port: {s.DB_PORT}")
            print(f"   - Database: {s.DB_NAME}")
            print(f"   - User: {s.DB_USER}")
        except:
            print("   - Could not load settings")
        print("")
        sys.exit(1)
    
    print("✅ PostgreSQL is running")
    
    if not has_pgvector:
        print("⚠️  pgvector extension not found (will be created on startup)")
    else:
        print("✅ pgvector extension is installed")
    
    # Check Tesseract OCR
    print("")
    print("🔍 Checking Tesseract OCR...")
    tess_ok, tess_version, tess_langs = check_tesseract()

    if tess_ok:
        print(f"✅ Tesseract {tess_version} installed")
        if 'ara' in tess_langs:
            print("✅ Arabic language pack available")
        else:
            print("⚠️  Arabic language pack not found")
            print("   Install with: sudo apt install tesseract-ocr-ara")
            print("   (or: choco install tesseract --pre  on Windows)")
        if 'eng' in tess_langs:
            print("✅ English language pack available")
    else:
        print("⚠️  Tesseract OCR not found (image/PDF OCR will be limited)")
        print("   Install: sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara")
        print("   (or: choco install tesseract --pre  on Windows)")

    # Check Ollama
    print("")
    print("🔍 Checking Ollama...")
    
    if not check_ollama():
        print("❌ Ollama is not running!")
        print("")
        print("   To start Ollama, run in a separate terminal:")
        print("   $ ollama serve")
        print("")
        print("   Make sure you have pulled a model:")
        print("   $ ollama pull llama3.1:8b")
        print("")
        sys.exit(1)
    
    print("✅ Ollama is running")
    
    # Determine if we should use reload mode
    # On Windows, reload=True causes PyTorch DLL issues with multiprocessing
    is_windows = platform.system() == "Windows"
    use_reload = not is_windows
    
    # Start the application
    print("")
    print("=" * 60)
    print("🚀 Starting Document Q&A API...")
    print("")
    print("   API Documentation: http://localhost:8000/docs")
    print("   Health Check:      http://localhost:8000/health")
    print("   API Base URL:      http://localhost:8000/api/v1")
    print("   Web Interface:     http://localhost:8000/client.html")
    print("")
    if is_windows:
        print("   ⚠️  Auto-reload disabled on Windows (PyTorch compatibility)")
        print("   Restart manually after code changes.")
    print("")
    print("=" * 60)
    print("")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=use_reload,
        log_level="info",
        timeout_keep_alive=1200,  # 20 minutes
        limit_concurrency=100,
    )


if __name__ == "__main__":
    main()