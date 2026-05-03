# RagDoc — Document Q&A with RAG

A RAG-based document intelligence platform with:
- **Multilingual support** (Arabic + English) via sentence-transformers
- **Local Tesseract OCR** with Arabic language support
- **Comprehensive document parsing** (PDF, Word, Excel, PowerPoint, Images)
- **MRZ extraction** for passports and ID cards
- **PostgreSQL + pgvector** for vector storage
- **Ollama** for local LLM

## Features

| Format | Parser | Capabilities |
|--------|--------|-------------|
| **PDF** | PyMuPDF + pdfplumber + Tesseract | Layout-aware text, tables, OCR for scanned pages, form fields, TOC, embedded images |
| **Word** | python-docx | Headers/footers, footnotes, comments, tracked changes, embedded images |
| **Excel** | openpyxl | Merged cells, formulas, charts, pivot tables, 25+ currency formats, column statistics |
| **PowerPoint** | python-pptx | Slides, speaker notes, tables, charts, grouped shapes, embedded images |
| **Images** | Tesseract + AI Vision | 9 preprocessing strategies, Arabic+English OCR, document classification |
| **Passports/IDs** | MRZ Reader | TD1/TD2/TD3 formats, ICAO 9303 validation, multi-rotation detection |
| **Text/CSV/JSON/XML** | Smart parsers | Auto-delimiter detection, JSON normalization, XML tree, Arabic encoding |

## Quick Start (Docker)

### Prerequisites

- Docker & Docker Compose
- Ollama running on host machine

### Step 1: Start Ollama on Host

```bash
# Install Ollama (if not installed)
# Windows: Download from https://ollama.ai
# Linux: curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama and pull required models
ollama serve
ollama pull llama3.1:8b
ollama pull llama3.2-vision  # Optional: for AI-enhanced OCR
```

### Step 2: Download Python Packages (one-time, requires internet)

```bash
cd app
download_wheels.bat      # Windows
# ./download_wheels.sh   # Linux/Mac
```

### Step 3: Build and Run with Docker

```bash
# Build base image (includes Tesseract OCR + Python packages)
docker build -f Dockerfile.base -t ragdoc-app-base:latest .
cd ..

# Start the application
docker-compose up -d --build
```

Open http://localhost:8000 in your browser.

### Step 4: Verify Services

```bash
# Check logs
docker-compose logs -f app

# Verify Ollama connectivity (from container)
docker exec ragdoc-app curl -s http://host.docker.internal:11434/api/tags
```

## Configuration

The `.env` file configures the application. Key settings for Docker:

```env
# PostgreSQL (Docker internal network)
DB_HOST=db
DB_PORT=5432
DB_NAME=docqa
DB_USER=docqa
DB_PASSWORD=docqa_password

# Ollama (running on host machine)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_VISION_MODEL=llama3.2-vision

# Embeddings (multilingual)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384

# Tesseract OCR (built into Docker image)
TESSERACT_LANGS=eng+ara

# Document Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
RETRIEVAL_K=4
```

**Note:** `host.docker.internal` allows the Docker container to access Ollama running on your host machine.

## Local Development (Alternative)

For development without Docker:

```bash
# Prerequisites: Python 3.10-3.12, PostgreSQL with pgvector, Tesseract OCR

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup database
psql -U postgres -f setup_database.sql

# Run the application
python run.py
```

See [DOCKER_BUILD.md](DOCKER_BUILD.md) for detailed Docker build instructions.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI (app/main.py)                                          │
│  ┌─────────────────┐  ┌─────────────────────────────────────┐   │
│  │ API Routes      │  │ DocumentProcessor (orchestrator)    │   │
│  └────────┬────────┘  │ ┌─────────┐ ┌─────────┐ ┌─────────┐ │   │
│           │           │ │PDFParser│ │WordParser│ │ExcelParser│   │
│           │           │ │PPTXParser│ │ImageParser│ │TextParser│   │
│           │           │ └─────────┘ └─────────┘ └─────────┘ │   │
│           │           │ ┌─────────────────────────────────┐ │   │
│           │           │ │ Tesseract OCR (eng+ara)        │ │   │
│           │           │ │ + MRZ Reader + AI Vision       │ │   │
│           │           │ └─────────────────────────────────┘ │   │
│           │           └─────────────────────────────────────┘   │
│           │                                                      │
│  ┌────────▼────────────────────────────────────────────────┐    │
│  │ VectorService (multilingual embeddings, 384-dim)        │    │
│  │ Hybrid search: keyword (ILIKE) + semantic (cosine)      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                    │                              │
                    ▼                              ▼
         ┌──────────────────┐           ┌─────────────────┐
         │ PostgreSQL       │           │ Ollama          │
         │ + pgvector       │           │ llama3.1:8b     │
         └──────────────────┘           └─────────────────┘
