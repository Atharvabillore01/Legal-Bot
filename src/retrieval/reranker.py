"""
src/retrieval/reranker.py

Intelligent reranking of retrieved chunks based on contradictions, authority, and recency.

Functions:
    - rerank_chunks: Main reranking orchestrator
    - compute_conflict_penalty: Adjust for contradictions
    - compute_authority_boost: Boost binding/precedent documents
    - compute_recency_boost: Boost recent documents
    - compute_uniqueness_boost: Boost sole results from documents
    - apply_reranking_adjustments: Compute final scores
"""

import logging
from typing import List, Dict
from datetime import datetime, timedelta

from src.retrieval.models import RetrievedChunk, ContradictionInfo
from src.retrieval.exceptions import RerankerError
from src.retrieval import constants

logger = logging.getLogger(__name__)


def rerank_chunks(
    chunks: List[RetrievedChunk],
    contradictions: Dict[str, ContradictionInfo],
) -> List[RetrievedChunk]:
    """
    Adjust scores based on contradictions, authority, and recency.
    
    Reranking pipeline:
    1. Conflict penalty: Reduce scores for chunks with contradictions
    2. Authority boost: Increase scores for binding/precedent docs
    3. Recency boost: Increase scores for recent documents
    4. Uniqueness boost: Increase scores for sole results from document
    5. Final computation: Multiply adjustments together
    
    Args:
        chunks: Pre-ranked chunks with base scores (hybrid_score)
        contradictions: Dict of detected contradictions
    
    Returns:
        List[RetrievedChunk] with updated final_rank_score and reranked_at
    
    Latency: <30ms for 50 chunks
    """
    
    if not chunks:
        return []
    
    try:
        # Build contradiction map: chunk_id → list of conflicts
        chunk_conflicts = {}
        for pair_key, contradiction_info in contradictions.items():
            chunk_ids = pair_key.split("|")
            for chunk_id in chunk_ids:
                if chunk_id not in chunk_conflicts:
                    chunk_conflicts[chunk_id] = []
                chunk_conflicts[chunk_id].append(contradiction_info)
        
        # Build doc coverage map: doc_id → chunk count
        doc_chunk_counts = {}
        for chunk in chunks:
            if chunk.doc_id not in doc_chunk_counts:
                doc_chunk_counts[chunk.doc_id] = 0
            doc_chunk_counts[chunk.doc_id] += 1
        
        # Apply reranking to each chunk
        for rank_pos, chunk in enumerate(chunks, 1):
            # Get base score
            base_score = chunk.hybrid_score if chunk.hybrid_score > 0 else chunk.semantic_score
            
            # Stage 1: Conflict penalty
            conflict_penalty = compute_conflict_penalty(chunk.chunk_id, chunk_conflicts)
            
            # Stage 2: Authority boost
            authority_boost = compute_authority_boost(chunk.doc_authority_level)
            
            # Stage 3: Recency boost
            recency_boost = compute_recency_boost(chunk.doc_last_modified)
            
            # Stage 4: Uniqueness boost
            uniqueness_boost = compute_uniqueness_boost(
                chunk.doc_id,
                doc_chunk_counts[chunk.doc_id]
            )
            
            # Stage 5: Final computation
            final_score = base_score * conflict_penalty * (1.0 + authority_boost + recency_boost + uniqueness_boost)
            final_score = min(1.0, max(0.0, final_score))  # Clamp to [0, 1]
            
            # Update chunk
            chunk.final_rank_score = final_score
            chunk.rank_position = rank_pos
            chunk.reranked_at = datetime.utcnow()
            
            # Update contradiction list
            if chunk.chunk_id in chunk_conflicts:
                chunk.has_contradictions = True
                chunk.contradictions = chunk_conflicts[chunk.chunk_id]
                
                # Compute max severity among conflicts
                severities = [c.severity for c in chunk.contradictions]
                if "high" in severities:
                    chunk.conflict_severity = "high"
                elif "medium" in severities:
                    chunk.conflict_severity = "medium"
                else:
                    chunk.conflict_severity = "low"
            
            logger.debug(
                f"Reranked {chunk.chunk_id}: "
                f"base={base_score:.3f}, "
                f"penalty={conflict_penalty:.2f}, "
                f"auth_boost={authority_boost:.2f}, "
                f"recency={recency_boost:.2f}, "
                f"unique={uniqueness_boost:.2f} "
                f"→ final={final_score:.3f}"
            )
        
        # Re-sort by final score
        chunks.sort(key=lambda c: c.final_rank_score, reverse=True)
        
        # Update rank positions after sort
        for pos, chunk in enumerate(chunks, 1):
            chunk.rank_position = pos
        
        logger.info(f"Reranked {len(chunks)} chunks successfully")
        return chunks
    
    except Exception as e:
        logger.error(f"Reranking failed: {e}", exc_info=True)
        raise RerankerError(f"Reranking failed: {str(e)}")


