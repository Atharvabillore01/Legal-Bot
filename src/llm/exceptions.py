"""
src/llm/exceptions.py

Exception hierarchy for the LLM interface and prompt builder module.

All exceptions inherit from LLMError base class.
Organized into 6 error families:
    - PromptError: Prompt construction and validation failures
    - TokenError: Token counting and budget issues
    - CompletionError: LLM API and response generation failures
    - CitationError: Citation parsing and validation failures
    - ContextError: Context length and formatting failures
    - ConfigError: Configuration validation failures
"""

from typing import Optional


class LLMError(Exception):
    """
    Base exception for all LLM interface module errors.
    
    Provides common error handling and logging capabilities.
    All specific errors inherit from this base class.
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[dict] = None):
        """
        Initialize LLMError.
        
        Args:
            message (str): Human-readable error message
            error_code (str, optional): Machine-readable error code (e.g., "PROMPT_001")
            details (dict, optional): Additional error context
        """
        self.message = message
        self.error_code = error_code or "GENERIC"
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for logging."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


# ============================================================================
# PROMPT ERRORS (Template construction, variable substitution, formatting)
# ============================================================================

class PromptError(LLMError):
    """Base exception for prompt construction errors."""
    pass


class PromptTemplateError(PromptError):
    """Error in prompt template structure or missing required fields."""
    
    def __init__(self, message: str, missing_fields: Optional[list] = None):
        super().__init__(message, error_code="PROMPT_001")
        self.missing_fields = missing_fields or []


class PromptVariableError(PromptError):
    """Error in variable substitution or placeholder resolution."""
    
    def __init__(self, message: str, variable_name: Optional[str] = None):
        super().__init__(message, error_code="PROMPT_002")
        self.variable_name = variable_name


class PromptFormatError(PromptError):
    """Error in prompt formatting or structure validation."""
    pass


class ChunkFormatError(PromptError):
    """Error in formatting individual chunks into prompt."""
    
    def __init__(self, message: str, chunk_id: Optional[str] = None):
        super().__init__(message, error_code="PROMPT_003")
        self.chunk_id = chunk_id


# ============================================================================
# TOKEN ERRORS (Token counting, budget allocation, overflow)
# ============================================================================

class TokenError(LLMError):
    """Base exception for token-related errors."""
    pass


class TokenCountError(TokenError):
    """Error in token counting or estimation."""
    
    def __init__(self, message: str, text_length: Optional[int] = None):
        super().__init__(message, error_code="TOKEN_001")
        self.text_length = text_length


class TokenBudgetExceededError(TokenError):
    """Total tokens exceed maximum context length (128K)."""
    
    def __init__(self, message: str, requested_tokens: int, max_tokens: int):
        super().__init__(message, error_code="TOKEN_002")
        self.requested_tokens = requested_tokens
        self.max_tokens = max_tokens
        self.excess_tokens = requested_tokens - max_tokens


class TokenAllocationError(TokenError):
    """Error in token budget allocation across components."""
    
    def __init__(self, message: str, allocation: Optional[dict] = None):
        super().__init__(message, error_code="TOKEN_003")
        self.allocation = allocation or {}


class TokenizerInitError(TokenError):
    """Error initializing tokenizer (e.g., tiktoken not available)."""
    pass


# ============================================================================
# COMPLETION ERRORS (LLM API calls, response generation)
# ============================================================================

class CompletionError(LLMError):
    """Base exception for LLM API and completion errors."""
    pass


class APIError(CompletionError):
    """General OpenAI API error."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, api_error: Optional[Exception] = None):
        super().__init__(message, error_code="API_001")
        self.status_code = status_code
        self.api_error = api_error


class RateLimitError(CompletionError):
    """OpenAI API rate limit exceeded."""
    
    def __init__(self, message: str, retry_after_seconds: int = 60):
        super().__init__(message, error_code="API_002")
        self.retry_after_seconds = retry_after_seconds


class AuthenticationError(CompletionError):
    """OpenAI API authentication failed (invalid key, quota exceeded)."""
    
    def __init__(self, message: str):
        super().__init__(message, error_code="API_003")


