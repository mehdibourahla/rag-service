"""Core data models and schemas for the RAG system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================================
# Enumerations
# ============================================================================


class FileType(str, Enum):
    """Supported file types for ingestion."""

    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    TXT = "txt"
    HTML = "html"
    MD = "md"

    # Images
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    TIFF = "tiff"

    # Unknown
    UNKNOWN = "unknown"


class Modality(str, Enum):
    """Content modality types."""

    TEXT = "text"
    SCANNED_TEXT = "scanned_text"
    IMAGE_CAPTION = "image_caption"
    IMAGE_WITH_TEXT = "image_with_text"
    HTML = "html"


class ProcessingStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentStatus(str, Enum):
    """Overall document status."""

    ACTIVE = "active"
    DELETED = "deleted"
    ARCHIVED = "archived"


# ============================================================================
# Core Data Models
# ============================================================================


class ChunkMetadata(BaseModel):
    """Metadata for a single chunk of text."""

    chunk_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    source: str
    modality: Modality
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Additional metadata
    char_count: int = 0
    token_count: int = 0


class TextChunk(BaseModel):
    """A chunk of text with metadata and optional embedding."""

    text: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None

    def __repr__(self) -> str:
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"TextChunk(id={self.metadata.chunk_id}, text='{preview}')"


class RetrievedChunk(BaseModel):
    """A retrieved chunk with relevance score."""

    text: str
    metadata: ChunkMetadata
    score: float = 0.0

    def __repr__(self) -> str:
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"RetrievedChunk(score={self.score:.3f}, text='{preview}')"


class DocumentMetadata(BaseModel):
    """Metadata for an uploaded document."""

    document_id: UUID = Field(default_factory=uuid4)
    filename: str
    file_type: FileType
    source_path: str
    size_bytes: int
    status: DocumentStatus = DocumentStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Optional fields
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = None
    num_pages: Optional[int] = None
    num_chunks: Optional[int] = None


# ============================================================================
# API Request Models
# ============================================================================


class QueryRequest(BaseModel):
    """Request model for querying documents."""

    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    filters: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    """A single chat message."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    messages: List[ChatMessage]
    stream: bool = True


# ============================================================================
# API Response Models
# ============================================================================


class UploadResponse(BaseModel):
    """Response model for document upload."""

    document_id: UUID
    filename: str
    file_type: FileType
    size_bytes: int
    status: ProcessingStatus
    message: str


class QueryResponse(BaseModel):
    """Response model for document query."""

    query: str
    answer: str
    chunks: List[RetrievedChunk]
    processing_time: float
    metadata: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    vector_store_count: int
    bm25_index_count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DeleteResponse(BaseModel):
    """Response model for document deletion."""

    document_id: UUID
    message: str
    deleted_at: datetime = Field(default_factory=datetime.utcnow)
