# =============================================================================
# Dockerfile - RagDoc App (FastAPI + LangChain RAG) — Offline Only
# =============================================================================
# Requires ragdoc-app-base:latest (built from app/Dockerfile.base).
# All Python packages and Tesseract OCR (eng+ara) are pre-installed in base.
#
# Build:
#   docker-compose build app
# =============================================================================

FROM ragdoc-app-base:latest

WORKDIR /app

# Copy application code
COPY ./app/                   /app/app/
COPY ./run.py                 /app/run.py
COPY ./migrate_embeddings.py  /app/migrate_embeddings.py
COPY ./requirements.txt       /app/requirements.txt
COPY ./client.html            /app/client.html

# Copy init.sql if it exists (optional, use glob pattern to ignore if missing)
COPY ./init.sq[l]             /app/

# models/ are volume-mounted at runtime (see docker-compose.yml)

# Install debugpy for VS Code remote debugging
RUN pip install --no-cache-dir debugpy

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Tesseract configuration
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

CMD ["python", "run.py"]
