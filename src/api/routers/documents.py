"""
Document management endpoints.

GET    /documents          — list user's documents (paginated)
GET    /documents/{id}     — get document detail
DELETE /documents/{id}     — delete document and remove from FAISS index
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..database import Document, get_db
from ..dependencies import get_current_user
from ..models import DocumentResponse, DocumentListResponse, DeleteDocumentResponse
from ..database import User

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents belonging to the authenticated user."""
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if status_filter:
        query = query.filter(Document.status == status_filter)

    total = query.count()
    docs = (
        query.order_by(Document.uploaded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detail for a specific document."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a document and remove its chunks from the FAISS index.
    """
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Remove chunks from FAISS index + metadata sidecar
    try:
        from src.embeddings.metadata import (
    resolve_chunk_ids_by_doc,
    remove_entries_from_metadata,
    save_metadata,
)
        from src.embeddings.indexer import remove_chunks_from_index

        chunk_ids = resolve_chunk_ids_by_doc(current_user.id, document_id)
        if chunk_ids:
            # Remove from FAISS (if indexer supports it)
            try:
                remove_chunks_from_index(current_user.id, chunk_ids)
            except Exception as e:
                logger.warning(f"Could not remove chunks from FAISS index: {e}")

            # Remove from metadata sidecar
            updated_meta = remove_entries_from_metadata(current_user.id, chunk_ids)
            save_metadata(current_user.id, updated_meta)

    except Exception as e:
        logger.error(f"Failed to clean up index for document {document_id}: {e}")
        # Don't block deletion — DB record is authoritative

    db.delete(doc)
    db.commit()
    logger.info(f"Deleted document {document_id} for user {current_user.id}")
    return DeleteDocumentResponse(message="Document deleted successfully", document_id=document_id)
