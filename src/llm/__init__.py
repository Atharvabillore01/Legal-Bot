"""
src/llm/__init__.py

Public API for the LLM Interface & Prompt Builder module (Module 4).

Aggregates all models, functions, and exceptions for external use.

Key Exports:
    Models:
        - QueryResponse: Complete structured response from LLM
        - Citation: Individual source citations
        - ConfidenceLevel: Confidence classification (LOW/MEDIUM/HIGH)
    
    Query Functions:
        - query_llm_simple: Simple wrapper for basic queries
        - LLMQueryEngine: Full-featured query orchestration
    
    Prompt Functions:
        - prepare_prompt_for_llm: End-to-end prompt preparation
        - count_tokens: Token counting utility
    
    Citation Functions:
        - build_citation_objects: Parse citations from response
        - parse_citations: Extract citation markers
    
    Confidence Functions:
        - calculate_query_confidence: Compute confidence score
        - classify_confidence_level: Assign LOW/MEDIUM/HIGH
    
    Exceptions:
        - LLMError: Base exception
        - EmptyContextError: No context provided
        - RateLimitError: API rate limited
        - All other exception types

Example Usage:
    from src.llm import query_llm_simple, QueryResponse
    
    chunks = [{"text": "...", "doc_name": "contract.pdf", ...}]
    metadata = {"chunk_0": {"doc_name": "contract.pdf", ...}}
    query = "What is the liability cap?"
    
    response = query_llm_simple(chunks, query, metadata)
    print(response.answer)
    print(f"Confidence: {response.confidence_level}")
    for citation in response.citations:
        print(f"- {citation.source_doc}, p.{citation.page_number}")
"""

# ============================================================================
# DATA MODELS
# ============================================================================

from .models import (
    Citation,
    SourceMetadata,
    ConfidenceLevel,
    QueryResponse
)

# ============================================================================
# LLM QUERY FUNCTIONS
# ============================================================================

from .llm_interface import (
    LLMQueryEngine,
    query_llm_simple
)

# ============================================================================
# PROMPT BUILDING FUNCTIONS
# ============================================================================

from .prompt_builder import (
    build_system_prompt,
    build_context_prompt,
    build_instruction_prompt,
    construct_full_prompt,
    allocate_token_budget,
    prepare_prompt_for_llm,
    count_tokens
)

# ============================================================================
# CITATION FUNCTIONS
# ============================================================================

from .citation_parser import (
    parse_citations,
    find_citation_offsets,
    extract_cited_text,
    map_citations_to_sources,
    build_citation_objects,
    clean_response_citations,
    validate_citations_in_chunks
)

# ============================================================================
# CONFIDENCE SCORING FUNCTIONS
# ============================================================================

from .confidence_scorer import (
    normalize_l2_distance,
    calculate_base_confidence,
    adjust_confidence_for_contradictions,
    adjust_confidence_for_authority,
    adjust_confidence_for_recency,
    calculate_query_confidence,
    classify_confidence_level,
    create_confidence_level_object,
    is_sufficient_confidence,
    score_variance,
    confidence_summary
)

# ============================================================================
# EXCEPTIONS
# ============================================================================

from .exceptions import (
    # Base exception
    LLMError,
    
    # Prompt errors
    PromptError,
    PromptTemplateError,
    PromptVariableError,
    PromptFormatError,
    ChunkFormatError,
    
    # Token errors
    TokenError,
    TokenCountError,
    TokenBudgetExceededError,
    TokenAllocationError,
    TokenizerInitError,
    
    # Completion errors
    CompletionError,
    APIError,
    RateLimitError,
    AuthenticationError,
    ModelNotFoundError,
    CompletionTimeoutError,
    ResponseParseError,
    
    # Citation errors
    CitationError,
    CitationParseError,
    CitationMappingError,
    CitationValidationError,
    OffsetCalculationError,
    
    # Context errors
    ContextError,
    ContextLengthError,
    MetadataLookupError,
    ChunkRetrievalError,
    EmptyContextError,
    
    # Config errors
    ConfigError,
    InvalidConfigError,
    MissingEnvironmentError,
    DeprecatedConfigError
)

# ============================================================================
# CONFIGURATION CONSTANTS (Advanced usage)
# ============================================================================

from .constants import (
    GPT_MODEL,
    GPT_MODEL_FALLBACK,
    MODEL_TEMPERATURE,
    MAX_CONTEXT_TOKENS,
    TOKEN_ALLOCATION_SYSTEM_PERCENT,
    TOKEN_ALLOCATION_CONTEXT_PERCENT,
    TOKEN_ALLOCATION_QUERY_PERCENT,
    TOKEN_ALLOCATION_RESPONSE_PERCENT,
    CONFIDENCE_THRESHOLD_LOW,
    CONFIDENCE_THRESHOLD_MEDIUM,
    CONFIDENCE_LEVELS,
    CITATION_MARKER_PATTERN,
    MAX_API_RETRIES,
    RETRY_BACKOFF_INITIAL,
    FEATURE_CITATIONS,
    FEATURE_EXPONENTIAL_BACKOFF
)

# ============================================================================
# VERSION
# ============================================================================

__version__ = "1.0.0"

# ============================================================================
# PUBLIC API - All public symbols
# ============================================================================

__all__ = [
    # Models
    "Citation",
    "SourceMetadata",
    "ConfidenceLevel",
    "QueryResponse",
    
    # Query functions (primary user-facing)
    "LLMQueryEngine",
    "query_llm_simple",
    
    # Prompt functions
    "build_system_prompt",
    "build_context_prompt",
    "build_instruction_prompt",
    "construct_full_prompt",
    "allocate_token_budget",
    "prepare_prompt_for_llm",
    "count_tokens",
    
    # Citation functions
    "parse_citations",
    "find_citation_offsets",
    "extract_cited_text",
    "map_citations_to_sources",
    "build_citation_objects",
    "clean_response_citations",
    "validate_citations_in_chunks",
    
    # Confidence functions
    "normalize_l2_distance",
    "calculate_base_confidence",
    "adjust_confidence_for_contradictions",
    "adjust_confidence_for_authority",
    "adjust_confidence_for_recency",
    "calculate_query_confidence",
    "classify_confidence_level",
    "create_confidence_level_object",
    "is_sufficient_confidence",
    "score_variance",
    "confidence_summary",
    
    # Exceptions (all of them)
    "LLMError",
    "PromptError",
    "PromptTemplateError",
    "PromptVariableError",
    "PromptFormatError",
    "ChunkFormatError",
    "TokenError",
    "TokenCountError",
    "TokenBudgetExceededError",
    "TokenAllocationError",
    "TokenizerInitError",
    "CompletionError",
    "APIError",
    "RateLimitError",
    "AuthenticationError",
    "ModelNotFoundError",
    "CompletionTimeoutError",
    "ResponseParseError",
    "CitationError",
    "CitationParseError",
    "CitationMappingError",
    "CitationValidationError",
    "OffsetCalculationError",
    "ContextError",
    "ContextLengthError",
    "MetadataLookupError",
    "ChunkRetrievalError",
    "EmptyContextError",
    "ConfigError",
    "InvalidConfigError",
    "MissingEnvironmentError",
    "DeprecatedConfigError",
    
    # Constants
    "GPT_MODEL",
    "GPT_MODEL_FALLBACK",
    "MODEL_TEMPERATURE",
    "MAX_CONTEXT_TOKENS",
    "CONFIDENCE_THRESHOLD_LOW",
    "CONFIDENCE_THRESHOLD_MEDIUM",
    "CONFIDENCE_LEVELS",
]