```

## API Endpoints

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload a document |
| GET | `/api/v1/documents` | List all documents |
| GET | `/api/v1/documents/{id}` | Get document details |
| DELETE | `/api/v1/documents/{id}` | Delete a document |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/sessions` | Create a new session |
| GET | `/api/v1/chat/sessions` | List all sessions |
| POST | `/api/v1/chat/sessions/{id}/messages` | Send a message (SSE streaming) |
| DELETE | `/api/v1/chat/sessions/{id}` | Delete a session |

### Example

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Upload document
with open("document.pdf", "rb") as f:
    resp = requests.post(f"{BASE_URL}/documents/upload", files={"file": f})
doc_id = resp.json()["id"]

# Create chat session
resp = requests.post(f"{BASE_URL}/chat/sessions", json={"document_ids": [doc_id]})
session_id = resp.json()["id"]

# Ask question (streaming)
resp = requests.post(
    f"{BASE_URL}/chat/sessions/{session_id}/messages",
    json={"content": "What is this document about?"},
    stream=True
)
for line in resp.iter_lines():
    print(line.decode())
```

## Project Structure

```
RagDoc/
├── app/
│   ├── api/routes.py           # FastAPI endpoints
│   ├── models/database.py      # SQLAlchemy + pgvector
│   ├── services/
│   │   ├── document_service.py # Document processing
│   │   ├── vector_service.py   # Embeddings + search
│   │   └── chat_service.py     # RAG + streaming
│   ├── parsers/                # Modular document parsers
│   │   ├── ai_enhancer.py      # Ollama Vision/Text
│   │   ├── image_parser.py     # Tesseract OCR (eng+ara)
│   │   ├── mrz_reader.py       # Passport/ID MRZ
│   │   ├── pdf_parser.py       # PDF extraction
│   │   ├── word_parser.py      # Word extraction
│   │   ├── excel_parser.py     # Comprehensive Excel
│   │   ├── pptx_parser.py      # PowerPoint extraction
│   │   ├── text_parser.py      # CSV/JSON/XML
│   │   ├── document_processor.py # Orchestrator
│   │   └── models/mrz_seg.onnx # MRZ segmentation model
│   ├── config.py
│   └── main.py
├── client.html                 # Web UI
├── run.py                      # Entry point
├── migrate_embeddings.py       # DB migration script
├── Dockerfile
├── docker-compose.yml
└── DOCKER_BUILD.md
```

## Supported File Types

`.pdf` `.docx` `.doc` `.xlsx` `.xls` `.xlsm` `.pptx` `.ppt`
`.png` `.jpg` `.jpeg` `.gif` `.bmp` `.tiff` `.webp`
`.txt` `.csv` `.tsv` `.md` `.json` `.xml` `.html` `.log`

## Bilingual Support

The system supports Arabic and English:
- **OCR**: Tesseract with `eng+ara` language packs
- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` (50+ languages)
- **Chat**: Responds in the same language as the question

Ask questions in Arabic and get Arabic responses:
```
User: ما هو محتوى هذا المستند؟
Assistant: هذا المستند يحتوي على...
```

## Migration from DPR (768-dim)

If you have existing data with 768-dim DPR embeddings:

```bash
python migrate_embeddings.py
```

This will:
1. Drop old chunks
2. Alter column Vector(768) → Vector(384)
3. Re-embed all documents with multilingual model

## License

MIT License
