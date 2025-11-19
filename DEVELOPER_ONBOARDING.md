# Pingo RAG Service - Complete Developer Onboarding Guide

Welcome to the Pingo team! This guide will help you understand our multi-tenant AI chatbot platform from the ground up.

---

## Table of Contents

1. [What is Pingo?](#1-what-is-pingo)
2. [Technology Stack](#2-technology-stack)
3. [Architecture Overview](#3-architecture-overview)
4. [Project Structure](#4-project-structure)
5. [Core Concepts](#5-core-concepts)
6. [How Data Flows](#6-how-data-flows)
7. [Key Components Deep Dive](#7-key-components-deep-dive)
8. [Development Setup](#8-development-setup)
9. [Common Tasks & Workflows](#9-common-tasks--workflows)
10. [Testing & Debugging](#10-testing--debugging)
11. [Best Practices](#11-best-practices)
12. [Implementation Status & Roadmap](#12-implementation-status--roadmap)

---

## 1. What is Pingo?

### The Big Picture

Pingo is a **multi-tenant AI chatbot platform** that helps businesses answer customer questions using their own documentation. Think of it like having a smart assistant that:

- Reads your company's documents (PDFs, docs, etc.)
- Understands customer questions
- Finds relevant information from your docs
- Provides accurate, cited answers

### Real-World Example

**Scenario:** An e-commerce company uploads their return policy PDF.

```
Customer: "How do I return a damaged item?"
Pingo: "For damaged items, you can return within 30 days.
       Contact support@company.com with your order number. [Source: Return Policy, Page 2]"
```

### Multi-Tenant Explained

**Multi-tenant** means one platform serves many customers (tenants):

```
Platform (Pingo)
├─ Tenant A (CompanyA) - Their docs, their customers
├─ Tenant B (CompanyB) - Their docs, their customers
└─ Tenant C (CompanyC) - Their docs, their customers
```

**Each tenant's data is completely isolated** - CompanyA never sees CompanyB's data.

---

## 2. Technology Stack

Here's what we use and why:

### Backend Framework
- **FastAPI** - Modern Python web framework
  - Why? Fast, automatic API docs, type hints
  - Think: Express.js but for Python

### Database & Storage
- **PostgreSQL** - Main database
  - Stores: tenants, users, sessions, jobs
  - Think: Your typical relational database

- **Qdrant** - Vector database
  - Stores: document embeddings (AI-friendly format)
  - Think: Specialized database for AI similarity search

- **Redis** - In-memory cache
  - Stores: job queue, temporary cache
  - Think: Super-fast temporary storage

### AI/ML
- **OpenAI API** - Language models
  - `text-embedding-3-small` - Converts text to numbers (embeddings)
  - `gpt-4o-mini` - Generates human-like responses

### Background Jobs
- **Redis Queue (RQ)** - Job processing
  - Why? Don't block API while processing large documents
  - Think: Celery but simpler

---

## 3. Architecture Overview

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    CLIENT (Web/Mobile)                    │
└────────────────────┬─────────────────────────────────────┘
                     │ HTTP Requests
                     ↓
┌──────────────────────────────────────────────────────────┐
│                  API LAYER (FastAPI)                      │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐     │
│  │ Rate Limit │→│ Auth (API Key)│→│ Route Handlers │     │
│  └────────────┘ └──────────────┘ └────────────────┘     │
└────────────────────┬─────────────────────────────────────┘
                     │
      ┌──────────────┼──────────────┐
      ↓              ↓              ↓
┌──────────┐  ┌─────────────┐  ┌────────────┐
│PostgreSQL│  │   Qdrant    │  │   Redis    │
│(metadata)│  │ (embeddings)│  │(jobs/cache)│
└──────────┘  └─────────────┘  └────────────┘
                     ↑
                     │
              ┌──────┴──────┐
              ↓             ↓
        ┌──────────┐  ┌──────────┐
        │ Worker 1 │  │ Worker 2 │
        │(Process  │  │(Process  │
        │ Docs)    │  │ Docs)    │
        └──────────┘  └──────────┘
```

### Request Flow Example

Let's trace what happens when a customer asks a question:

```
1. Customer sends: "What's your return policy?"
   ↓
2. API receives request → Checks API key (tenant auth)
   ↓
3. Rate limiter → Checks if tenant is within limits
   ↓
4. Chat handler → Processes the request
   ↓
5. Retriever → Searches Qdrant for relevant doc chunks
   ↓
6. Generator → Sends chunks + question to OpenAI
   ↓
7. OpenAI → Returns answer citing sources
   ↓
8. API → Streams response back to customer
```

---

## 4. Project Structure

### Directory Tree

```
rag-service/
├── alembic/                    # Database migrations
│   └── versions/              # Migration files
│       ├── 001_initial_schema.py
│       └── 002_add_jobs_table.py
│
├── scripts/                    # Utility scripts
│   └── start_worker.py        # Background worker launcher
│
├── src/                        # Main application code
│   ├── agent/                 # AI agent logic
│   │   ├── executor.py        # Orchestrates agent actions
│   │   ├── memory.py          # Conversation context management
│   │   └── planner.py         # Intent classification
│   │
│   ├── api/                   # API layer
│   │   ├── app.py            # FastAPI application setup
│   │   ├── dependencies.py    # Shared dependencies (DI)
│   │   ├── error_handlers.py  # Centralized error handling
│   │   └── routes/           # API endpoints
│   │       ├── chat.py       # Chat & query endpoints
│   │       ├── documents.py   # Document upload/delete
│   │       ├── health.py      # Health checks
│   │       ├── jobs.py        # Job status
│   │       ├── sessions.py    # Chat sessions
│   │       └── tenants.py     # Tenant management
│   │
│   ├── core/                  # Core configuration
│   │   └── config.py         # Settings (env vars)
│   │
│   ├── db/                    # Database
│   │   ├── base.py           # SQLAlchemy base
│   │   ├── models.py         # ORM models
│   │   └── session.py        # DB connection
│   │
│   ├── ingestion/             # Document processing
│   │   ├── chunker.py        # Split docs into chunks
│   │   ├── embedder.py       # Convert text to embeddings
│   │   ├── file_detector.py   # Detect file types
│   │   ├── router.py         # Route to processors
│   │   └── processors/       # File type handlers
│   │       ├── pdf_processor.py
│   │       └── text_processor.py
│   │
│   ├── middleware/            # Request processing
│   │   ├── rate_limit.py     # API rate limiting
│   │   └── tenant.py         # Tenant extraction
│   │
│   ├── models/                # Pydantic models (API schemas)
│   │   ├── job.py
│   │   ├── schemas.py
│   │   ├── session.py
│   │   └── tenant.py
│   │
│   ├── retrieval/             # RAG retrieval system
│   │   ├── bm25_index.py     # Keyword search
│   │   ├── generator.py       # LLM response generation
│   │   ├── hybrid_retriever.py # Combined search
│   │   └── vector_store.py    # Qdrant wrapper
│   │
│   ├── services/              # Business logic
│   │   ├── auth_service.py    # API key management
│   │   ├── cache_service.py   # Caching layer
│   │   ├── document_service.py # Doc processing
│   │   ├── job_service.py     # Job management
│   │   ├── quota_service.py   # Usage limits
│   │   ├── session_service.py  # Chat sessions
│   │   └── tenant_service.py  # Tenant CRUD
│   │
│   └── workers/               # Background workers
│       ├── document_worker.py # Process docs async
│       └── queue.py          # Job queue wrapper
│
├── docker-compose.yml         # Local development setup
├── Dockerfile                 # Container definition
├── pyproject.toml            # Python dependencies
└── requirements.txt          # Pinned dependencies
```

### What Goes Where?

**Quick Reference:**

- **Add new API endpoint?** → `src/api/routes/`
- **Add database table?** → `src/db/models.py` + migration
- **Add business logic?** → `src/services/`
- **Change configuration?** → `src/core/config.py` + `.env`
- **Add background job?** → `src/workers/`

---

## 5. Core Concepts

### 5.1 RAG (Retrieval-Augmented Generation)

**Simple Explanation:**

Instead of asking AI a question directly, we:
1. **Retrieve** relevant documents first
2. Give those documents to AI as context
3. AI **generates** an answer based on the context

**Why?** Prevents AI from making things up (hallucinating).

**Visual:**

```
Without RAG:
User: "What's your return policy?"
AI: *makes up answer* ❌

With RAG:
User: "What's your return policy?"
  ↓
System finds: [Return Policy PDF, Page 2]
  ↓
AI reads and says: "Our return policy allows 30 days..." ✅
```

### 5.2 Embeddings

**Simple Explanation:**

Converting text into numbers that AI can understand and compare.

**Example:**

```python
Text: "How do I return an item?"
Embedding: [0.23, -0.45, 0.67, ...] (1536 numbers)

Text: "What's your refund policy?"
Embedding: [0.25, -0.42, 0.69, ...] (similar numbers!)
```

**Why?** Similar meanings → Similar numbers → Easy to find related docs

### 5.3 Vector Search

**Simple Explanation:**

Finding documents with similar meanings (not just matching keywords).

**Example:**

```
Query: "laptop computer"

Keyword search finds:
- "This laptop has..." ✅
- "Computer specs..." ✅

Vector search ALSO finds:
- "This notebook has..." ✅ (knows laptop ≈ notebook)
- "MacBook features..." ✅ (knows MacBook ≈ laptop)
```

### 5.4 Hybrid Search

**Simple Explanation:**

Combine keyword search (BM25) + vector search for best results.

```python
# Vector search (semantic)
results_vector = ["laptop specs", "MacBook review", "notebook guide"]

# Keyword search (exact matches)
results_keyword = ["laptop computer sale", "laptop discount"]

# Hybrid = Best of both
results_hybrid = merge_and_rank(results_vector, results_keyword)
```

### 5.5 Multi-Tenancy

**Key Principle:** One platform, many customers, zero data leakage.

**Implementation:**

Every query has a `tenant_id`:

```python
# Good ✅
chunks = vector_store.search(query, tenant_id=tenant_a)
# Returns only Tenant A's documents

# Bad ❌
chunks = vector_store.search(query)
# Returns ALL tenants' documents (security breach!)
```

---

## 6. How Data Flows

### Flow 1: Document Upload

```
┌─────────────┐
│ 1. Customer │ Uploads PDF "returns.pdf"
│   uploads   │
└──────┬──────┘
       │ POST /api/v1/documents/upload
       ↓
┌──────────────────────────────────────────┐
│ 2. API Handler (documents.py)            │
│  - Check API key → Get tenant_id         │
│  - Check quota (10 docs for FREE tier)   │
│  - Save file to disk                     │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 3. Create Job (job_service.py)          │
│  - Job ID: abc-123                       │
│  - Status: PENDING                       │
│  - Save to PostgreSQL                    │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 4. Enqueue to Redis                      │
│  - Add job to queue                      │
│  - Return immediately to user            │
└──────────────────────────────────────────┘
       │
       ↓ (async, background)
┌──────────────────────────────────────────┐
│ 5. Worker picks up job                   │
│  - Update status: PROCESSING             │
│  - Read PDF file                         │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 6. Process Document                      │
│  - Extract text from PDF                 │
│  - Split into chunks (512 tokens each)   │
│  - Generate embeddings (OpenAI API)      │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 7. Store in Databases                    │
│  - Qdrant: Store embeddings with tenant_id│
│  - BM25 Index: Store for keyword search  │
│  - Update job: Status = COMPLETED        │
└──────────────────────────────────────────┘
```

### Flow 2: Chat Query

```
┌─────────────┐
│ Customer    │ Asks: "What's your return policy?"
└──────┬──────┘
       │ POST /api/v1/chat
       ↓
┌──────────────────────────────────────────┐
│ 1. API Handler (chat.py)                 │
│  - Extract tenant_id from API key        │
│  - Check rate limit                      │
│  - Create/load session                   │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 2. Conversation Memory                   │
│  - Load chat history                     │
│  - Compress old messages                 │
│  - Extract context                       │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 3. Agent Planner                         │
│  - Classify intent: "knowledge question" │
│  - Decide: needs_retrieval = True        │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 4. Hybrid Retriever                      │
│  - Convert query to embedding            │
│  - Search Qdrant (vector search)         │
│  - Search BM25 (keyword search)          │
│  - Merge results (RRF fusion)            │
│  - LLM reranking (batched)               │
│  - Return top 5 chunks                   │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 5. Generator (OpenAI)                    │
│  - Build prompt with chunks              │
│  - Call GPT-4o-mini                      │
│  - Stream response                       │
└──────┬───────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────┐
│ 6. Return to Customer                    │
│  - Stream answer with citations          │
│  - Save message to session               │
│  - Return source metadata                │
└──────────────────────────────────────────┘
```

---

## 7. Key Components Deep Dive

### 7.1 Database Models (`src/db/models.py`)

**What:** SQLAlchemy ORM models for PostgreSQL tables.

**Key Tables:**

```python
# Tenant - Each customer account
class Tenant(Base):
    tenant_id = UUID (PK)
    name = String
    tier = ENUM (FREE, PRO)  # Pricing tier
    settings = JSON  # Flexible config

# TenantAPIKey - Authentication
class TenantAPIKey(Base):
    key_id = UUID (PK)
    tenant_id = UUID (FK → Tenant)
    key_hash = String  # bcrypt hashed
    prefix = String  # First 12 chars for display

# ChatSession - Conversation tracking
class ChatSession(Base):
    session_id = UUID (PK)
    tenant_id = UUID (FK → Tenant)
    message_count = Integer

# Message - Individual chat messages
class Message(Base):
    message_id = UUID (PK)
    session_id = UUID (FK → ChatSession)
    role = ENUM (USER, ASSISTANT)
    content = Text
    chunks_retrieved = Integer
    sources_used = JSON

# Job - Background tasks
class Job(Base):
    job_id = UUID (PK)
    tenant_id = UUID (FK → Tenant)
    job_type = ENUM (DOCUMENT_UPLOAD, WEB_SCRAPING)
    status = ENUM (PENDING, PROCESSING, COMPLETED, FAILED)
    result = JSON
```

**Example Usage:**

```python
# Create a tenant
tenant = Tenant(
    name="Acme Corp",
    tier=TenantTier.PRO,
    settings={"max_documents": 1000}
)
db.add(tenant)
db.commit()

# Query tenant
tenant = db.query(Tenant).filter(
    Tenant.tenant_id == tenant_id
).first()
```

### 7.2 Services Layer

**What:** Business logic separated from API routes.

**Example: `tenant_service.py`**

```python
class TenantService:
    @staticmethod
    def create_tenant(db: Session, request: CreateTenantRequest) -> Tenant:
        """Create a new tenant with validation."""
        # Business logic:
        # 1. Validate name is unique
        # 2. Set default tier
        # 3. Initialize settings
        # 4. Create in database

        tenant = Tenant(
            name=request.name,
            tier=request.tier or TenantTier.FREE,
            settings=DEFAULT_SETTINGS[request.tier]
        )
        db.add(tenant)
        db.commit()
        return tenant
```

**Why services?**
- ✅ Reusable across different endpoints
- ✅ Easier to test
- ✅ Keeps routes clean

### 7.3 Hybrid Retriever (`src/retrieval/hybrid_retriever.py`)

**What:** Combines vector + keyword search for best results.

**Flow:**

```python
class HybridRetriever:
    def retrieve(self, query: str, tenant_id: UUID) -> List[Chunk]:
        # 1. Vector search (semantic)
        query_embedding = embedder.embed(query)
        vector_results = qdrant.search(
            embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=20
        )

        # 2. Keyword search (BM25)
        keyword_results = bm25.search(
            query=query,
            tenant_id=tenant_id,
            top_k=20
        )

        # 3. Merge using Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(
            vector_results,
            keyword_results
        )

        # 4. LLM reranking (batched for speed)
        top_candidates = fused[:10]
        reranked = self._rerank_with_llm(query, top_candidates)

        return reranked[:5]  # Top 5 final results
```

### 7.4 Job Queue (`src/workers/queue.py`)

**What:** Redis Queue wrapper for background processing.

**Why?** Document processing takes time (30s - 5min). Don't block API.

```python
# Upload endpoint (fast response)
@router.post("/documents/upload")
async def upload(file: UploadFile):
    # Save file
    file_path.write_bytes(await file.read())

    # Create job
    job = JobService.create_job(
        tenant_id=tenant_id,
        job_type=JobType.DOCUMENT_UPLOAD,
        file_path=str(file_path)
    )

    # Enqueue (non-blocking)
    queue.enqueue_document_processing(
        job_id=job.job_id,
        file_path=str(file_path)
    )

    # Return immediately!
    return {"job_id": job.job_id, "status": "PENDING"}
```

**Worker (background):**

```python
# scripts/start_worker.py
def process_document_job(job_id, document_id, file_path, tenant_id):
    try:
        # Update status
        JobService.update_status(job_id, JobStatus.PROCESSING)

        # Do the work (slow)
        process_document(document_id, file_path, tenant_id)

        # Mark complete
        JobService.update_status(job_id, JobStatus.COMPLETED)
    except Exception as e:
        JobService.update_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e)
        )
```

### 7.5 Quota Management (`src/services/quota_service.py`)

**What:** Enforce usage limits per tier.

**Tiers:**

```python
FREE tier:
  max_documents: 10
  max_file_size_mb: 10
  max_queries_per_day: 100

PRO tier:
  max_documents: 1,000
  max_file_size_mb: 50
  max_queries_per_day: 10,000
```

**Usage:**

```python
# Before upload
QuotaService.check_document_quota(
    db,
    tenant,
    file_size_mb=5.2
)
# Raises QuotaExceededError if limit hit
```

---

## 8. Development Setup

### Prerequisites

```bash
# Required
Python 3.11+
Docker & Docker Compose
PostgreSQL 14+
Redis 7+

# Optional (for production)
Qdrant (or use Docker)
```

### Step-by-Step Setup

#### 1. Clone & Environment

```bash
# Clone repo
git clone <repo-url>
cd rag-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Environment Variables

Create `.env` file:

```bash
# Copy example
cp .env.example .env

# Edit .env
nano .env
```

Required variables:

```bash
# OpenAI (REQUIRED)
OPENAI_API_KEY=sk-proj-...

# Database
DATABASE_URL=postgresql://pingo:pingo@localhost:5432/pingo

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Security
SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
```

#### 3. Start Infrastructure

```bash
# Start PostgreSQL + Redis + Qdrant
docker-compose up -d

# Check they're running
docker-compose ps
```

#### 4. Database Setup

```bash
# Run migrations
alembic upgrade head

# Verify tables created
psql postgresql://pingo:pingo@localhost:5432/pingo
\dt  # List tables
```

#### 5. Start Application

**Terminal 1: API Server**
```bash
uvicorn src.api.app:app --reload --port 8001
```

**Terminal 2: Background Worker**
```bash
python scripts/start_worker.py
```

**Terminal 3: Monitor Jobs**
```bash
# Watch Redis queue
redis-cli
> LLEN rq:queue:default  # Check queue length
```

#### 6. Verify Setup

```bash
# Health check
curl http://localhost:8001/api/v1/health

# API docs
open http://localhost:8001/docs
```

---

## 9. Common Tasks & Workflows

### Task 1: Create a New Tenant

```bash
# Using API
curl -X POST http://localhost:8001/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Corp",
    "tier": "PRO",
    "contact_email": "admin@testcorp.com"
  }'

# Response
{
  "tenant_id": "abc-123",
  "api_key": "pk_live_xyz789...",  # Save this!
  "tier": "PRO"
}
```

### Task 2: Upload a Document

```bash
# Upload PDF
curl -X POST http://localhost:8001/api/v1/documents/upload \
  -H "X-API-Key: pk_live_xyz789..." \
  -F "file=@path/to/document.pdf"

# Response
{
  "document_id": "doc-456",
  "job_id": "job-789",
  "status": "PENDING",
  "message": "Processing in background"
}
```

### Task 3: Check Job Status

```bash
# Poll job status
curl http://localhost:8001/api/v1/jobs/job-789 \
  -H "X-API-Key: pk_live_xyz789..."

# Response (processing)
{
  "job_id": "job-789",
  "status": "PROCESSING",
  "progress": 0.65,
  "started_at": "2025-11-19T10:30:00Z"
}

# Response (completed)
{
  "job_id": "job-789",
  "status": "COMPLETED",
  "progress": 1.0,
  "result": {
    "chunks_created": 47,
    "embeddings_generated": 47
  }
}
```

### Task 4: Query Documents

```bash
# Ask a question
curl -X POST http://localhost:8001/api/v1/query \
  -H "X-API-Key: pk_live_xyz789..." \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is your return policy?",
    "top_k": 5
  }'

# Response
{
  "query": "What is your return policy?",
  "answer": "Our return policy allows returns within 30 days... [1][2]",
  "chunks": [
    {
      "text": "Returns are accepted within 30 days...",
      "score": 0.87,
      "metadata": {
        "source": "returns.pdf",
        "page_number": 2
      }
    }
  ]
}
```

### Task 5: Chat with Streaming

```python
# Python example
import requests

url = "http://localhost:8001/api/v1/chat"
headers = {"X-API-Key": "pk_live_xyz789..."}
data = {
    "messages": [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi! How can I help?"},
        {"role": "user", "content": "What's your return policy?"}
    ]
}

# Stream response
response = requests.post(url, json=data, headers=headers, stream=True)
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

---

## 10. Testing & Debugging

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_retrieval.py

# With coverage
pytest --cov=src tests/
```

### Common Debugging Scenarios

#### Debug 1: Document Not Found After Upload

**Problem:** Upload succeeds but can't find document in search.

**Check:**
```python
# 1. Verify job completed
job = JobService.get_job(db, job_id, tenant_id)
print(f"Status: {job.status}")
print(f"Error: {job.error_message}")

# 2. Check Qdrant
from src.api.dependencies import get_vector_store
vector_store = get_vector_store()
count = vector_store.count(tenant_id)
print(f"Chunks in Qdrant: {count}")

# 3. Check BM25 index
from src.retrieval.bm25_index import BM25Index
bm25 = BM25Index(tenant_id=tenant_id)
count = bm25.count()
print(f"Chunks in BM25: {count}")
```

#### Debug 2: Rate Limit Errors

**Problem:** `429 Too Many Requests`

**Check:**
```python
# Check tenant tier
tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
print(f"Tier: {tenant.tier}")

# Check quota usage
from src.services.quota_service import QuotaService
usage = QuotaService.get_quota_usage(db, tenant)
print(usage)
```

#### Debug 3: Poor Search Results

**Problem:** Returns irrelevant documents.

**Debug:**
```python
# Check retrieval step-by-step
retriever = get_tenant_retriever(tenant_id)

# 1. Vector search only
query_embedding = embedder.embed("your query")
vector_results = vector_store.search(query_embedding, top_k=10)
print("Vector results:", [r['text'][:100] for r in vector_results])

# 2. BM25 search only
keyword_results = bm25.search("your query", top_k=10)
print("Keyword results:", [r['text'][:100] for r in keyword_results])

# 3. Full hybrid
final_results = retriever.retrieve("your query", top_k=5)
for chunk in final_results:
    print(f"Score: {chunk.score:.2f} - {chunk.text[:100]}")
```

### Logging

**View logs:**

```bash
# API server logs
tail -f logs/api.log

# Worker logs
tail -f logs/worker.log

# Filter by tenant
grep "tenant_id=abc-123" logs/api.log
```

**Enable debug logging:**

```python
# .env
LOG_LEVEL=DEBUG

# Or in code
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 11. Best Practices

### Code Style

```python
# ✅ Good: Type hints everywhere
def create_tenant(db: Session, name: str) -> Tenant:
    ...

# ❌ Bad: No type hints
def create_tenant(db, name):
    ...

# ✅ Good: Docstrings
def retrieve(self, query: str, top_k: int = 5) -> List[Chunk]:
    """
    Retrieve relevant chunks for a query.

    Args:
        query: User's question
        top_k: Number of chunks to return

    Returns:
        List of chunks sorted by relevance
    """
    ...

# ❌ Bad: No documentation
def retrieve(self, query, top_k=5):
    ...
```

### Error Handling

```python
# ✅ Good: Specific exceptions
from src.services.quota_service import QuotaExceededError

try:
    QuotaService.check_document_quota(db, tenant)
except QuotaExceededError as e:
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "error": "QuotaExceeded",
            "tier": e.tier,
            "limit": e.limit,
            "current": e.current
        }
    )

# ❌ Bad: Generic exceptions
try:
    QuotaService.check_document_quota(db, tenant)
except Exception as e:
    raise HTTPException(500, str(e))
```

### Multi-Tenancy

```python
# ✅ ALWAYS pass tenant_id
def get_documents(tenant_id: UUID) -> List[Document]:
    return vector_store.search(tenant_id=tenant_id)

# ❌ NEVER query without tenant_id (security breach!)
def get_documents():
    return vector_store.search()  # Returns ALL tenants' data!
```

### Database Queries

```python
# ✅ Good: Use ORM, prevent SQL injection
tenant = db.query(Tenant).filter(
    Tenant.tenant_id == tenant_id
).first()

# ❌ Bad: Raw SQL with string formatting
tenant = db.execute(
    f"SELECT * FROM tenants WHERE tenant_id = '{tenant_id}'"
).first()
```

### API Keys

```python
# ✅ Good: Hash API keys, never store plaintext
key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt())
db_record.key_hash = key_hash.decode()

# ✅ Good: Show API key only once on creation
return {"api_key": api_key}  # User must save it

# ❌ Bad: Store plaintext
db_record.key = api_key
```

---

## 12. Implementation Status & Roadmap

This section tracks our progress against the [Pingo Architecture Document](./docs/architecture.md) requirements.

### Legend

- ✅ **Complete** - Fully implemented and tested
- 🟡 **Partial** - Implemented but incomplete or needs enhancement
- ❌ **Not Started** - Not yet implemented
- 🔄 **In Progress** - Currently being worked on

---

## Phase 1: Agentic RAG (Knowledge-Only)

### 1.1 Multi-Tenant Foundation ✅

| Component | Status | Details |
|-----------|--------|---------|
| Tenant management | ✅ | CRUD operations, database models |
| API key authentication | ✅ | Bcrypt hashing, secure generation |
| Tenant isolation | ✅ | tenant_id filtering in all queries |
| Quota management | ✅ | Tier-based limits (FREE/PRO) |
| Rate limiting | ✅ | Per-tenant, per-endpoint limits |
| Background jobs | ✅ | Redis Queue for async processing |

**Files:** `src/db/models.py`, `src/services/tenant_service.py`, `src/middleware/tenant.py`

---

### 1.2 Tenant Onboarding 🟡

| Component | Status | Details | Priority |
|-----------|--------|---------|----------|
| Basic info (name, contact) | ✅ | Fully implemented | - |
| Tier selection (FREE/PRO) | ✅ | With default quotas | - |
| **Industry vertical** | ❌ | Not captured | **HIGH** |
| **Brand tone** | ❌ | Not captured | **HIGH** |
| **Languages** | ❌ | Not captured | **MEDIUM** |
| **Base URLs for scraping** | ❌ | Not captured | **HIGH** |
| **Constraints/Policies** | ❌ | Not captured | **HIGH** |
| Document upload | ✅ | PDF, DOCX, TXT support | - |

**What's Missing:**

```python
# Current Tenant model (src/models/tenant.py)
class Tenant(Base):
    name: str
    tier: TenantTier  # FREE or PRO
    settings: JSON

# ❌ MISSING FIELDS:
# - industry: Industry  # e-commerce, finance, real estate, etc.
# - brand_tone: BrandTone  # professional, friendly, casual
# - languages: List[str]  # ["en", "fr", "es"]
# - base_urls: List[str]  # ["https://company.com"]
# - constraints: List[str]  # What chatbot cannot say/do
# - capabilities: List[str]  # What chatbot can help with
```

**TODO Tasks:**

- [ ] Add `industry`, `brand_tone`, `languages` fields to Tenant model
- [ ] Add `base_urls` (list) for web scraping configuration
- [ ] Add `constraints` (list) for policy enforcement
- [ ] Add `capabilities` (list) for agent guidance
- [ ] Create database migration for new fields
- [ ] Update `TenantService.create_tenant()` to accept new fields
- [ ] Add validation for new fields in API

**Files to modify:**
- `src/models/tenant.py` - Add Pydantic models
- `src/db/models.py` - Add database fields
- `alembic/versions/` - New migration
- `src/services/tenant_service.py` - Update logic

---

### 1.3 Ingestion & Knowledge Base 🟡

| Component | Status | Details | Priority |
|-----------|--------|---------|----------|
| Document parsing (PDF, DOCX) | ✅ | Multiple processors | - |
| Text chunking | ✅ | Configurable size/overlap | - |
| Embeddings generation | ✅ | OpenAI text-embedding-3-small | - |
| Vector indexing (Qdrant) | ✅ | Tenant-isolated | - |
| Keyword indexing (BM25) | ✅ | Tenant-specific files | - |
| Caching layer | ✅ | Redis-based caching | - |
| **Web scraping** | ❌ | Playwright removed in cleanup | **CRITICAL** |

**What's Missing:**

The architecture explicitly requires web scraping in Phase 1:

> "Scraping of public pages via Playwright (with depth and domain limits)"

**TODO Tasks:**

- [ ] Re-add Playwright to dependencies
- [ ] Create `src/ingestion/web_scraper.py`
  - Sitemap parser
  - Depth/domain limits
  - Respect robots.txt
  - Rate limiting per domain
- [ ] Create `WebScrapingJob` type
- [ ] Create `src/workers/scraping_worker.py`
- [ ] Add API endpoint: `POST /api/v1/tenants/{id}/scrape`
- [ ] Add scraping configuration to Tenant model
- [ ] Add job progress tracking for long scrapes

**Implementation Example:**

```python
# src/api/routes/tenants.py
@router.post("/{tenant_id}/scrape")
async def start_web_scraping(
    tenant_id: UUID,
    request: WebScrapingRequest,  # urls, max_depth, max_pages
    db: Session = Depends(get_db)
):
    """Start web scraping job for tenant."""
    job = JobService.create_job(
        tenant_id=tenant_id,
        job_type=JobType.WEB_SCRAPING,
        metadata={"urls": request.urls, "max_depth": request.max_depth}
    )

    queue.enqueue_web_scraping(job.job_id, tenant_id, request.urls)

    return {"job_id": job.job_id, "status": "PENDING"}
```

**Files to create:**
- `src/ingestion/web_scraper.py`
- `src/workers/scraping_worker.py`
- `src/models/scraping.py` (request/response models)

**Files to modify:**
- `pyproject.toml` - Add `playwright`
- `src/models/job.py` - Add `WEB_SCRAPING` job type
- `src/api/routes/tenants.py` - Add scraping endpoint

---

### 1.4 Context Builder 🟡

| Component | Status | Details | Priority |
|-----------|--------|---------|----------|
| Conversation history | ✅ | Memory with compression | - |
| Retrieved knowledge snippets | ✅ | Hybrid search results | - |
| Date-aware prompts | ✅ | Current date injection | - |
| **Tenant persona injection** | ❌ | Industry/brand tone missing | **HIGH** |
| **Policy enforcement** | ❌ | Constraints not checked | **HIGH** |
| **User profile context** | ❌ | Not implemented | **LOW** |

**What's Missing:**

The architecture describes:

> "Context Builder assembles all relevant context:
> - Tenant context (industry, brand tone, capabilities)
> - Conversation history ✅
> - Retrieved knowledge snippets ✅
> - Policy snippets ❌"

**Current Generator System Prompt:**

```python
# src/retrieval/generator.py
system_message = f"""You are a helpful AI assistant that answers questions based on provided context.
Today's date is {current_date}. Use this for any date-related calculations.
Always cite your sources using the source numbers [1], [2], etc."""
```

**Should Be:**

```python
system_message = f"""You are a {tenant.brand_tone} AI assistant for {tenant.name}, a {tenant.industry} company.

Today's date is {current_date}.

Brand & Communication:
- Industry: {tenant.industry}
- Tone: {tenant.brand_tone}
- Languages: {", ".join(tenant.languages)}

Capabilities:
{format_capabilities(tenant.capabilities)}

Constraints - You MUST NOT:
{format_constraints(tenant.constraints)}

Answer questions based on the provided context and cite sources [1], [2], etc."""
```

**TODO Tasks:**

- [ ] Update `Generator.__init__()` to accept `tenant_config`
- [ ] Modify `_build_prompt()` to inject tenant persona
- [ ] Create prompt template system for different industries
- [ ] Add constraint checking before response generation
- [ ] Add policy violation detection
- [ ] Create brand tone guidelines per industry

**Files to modify:**
- `src/retrieval/generator.py` - Add tenant context
- `src/api/routes/chat.py` - Pass tenant to generator
- `src/models/tenant.py` - Add helper methods

---

### 1.5 Agent Orchestrator ✅

| Component | Status | Details |
|-----------|--------|---------|
| Intent classification | ✅ | greeting/knowledge/action/fallback |
| ReAct pattern execution | ✅ | Planning + execution + reflection |
| Retrieval orchestration | ✅ | Hybrid search coordination |
| Conversation memory | ✅ | Context compression |
| Query enhancement | ✅ | Context-aware query rewriting |
| Retry logic | ✅ | Single retry with expansion |

**Files:** `src/agent/executor.py`, `src/agent/planner.py`, `src/agent/memory.py`

---

### 1.6 Widget & API Gateway 🟡

| Component | Status | Details | Priority |
|-----------|--------|---------|----------|
| REST API endpoints | ✅ | Complete CRUD + chat | - |
| API authentication | ✅ | API key based | - |
| Rate limiting | ✅ | Per-tenant limits | - |
| Streaming responses | ✅ | AI SDK protocol | - |
| Error handling | ✅ | Centralized handlers | - |
| **Embeddable widget** | ❌ | Not started | **PHASE 3** |
| **CORS configuration** | 🟡 | Basic setup | **MEDIUM** |
| **Webhook support** | ❌ | Not started | **LOW** |

**Widget Implementation (Phase 3):**

The architecture requires:

> "Embeddable chatbot widget that client teams can embed with a script tag"

**Planned Implementation:**

```html
<!-- Client website -->
<script src="https://cdn.pingo.ai/widget.js"
        data-api-key="pk_live_xyz..."
        data-position="bottom-right"></script>
```

**TODO Tasks (Phase 3):**

- [ ] Create React widget component
- [ ] Widget configuration options (position, colors, logo)
- [ ] Build system for widget.js bundle
- [ ] CDN setup for widget distribution
- [ ] Widget API for programmatic control
- [ ] Mobile-responsive design
- [ ] Accessibility (WCAG 2.1)

**Files to create (Phase 3):**
- `widget/src/` - React components
- `widget/public/` - Static assets
- `widget/build.js` - Build pipeline

---

### 1.7 Analytics & Observability 🟡

| Component | Status | Details | Priority |
|-----------|--------|---------|----------|
| Message logging | ✅ | All messages saved | - |
| Session tracking | ✅ | Complete history | - |
| Processing time metrics | ✅ | Per-query timing | - |
| Source attribution | ✅ | Which docs used | - |
| **Deflection rate** | ❌ | Not calculated | **HIGH** |
| **Feedback collection** | 🟡 | Model exists, no UI | **MEDIUM** |
| **Usage dashboards** | ❌ | No visualization | **MEDIUM** |
| **Token usage tracking** | ❌ | Not tracked | **MEDIUM** |

**What's Missing:**

Deflection rate calculation:

```python
# ❌ NOT IMPLEMENTED
deflection_rate = (
    queries_answered_without_human / total_queries
) * 100
```

**TODO Tasks:**

- [ ] Add `resolved_without_human` flag to Message model
- [ ] Create analytics service for metric calculations
- [ ] Add endpoint: `GET /api/v1/tenants/{id}/analytics`
- [ ] Track token usage per query (OpenAI API)
- [ ] Create admin dashboard (Phase 3)
- [ ] Export metrics to external tools (Prometheus, DataDog)

**Files to create:**
- `src/services/analytics_service.py`
- `src/api/routes/analytics.py`

**Files to modify:**
- `src/db/models.py` - Add analytics fields

---

## Phase 2: Agentic RAG + MCP Tools (Actions) ❌

**Status:** Not started (Future work)

### Components

| Component | Status | Priority |
|-----------|--------|----------|
| MCP server setup | ❌ | Phase 2 |
| Tool schema generation | ❌ | Phase 2 |
| Action agent implementation | ❌ | Phase 2 |
| Confirmation prompts | ❌ | Phase 2 |
| Audit logging | ❌ | Phase 2 |
| Human-in-the-loop | ❌ | Phase 2 |
| Tool allowlist management | ❌ | Phase 2 |

**Note:** Phase 2 should only begin after Phase 1 is complete.

---

## Critical Path for Phase 1 Completion

Based on the architecture requirements, here's the priority order:

### Priority 1: CRITICAL (Block customer onboarding)

1. **Web Scraping**
   - Estimated: 8-12 hours
   - Blocker: Can't ingest customer websites
   - Files: 5 new, 3 modified

2. **Tenant Persona Configuration**
   - Estimated: 4-6 hours
   - Blocker: Responses not brand-aligned
   - Files: 4 modified, 1 migration

3. **Context Builder Enhancement**
   - Estimated: 3-4 hours
   - Blocker: Generic responses, no policy enforcement
   - Files: 2 modified

**Total Critical Path: ~20 hours work**

### Priority 2: HIGH (Quality & Safety)

4. **Policy Enforcement**
   - Estimated: 4-5 hours
   - Files: 2 new, 1 modified

5. **Deflection Rate Analytics**
   - Estimated: 2-3 hours
   - Files: 1 new, 1 modified

### Priority 3: MEDIUM (Nice to have)

6. **Enhanced CORS & Security**
   - Estimated: 2 hours

7. **Token Usage Tracking**
   - Estimated: 2 hours

8. **Analytics Dashboard** (Phase 3)
   - Estimated: 16+ hours

---

## Quick Start Checklist for New Developer

**Day 1:**
- [ ] Read sections 1-5 (concepts)
- [ ] Set up development environment (section 8)
- [ ] Run the application successfully
- [ ] Create a test tenant and upload a document
- [ ] Query the document via API

**Week 1:**
- [ ] Read sections 6-7 (flows & components)
- [ ] Fix a small bug or add logging
- [ ] Review one of the priority tasks above
- [ ] Ask questions in team chat

**Month 1:**
- [ ] Complete one priority task from the roadmap
- [ ] Write tests for your changes
- [ ] Review another developer's PR
- [ ] Understand the full request flow

---

## Quick Reference

### Important URLs (Local Dev)

```
API Docs:     http://localhost:8001/docs
Health:       http://localhost:8001/api/v1/health
Qdrant UI:    http://localhost:6333/dashboard
PostgreSQL:   localhost:5432 (user: pingo, pass: pingo)
Redis:        localhost:6379
```

### Key Commands

```bash
# Start everything
docker-compose up -d
uvicorn src.api.app:app --reload --port 8001
python scripts/start_worker.py

# Database
alembic upgrade head                    # Run migrations
alembic revision --autogenerate -m "..." # Create migration

# Testing
pytest                                  # Run tests
pytest --cov=src                       # With coverage

# Code quality
black src/                             # Format code
ruff check src/                        # Lint code
mypy src/                              # Type check
```

### Architecture at a Glance

```
Request → Rate Limit → Auth → Route → Service → Database
                                  ↓
                              Retriever → Qdrant/BM25
                                  ↓
                              Generator → OpenAI
```

---

## Getting Help

**Questions?** Ask in:
- Team Slack: #pingo-dev
- Daily standup
- Code reviews

**Resources:**
- Architecture doc: `./docs/architecture.md`
- API docs: http://localhost:8001/docs (when running)
- This guide: `./DEVELOPER_ONBOARDING.md`

**Welcome to the team! 🎉**
