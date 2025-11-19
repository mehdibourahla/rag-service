"""FastAPI application setup."""

import logging
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api import error_handlers
from src.api.routes import chat, documents, health, jobs, sessions, tenants
from src.core.config import settings
from src.middleware.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Initialize Sentry for error tracking (if DSN is configured)
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        # Sample rate for performance monitoring
        traces_sample_rate=0.1 if settings.app_env == "production" else 1.0,
        # Sample rate for profiling
        profiles_sample_rate=0.1 if settings.app_env == "production" else 1.0,
        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        # Release tracking
        release=f"pingo-chatbot@0.2.0",
        # Send default PII (user IDs, but not sensitive data)
        send_default_pii=False,
        # Attach stack locals to errors (development only)
        attach_stacktrace=settings.app_env != "production",
    )
    logger.info(f"Sentry initialized for environment: {settings.app_env}")
else:
    logger.info("Sentry not configured (SENTRY_DSN not set)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.app_env}")

    # Startup: initialize services
    from src.api.dependencies import get_bm25_index, get_vector_store

    vector_store = get_vector_store()
    bm25_index = get_bm25_index()

    logger.info(f"Vector store: {vector_store.count()} chunks")
    logger.info(f"BM25 index: {bm25_index.count()} chunks")

    yield

    # Shutdown: cleanup
    logger.info(f"Shutting down {settings.app_name}")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Multi-tenant AI chatbot platform with agentic RAG",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger.info("Rate limiting enabled")

# CORS middleware - restrict to configured origins for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

logger.info(f"CORS allowed origins: {settings.get_allowed_origins()}")

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request."""
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Sentry context enrichment middleware
if settings.sentry_dsn:
    @app.middleware("http")
    async def add_sentry_context(request: Request, call_next):
        """Enrich Sentry events with request and tenant context."""
        with sentry_sdk.configure_scope() as scope:
            # Add request context
            scope.set_context("request", {
                "url": str(request.url),
                "method": request.method,
                "headers": dict(request.headers),
                "request_id": getattr(request.state, "request_id", None),
            })

            # Add tenant context (if available)
            tenant = getattr(request.state, "tenant", None)
            if tenant:
                scope.set_user({
                    "id": str(tenant.tenant_id),
                    "username": tenant.name,
                    "email": tenant.contact_email,
                })
                scope.set_tag("tenant_tier", tenant.tier)
                scope.set_tag("tenant_id", str(tenant.tenant_id))

        return await call_next(request)

# Register error handlers
app.add_exception_handler(Exception, error_handlers.generic_exception_handler)
app.add_exception_handler(RequestValidationError, error_handlers.validation_exception_handler)
app.add_exception_handler(ValidationError, error_handlers.validation_exception_handler)
app.add_exception_handler(ValueError, error_handlers.value_error_handler)

# Include all route modules
app.include_router(health.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "0.2.0",
        "description": "Multi-tenant AI chatbot platform",
        "status": "running",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }
