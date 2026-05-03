# Docker Build Guide — RagDoc

Build and deploy RagDoc with Docker. Includes local Tesseract OCR (English + Arabic) and multilingual embeddings.

## Prerequisites

- Docker and Docker Compose
- PostgreSQL with pgvector running (on `pg18_default` network)
- Ollama running on host (for LLM chat)

## Quick Start

```bash
# 1. Build base image (includes Tesseract + Python packages)
cd app
docker build -f Dockerfile.base -t ragdoc-app-base:latest .
cd ..

# 2. Build and start app (edit .env first if needed)
docker-compose up -d --build

# 3. Check logs
docker-compose logs -f app
```

Open http://localhost:8000 in your browser.

## Build Steps (Detailed)

### Step 1: Download Python Wheels (for offline build)

Run on a machine with internet access:

```bash
cd app
# Windows
download_wheels.bat

# Linux/Mac
./download_wheels.sh
```

This downloads all Python packages to `app/packages/`.

### Step 2: Build Base Image

The base image includes:
- Python 3.12
- Tesseract OCR with English + Arabic language packs
- All Python dependencies (torch, transformers, langchain, etc.)
- OpenCV for image preprocessing

```bash
cd app
docker build -f Dockerfile.base -t ragdoc-app-base:latest .
```

### Step 3: Configure Environment

Edit `.env` with your settings (defaults work for most setups):

```env
# PostgreSQL
DB_HOST=postgres-18
DB_PORT=5432
DB_NAME=docqa
DB_USER=docqa
DB_PASSWORD=docqa_password

# Ollama (adjust for your setup)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_VISION_MODEL=llama3.2-vision

# Embeddings (multilingual)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384
```

### Step 4: Download Embedding Models (for offline)

Download HuggingFace models to `./models/` for offline operation:

```bash
mkdir -p models
# Download with Python
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
model.save('./models/paraphrase-multilingual-MiniLM-L12-v2')
"
```

Update `.env`:
```env
HF_MODELS_OFFLINE=true
HF_MODELS_PATH=/app/models
EMBEDDING_MODEL=./models/paraphrase-multilingual-MiniLM-L12-v2
```

### Step 5: Build and Run

```bash
docker-compose up -d --build
```

## Migration (from old 768-dim embeddings)

If you have existing data with 768-dim DPR embeddings:

```bash
docker-compose exec app python migrate_embeddings.py
```

This will:
1. Drop old chunks
2. Alter column Vector(768) → Vector(384)
3. Re-embed all documents with multilingual model

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  ragdoc-app container                                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ FastAPI + uvicorn                                      │ │
│  │ ┌──────────────┐  ┌─────────────────────────────────┐  │ │
│  │ │ API Routes   │  │ DocumentProcessor               │  │ │
│  │ └──────┬───────┘  │ ┌─────────┐ ┌─────────────────┐ │  │ │
│  │        │          │ │PDFParser│ │ExcelParser      │ │  │ │
│  │        │          │ │WordParser│ │(1234 lines)    │ │  │ │
│  │        │          │ │PPTXParser│ │ImageParser     │ │  │ │
│  │        │          │ └─────────┘ └─────────────────┘ │  │ │
│  │        │          │ ┌─────────────────────────────┐ │  │ │
│  │        │          │ │ Tesseract OCR (eng+ara)    │ │  │ │
│  │        │          │ │ + Ollama AI Vision         │ │  │ │
│  │        │          │ └─────────────────────────────┘ │  │ │
│  │        │          └─────────────────────────────────┘  │ │
│  │        │                                               │ │
│  │  ┌─────▼─────────────────────────────────────────────┐ │ │
│  │  │ VectorService (multilingual embeddings 384-dim)   │ │ │
│  │  └───────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Volume: models/ (HuggingFace models, MRZ ONNX)        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌──────────────────────┐           ┌────────────────────────┐
│ PostgreSQL + pgvector│           │ Ollama (host)          │
│ (pg18_default network)│          │ llama3.1:8b            │
│                      │           │ llama3.2-vision        │
└──────────────────────┘           └────────────────────────┘
```

## Volumes

| Volume | Path | Purpose |
|--------|------|---------|
| `ragdoc-uploads` | `/app/data/uploads` | Uploaded documents |
| `./models` | `/app/models` | HuggingFace models (offline) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama API URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | Chat model |
| `OLLAMA_VISION_MODEL` | `llama3.2-vision` | Vision model for AI-enhanced parsing |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Multilingual embeddings |
| `EMBEDDING_DIMENSION` | `384` | Embedding vector size |
| `TESSERACT_LANGS` | `eng+ara` | OCR languages |
| `CHUNK_SIZE` | `1000` | Document chunk size |
| `RETRIEVAL_K` | `4` | Number of chunks to retrieve |

## Troubleshooting

### Tesseract not found
The base image includes Tesseract. Check with:
```bash
docker-compose exec app tesseract --version
docker-compose exec app tesseract --list-langs
```

### Ollama connection refused
On Linux, ensure `extra_hosts` is set in docker-compose.yml:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Or use your host IP directly:
```env
OLLAMA_BASE_URL=http://192.168.1.100:11434
```

### PostgreSQL connection error
Ensure PostgreSQL is on the `pg18_default` network:
```bash
docker network inspect pg18_default
```

### Migration fails
Check PostgreSQL logs and ensure pgvector extension is installed:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
