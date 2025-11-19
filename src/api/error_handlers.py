"""Global error handlers for FastAPI application."""

import logging
import uuid
from typing import Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.core.config import settings
from src.services.quota_service import QuotaExceededError

logger = logging.getLogger(__name__)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all unhandled exceptions.

    In production, returns a generic error message without exposing internal details.
    In development, includes more information for debugging.
    """
    # Generate request ID if not present
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # Log full details server-side
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "tenant_id": getattr(request.state, "tenant_id", None),
        },
    )

    # Determine response based on environment
    if settings.app_env == "production":
        # Production: sanitized error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred. Please contact support if this persists.",
                "request_id": request_id,
            },
        )
    else:
        # Development: include more details
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": str(exc),
                "type": exc.__class__.__name__,
                "request_id": request_id,
            },
        )


async def validation_exception_handler(
    request: Request, exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Returns structured validation error details.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    logger.warning(
        f"Validation error: {exc}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "errors": exc.errors() if hasattr(exc, "errors") else str(exc),
        },
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Invalid request data",
            "details": exc.errors() if hasattr(exc, "errors") else [{"msg": str(exc)}],
            "request_id": request_id,
        },
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """
    Handle ValueError exceptions.

    These are typically business logic errors that should be communicated to the user.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    logger.warning(
        f"ValueError: {exc}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "bad_request",
            "message": str(exc),
            "request_id": request_id,
        },
    )


async def quota_exceeded_handler(request: Request, exc: QuotaExceededError) -> JSONResponse:
    """
    Handle QuotaExceededError exceptions.

    Returns HTTP 402 Payment Required with details about the quota limit.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    logger.warning(
        f"Quota exceeded: {exc}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "quota_type": exc.quota_type,
            "current": exc.current,
            "limit": exc.limit,
            "tier": exc.tier,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={
            "error": "quota_exceeded",
            "message": str(exc),
            "quota_type": exc.quota_type,
            "current": exc.current,
            "limit": exc.limit,
            "tier": exc.tier,
            "upgrade_required": True,
            "request_id": request_id,
        },
    )
