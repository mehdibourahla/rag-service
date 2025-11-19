"""API tests for tenant routes."""

import pytest
from fastapi.testclient import TestClient

from src.db.models import Tenant
from src.models.tenant import TenantTier


@pytest.mark.api
class TestTenantsAPI:
    """Test /api/v1/tenants endpoints."""

    def test_create_tenant(self, client: TestClient):
        """Test POST /api/v1/tenants - Create new tenant."""
        payload = {
            "name": "New Test Company",
            "tier": "FREE",
            "brand_name": "TestBrand",
            "brand_tone": "professional",
            "language": "en",
            "industry": "technology",
            "contact_email": "contact@test.com",
        }

        response = client.post("/api/v1/tenants", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Test Company"
        assert data["tier"] == "FREE"
        assert data["brand_name"] == "TestBrand"
        assert "tenant_id" in data
        assert "created_at" in data

    def test_create_tenant_missing_required_fields(self, client: TestClient):
        """Test creating tenant without required fields fails."""
        payload = {"name": "Incomplete Tenant"}

        response = client.post("/api/v1/tenants", json=payload)

        assert response.status_code == 422  # Validation error

    def test_get_tenant(self, client: TestClient, free_tenant: Tenant):
        """Test GET /api/v1/tenants/{tenant_id} - Get tenant by ID."""
        response = client.get(f"/api/v1/tenants/{free_tenant.tenant_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == str(free_tenant.tenant_id)
        assert data["name"] == free_tenant.name
        assert data["tier"] == free_tenant.tier.value

    def test_get_nonexistent_tenant(self, client: TestClient):
        """Test getting non-existent tenant returns 404."""
        from uuid import uuid4

        fake_id = uuid4()
        response = client.get(f"/api/v1/tenants/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_tenant(self, client: TestClient, free_tenant: Tenant):
        """Test PATCH /api/v1/tenants/{tenant_id} - Update tenant."""
        payload = {
            "brand_name": "Updated Brand",
            "brand_tone": "friendly",
        }

        response = client.patch(f"/api/v1/tenants/{free_tenant.tenant_id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["brand_name"] == "Updated Brand"
        assert data["brand_tone"] == "friendly"

    def test_list_tenants(self, client: TestClient, multiple_tenants: list[Tenant]):
        """Test GET /api/v1/tenants - List all tenants."""
        response = client.get("/api/v1/tenants")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= len(multiple_tenants)

    def test_get_tenant_stats(self, client: TestClient, free_tenant: Tenant):
        """Test GET /api/v1/tenants/{tenant_id}/stats - Get tenant statistics."""
        response = client.get(f"/api/v1/tenants/{free_tenant.tenant_id}/stats")

        assert response.status_code == 200
        data = response.json()
        assert "sessions_count" in data
        assert "messages_count" in data
        assert "api_keys_count" in data

    def test_get_tenant_quotas(self, client: TestClient, free_tenant: Tenant):
        """Test GET /api/v1/tenants/{tenant_id}/quotas - Get quota usage."""
        response = client.get(f"/api/v1/tenants/{free_tenant.tenant_id}/quotas")

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "FREE"
        assert "quotas" in data
        assert "usage" in data
        assert data["quotas"]["max_documents"] == 10
        assert data["quotas"]["max_queries_per_day"] == 100

    def test_deactivate_tenant(self, client: TestClient, free_tenant: Tenant):
        """Test DELETE /api/v1/tenants/{tenant_id} - Deactivate tenant."""
        response = client.delete(f"/api/v1/tenants/{free_tenant.tenant_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"

        # Verify tenant is marked as deleted
        get_response = client.get(f"/api/v1/tenants/{free_tenant.tenant_id}")
        assert get_response.json()["status"] == "deleted"

    def test_create_api_key(self, client: TestClient, free_tenant: Tenant):
        """Test POST /api/v1/tenants/{tenant_id}/api-keys - Create API key."""
        payload = {
            "name": "Test API Key",
            "scopes": ["chat", "upload"],
            "environment": "test",
        }

        response = client.post(
            f"/api/v1/tenants/{free_tenant.tenant_id}/api-keys",
            json=payload,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test API Key"
        assert data["scopes"] == ["chat", "upload"]
        assert data["environment"] == "test"
        assert "key" in data
        assert data["key"].startswith("pk_test_")

    def test_list_api_keys(self, client: TestClient, free_tenant: Tenant, api_key_free):
        """Test GET /api/v1/tenants/{tenant_id}/api-keys - List API keys."""
        response = client.get(f"/api/v1/tenants/{free_tenant.tenant_id}/api-keys")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Keys should be truncated in list
        for key_data in data:
            assert "key" not in key_data  # Full key not exposed
            assert "key_preview" in key_data  # Only preview shown

    def test_revoke_api_key(self, client: TestClient, free_tenant: Tenant, api_key_free):
        """Test DELETE /api/v1/tenants/{tenant_id}/api-keys/{key_id} - Revoke key."""
        response = client.delete(
            f"/api/v1/tenants/{free_tenant.tenant_id}/api-keys/{api_key_free.key_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
