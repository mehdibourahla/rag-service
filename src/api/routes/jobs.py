"""Job status and management API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from src.db.session import get_db
from src.middleware.tenant import get_current_tenant_id
from src.models.job import JobResponse
from src.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> JobResponse:
    """
    Get job status and details.

    Requires: X-API-Key header

    Args:
        job_id: Job ID to check
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Job details including status, progress, and result

    Raises:
        HTTPException: If job not found
    """
    try:
        job = JobService.get_job(db, job_id, tenant_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        return JobService.to_response(job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job {job_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
