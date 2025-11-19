"""Health check and system status routes."""

import logging
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy.orm import Session as DBSession
from fastapi import Depends

from src.api.dependencies import get_bm25_index, get_vector_store
from src.db.session import get_db
from src.db.models import ChatSession, Message, Tenant, TenantAPIKey

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: DBSession = Depends(get_db)):
    """
    Health check endpoint with system statistics.

    Returns:
        System health status and statistics
    """
    try:
        vector_store = get_vector_store()
        bm25_index = get_bm25_index()

        # Get database stats
        total_tenants = db.query(Tenant).count()
        active_tenants = db.query(Tenant).filter(Tenant.status == "active").count()
        total_api_keys = db.query(TenantAPIKey).count()
        active_api_keys = db.query(TenantAPIKey).filter(TenantAPIKey.is_active).count()
        total_sessions = db.query(ChatSession).count()
        total_messages = db.query(Message).count()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "storage": {
                "vector_store_count": vector_store.count(),
                "bm25_index_count": bm25_index.count(),
            },
            "database": {
                "total_tenants": total_tenants,
                "active_tenants": active_tenants,
                "total_api_keys": total_api_keys,
                "active_api_keys": active_api_keys,
                "total_sessions": total_sessions,
                "total_messages": total_messages,
            },
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/readiness")
async def readiness_check(db: DBSession = Depends(get_db)):
    """
    Readiness check for Kubernetes/container orchestration.

    Returns:
        Readiness status
    """
    try:
        # Check database connection
        db.execute("SELECT 1")

        # Check vector store
        vector_store = get_vector_store()
        vector_store.count()

        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/liveness")
async def liveness_check():
    """
    Liveness check for Kubernetes/container orchestration.

    Returns:
        Liveness status (always returns 200 if server is running)
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }
