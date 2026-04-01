"""
src/retrieval/semantic_search.py

FAISS cosine similarity semantic search implementation.

Functions:
    - semantic_search: Execute FAISS knn search
    - normalize_semantic_score: Convert L2 distance to [0,1]
"""

import logging
import time
from typing import List
import numpy as np

from src.embeddings import get_index, resolve_faiss_id, load_metadata_for_user
from src.retrieval.models import SemanticResult
from src.retrieval.exceptions import (
    UserIndexNotFound, SemanticSearchError, InvalidEmbeddingError, SearchTimeoutError
)
from src.retrieval import constants

logger = logging.getLogger(__name__)


def semantic_search(
    user_id: str,
    query_embedding: np.ndarray,
    k: int = constants.SEMANTIC_K_DEFAULT,
    threshold: float = constants.SEMANTIC_DISTANCE_THRESHOLD,
) -> List[SemanticResult]:
    """
    Execute FAISS cosine similarity search.
    
    FAISS IndexFlatL2 stores L2 distance.
    Conversion: cosine_sim = 1 / (1 + l2_distance)
    
    Args:
        user_id: Index owner
        query_embedding: 3072-D query vector from Module 2 embedder
        k: Number of results (default 50 for filtering, override with 7 for final)
        threshold: Max L2 distance to include
    
    Returns:
        List[SemanticResult] sorted by distance (ascending = most similar first)
    
    Raises:
        UserIndexNotFound: No index for user_id
        SemanticSearchError: FAISS search failed
        InvalidEmbeddingError: Query embedding malformed
        SearchTimeoutError: Exceeded time budget
    
    Latency: <50ms for k=50
    """
    
    start_time = time.perf_counter()
    
    try:
        # Validate embedding
        if not isinstance(query_embedding, np.ndarray):
            raise InvalidEmbeddingError("Query embedding must be numpy array")
        
        if query_embedding.shape != (3072,):
            raise InvalidEmbeddingError(
                f"Query embedding must be 3072-D, got {query_embedding.shape}"
            )
        
        if query_embedding.dtype != np.float32:
            query_embedding = query_embedding.astype(np.float32)
        
        # Reshape for FAISS (1 x 3072)
        query_embedding = query_embedding.reshape(1, -1)
        
        # Load FAISS index
        logger.debug(f"Loading FAISS index for {user_id}")
        try:
            index = get_index(user_id)
        except Exception as e:
            if "not found" in str(e).lower():
                raise UserIndexNotFound(f"No index for user {user_id}")
            raise SemanticSearchError(f"Failed to load index: {e}")
        
        # Execute search
        logger.debug(f"Searching FAISS for k={k}")
        distances, faiss_ids = index.search(query_embedding, k)
        
        # Flatten results (reshape to 1D arrays)
        distances = distances.flatten().tolist()
        faiss_ids = faiss_ids.flatten().tolist()
        
        # Load metadata for lookups
        metadata = load_metadata_for_user(user_id)
        
        # Convert to SemanticResult
        results = []
        for faiss_id, distance in zip(faiss_ids, distances):
            # Skip if -1 (placeholder when k > index size)
            if faiss_id == -1:
                continue
            
            # Skip if distance exceeds threshold
            if distance > threshold:
                logger.debug(f"Skipping faiss_id={faiss_id}, distance={distance} > {threshold}")
                continue
            
            # Resolve FAISS ID to chunk metadata
            try:
                chunk_info = resolve_faiss_id_to_chunk(metadata, faiss_id)
            except Exception as e:
                logger.warning(f"Could not resolve faiss_id {faiss_id}: {e}")
                continue
            
            # Normalize score
            semantic_score = normalize_semantic_score(distance)
            
            result = SemanticResult(
                chunk_id=chunk_info["chunk_id"],
                doc_id=chunk_info["doc_id"],
                faiss_id=faiss_id,
                l2_distance=float(distance),
                semantic_score=semantic_score,
            )
            results.append(result)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Semantic search completed in {elapsed_ms:.1f}ms, found {len(results)} results")
        
        # Check SLA
        if elapsed_ms > constants.LATENCY_SEMANTIC_SEARCH_MS * constants.LATENCY_WARNING_THRESHOLD:
            logger.warning(
                f"Semantic search latency {elapsed_ms:.1f}ms exceeds SLA "
                f"{constants.LATENCY_SEMANTIC_SEARCH_MS}ms"
            )
        
        return results
    
    except UserIndexNotFound:
        raise
    except InvalidEmbeddingError:
        raise
    except SearchTimeoutError:
        raise
    except Exception as e:
        logger.error(f"Semantic search failed: {e}", exc_info=True)
        raise SemanticSearchError(f"FAISS search failed: {str(e)}")


def normalize_semantic_score(l2_distance: float) -> float:
    """
    Convert L2 distance to [0, 1] similarity score.
    
    Formula:
        semantic_score = 1 / (1 + l2_distance)
    
    Properties:
        - Monotonic decreasing with distance
        - Range [0, 1]
        - Distance 0 → score 1.0 (identical)
        - Distance ∞ → score 0.0 (completely different)
    
    Examples:
        distance=0.1  → score=0.909
        distance=0.5  → score=0.667
        distance=1.0  → score=0.500
        distance=2.0  → score=0.333
    
    Args:
        l2_distance: L2 distance from FAISS
    
    Returns:
        float in [0, 1]
    """
    
    if l2_distance < 0:
        raise ValueError(f"L2 distance cannot be negative: {l2_distance}")
    
    score = 1.0 / (1.0 + l2_distance)
    
    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))
    
    return score


def resolve_faiss_id_to_chunk(metadata: dict, faiss_id: int) -> dict:
    """
    Resolve FAISS integer ID to chunk metadata.
    
    Args:
        metadata: Metadata dict from metadata.json
        faiss_id: FAISS integer ID (0, 1, 2, ...)
    
    Returns:
        dict with chunk_id, doc_id, etc.
    
    Raises:
        ValueError: faiss_id not found in metadata
    """
    
    entries = metadata.get("entries", [])
    
    # Build reverse lookup if not cached
    if "faiss_id_to_chunk_id" not in metadata:
        for entry in entries:
            if entry.get("faiss_id") == faiss_id:
                return entry
        raise ValueError(f"FAISS ID {faiss_id} not found in metadata")
    
    # Use cached lookup
    lookup = metadata["faiss_id_to_chunk_id"]
    chunk_id = lookup.get(str(faiss_id))
    
    if not chunk_id:
        raise ValueError(f"FAISS ID {faiss_id} not in lookup")
    
    # Find entry by chunk_id
    for entry in entries:
        if entry.get("chunk_id") == chunk_id:
            return entry
    
    raise ValueError(f"Chunk {chunk_id} not found in metadata")
