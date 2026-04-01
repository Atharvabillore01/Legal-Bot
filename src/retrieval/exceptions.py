"""
src/retrieval/exceptions.py

Exception hierarchy for the retrieval and reranking module.

All exceptions inherit from RetrievalError base class.
Organized into 5 families:
    - Input Errors: User/query validation
    - Index Errors: FAISS index issues
    - Search Errors: Semantic or keyword search failures
    - Processing Errors: Reranking, contradiction detection
    - Fallback Errors: Recovery strategy failures
"""


class RetrievalError(Exception):
    """Base exception for retrieval module."""
    pass


# ============================================================
# INPUT/USER VALIDATION ERRORS
# ============================================================

class InvalidQueryError(RetrievalError):
    """
    Query is empty, too long, or malformed.
    
    Raised when:
        - query is empty string
        - query exceeds 1000 characters
        - query has <1 or >128 tokens
        - query is only punctuation/numbers
    """
    pass


class InvalidFilterError(RetrievalError):
    """
    Filter specification is invalid.
    
    Raised when:
        - SearchFilter dates are invalid (date_to < date_from)
        - Unknown jurisdiction/authority values
        - Filter criteria are contradictory
    """
    pass


class InvalidSearchOptionsError(RetrievalError):
    """
    SearchOptions contains invalid values.
    
    Raised when:
        - k is not 1-50
        - alpha is not 0-1
        - Both use_semantic and use_keyword are False
    """
    pass


# ============================================================
# INDEX/DATA ERRORS
# ============================================================

class UserIndexNotFound(RetrievalError):
    """
    User has no FAISS index.
    
    Means:
        - User_id not in /indexes/ directory
        - Module 2 (embeddings) not yet run
        - Index was deleted
    
    Recovery:
        - User must ingest documents (Module 1) and create embeddings (Module 2)
    """
    pass


class CorruptedIndexError(RetrievalError):
    """
    FAISS index is corrupted or incomplete.
    
    Indicates:
        - index.faiss file is corrupted
        - Index cannot be loaded by FAISS library
        - Index has incorrect dimensions
    
    Recovery:
        - Recover from backup via recover_from_backup()
        - Or re-create index from scratch
    """
    pass


class MetadataError(RetrievalError):
    """
    Metadata sidecar is missing or malformed.
    
    Indicates:
        - metadata.json not found
        - metadata.json is invalid JSON
        - metadata.json is out of sync with FAISS index
    
    Recovery:
        - Recover from backup
        - Or rebuild metadata from index
    """
    pass


class MetadataOutOfSyncError(RetrievalError):
    """
    Metadata does not match FAISS index.
    
    Indicates:
        - FAISS contains IDs not in metadata
        - Metadata contains IDs not in FAISS
        - Chunk count mismatch
    """
    pass


# ============================================================
# SEARCH ERRORS
# ============================================================

class SemanticSearchError(RetrievalError):
    """
    FAISS semantic search failed.
    
    Causes:
        - Invalid query embedding
        - FAISS index corruption
        - Out of memory
    """
    pass


class InvalidEmbeddingError(RetrievalError):
    """Query embedding is malformed."""
    pass


class KeywordSearchError(RetrievalError):
    """
    BM25 keyword search failed.
    
    Causes:
        - BM25 index not found
        - Query tokenization failed
        - Out of memory
    """
    pass


class BM25IndexNotFoundError(RetrievalError):
    """BM25 index not built for user."""
    pass


class SearchTimeoutError(RetrievalError):
    """
    Search exceeded time budget (>200ms).
    
    Indicates:
        - FAISS search took too long
        - BM25 search took too long
        - Network latency
    
    Recovery:
        - Auto-fallback to reduce k (fewer results, faster)
        - Retry with longer timeout if configured
    """
    pass


class SearchCancelledError(RetrievalError):
    """Search was cancelled by user or system."""
    pass


# ============================================================
# PROCESSING ERRORS
# ============================================================

class RerankerError(RetrievalError):
    """
    Reranking failed.
    
    Causes:
        - Metadata missing for reranking
        - Invalid score values
        - Computation overflow
    """
    pass


class ContradictionDetectionError(RetrievalError):
    """
    Contradiction detection failed.
    
    Causes:
        - NLP parsing error
        - Value extraction failed
        - Out of memory
    """
    pass


class ValueExtractionError(RetrievalError):
    """Failed to extract values from chunk text."""
    pass


class ClauseMatchingError(RetrievalError):
    """Failed to match clauses between chunks."""
    pass


class FilteringError(RetrievalError):
    """
    Metadata filtering failed.
    
    Causes:
        - Jurisdiction lookup error
        - Date parsing error
        - All results filtered out
    """
    pass


# ============================================================
# FALLBACK/RECOVERY ERRORS
# ============================================================

class NoResultsError(RetrievalError):
    """
    No results found after all fallback strategies.
    
    Means:
        - Query matches 0 chunks
        - All matching chunks filtered out
        - Fallback strategies exhausted
    
    Recovery:
        - Broaden query
        - Relax filters
        - Check if index has documents
    """
    pass


class AllResultsFilteredError(RetrievalError):
    """All results removed by filters; fallback failed."""
    pass


class FallbackExhaustedError(RetrievalError):
    """
    All fallback strategies were attempted; no recovery possible.
    
    Sequence attempted:
        1. Return all results (even <k)
        2. Relax date filter
        3. Relax authority filter
        4. Relax jurisdiction filter
        5. Disable deduplication
        6. Lower confidence threshold
        7. Fall back to semantic-only (if hybrid)
    """
    pass


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def is_retrieval_error(exc: Exception) -> bool:
    """Check if exception is RetrievalError or subclass."""
    return isinstance(exc, RetrievalError)


def categorize_error(exc: Exception) -> str:
    """
    Categorize error type for logging/monitoring.
    
    Returns:
        - "input_validation"
        - "index"
        - "search"
        - "processing"
        - "fallback"
        - "unknown"
    """
    if isinstance(exc, (InvalidQueryError, InvalidFilterError, InvalidSearchOptionsError)):
        return "input_validation"
    elif isinstance(exc, (UserIndexNotFound, CorruptedIndexError, MetadataError)):
        return "index"
    elif isinstance(exc, (SemanticSearchError, KeywordSearchError, SearchTimeoutError)):
        return "search"
    elif isinstance(exc, (RerankerError, ContradictionDetectionError, FilteringError)):
        return "processing"
    elif isinstance(exc, (NoResultsError, FallbackExhaustedError)):
        return "fallback"
    else:
        return "unknown"
