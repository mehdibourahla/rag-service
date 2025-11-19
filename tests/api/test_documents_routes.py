"""API tests for document routes."""

import io
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from src.db.models import Tenant, APIKey


@pytest.mark.api
class TestDocumentsAPI:
    """Test /api/v1/documents endpoints."""

    def test_upload_document_requires_auth(self, client: TestClient):
        """Test that document upload requires API key authentication."""
        files = {"file": ("test.txt", io.BytesIO(b"Test content"), "text/plain")}

        response = client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 401  # Unauthorized

    def test_upload_document_txt(
        self, authenticated_client_free: TestClient, free_tenant: Tenant, mock_redis, mocker
    ):
        """Test uploading a text document."""
        # Mock Redis Queue and OpenAI
        mock_queue = mocker.Mock()
        mock_queue.enqueue_document_processing.return_value = None
        mocker.patch("src.workers.queue.get_job_queue", return_value=mock_queue)

        content = b"This is a test document with some content."
        files = {"file": ("test.txt", io.BytesIO(content), "text/plain")}

        response = authenticated_client_free.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 202  # Accepted for async processing
        data = response.json()
        assert "document_id" in data
        assert "job_id" in data
        assert data["filename"] == "test.txt"
        assert data["status"] == "PENDING"

    def test_upload_document_pdf(
        self, authenticated_client_free: TestClient, free_tenant: Tenant, mocker
    ):
        """Test uploading a PDF document."""
        mock_queue = mocker.Mock()
        mocker.patch("src.workers.queue.get_job_queue", return_value=mock_queue)

        # Simple PDF header (not a real PDF, but for testing)
        content = b"%PDF-1.4\nTest PDF content"
        files = {"file": ("test.pdf", io.BytesIO(content), "application/pdf")}

        response = authenticated_client_free.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 202
        data = response.json()
        assert data["filename"] == "test.pdf"
        assert data["file_type"] in ["pdf", "application/pdf"]

    def test_upload_exceeds_quota(
        self, authenticated_client_free: TestClient, free_tenant: Tenant, mocker
    ):
        """Test that upload fails when quota is exceeded."""
        # Mock quota check to raise quota exceeded error
        from src.services.quota_service import QuotaExceededError

        mocker.patch(
            "src.services.quota_service.QuotaService.check_document_quota",
            side_effect=QuotaExceededError(
                "Document count quota exceeded",
                quota_type="max_documents",
                current=10,
                limit=10,
                tier="FREE",
            ),
        )

        files = {"file": ("test.txt", io.BytesIO(b"Test"), "text/plain")}
        response = authenticated_client_free.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 402  # Payment Required
        data = response.json()
        assert data["error"] == "quota_exceeded"
        assert data["quota_type"] == "max_documents"
        assert data["upgrade_required"] is True

    def test_upload_file_too_large(
        self, authenticated_client_free: TestClient, free_tenant: Tenant, mocker
    ):
        """Test uploading file exceeding size quota."""
        from src.services.quota_service import QuotaExceededError

        # Mock quota check to raise file size error
        mocker.patch(
            "src.services.quota_service.QuotaService.check_document_quota",
            side_effect=QuotaExceededError(
                "File size exceeds quota",
                quota_type="max_file_size_mb",
                current=15.0,
                limit=10.0,
                tier="FREE",
            ),
        )

        # Large file (15MB mock)
        large_content = b"x" * (15 * 1024 * 1024)
        files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}

        response = authenticated_client_free.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 402
        data = response.json()
        assert data["quota_type"] == "max_file_size_mb"

    def test_get_document_stats(
        self, authenticated_client_free: TestClient, free_tenant: Tenant, mock_qdrant
    ):
        """Test GET /api/v1/documents/stats - Get document statistics."""
        # Mock vector store and BM25 counts
        mock_qdrant.count.return_value = 5

        response = authenticated_client_free.get("/api/v1/documents/stats")

        assert response.status_code == 200
        data = response.json()
        assert "tenant_id" in data
        assert "vector_store_count" in data
        assert "bm25_index_count" in data

    def test_delete_document(
        self,
        authenticated_client_free: TestClient,
        free_tenant: Tenant,
        mock_qdrant,
        mock_redis,
    ):
        """Test DELETE /api/v1/documents/{document_id} - Delete document."""
        document_id = uuid4()

        response = authenticated_client_free.delete(f"/api/v1/documents/{document_id}")

        assert response.status_code == 204  # No content

    def test_clear_all_documents(
        self,
        authenticated_client_free: TestClient,
        free_tenant: Tenant,
        mock_qdrant,
        mock_redis,
    ):
        """Test DELETE /api/v1/documents/clear - Clear all documents."""
        mock_qdrant.delete.return_value = True

        response = authenticated_client_free.delete("/api/v1/documents/clear")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "All documents cleared successfully"
        assert data["vector_store_cleared"] is True
        assert data["bm25_index_cleared"] is True

    def test_tenant_isolation_upload(
        self,
        authenticated_client_free: TestClient,
        authenticated_client_pro: TestClient,
        free_tenant: Tenant,
        pro_tenant: Tenant,
        mocker,
    ):
        """Test that uploaded documents are isolated per tenant."""
        mock_queue = mocker.Mock()
        mocker.patch("src.workers.queue.get_job_queue", return_value=mock_queue)

        # Upload with FREE tenant
        files_free = {"file": ("free_doc.txt", io.BytesIO(b"Free content"), "text/plain")}
        response_free = authenticated_client_free.post(
            "/api/v1/documents/upload", files=files_free
        )
        assert response_free.status_code == 202

        # Upload with PRO tenant
        files_pro = {"file": ("pro_doc.txt", io.BytesIO(b"Pro content"), "text/plain")}
        response_pro = authenticated_client_pro.post(
            "/api/v1/documents/upload", files=files_pro
        )
        assert response_pro.status_code == 202

        # Each should have unique document IDs
        assert response_free.json()["document_id"] != response_pro.json()["document_id"]

    def test_rate_limiting_upload(
        self, authenticated_client_free: TestClient, free_tenant: Tenant, mocker
    ):
        """Test that rate limiting is enforced on uploads."""
        # Note: Rate limiting specifics depend on slowapi configuration
        # This is a placeholder for rate limit testing
        # Actual implementation may vary
        pass  # TODO: Implement based on rate limit configuration
