"""Job queue management using Redis Queue (RQ)."""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

import redis
from rq import Queue
from rq.job import Job

from src.core.config import settings

logger = logging.getLogger(__name__)


class JobQueue:
    """Wrapper for RQ job queue operations."""

    def __init__(self):
        """Initialize Redis connection and RQ queue."""
        try:
            self.redis_conn = redis.from_url(
                settings.redis_url,
                decode_responses=False,  # RQ requires bytes
            )
            self.queue = Queue(connection=self.redis_conn, default_timeout="10m")
            logger.info(f"Job queue initialized: {settings.redis_url}")
        except Exception as e:
            logger.error(f"Failed to initialize job queue: {e}")
            raise

    def enqueue_document_processing(
        self,
        job_id: UUID,
        document_id: UUID,
        file_path: str,
        tenant_id: UUID,
    ) -> Job:
        """
        Enqueue a document processing job.

        Args:
            job_id: Job ID (for tracking)
            document_id: Document ID to process
            file_path: Path to the uploaded file
            tenant_id: Tenant ID

        Returns:
            RQ Job object
        """
        from src.workers.document_worker import process_document_job

        rq_job = self.queue.enqueue(
            process_document_job,
            str(job_id),
            str(document_id),
            file_path,
            str(tenant_id),
            description=f"Process document {document_id} for tenant {tenant_id}",
            meta={"job_id": str(job_id), "tenant_id": str(tenant_id)},
        )

        logger.info(
            f"Enqueued document processing job: {job_id} "
            f"(RQ job: {rq_job.id}, position: {self.queue.count})"
        )

        return rq_job

    def get_job_info(self, rq_job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get RQ job information.

        Args:
            rq_job_id: RQ job ID

        Returns:
            dict with job info or None
        """
        try:
            from rq.job import Job

            rq_job = Job.fetch(rq_job_id, connection=self.redis_conn)

            return {
                "rq_job_id": rq_job.id,
                "status": rq_job.get_status(),
                "created_at": rq_job.created_at,
                "started_at": rq_job.started_at,
                "ended_at": rq_job.ended_at,
                "result": rq_job.result,
                "exc_info": rq_job.exc_info,
                "meta": rq_job.meta,
            }
        except Exception as e:
            logger.error(f"Failed to fetch RQ job {rq_job_id}: {e}")
            return None

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "count": len(self.queue),
            "failed_count": len(self.queue.failed_job_registry),
            "finished_count": len(self.queue.finished_job_registry),
            "started_count": len(self.queue.started_job_registry),
            "deferred_count": len(self.queue.deferred_job_registry),
        }


# Global job queue instance (initialized on first use)
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get or create the global job queue instance."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    return _job_queue
