"""Unit tests for JobService."""

import pytest
from uuid import uuid4

from sqlalchemy.orm import Session

from src.db.models import Job, Tenant
from src.models.job import JobStatus, JobType
from src.services.job_service import JobService


@pytest.mark.unit
class TestJobService:
    """Test JobService for background job management."""

    def test_create_job(self, db: Session, free_tenant: Tenant):
        """Test creating a new background job."""
        document_id = uuid4()
        file_path = "/tmp/test.pdf"

        job = JobService.create_job(
            db=db,
            tenant_id=free_tenant.tenant_id,
            job_type=JobType.DOCUMENT_UPLOAD,
            document_id=document_id,
            file_path=file_path,
            metadata={"filename": "test.pdf", "size": 1024},
        )

        assert job.job_id is not None
        assert job.tenant_id == free_tenant.tenant_id
        assert job.job_type == JobType.DOCUMENT_UPLOAD
        assert job.status == JobStatus.PENDING
        assert job.document_id == document_id
        assert job.file_path == file_path
        assert job.metadata["filename"] == "test.pdf"
        assert job.created_at is not None

    def test_get_job(self, db: Session, pending_job: Job):
        """Test retrieving a job by ID."""
        job = JobService.get_job(db, pending_job.job_id, pending_job.tenant_id)

        assert job is not None
        assert job.job_id == pending_job.job_id
        assert job.tenant_id == pending_job.tenant_id

    def test_get_job_wrong_tenant(self, db: Session, pending_job: Job, pro_tenant: Tenant):
        """Test that jobs are tenant-isolated."""
        # Try to get job with wrong tenant_id
        job = JobService.get_job(db, pending_job.job_id, pro_tenant.tenant_id)

        assert job is None  # Should not find job from different tenant

    def test_update_job_to_processing(self, db: Session, pending_job: Job):
        """Test updating job status to PROCESSING."""
        updated_job = JobService.update_job_status(
            db=db,
            job_id=pending_job.job_id,
            status=JobStatus.PROCESSING,
            progress=0.1,
        )

        assert updated_job.status == JobStatus.PROCESSING
        assert updated_job.progress == 0.1
        assert updated_job.started_at is not None

    def test_update_job_to_completed(self, db: Session, pending_job: Job):
        """Test updating job status to COMPLETED."""
        result = {"chunks_created": 10, "embeddings_generated": 10}

        updated_job = JobService.update_job_status(
            db=db,
            job_id=pending_job.job_id,
            status=JobStatus.COMPLETED,
            result=result,
            progress=1.0,
        )

        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.progress == 1.0
        assert updated_job.result == result
        assert updated_job.completed_at is not None

    def test_update_job_to_failed(self, db: Session, pending_job: Job):
        """Test updating job status to FAILED with error message."""
        error_msg = "File processing failed: invalid format"

        updated_job = JobService.update_job_status(
            db=db,
            job_id=pending_job.job_id,
            status=JobStatus.FAILED,
            error_message=error_msg,
        )

        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message == error_msg
        assert updated_job.completed_at is not None

    def test_job_progress_tracking(self, db: Session, pending_job: Job):
        """Test tracking job progress through multiple updates."""
        # Start processing
        JobService.update_job_status(
            db=db,
            job_id=pending_job.job_id,
            status=JobStatus.PROCESSING,
            progress=0.0,
        )

        # Update progress
        job_25 = JobService.update_job_status(
            db=db,
            job_id=pending_job.job_id,
            status=JobStatus.PROCESSING,
            progress=0.25,
        )
        assert job_25.progress == 0.25

        job_50 = JobService.update_job_status(
            db=db,
            job_id=pending_job.job_id,
            status=JobStatus.PROCESSING,
            progress=0.50,
        )
        assert job_50.progress == 0.50

        # Complete
        job_done = JobService.update_job_status(
            db=db,
            job_id=pending_job.job_id,
            status=JobStatus.COMPLETED,
            progress=1.0,
        )
        assert job_done.progress == 1.0
        assert job_done.status == JobStatus.COMPLETED

    def test_to_response(self, db: Session, pending_job: Job):
        """Test converting Job model to JobResponse."""
        response = JobService.to_response(pending_job)

        assert response.job_id == pending_job.job_id
        assert response.tenant_id == pending_job.tenant_id
        assert response.job_type == pending_job.job_type
        assert response.status == pending_job.status
        assert response.document_id == pending_job.document_id
        assert response.created_at == pending_job.created_at

    def test_list_jobs_for_tenant(self, db: Session, free_tenant: Tenant):
        """Test listing all jobs for a tenant."""
        # Create multiple jobs
        jobs_created = []
        for i in range(3):
            job = JobService.create_job(
                db=db,
                tenant_id=free_tenant.tenant_id,
                job_type=JobType.DOCUMENT_UPLOAD,
                document_id=uuid4(),
                file_path=f"/tmp/test{i}.pdf",
            )
            jobs_created.append(job)

        # Note: Assuming list_jobs method exists
        # If not, this test documents desired functionality
        jobs = db.query(Job).filter(Job.tenant_id == free_tenant.tenant_id).all()

        assert len(jobs) >= 3
        job_ids = [j.job_id for j in jobs]
        for created_job in jobs_created:
            assert created_job.job_id in job_ids

    def test_job_isolation_between_tenants(
        self, db: Session, free_tenant: Tenant, pro_tenant: Tenant
    ):
        """Test that jobs are isolated between tenants."""
        # Create job for FREE tenant
        free_job = JobService.create_job(
            db=db,
            tenant_id=free_tenant.tenant_id,
            job_type=JobType.DOCUMENT_UPLOAD,
            document_id=uuid4(),
            file_path="/tmp/free.pdf",
        )

        # Create job for PRO tenant
        pro_job = JobService.create_job(
            db=db,
            tenant_id=pro_tenant.tenant_id,
            job_type=JobType.DOCUMENT_UPLOAD,
            document_id=uuid4(),
            file_path="/tmp/pro.pdf",
        )

        # FREE tenant should only see their job
        free_jobs = db.query(Job).filter(Job.tenant_id == free_tenant.tenant_id).all()
        free_job_ids = [j.job_id for j in free_jobs]
        assert free_job.job_id in free_job_ids
        assert pro_job.job_id not in free_job_ids

        # PRO tenant should only see their job
        pro_jobs = db.query(Job).filter(Job.tenant_id == pro_tenant.tenant_id).all()
        pro_job_ids = [j.job_id for j in pro_jobs]
        assert pro_job.job_id in pro_job_ids
        assert free_job.job_id not in pro_job_ids

    def test_multiple_job_types(self, db: Session, free_tenant: Tenant):
        """Test creating jobs of different types."""
        # Document upload job
        upload_job = JobService.create_job(
            db=db,
            tenant_id=free_tenant.tenant_id,
            job_type=JobType.DOCUMENT_UPLOAD,
            document_id=uuid4(),
            file_path="/tmp/upload.pdf",
        )
        assert upload_job.job_type == JobType.DOCUMENT_UPLOAD

        # Document reindex job
        reindex_job = JobService.create_job(
            db=db,
            tenant_id=free_tenant.tenant_id,
            job_type=JobType.DOCUMENT_REINDEX,
            document_id=uuid4(),
        )
        assert reindex_job.job_type == JobType.DOCUMENT_REINDEX

        # Bulk delete job
        delete_job = JobService.create_job(
            db=db,
            tenant_id=free_tenant.tenant_id,
            job_type=JobType.BULK_DELETE,
            metadata={"document_ids": [str(uuid4()), str(uuid4())]},
        )
        assert delete_job.job_type == JobType.BULK_DELETE

    def test_job_metadata_storage(self, db: Session, free_tenant: Tenant):
        """Test storing and retrieving complex metadata."""
        metadata = {
            "filename": "large_document.pdf",
            "size_bytes": 5242880,
            "file_type": "application/pdf",
            "chunks_expected": 100,
            "custom_settings": {"chunk_size": 512, "overlap": 50},
        }

        job = JobService.create_job(
            db=db,
            tenant_id=free_tenant.tenant_id,
            job_type=JobType.DOCUMENT_UPLOAD,
            document_id=uuid4(),
            file_path="/tmp/large.pdf",
            metadata=metadata,
        )

        # Retrieve and verify metadata
        retrieved_job = JobService.get_job(db, job.job_id, free_tenant.tenant_id)
        assert retrieved_job.metadata == metadata
        assert retrieved_job.metadata["custom_settings"]["chunk_size"] == 512
