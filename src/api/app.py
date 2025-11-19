"""FastAPI application setup."""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api import error_handlers
from src.api.routes import chat, documents, health, sessions, tenants
from src.core.config import settings
from src.middleware.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


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
