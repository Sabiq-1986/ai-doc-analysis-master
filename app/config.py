# app/config.py
"""
=======================================================
  CONFIGURATION FILE - Edit these settings as needed!
=======================================================
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # =======================================================
    #  PostgreSQL Database Settings
    # =======================================================
    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_NAME: str = 'docqa'
    DB_USER: str = 'docqa'
    DB_PASSWORD: str = 'docqa_password'  # <-- CHANGE THIS in production!

    # =======================================================
    #  Ollama (Local LLM) Settings
    # =======================================================
    OLLAMA_BASE_URL: str = 'http://host.docker.internal:11434'
    OLLAMA_MODEL: str = 'qwen2.5:7b'  # Options: 'llama3.1:8b', 'mistral:7b'
    OLLAMA_VISION_MODEL: str = 'llama3.2-vision'  # For AI-enhanced document parsing

    # =======================================================
    #  Embedding Model Settings (Multilingual)
    # =======================================================
    # Multilingual model: supports Arabic, English, and 50+ languages
    EMBEDDING_MODEL: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    EMBEDDING_DIMENSION: int = 384  # 384 for multilingual MiniLM

    # Offline model settings (for air-gapped deployment)
    HF_MODELS_OFFLINE: bool = False  # Set to True for offline mode
    HF_MODELS_PATH: str = '/app/models'  # Path to pre-downloaded models

    # Legacy DPR settings (kept for .env backward compatibility, not used)
    USE_DPR: bool = False
    DPR_QUESTION_ENCODER: str = 'facebook/dpr-question_encoder-single-nq-base'
    DPR_CONTEXT_ENCODER: str = 'facebook/dpr-ctx_encoder-single-nq-base'

    # =======================================================
    #  Tesseract OCR Settings (Local)
    # =======================================================
    TESSERACT_CMD: str = ''  # Path to tesseract executable (auto-detect if empty)
    TESSERACT_LANGS: str = 'eng+ara'  # OCR languages: English + Arabic

    # =======================================================
    #  Document Processing Settings
    # =======================================================
    CHUNK_SIZE: int = 800  # Smaller chunks = faster processing
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_K: int = 40  # Retrieve more candidates, rerank down to top N

    # =======================================================
    #  Full Context Mode (skip RAG for small documents)
    # =======================================================
    FULL_CONTEXT_MAX_CHARS: int = 50000  # ~12K tokens; docs under this skip RAG

    # =======================================================
    #  Reranker Settings (cross-encoder for better retrieval)
    # =======================================================
    RERANKER_MODEL: str = 'cross-encoder/bge-reranker-v2-m3'
    RERANKER_TOP_N: int = 16  # Final chunks after reranking (for large context LLMs)

    # =======================================================
    #  Timeout Settings (in seconds)
    # =======================================================
    OLLAMA_TIMEOUT: int = 1200  # 20 minutes

    # =======================================================
    #  File Storage Settings
    # =======================================================
    UPLOAD_DIR: str = './data/uploads'

    # =======================================================
    #  Computed Properties (Auto-generated)
    # =======================================================
    @property
    def DATABASE_URL(self) -> str:
        """Async connection string for FastAPI."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync connection string for vector operations."""
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in .env file


@lru_cache()
def get_settings():
    settings = Settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    return settings


# =======================================================
#  Export settings for easy access
# =======================================================
# You can import these directly: from app.config import DB_HOST, DB_PORT, etc.

def _get_setting(name):
    return getattr(get_settings(), name)

# Make settings accessible as module-level variables
DB_HOST = property(lambda self: _get_setting('DB_HOST'))
DB_PORT = property(lambda self: _get_setting('DB_PORT'))
DB_NAME = property(lambda self: _get_setting('DB_NAME'))
DB_USER = property(lambda self: _get_setting('DB_USER'))
DB_PASSWORD = property(lambda self: _get_setting('DB_PASSWORD'))
