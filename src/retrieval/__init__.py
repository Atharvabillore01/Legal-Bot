"""
src/retrieval/__init__.py

Public API for the Retrieval & Reranking module.

Aggregates all models, functions, and exceptions for easy import.

Usage:
    from src.retrieval import retrieve_and_rerank, SearchOptions, RetrievedChunk
    
    result = retrieve_and_rerank(
        user_id="user_123",
        query="liability caps",
        options=SearchOptions(k=7, detect_contradictions=True)
    )
    
    for chunk in result.results:
        print(f"{chunk.rank_position}. {chunk.final_rank_score:.1%}: {chunk.text[:50]}")
"""

# Models
from src.retrieval.models import (
    RetrievedChunk,
    ContradictionInfo,
    SearchFilter,
    DateRange,
    SearchOptions,
    RetrievalResult,
    SemanticResult,
    KeywordResult,
    HybridResult,
    ExtractedValues,
    ContradictionScore,
)

# Functions
from src.retrieval.retriever import (
    retrieve_and_rerank,
    apply_metadata_filters,
    apply_fallback_strategy,
)

from src.retrieval.semantic_search import (
    semantic_search,
    normalize_semantic_score,
)

from src.retrieval.contradiction_detector import (
    detect_contradictions,
    extract_clause_names,
    extract_values,
    score_contradiction,
)

from src.retrieval.reranker import (
    rerank_chunks,
    compute_conflict_penalty,
    compute_authority_boost,
    compute_recency_boost,
    compute_uniqueness_boost,
)

# Exceptions
from src.retrieval.exceptions import (
    RetrievalError,
    InvalidQueryError,
    InvalidFilterError,
    InvalidSearchOptionsError,
    UserIndexNotFound,
    CorruptedIndexError,
    MetadataError,
    MetadataOutOfSyncError,
    SemanticSearchError,
    InvalidEmbeddingError,
    KeywordSearchError,
    BM25IndexNotFoundError,
    SearchTimeoutError,
    SearchCancelledError,
    RerankerError,
    ContradictionDetectionError,
    ValueExtractionError,
    ClauseMatchingError,
    FilteringError,
    NoResultsError,
    AllResultsFilteredError,
    FallbackExhaustedError,
    is_retrieval_error,
    categorize_error,
)

# Constants
from src.retrieval import constants

__all__ = [
    # Models
    "RetrievedChunk",
    "ContradictionInfo",
    "SearchFilter",
    "DateRange",
    "SearchOptions",
    "RetrievalResult",
    "SemanticResult",
    "KeywordResult",
    "HybridResult",
    "ExtractedValues",
    "ContradictionScore",
    # Functions
    "retrieve_and_rerank",
    "apply_metadata_filters",
    "apply_fallback_strategy",
    "semantic_search",
    "normalize_semantic_score",
    "detect_contradictions",
    "extract_clause_names",
    "extract_values",
    "score_contradiction",
    "rerank_chunks",
    "compute_conflict_penalty",
    "compute_authority_boost",
    "compute_recency_boost",
    "compute_uniqueness_boost",
    # Exceptions
    "RetrievalError",
    "InvalidQueryError",
    "InvalidFilterError",
    "InvalidSearchOptionsError",
    "UserIndexNotFound",
    "CorruptedIndexError",
    "MetadataError",
    "MetadataOutOfSyncError",
    "SemanticSearchError",
    "InvalidEmbeddingError",
    "KeywordSearchError",
    "BM25IndexNotFoundError",
    "SearchTimeoutError",
    "SearchCancelledError",
    "RerankerError",
    "ContradictionDetectionError",
    "ValueExtractionError",
    "ClauseMatchingError",
    "FilteringError",
    "NoResultsError",
    "AllResultsFilteredError",
    "FallbackExhaustedError",
    "is_retrieval_error",
    "categorize_error",
    # Constants
    "constants",
]

__version__ = "1.0.0"
__author__ = "Legal RAG System"
