# RAG Service

Production-grade multi-modal RAG (Retrieval-Augmented Generation) system with support for text, images, audio, and video documents.

## Features

- **Multi-modal document processing**:
  - Text documents: PDF, DOCX, TXT
  - Scanned documents: OCR with Tesseract
  - Images: Automatic captioning with vision models
  - Audio & Video: Transcription with Whisper

- **Hybrid retrieval**:
  - Dense vector search with Qdrant
  - Sparse retrieval with BM25
  - Reciprocal Rank Fusion (RRF)
  - LLM-based relevance reranking with GPT-4o-mini

- **Production-ready architecture**:
  - FastAPI REST API
  - Async task processing with RQ
  - Local-first storage
  - Containerized services

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│   FastAPI Server    │
│  (Upload & Query)   │
└──────┬──────────────┘
       │
       ├──────────────┐
       │              │
       ▼              ▼
┌─────────────┐  ┌──────────────┐
│  RQ Worker  │  │   Retrieval  │
│ (Ingestion) │  │   Pipeline   │
└──────┬──────┘  └───┬──────┬───┘
       │             │      │
       ▼             ▼      ▼
┌─────────────────────────────┐
│  Document Processors        │
│  • Text (unstructured)      │
│  • Image (BLIP)             │
│  • Audio/Video (Whisper)    │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Chunking & Embedding       │
│  • OpenAI embeddings        │
│  •  (text-embedding-3)      │
│  • Token-based chunking     │
└──────┬──────────────────────┘
       │
       ▼
┌──────────────────┬──────────┐
│  Qdrant (Dense)  │  BM25    │
└──────────────────┴──────────┘
       │
       ▼
┌─────────────────────────────┐
│  Hybrid Retrieval + Rerank  │
│  • RRF fusion               │
│  • LLM-based reranking      │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  OpenAI GPT-4o-mini         │
│  • Structured Outputs       │
│  • Citation tracking        │
└─────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- **OpenAI API Key** (for embeddings, reranking, and generation)
- System dependencies:
  - Tesseract OCR
  - Poppler (for PDF processing)
  - FFmpeg (for audio/video processing)

### Installation

1. **Clone and setup**:
```bash
git clone <your-repo>
cd rag-service
./scripts/setup.sh
```

2. **Configure environment with OpenAI API Key**:
```bash
# Copy and edit .env file
cp .env.example .env
nano .env

# Set your OpenAI API key:
OPENAI_API_KEY=sk-your-key-here

# Optional: Customize models
EMBEDDING_MODEL=text-embedding-3-small  # or text-embedding-3-large
LLM_MODEL=gpt-4o-mini  # or gpt-4o
```

3. **Start services**:
```bash
# Start Qdrant and Redis
docker-compose up -d

# Start API server
poetry run python main.py

# (Optional) Start worker for async processing
poetry run python worker.py
```

### API Usage

The API will be available at `http://localhost:8001`

**Interactive API docs**: http://localhost:8001/docs

#### Upload a document:
```bash
curl -X POST "http://localhost:8001/api/v1/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

Response:
```json
{
  "document_id": "uuid-here",
  "filename": "document.pdf",
  "file_type": "pdf",
  "size_bytes": 12345,
  "status": "completed",
  "message": "Document processed successfully"
}
```

#### Query documents:
```bash
curl -X POST "http://localhost:8001/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic of the document?",
    "top_k": 5
  }'
