"""
src/retrieval/retriever.py

Main orchestration for retrieval and reranking pipeline.

Functions:
    - retrieve_and_rerank: Complete pipeline from query to ranked results
    - apply_metadata_filters: Post-retrieval filtering
    - apply_fallback_strategy: Handle <k results
    - format_results: Create RetrievalResult wrapper
"""

import logging
import time
from typing import List, Optional

from src.embeddings import embed_query, load_metadata_for_user
from src.retrieval.models import (
    RetrievedChunk, RetrievalResult, SearchOptions, SearchFilter
)
from src.retrieval.exceptions import (
    RetrievalError, InvalidQueryError, UserIndexNotFound,
    NoResultsError, FallbackExhaustedError
)
from src.retrieval.semantic_search import semantic_search
from src.retrieval.contradiction_detector import detect_contradictions
from src.retrieval.reranker import rerank_chunks
from src.retrieval import constants

logger = logging.getLogger(__name__)


def retrieve_and_rerank(
    user_id: str,
    query: str,
    options: Optional[SearchOptions] = None,
) -> RetrievalResult:
    """
    Complete retrieval and reranking pipeline.
    
    Pipeline:
    1. Validate query and options
    2. Generate query embedding
    3. Execute semantic search (FAISS)
    4. Apply metadata filters
    5. Detect contradictions
    6. Rerank results
    7. Select top-K
    8. Handle fallback if <k results
    9. Return RetrievalResult
    
    Args:
        user_id: User ID for accessing FAISS index
        query: Natural language query
        options: SearchOptions (uses defaults if None)
    
    Returns:
        RetrievalResult with ranked RetrievedChunk list
    
    Raises:
        InvalidQueryError: Query is empty or invalid
        UserIndexNotFound: No index for user
        RetrievalError: Processing failed
        NoResultsError: No results found even after fallback
    
    Latency: <200ms (50ms semantic + 20ms filter + 60ms detect + 30ms rerank)
    """
    
    start_time = time.perf_counter()
    
    if options is None:
        options = SearchOptions()
    
    # Initialize tracking
    search_method = "semantic"
    has_contradictions = False
    fallback_applied = False
    fallback_reason = None
    
    try:
        # Step 1: Validate query
        logger.info(f"Retrieving for user {user_id}, query: '{query[:50]}...'")
        
        if not query or not isinstance(query, str):
            raise InvalidQueryError("Query must be non-empty string")
        
        query = query.strip()
        
        if len(query) > constants.QUERY_MAX_LENGTH:
            raise InvalidQueryError(f"Query exceeds max length {constants.QUERY_MAX_LENGTH}")
        
        if len(query) < constants.QUERY_MIN_LENGTH:
            raise InvalidQueryError(f"Query too short (min {constants.QUERY_MIN_LENGTH} chars)")
        
        # Step 2: Generate query embedding
        logger.debug("Embedding query")
        try:
            query_embedding = embed_query(query, user_id)
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            raise RetrievalError(f"Cannot embed query: {str(e)}")
        
        # Step 3: Semantic search
        logger.debug(f"Executing semantic search (k={options.k})")
        retrieval_k = max(options.k * constants.SEMANTIC_K_RETRIEVAL_MULTIPLIER, 50)
        
        try:
            semantic_results = semantic_search(
                user_id=user_id,
                query_embedding=query_embedding,
                k=int(retrieval_k),
            )
        except UserIndexNotFound:
            raise
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise
        
        if not semantic_results:
            if options.return_all_matches:
                # Return empty result gracefully
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return RetrievalResult(
                    query=query,
                    results=[],
                    result_count=0,
                    covered_docs=0,
                    has_contradictions=False,
                    execution_time_ms=elapsed_ms,
                    fallback_applied=False,
                    fallback_reason="No matches found",
                    search_method="semantic",
                )
            else:
                raise NoResultsError("No semantic matches found")
        
        # Load metadata sidecar to enrich chunks
        metadata_store = load_metadata_for_user(user_id)
        chunk_id_to_meta = {e["chunk_id"]: e for e in metadata_store.get("entries", [])}

        # Convert semantic results to RetrievedChunk
        now = __import__("datetime").datetime.utcnow()
        chunks = []
        for rank, r in enumerate(semantic_results, start=1):
            meta = chunk_id_to_meta.get(r.chunk_id, {})
            uploaded_at_raw = meta.get("uploaded_at")
            try:
                from datetime import datetime as _dt
                doc_uploaded_at = _dt.fromisoformat(uploaded_at_raw.rstrip("Z")) if uploaded_at_raw else now
            except Exception:
                doc_uploaded_at = now
            chunks.append(
                RetrievedChunk(
                    chunk_id=r.chunk_id,
                    doc_id=r.doc_id,
                    doc_name=meta.get("doc_name", ""),
                    chunk_index=meta.get("chunk_index", 0),
                    text=meta.get("text") or "",
                    section=meta.get("section") or "",
                    page_number=meta.get("page_number") or 0,
                    jurisdiction=meta.get("jurisdiction") or "",
                    doc_uploaded_at=doc_uploaded_at,
                    doc_last_modified=doc_uploaded_at,
                    semantic_score=r.semantic_score,
                    keyword_score=0.0,
                    hybrid_score=r.semantic_score,
                    final_rank_score=r.semantic_score,
                    rank_position=rank,
                    retrieval_method="semantic",
                    confidence_score=r.semantic_score,
                )
            )
        
        # Step 4: Apply metadata filters
        if options.filters:
            logger.debug("Applying metadata filters")
            try:
                chunks = apply_metadata_filters(chunks, options.filters)
            except Exception as e:
                logger.warning(f"Filtering failed: {e}")
                # Continue with unfiltered results
        
        # Step 5: Detect contradictions
        if options.detect_contradictions:
            logger.debug("Detecting contradictions")
            try:
                contradictions = detect_contradictions(chunks)
                has_contradictions = len(contradictions) > 0
            except Exception as e:
                logger.warning(f"Contradiction detection failed: {e}")
                contradictions = {}
        else:
            contradictions = {}
        
        # Step 6: Rerank
        if options.rerank:
            logger.debug("Reranking chunks")
            try:
                chunks = rerank_chunks(chunks, contradictions)
            except Exception as e:
                logger.warning(f"Reranking failed: {e}")
                # Continue with un-reranked results
        
        # Step 7: Select top-K
        logger.debug(f"Selecting top {options.k}")
        final_chunks = chunks[:options.k]
        
        # Step 8: Check fallback
        if len(final_chunks) < options.k:
            if options.return_all_matches:
                fallback_applied = False
                fallback_reason = "Fewer than k results found"
            else:
                logger.warning(f"Only {len(final_chunks)} results, need {options.k}")
                try:
                    final_chunks, fallback_applied, fallback_reason = apply_fallback_strategy(
                        final_chunks,
                        chunks,
                        options.k,
                    )
                except FallbackExhaustedError as e:
                    if len(final_chunks) == 0:
                        raise NoResultsError(f"Fallback exhausted: {str(e)}")
        
        # Step 9: Format results
        covered_docs = len(set(c.doc_id for c in final_chunks))
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"Retrieval completed in {elapsed_ms:.1f}ms: "
            f"{len(final_chunks)} results, {covered_docs} docs, "
            f"contradictions={has_contradictions}, fallback={fallback_applied}"
        )
        
        return RetrievalResult(
            query=query,
            results=final_chunks,
            result_count=len(final_chunks),
            covered_docs=covered_docs,
            has_contradictions=has_contradictions,
            execution_time_ms=elapsed_ms,
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
            search_method=search_method,
        )
    
    except RetrievalError:
        raise
    except Exception as e:
        logger.error(f"Unexpected retrieval error: {e}", exc_info=True)
        raise RetrievalError(f"Unexpected error: {str(e)}")