def compute_conflict_penalty(
    chunk_id: str,
    chunk_conflicts: Dict[str, List[ContradictionInfo]],
) -> float:
    """
    Compute penalty for chunks with contradictions.
    
    Each conflict reduces score by up to 15% based on severity:
    - low: -5%
    - medium: -10%
    - high: -15%
    
    Formula:
        penalty = 1.0 - Σ(severity_weight for each conflict)
    
    Args:
        chunk_id: Chunk ID
        chunk_conflicts: Map of chunk_id → contradictions
    
    Returns:
        float in [0, 1] to multiply with base score
    
    Example:
        No conflicts: penalty = 1.0
        1 medium conflict: penalty = 1.0 - 0.10 = 0.90
        2 high conflicts: penalty = 1.0 - 0.15 - 0.15 = 0.70
    """
    
    if chunk_id not in chunk_conflicts:
        return 1.0
    
    conflicts = chunk_conflicts[chunk_id]
    
    penalty_reduction = 0.0
    for conflict in conflicts:
        if conflict.severity == "high":
            penalty_reduction += constants.RERANK_CONFLICT_PENALTY_PER_ISSUE
        elif conflict.severity == "medium":
            penalty_reduction += constants.RERANK_CONFLICT_PENALTY_PER_ISSUE * 0.67
        elif conflict.severity == "low":
            penalty_reduction += constants.RERANK_CONFLICT_PENALTY_PER_ISSUE * 0.33
    
    # Clamp to [0, 1]
    penalty = max(0.0, 1.0 - penalty_reduction)
    return penalty


def compute_authority_boost(authority_level: str) -> float:
    """
    Boost for binding and precedent documents.
    
    Levels:
    - binding: +10%
    - precedent: +5%
    - reference: +0%
    
    Args:
        authority_level: "binding", "precedent", or "reference"
    
    Returns:
        float in [0, 0.10] to add to multiplier
    """
    
    if authority_level == "binding":
        return constants.RERANK_AUTHORITY_BONUS_BINDING
    elif authority_level == "precedent":
        return constants.RERANK_AUTHORITY_BONUS_PRECEDENT
    else:
        return constants.RERANK_AUTHORITY_BONUS_REFERENCE


def compute_recency_boost(doc_last_modified: datetime) -> float:
    """
    Boost for recent documents.
    
    Linear decay over 1 year:
    - <1 year old: +10% down to +0%
    - >1 year old: 0%
    
    Formula:
        boost = max(0, (365 - age_days) / 3650)
    
    Examples:
        0 days old: boost = 365/3650 = 0.10 (+10%)
        91 days old: boost = 274/3650 = 0.075 (+7.5%)
        365 days old: boost = 0/3650 = 0.0
        730 days old: boost = 0.0 (clamped)
    
    Args:
        doc_last_modified: Document modification timestamp
    
    Returns:
        float in [0, 0.10]
    """
    
    from datetime import timezone

    now = datetime.now(timezone.utc)

    # Ensure doc_last_modified is timezone-aware
    if doc_last_modified.tzinfo is None:
        doc_last_modified = doc_last_modified.replace(tzinfo=timezone.utc)

    age_days = (now - doc_last_modified).days
    boost = max(0.0, (constants.RERANK_RECENCY_DECAY_DAYS - age_days) / (constants.RERANK_RECENCY_DECAY_DAYS * 10))
    return boost


def compute_uniqueness_boost(doc_id: str, chunk_count_in_results: int) -> float:
    """
    Boost for chunks that are the sole result from their document.
    
    If a document has only 1 chunk in results, it gets a small boost for diversity.
    
    Args:
        doc_id: Document ID
        chunk_count_in_results: How many chunks from this doc in results
    
    Returns:
        float: +5% if sole chunk, 0% otherwise
    """
    
    if chunk_count_in_results == 1:
        return constants.RERANK_UNIQUENESS_BONUS
    else:
        return 0.0


def apply_reranking_adjustments(
    chunks: List[RetrievedChunk],
) -> List[RetrievedChunk]:
    """
    High-level function to apply all reranking adjustments.
    
    Wrapper that calls rerank_chunks with empty contradictions
    (useful if contradiction detection is disabled).
    
    Args:
        chunks: Chunks to rerank
    
    Returns:
        Reranked chunks
    """
    
    return rerank_chunks(chunks, contradictions={})
