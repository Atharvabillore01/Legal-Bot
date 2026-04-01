"""
Document ingestion endpoint.

POST /ingest  — upload a PDF/DOCX/TXT file, chunk it, embed it, index it.

The heavy work runs as a FastAPI BackgroundTask so the upload response
is immediate (202 Accepted) while processing happens asynchronously.
"""

import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks, status
from sqlalchemy.orm import Session

from ..database import Document, get_db
from ..dependencies import get_current_user, rate_limit
from ..models import IngestResponse
from ..database import User

router = APIRouter(prefix="/ingest", tags=["Ingestion"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"pdf", "docx", "txt"}
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024


@router.post("", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    jurisdiction: Optional[str] = Form(None),
    authority_level: str = Form("reference"),
    db: Session = Depends(get_db),
    current_user: User = Depends(rate_limit(max_calls=20, window_seconds=3600)),
):
    """
    Upload a legal document for ingestion.

    - Accepts PDF, DOCX, or TXT files up to MAX_FILE_SIZE_MB.
    - Returns immediately with a document_id.
    - Processing (chunking + embedding + indexing) runs in the background.
    - Poll GET /documents/{document_id} to check status.
    """
    # Validate extension
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_TYPES)}",
        )

    if authority_level not in ("binding", "precedent", "reference"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid authority_level")

    # Read file content and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB",
        )

    # Create DB record immediately
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=f"{doc_id}.{ext}",
        original_filename=filename,
        file_type=ext,
        file_size_bytes=len(content),
        status="pending",
        jurisdiction=jurisdiction,
        authority_level=authority_level,
    )
    db.add(doc)
    db.commit()

    # Schedule background processing
    background_tasks.add_task(
        _process_document,
        doc_id=doc_id,
        user_id=current_user.id,
        content=content,
        ext=ext,
        jurisdiction=jurisdiction,
    )

    logger.info(f"Queued ingestion for document {doc_id} ({filename}) user={current_user.id}")
    return IngestResponse(
        document_id=doc_id,
        status="pending",
        message="Document received and queued for processing",
        filename=filename,
    )


def _process_document(
    doc_id: str,
    user_id: str,
    content: bytes,
    ext: str,
    jurisdiction: Optional[str],
) -> None:
    """
    Background task: ingest → embed → index.
    Updates document status in DB at each stage.
    """
    from ..database import SessionLocal, Document

    db = SessionLocal()
    try:
        # Mark as processing
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return
        doc.status = "processing"
        db.commit()

        # Write to temp file (ingestion module expects file path)
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Step 1: Ingest (load → clean → chunk)
            from src.ingestion import ingest_document as _ingest

            ingestion_result = _ingest(
                file_path=tmp_path,
                user_id=user_id,
                jurisdiction=jurisdiction,
            )
            chunks = ingestion_result

            if not chunks:
                raise ValueError("No chunks produced from document")

            # Step 2: Embed chunks
            from src.embeddings import embed_chunks
            embedded_chunks = embed_chunks(chunks, user_id)

            # Step 3: Index (create index if needed, then add chunks)
            from src.embeddings import create_user_index, add_chunks_to_index, get_index
            try:
                get_index(user_id)
            except Exception:
                create_user_index(user_id)
            add_chunks_to_index(user_id, embedded_chunks)

            # Success
            doc.status = "ready"
            doc.chunk_count = len(chunks)
            doc.processed_at = datetime.utcnow()
            logger.info(f"Document {doc_id} processed: {len(chunks)} chunks indexed")

        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Ingestion failed for document {doc_id}: {e}", exc_info=True)
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = "failed"
            doc.error_message = str(e)[:500]
            doc.processed_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()
