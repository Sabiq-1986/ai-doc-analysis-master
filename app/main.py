# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from app.api.routes import router
from app.models.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("=" * 50)
    print("Starting Document Q&A API...")
    print("=" * 50)
    
    print("Initializing database with pgvector...")
    await init_db()
    print("✓ Database initialized")
    
    print("Loading multilingual embedding model...")
    from app.services.vector_service import vector_service
    print("✓ Embedding model loaded")

    # Check Tesseract OCR availability
    print("Checking Tesseract OCR...")
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages()
        print(f"✓ Tesseract {version} (languages: {', '.join(langs)})")
        if 'ara' not in langs:
            print("  Note: Arabic language pack not installed (tesseract-ocr-ara)")
    except Exception:
        print("  Note: Tesseract OCR not available (image OCR will be limited)")

    print("=" * 50)
    print("API is ready!")
    print("Open http://localhost:8000 in your browser")
    print("=" * 50)
    
    yield
    
    print("Shutting down...")


app = FastAPI(
    title="Document Q&A API",
    description="RAG-based Document Question Answering System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


@app.get("/", tags=["Root"])
async def root():
    """Serve the client.html file."""
    # Look for client.html in the project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client_path = os.path.join(base_dir, "client.html")
    
    if os.path.exists(client_path):
        return FileResponse(client_path, media_type="text/html")
    
    # Fallback to JSON if client.html not found
    return {
        "message": "Document Q&A API",
        "note": "client.html not found. Place it in the project root.",
        "docs": "/docs"
    }