def apply_metadata_filters(
    chunks: List[RetrievedChunk],
    filters: SearchFilter,
) -> List[RetrievedChunk]:
    """
    Filter chunks by metadata criteria (post-retrieval).
    
    Filter Priority:
    1. Jurisdictions
    2. Document names
    3. Document IDs
    4. Date range
    5. Authority levels
    6. Confidence threshold
    7. Deduplication
    
    Args:
        chunks: Pre-filtered results
        filters: SearchFilter with criteria
    
    Returns:
        Filtered chunks list
    """
    
    if not chunks:
        return []
    
    result = chunks
    
    # Jurisdiction filter
    if filters.jurisdictions:
        result = [c for c in result if c.jurisdiction in filters.jurisdictions]
    
    # Document name filter
    if filters.doc_names:
        result = [c for c in result if c.doc_name in filters.doc_names]
    
    # Document ID filter
    if filters.doc_ids:
        result = [c for c in result if c.doc_id in filters.doc_ids]
    
    # Date range filter
    if filters.date_range:
        if filters.date_range.date_from:
            result = [c for c in result if c.doc_uploaded_at >= filters.date_range.date_from]
        if filters.date_range.date_to:
            result = [c for c in result if c.doc_uploaded_at <= filters.date_range.date_to]
    
    # Authority level filter
    if filters.authority_levels:
        result = [c for c in result if c.doc_authority_level in filters.authority_levels]
    
    # Confidence threshold filter
    if filters.min_confidence > 0:
        result = [c for c in result if c.confidence_score >= filters.min_confidence]
    
    # Deduplication: max 1 per document
    if filters.exclude_overlapping:
        seen_docs = set()
        deduped = []
        for chunk in result:
            if chunk.doc_id not in seen_docs:
                deduped.append(chunk)
                seen_docs.add(chunk.doc_id)
        result = deduped
    
    logger.debug(f"Filtering: {len(chunks)} input → {len(result)} output")
    
    return result


def apply_fallback_strategy(
    current_results: List[RetrievedChunk],
    all_candidates: List[RetrievedChunk],
    target_k: int,
) -> tuple:
    """
    Handle case when <k results remain after processing.
    
    Fallback strategies (in order):
    1. Return all available (if return_all_matches allowed)
    2. Increment k to get more from candidates
    3. Return remaining above threshold
    
    Args:
        current_results: Current results (<k)
        all_candidates: All candidates before filtering
        target_k: Target number of results
    
    Returns:
        (results, fallback_applied, fallback_reason)
    """
    
    if len(current_results) < target_k:
        # Try to get more from candidates
        additional = all_candidates[len(current_results):target_k]
        if additional:
            current_results.extend(additional)
            fallback_applied = True
            fallback_reason = f"Expanded k from {len(current_results)-len(additional)} to {len(current_results)}"
        else:
            fallback_applied = True
            fallback_reason = f"Only {len(current_results)} results available (fallback to all)"
    else:
        fallback_applied = False
        fallback_reason = None
    
    return current_results, fallback_applied, fallback_reason
