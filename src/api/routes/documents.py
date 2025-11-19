"""Document upload and management API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session as DBSession

from src.api.dependencies import get_tenant_bm25_index, get_vector_store
from src.core.config import settings
from src.db.session import get_db
from src.ingestion.file_detector import FileDetector
from src.middleware.rate_limit import get_tenant_rate_limit, limiter
from src.middleware.tenant import get_current_tenant_id
from src.models.schemas import (
    DocumentMetadata,
    ProcessingStatus,
    UploadResponse,
)
from src.services.document_service import process_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
@limiter.limit(get_tenant_rate_limit("upload"))
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> UploadResponse:
    """
    Upload and process a document.

    Requires: X-API-Key header

    Rate Limits:
        - FREE tier: 10 uploads/hour
        - PRO tier: 1,000 uploads/hour

    Args:
        file: Uploaded file
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Upload response with document ID and status

    Raises:
        HTTPException: If upload or processing fails
    """
    try:
        # Save uploaded file
        file_path = settings.upload_dir / f"{tenant_id}_{file.filename}"
        content = await file.read()
        file_path.write_bytes(content)

        # Detect file type
        file_type = FileDetector.detect(file_path)

        # Create metadata
        metadata = DocumentMetadata(
            filename=file.filename,
            file_type=file_type,
            source_path=str(file_path),
            size_bytes=len(content),
        )

        logger.info(f"Tenant {tenant_id} uploaded {file.filename} ({file_type}) - {metadata.document_id}")

        # Process document (tenant-scoped)
        try:
            process_document(metadata.document_id, str(file_path), tenant_id=tenant_id)
            status_value = ProcessingStatus.COMPLETED
            message = "Document processed successfully"
        except Exception as e:
            logger.error(f"Error processing document for tenant {tenant_id}: {e}")
            status_value = ProcessingStatus.FAILED
            message = f"Processing failed: {str(e)}"

        return UploadResponse(
            document_id=metadata.document_id,
            filename=metadata.filename,
            file_type=metadata.file_type,
            size_bytes=metadata.size_bytes,
            status=status_value,
            message=message,
        )

    except Exception as e:
        logger.error(f"Upload error for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
):
    """
    Delete a document and all its chunks.

    Requires: X-API-Key header

    Args:
        document_id: Document ID to delete
        tenant_id: Tenant ID (from API key)
        db: Database session

    Raises:
        HTTPException: If deletion fails
    """
    try:
        # Get tenant-specific components
        vector_store = get_vector_store()
        bm25_index = get_tenant_bm25_index(tenant_id)

        # Delete from both stores (with tenant_id for safety)
        vector_store.delete_by_document(document_id, tenant_id=tenant_id)
        bm25_index.delete_by_document(document_id)

        logger.info(f"Tenant {tenant_id} deleted document {document_id}")

    except Exception as e:
        logger.error(f"Delete error for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/stats")
async def get_document_stats(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
):
    """
    Get document statistics for the tenant.

    Requires: X-API-Key header

    Args:
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Document statistics
    """
    try:
        vector_store = get_vector_store()
        bm25_index = get_tenant_bm25_index(tenant_id)

        return {
            "tenant_id": str(tenant_id),
            "vector_store_count": vector_store.count(tenant_id),
            "bm25_index_count": bm25_index.count(),
        }
    except Exception as e:
        logger.error(f"Stats error for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/clear", status_code=status.HTTP_200_OK)
async def clear_all_documents(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
):
    """
    Clear all documents and chunks for the tenant.

    This will delete all documents from the knowledge base for this tenant only.

    Requires: X-API-Key header

    Args:
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Status of the operation
    """
    try:
        vector_store = get_vector_store()
        bm25_index = get_tenant_bm25_index(tenant_id)

        logger.info(f"Clearing all indexes for tenant {tenant_id}...")

        # Clear both stores (tenant-scoped)
        vector_success = vector_store.clear_all(tenant_id=tenant_id)
        bm25_success = bm25_index.clear_all()

        if vector_success and bm25_success:
            logger.info(f"All indexes cleared successfully for tenant {tenant_id}")
            return {
                "message": "All documents cleared successfully",
                "tenant_id": str(tenant_id),
                "vector_store_cleared": True,
                "bm25_index_cleared": True,
            }
        else:
            logger.warning(f"Some indexes failed to clear for tenant {tenant_id}")
            return {
                "message": "Some indexes failed to clear",
                "tenant_id": str(tenant_id),
                "vector_store_cleared": vector_success,
                "bm25_index_cleared": bm25_success,
            }

    except Exception as e:
        logger.error(f"Clear indexes error for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
