"""Document processing background worker."""

import logging
from pathlib import Path
from uuid import UUID

from rq import get_current_job
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.session import SessionLocal
from src.models.job import JobStatus
from src.services.document_service import process_document
from src.services.job_service import JobService

logger = logging.getLogger(__name__)


def process_document_job(
    job_id: str,
    document_id: str,
    file_path: str,
    tenant_id: str,
) -> dict:
    """
    Background job to process a document.

    This function runs in a separate RQ worker process.

    Args:
        job_id: Job ID (UUID as string)
        document_id: Document ID (UUID as string)
        file_path: Path to uploaded file
        tenant_id: Tenant ID (UUID as string)

    Returns:
        dict with processing results
    """
    db: Session = SessionLocal()
    rq_job = get_current_job()

    try:
        # Convert string UUIDs back to UUID objects
        job_uuid = UUID(job_id)
        document_uuid = UUID(document_id)
        tenant_uuid = UUID(tenant_id)

        logger.info(
            f"[RQ Worker] Starting document processing: "
            f"job={job_id}, document={document_id}, tenant={tenant_id}"
        )

        # Update job status to processing
        JobService.update_job_status(
            db, job_uuid, JobStatus.PROCESSING, progress=0.0
        )

        # Update progress (optional - can be called during processing)
        if rq_job:
            rq_job.meta["progress"] = 0.1
            rq_job.save_meta()

        # Process the document (this is the existing sync function)
        process_document(document_uuid, file_path, tenant_id=tenant_uuid)

        # Update progress
        if rq_job:
            rq_job.meta["progress"] = 0.9
            rq_job.save_meta()

        # Mark job as completed
        result = {
            "status": "success",
            "document_id": document_id,
            "file_path": file_path,
            "message": "Document processed successfully",
        }

        JobService.update_job_status(
            db, job_uuid, JobStatus.COMPLETED, result=result, progress=1.0
        )

        logger.info(f"[RQ Worker] Document processing completed: job={job_id}")

        return result

    except Exception as e:
        logger.error(f"[RQ Worker] Document processing failed: job={job_id}, error={e}", exc_info=True)

        # Mark job as failed
        error_msg = f"{type(e).__name__}: {str(e)}"
        JobService.update_job_status(
            db,
            UUID(job_id),
            JobStatus.FAILED,
            error_message=error_msg,
        )

        # Re-raise to mark RQ job as failed
        raise

    finally:
        db.close()