class ModelNotFoundError(CompletionError):
    """Requested model (e.g., gpt-4o) is not available."""
    
    def __init__(self, message: str, model_name: str):
        super().__init__(message, error_code="API_004")
        self.model_name = model_name


class CompletionTimeoutError(CompletionError):
    """LLM API call timed out."""
    
    def __init__(self, message: str, timeout_seconds: float):
        super().__init__(message, error_code="API_005")
        self.timeout_seconds = timeout_seconds


class ResponseParseError(CompletionError):
    """Error parsing LLM response JSON."""
    
    def __init__(self, message: str, raw_response: Optional[str] = None):
        super().__init__(message, error_code="API_006")
        self.raw_response = raw_response[:500] if raw_response else None  # Truncate for logging


# ============================================================================
# CITATION ERRORS (Citation extraction, parsing, validation)
# ============================================================================

class CitationError(LLMError):
    """Base exception for citation-related errors."""
    pass


class CitationParseError(CitationError):
    """Error extracting [[CITE:...]] markers from response."""
    
    def __init__(self, message: str, unparseable_text: Optional[str] = None):
        super().__init__(message, error_code="CITE_001")
        self.unparseable_text = unparseable_text


class CitationMappingError(CitationError):
    """Error mapping chunk_id to source metadata."""
    
    def __init__(self, message: str, chunk_id: Optional[str] = None):
        super().__init__(message, error_code="CITE_002")
        self.chunk_id = chunk_id


class CitationValidationError(CitationError):
    """Citation validation failed (invalid format, missing fields)."""
    
    def __init__(self, message: str, citation_data: Optional[dict] = None):
        super().__init__(message, error_code="CITE_003")
        self.citation_data = citation_data


class OffsetCalculationError(CitationError):
    """Error calculating character offsets for citations."""
    
    def __init__(self, message: str, text_length: Optional[int] = None):
        super().__init__(message, error_code="CITE_004")
        self.text_length = text_length


# ============================================================================
# CONTEXT ERRORS (Context length, chunk formatting, metadata)
# ============================================================================

class ContextError(LLMError):
    """Base exception for context-related errors."""
    pass


class ContextLengthError(ContextError):
    """Context exceeds maximum length and cannot be truncated safely."""
    
    def __init__(self, message: str, context_tokens: int, max_tokens: int):
        super().__init__(message, error_code="CONTEXT_001")
        self.context_tokens = context_tokens
        self.max_tokens = max_tokens


class MetadataLookupError(ContextError):
    """Error looking up chunk metadata from Module 2."""
    
    def __init__(self, message: str, chunk_id: Optional[str] = None):
        super().__init__(message, error_code="CONTEXT_002")
        self.chunk_id = chunk_id


class ChunkRetrievalError(ContextError):
    """Error retrieving chunks from Module 3."""
    
    def __init__(self, message: str, query: Optional[str] = None):
        super().__init__(message, error_code="CONTEXT_003")
        self.query = query


class EmptyContextError(ContextError):
    """No context chunks available (Module 3 returned empty results)."""
    
    def __init__(self, message: str = "No relevant context found for query"):
        super().__init__(message, error_code="CONTEXT_004")


# ============================================================================
# CONFIG ERRORS (Configuration validation and initialization)
# ============================================================================

class ConfigError(LLMError):
    """Base exception for configuration errors."""
    pass


class InvalidConfigError(ConfigError):
    """Invalid configuration parameter."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, config_value: Optional[str] = None):
        super().__init__(message, error_code="CONFIG_001")
        self.config_key = config_key
        self.config_value = config_value


class MissingEnvironmentError(ConfigError):
    """Required environment variable not set."""
    
    def __init__(self, message: str, env_var: str):
        super().__init__(message, error_code="CONFIG_002")
        self.env_var = env_var


class DeprecatedConfigError(ConfigError):
    """Deprecated configuration parameter used."""
    
    def __init__(self, message: str, deprecated_key: str, replacement: Optional[str] = None):
        super().__init__(message, error_code="CONFIG_003")
        self.deprecated_key = deprecated_key
        self.replacement = replacement
