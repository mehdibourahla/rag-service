"""Shared test fixtures and configuration."""

import os
from datetime import datetime, timedelta
from typing import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.app import app
from src.core.config import settings
from src.db.models import Base, Job, Tenant, TenantAPIKey as APIKey
from src.db.session import get_db
from src.models.tenant import TenantTier


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()

    yield session

    session.close()


@pytest.fixture(scope="function")
def db(db_session) -> Generator[Session, None, None]:
    """Alias for db_session for cleaner test signatures."""
    yield db_session


# ============================================================================
# Tenant Fixtures
# ============================================================================


@pytest.fixture
def free_tenant(db: Session) -> Tenant:
    """Create a FREE tier tenant for testing."""
    tenant = Tenant(
        tenant_id=uuid4(),
        name="Test Tenant (FREE)",
        tier=TenantTier.FREE,
        brand_name="Test Brand",
        brand_tone="professional",
        language="en",
        industry="technology",
        contact_email="test@example.com",
        status="active",
        settings={},
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@pytest.fixture
def pro_tenant(db: Session) -> Tenant:
    """Create a PRO tier tenant for testing."""
    tenant = Tenant(
        tenant_id=uuid4(),
        name="Test Tenant (PRO)",
        tier=TenantTier.PRO,
        brand_name="Test Pro Brand",
        brand_tone="friendly",
        language="en",
        industry="e-commerce",
        contact_email="pro@example.com",
        status="active",
        settings={},
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@pytest.fixture
def multiple_tenants(db: Session) -> list[Tenant]:
    """Create multiple tenants for multi-tenancy isolation tests."""
    tenants = [
        Tenant(
            tenant_id=uuid4(),
            name=f"Tenant {i}",
            tier=TenantTier.FREE if i % 2 == 0 else TenantTier.PRO,
            brand_name=f"Brand {i}",
            brand_tone="professional",
            language="en",
            industry="technology",
            contact_email=f"tenant{i}@example.com",
            status="active",
            settings={},
        )
        for i in range(3)
    ]
    db.add_all(tenants)
    db.commit()
    for tenant in tenants:
        db.refresh(tenant)
    return tenants


# ============================================================================
# API Key Fixtures
# ============================================================================


@pytest.fixture
def api_key_free(db: Session, free_tenant: Tenant) -> APIKey:
    """Create an API key for the FREE tier tenant."""
    from src.services.auth_service import AuthService

    api_key_obj = AuthService.create_api_key(
        db=db,
        tenant_id=free_tenant.tenant_id,
        name="Test API Key (FREE)",
        scopes=["chat", "upload", "query"],
        environment="test",
    )
    # Store the raw key for testing
    api_key_obj.raw_key = api_key_obj.key  # This is the untruncated key before save
    return api_key_obj


@pytest.fixture
def api_key_pro(db: Session, pro_tenant: Tenant) -> APIKey:
    """Create an API key for the PRO tier tenant."""
    from src.services.auth_service import AuthService

    api_key_obj = AuthService.create_api_key(
        db=db,
        tenant_id=pro_tenant.tenant_id,
        name="Test API Key (PRO)",
        scopes=["chat", "upload", "query"],
        environment="test",
    )
    api_key_obj.raw_key = api_key_obj.key
    return api_key_obj


# ============================================================================
# FastAPI Test Client Fixtures
# ============================================================================


@pytest.fixture
def client(db_session) -> TestClient:
    """Create a FastAPI test client with database override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # Session cleanup handled by db_session fixture

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup overrides
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client_free(client: TestClient, api_key_free: APIKey) -> TestClient:
    """Test client authenticated with FREE tier API key."""
    client.headers["X-API-Key"] = api_key_free.raw_key
    return client


@pytest.fixture
def authenticated_client_pro(client: TestClient, api_key_pro: APIKey) -> TestClient:
    """Test client authenticated with PRO tier API key."""
    client.headers["X-API-Key"] = api_key_pro.raw_key
    return client


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_openai_embeddings(mocker):
    """Mock OpenAI embeddings API to avoid actual API calls."""
    mock_response = mocker.Mock()
    mock_response.data = [mocker.Mock(embedding=[0.1] * 1536)]
    mock_create = mocker.patch("openai.OpenAI.embeddings.create", return_value=mock_response)
    return mock_create


@pytest.fixture
def mock_openai_chat(mocker):
    """Mock OpenAI chat completion API."""
    mock_response = mocker.Mock()
    mock_response.choices = [mocker.Mock(message=mocker.Mock(content="Test response"))]
    mock_create = mocker.patch("openai.OpenAI.chat.completions.create", return_value=mock_response)
    return mock_create


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis connection for caching tests."""
    mock_redis_client = mocker.Mock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.get.return_value = None
    mock_redis_client.setex.return_value = True
    mock_redis_client.delete.return_value = 1
    mock_redis_client.keys.return_value = []
    mocker.patch("redis.from_url", return_value=mock_redis_client)
    return mock_redis_client


@pytest.fixture
def mock_qdrant(mocker):
    """Mock Qdrant vector store."""
    mock_client = mocker.Mock()
    mock_client.upsert.return_value = None
    mock_client.search.return_value = []
    mock_client.delete.return_value = None
    mocker.patch("qdrant_client.QdrantClient", return_value=mock_client)
    return mock_client


# ============================================================================
# Job Fixtures
# ============================================================================


@pytest.fixture
def pending_job(db: Session, free_tenant: Tenant) -> Job:
    """Create a pending job for testing."""
    from src.models.job import JobStatus, JobType

    job = Job(
        job_id=uuid4(),
        tenant_id=free_tenant.tenant_id,
        job_type=JobType.DOCUMENT_UPLOAD,
        status=JobStatus.PENDING,
        document_id=uuid4(),
        file_path="/tmp/test.pdf",
        job_metadata={"filename": "test.pdf"},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def sample_text_chunks() -> list[dict]:
    """Sample text chunks for testing retrieval."""
    return [
        {
            "chunk_id": str(uuid4()),
            "text": "Python is a high-level programming language.",
            "metadata": {"source": "test.pdf", "page": 1},
        },
        {
            "chunk_id": str(uuid4()),
            "text": "FastAPI is a modern web framework for Python.",
            "metadata": {"source": "test.pdf", "page": 2},
        },
        {
            "chunk_id": str(uuid4()),
            "text": "Pydantic provides data validation using Python type annotations.",
            "metadata": {"source": "test.pdf", "page": 3},
        },
    ]


# ============================================================================
# Environment Setup
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    os.environ["APP_ENV"] = "testing"
    os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"
    os.environ["OPENAI_API_KEY"] = "sk-test-key"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    yield
    # Cleanup is handled automatically
