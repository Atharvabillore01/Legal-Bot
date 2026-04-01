"""
Vector search and retrieval from FAISS indices.
"""

import logging
from typing import List, Optional
import numpy as np

from .models import RetrievalResult, EmbeddedChunk
from .metadata import load_metadata
from .indexer import search_index
from .embedder import embed_query
from .concurrency import read_lock
from .exceptions import IndexNotFoundError, EmbeddingError
from .constants import DEFAULT_K, MAX_K, DEFAULT_DISTANCE_THRESHOLD

logger = logging.getLogger(__name__)


def retrieve(
    user_id: str,
    query: str,
    k: int = DEFAULT_K,
    threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> List[RetrievalResult]:
    """
    Retrieve semantically similar chunks for query.
    
    Args:
        user_id: Index owner
        query: Query string
        k: Number of results
        threshold: Max L2 distance (lower = more similar)
    
    Returns:
        List[RetrievalResult]: Ranked chunks with similarity scores
    
    Raises:
        IndexNotFoundError: User's index does not exist
        EmbeddingError: Cannot embed query
    
    Process:
        1. Embed query using embed_query()
        2. Search FAISS index: index.search()
        3. Look up metadata for each result
        4. Rank by similarity
        5. Apply threshold filter
        6. Return RetrievalResult objects
    """
    if k < 1 or k > MAX_K:
        raise ValueError(f"k must be in range [1, {MAX_K}]")
    
    logger.debug(f"Retrieving {k} results for query: {query[:50]}...")
    
    # Embed query
    try:
        query_embedding = embed_query(query, user_id)
    except EmbeddingError as e:
        logger.error(f"Failed to embed query: {e}")
        raise
    
    # Acquire read lock
    with read_lock(user_id):
        # Search FAISS index
        try:
            results = search_index(
                user_id,
                query_embedding,
                k=k,
                threshold=threshold,
            )
        except IndexNotFoundError as e:
            logger.error(f"Index not found for user {user_id}")
            raise
        
        # Load metadata
        try:
            metadata = load_metadata(user_id)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            raise
        
        # Build lookup: faiss_id → metadata entry
        faiss_id_to_entry = {
            entry["faiss_id"]: entry
            for entry in metadata.get("entries", [])
        }
        
        # Convert search results to RetrievalResult
        retrieval_results = []
        for faiss_id, distance in results:
            if faiss_id not in faiss_id_to_entry:
                logger.warning(f"Metadata missing for FAISS ID {faiss_id}")
                continue
            
            entry = faiss_id_to_entry[faiss_id]
            
            # Normalize distance to similarity score
            # L2 distance -> similarity: higher similarity = lower distance
            # Approximate: similarity = exp(-distance/10)
            similarity_score = max(0.0, 1.0 / (1.0 + distance))
            
            result = RetrievalResult(
                chunk_id=entry["chunk_id"],
                text=entry.get("text", ""),  # Not in metadata, need to fetch
                doc_name=entry["doc_name"],
                doc_id=entry["doc_id"],
                chunk_index=entry["chunk_index"],
                page_number=entry.get("page_number"),
                section=entry.get("section"),
                jurisdiction=entry.get("jurisdiction"),
                distance=distance,
                similarity_score=similarity_score,
                token_count=entry["token_count"],
                has_ocr=entry.get("has_ocr", False),
            )
            retrieval_results.append(result)
        
        logger.info(
            f"Retrieved {len(retrieval_results)} results for user {user_id}"
        )
        
        return retrieval_results


def retrieve_with_reranking(
    user_id: str,
    query: str,
    k_initial: int = 50,
    k_final: int = DEFAULT_K,
) -> List[RetrievalResult]:
    """
    Retrieve with optional semantic re-ranking.
    
    Process:
        1. Get k_initial results from FAISS (fast)
        2. [OPTIONAL] Re-rank with cross-encoder (slower, more accurate)
        3. Return top k_final
    
    Args:
        user_id: Index owner
        query: Query string
        k_initial: Initial retrieval count
        k_final: Final result count
    
    Returns:
        List[RetrievalResult]: Top k_final ranked results
    
    Note:
        Future: Implement cross-encoder re-ranking for accuracy improvement.
    """
    # Get initial results
    results = retrieve(user_id, query, k=k_initial)
    
    # TODO: Re-rank with cross-encoder if available
    # For now, just return top k_final
    
    return results[:k_final]


def batch_retrieve(
    user_id: str,
    queries: List[str],
    k: int = DEFAULT_K,
) -> List[List[RetrievalResult]]:
    """
    Retrieve results for multiple queries.
    
    Args:
        user_id: Index owner
        queries: List of query strings
        k: Results per query
    
    Returns:
        List[List[RetrievalResult]]: Results for each query
    """
    results_per_query = []
    
    for query in queries:
        try:
            results = retrieve(user_id, query, k=k)
            results_per_query.append(results)
        except Exception as e:
            logger.warning(f"Failed to retrieve for query '{query}': {e}")
            results_per_query.append([])
    
    return results_per_query
