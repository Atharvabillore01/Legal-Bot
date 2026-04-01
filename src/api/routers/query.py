"""
Query endpoint.

POST /query  — semantic search + LLM response with citations and confidence score.
"""

import logging
import time
from datetime import datetime
from tracemalloc import start

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import AuditLog, get_db
from ..dependencies import get_current_user, rate_limit
from ..models import QueryRequest, QueryResponse, CitationOut, SourceChunkOut
from ..database import User

router = APIRouter(prefix="/query", tags=["Query"])
logger = logging.getLogger(__name__)


@router.post("", response_model=QueryResponse)
async def query_documents(
    body: QueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(rate_limit(max_calls=30, window_seconds=60)),
):
    """
    Query the user's document collection with a natural language question.

    Pipeline:
    1. Retrieve relevant chunks via FAISS semantic search
    2. Rerank and detect contradictions
    3. Build prompt and call GPT-4o
    4. Extract citations and score confidence
    5. Return cited answer with confidence level
    """
    start = time.perf_counter()
    audit_details: dict = {"query": body.query[:200], "k": body.k}

    try:
        # ── Retrieval ─────────────────────────────────────────────────────────
        search_start = time.perf_counter()
        from src.retrieval.retriever import retrieve_and_rerank
        from src.retrieval.models import SearchOptions, SearchFilter

        filters = None
        if body.jurisdiction or body.doc_ids:
            filters = SearchFilter(
                jurisdictions=[body.jurisdiction] if body.jurisdiction else None,
                doc_ids=body.doc_ids,
            )

        options = SearchOptions(
            k=body.k,
            filters=filters,
            detect_contradictions=body.detect_contradictions,
            rerank=body.rerank,
            return_all_matches=True,
        )

        retrieval_result = retrieve_and_rerank(
            user_id=current_user.id,
            query=body.query,
            options=options,
        )
        search_time_ms = (time.perf_counter() - search_start) * 1000

        if not retrieval_result.results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No relevant documents found. Upload documents first.",
            )

        # ── LLM query ─────────────────────────────────────────────────────────
        # ── LLM query ─────────────────────────────────────────────────────────
        llm_start = time.perf_counter()
        from src.llm.llm_interface import LLMQueryEngine

        engine = LLMQueryEngine()

        # Build chunk_metadata lookup {chunk_id: {doc_name, page_number, jurisdiction, ...}}
        chunk_metadata = {
            chunk.chunk_id: {
                "doc_name": chunk.doc_name,
                "page_number": chunk.page_number,
                "jurisdiction": chunk.jurisdiction,
                "section": chunk.section,
                "character_offset_start": getattr(chunk, "character_offset_start", None),
                "character_offset_end": getattr(chunk, "character_offset_end", None),
            }
            for chunk in retrieval_result.results
        }

        chunk_scores = [chunk.final_rank_score for chunk in retrieval_result.results]
# Convert RetrievedChunk Pydantic objects → dicts that prompt_builder expects
        chunks_as_dicts = [chunk.model_dump() for chunk in retrieval_result.results]

        llm_response = engine.query_llm(
            chunks=chunks_as_dicts,
            query=body.query,
            chunk_metadata=chunk_metadata,
            chunk_scores=chunk_scores,
            contradiction_count=sum(len(chunk.contradictions) for chunk in retrieval_result.results) if retrieval_result.has_contradictions else 0,
            user_id=str(current_user.id),
    )
        llm_time_ms = (time.perf_counter() - llm_start) * 1000
        total_time_ms = (time.perf_counter() - start) * 1000
        # ── Build response ────────────────────────────────────────────────────
        citations_out = [
            CitationOut(
                chunk_id=c.chunk_id,
                source_doc=c.source_doc,
                page_number=c.page_number,
                text_excerpt=c.text_excerpt,
                jurisdiction=c.jurisdiction,
                section=c.section,
                character_offset_start=c.character_offset_start,
                character_offset_end=c.character_offset_end,
            )
            for c in llm_response.citations
        ]

        source_chunks_out = [
            SourceChunkOut(
                chunk_id=chunk.chunk_id,
                doc_name=chunk.doc_name,
                page_number=chunk.page_number if chunk.page_number else None,
                section=chunk.section or None,
                jurisdiction=chunk.jurisdiction or None,
                text=chunk.text,
                relevance_score=round(chunk.final_rank_score, 4),
                rank=chunk.rank_position,
            )
            for chunk in retrieval_result.results
        ]

        audit_details.update({
            "result_count": retrieval_result.result_count,
            "confidence_level": llm_response.confidence_level,
            "has_contradictions": retrieval_result.has_contradictions,
        })

        # ── Audit log ─────────────────────────────────────────────────────────
        _write_audit(
            db, current_user.id, "query", "query", None,
            audit_details, request, "success", total_time_ms,
        )

        return QueryResponse(
            answer=llm_response.answer,
            citations=citations_out,
            source_chunks=source_chunks_out,
            confidence_score=llm_response.confidence_score,
            confidence_level=llm_response.confidence_level,
            query=body.query,
            search_time_ms=search_time_ms,
            llm_time_ms=llm_time_ms,
            total_time_ms=total_time_ms,
            model=llm_response.model,
            created_at=llm_response.created_at,
            has_contradictions=retrieval_result.has_contradictions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed for user {current_user.id}: {e}", exc_info=True)
        _write_audit(
            db, current_user.id, "query", "query", None,
            {**audit_details, "error": str(e)[:200]}, request, "failure",
            (time.perf_counter() - start) * 1000,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query processing failed. Please try again.",
        )


def _write_audit(
    db, user_id, action, resource_type, resource_id,
    details, request, result_status, latency_ms,
):
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status=result_status,
            latency_ms=latency_ms,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")
