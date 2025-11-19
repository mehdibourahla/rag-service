"""Job models for background task processing."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class JobType(str, Enum):
    """Types of background jobs."""

    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_REINDEX = "document_reindex"
    BULK_DELETE = "bulk_delete"


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobResponse(BaseModel):
    """Response containing job information."""

    job_id: UUID
    tenant_id: UUID
    job_type: JobType
    status: JobStatus

    document_id: Optional[UUID] = None
    file_path: Optional[str] = None

    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Progress from 0.0 to 1.0")
    metadata: Dict[str, Any] = {}