```

Response:
```json
{
  "query": "What is the main topic...",
  "answer": "Based on the documents, the main topic is...",
  "chunks": [
    {
      "text": "Retrieved text chunk...",
      "score": 0.95,
      "metadata": {
        "source": "document.pdf",
        "chunk_index": 0,
        "modality": "text"
      }
    }
  ],
  "processing_time": 1.23
}
```

#### Health check:
```bash
curl http://localhost:8001/api/v1/health
```

#### Delete a document:
```bash
curl -X DELETE "http://localhost:8001/api/v1/documents/{document_id}"
```

## Project Structure

```
rag-service/
├── src/
│   ├── api/              # FastAPI application
│   │   ├── app.py        # Main app setup
│   │   ├── routes.py     # API endpoints
│   │   └── dependencies.py
│   ├── core/             # Configuration
│   │   └── config.py
│   ├── ingestion/        # Document processing
│   │   ├── processors/   # File type processors
│   │   ├── router.py     # Processor routing
│   │   ├── chunker.py    # Text chunking
│   │   └── embedder.py   # Embedding generation
│   ├── retrieval/        # Retrieval & generation
│   │   ├── vector_store.py   # Qdrant integration
│   │   ├── bm25_index.py     # BM25 index
│   │   ├── hybrid_retriever.py
│   │   └── generator.py      # LLM generation
│   ├── models/           # Pydantic schemas
│   └── worker/           # Background tasks
├── data/                 # Local storage
│   ├── uploads/          # Uploaded files
│   ├── processed/        # Processed files
│   └── chunks/           # BM25 index
├── models/               # LLM models
├── scripts/              # Utility scripts
├── tests/                # Tests
├── docker-compose.yml    # Services (Qdrant, Redis)
├── pyproject.toml        # Dependencies
└── main.py               # Entry point
```

## Configuration

All configuration is managed via environment variables (`.env` file):

### Core Settings
- `APP_NAME`: Application name
- `APP_ENV`: Environment (development/production)
- `LOG_LEVEL`: Logging level (INFO/DEBUG/WARNING)

### API Settings
- `API_HOST`: API host (default: 0.0.0.0)
- `API_PORT`: API port (default: 8001)

### OpenAI API
- `OPENAI_API_KEY`: Your OpenAI API key (required)

### Storage
- `UPLOAD_DIR`: Upload directory (default: ./data/uploads)
- `PROCESSED_DIR`: Processed files directory
- `CHUNKS_DIR`: Chunks and BM25 index directory

### Services
- `QDRANT_HOST`: Qdrant host (default: localhost)
- `QDRANT_PORT`: Qdrant port (default: 6333)
- `REDIS_HOST`: Redis host (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)

### Models
- `EMBEDDING_MODEL`: OpenAI embedding model (default: text-embedding-3-small)
  - Options: `text-embedding-3-small` (1536 dims), `text-embedding-3-large` (3072 dims)
- `LLM_MODEL`: OpenAI model for generation (default: gpt-4o-mini)
  - Options: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`

### Processing
- `CHUNK_SIZE`: Tokens per chunk (default: 512)
- `CHUNK_OVERLAP`: Overlap tokens (default: 50)
- `RETRIEVAL_TOP_K`: Initial retrieval count (default: 20)
- `FINAL_TOP_K`: Final reranked results (default: 5)

## Development

### Install dev dependencies:
```bash
poetry install
```

### Run tests:
```bash
poetry run pytest
```

### Format code:
```bash
poetry run black src/
poetry run ruff check src/
```

### Type checking:
```bash
poetry run mypy src/
```

## Docker Deployment

Build and run the entire stack with Docker:

```bash
# Build image
docker build -t rag-service .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

## Performance Tuning

### Cost Optimization
- **Embeddings**: Use `text-embedding-3-small` for cost-efficiency ($0.02/1M tokens)
  - Upgrade to `text-embedding-3-large` for better accuracy ($0.13/1M tokens)
- **Generation**: Use `gpt-4o-mini` for fast, cost-effective responses
  - Upgrade to `gpt-4o` for complex queries requiring deeper reasoning
- **Reranking**: Disable LLM reranking for high-volume use cases to save costs

### Scaling
- Increase `MAX_WORKERS` for parallel processing
- Run multiple RQ workers for increased throughput
- Use larger Qdrant instances for production
- Batch embeddings (API handles up to 2048 inputs per request)

### Model Selection
- **Embeddings**:
  - `text-embedding-3-small`: 1536 dims, best cost/performance ratio
  - `text-embedding-3-large`: 3072 dims, highest accuracy
- **Generation**:
  - `gpt-4o-mini`: Fast, cost-effective, supports structured outputs
  - `gpt-4o`: More capable, better for complex reasoning
- **Reranking**: LLM-based using GPT-4o-mini with structured outputs

## Troubleshooting

### Common Issues

1. **Tesseract not found**:
   - Install: `sudo apt-get install tesseract-ocr` (Linux)
   - Or: `brew install tesseract` (macOS)

2. **Poppler not found**:
   - Install: `sudo apt-get install poppler-utils` (Linux)
   - Or: `brew install poppler` (macOS)

3. **FFmpeg not found**:
   - Install: `sudo apt-get install ffmpeg` (Linux)
   - Or: `brew install ffmpeg` (macOS)

4. **OpenAI API key error**:
   - Ensure `OPENAI_API_KEY` is set in `.env`
   - Verify key is valid at https://platform.openai.com/api-keys
   - Check API quota and billing status

5. **Qdrant connection error**:
   - Ensure Docker services are running: `docker-compose up -d`
   - Check Qdrant dashboard: http://localhost:6333/dashboard

6. **Rate limiting from OpenAI**:
   - Reduce `RETRIEVAL_TOP_K` to minimize reranking API calls
   - Disable LLM reranking by setting `use_llm_reranking=False` in retriever
   - Implement request throttling or caching

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
