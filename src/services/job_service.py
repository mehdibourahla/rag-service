"""Job management service for background processing."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import Job
from src.models.job import JobResponse, JobStatus, JobType

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing background jobs."""

    @staticmethod
    def create_job(
        db: Session,
        tenant_id: UUID,
        job_type: JobType,
        document_id: Optional[UUID] = None,
        file_path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Job:
        """Create a new job."""
        job = Job(
            tenant_id=tenant_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            document_id=document_id,
            file_path=file_path,
            job_metadata=metadata or {},
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(
            f"Created job {job.job_id} for tenant {tenant_id} "
            f"(type={job_type}, document={document_id})"
        )

        return job

    @staticmethod
    def get_job(db: Session, job_id: UUID, tenant_id: UUID) -> Optional[Job]:
        """Get job by ID (tenant-scoped)."""
        return db.query(Job).filter(
            Job.job_id == job_id,
            Job.tenant_id == tenant_id
        ).first()

    @staticmethod
    def update_job_status(
        db: Session,
        job_id: UUID,
        status: JobStatus,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
        progress: Optional[float] = None,
    ) -> Optional[Job]:
        """Update job status and optionally result/error."""
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return None

        job.status = status

        if status == JobStatus.PROCESSING and not job.started_at:
            job.started_at = datetime.utcnow()

        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.completed_at = datetime.utcnow()

        if result is not None:
            job.result = result

        if error_message is not None:
            job.error_message = error_message

        if progress is not None:
            job.progress = progress

        db.commit()
        db.refresh(job)

        logger.info(f"Updated job {job_id} status to {status}")

        return job

    @staticmethod
    def to_response(job: Job) -> JobResponse:
        """Convert Job ORM model to response Pydantic model."""
        return JobResponse(
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            job_type=job.job_type,
            status=job.status,
            document_id=job.document_id,
            file_path=job.file_path,
            result=job.result,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            progress=job.progress,
            metadata=job.job_metadata,
        )
