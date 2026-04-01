"""
src/llm/llm_interface.py

OpenAI GPT-4o integration with structured response parsing.

Handles:
  - Calling GPT-4o API with exponential backoff on rate limits
  - Parsing structured responses
  - Error handling and recovery
  - Token counting and budget management
  - Citation extraction from responses

Key Functions:
    - query_llm: Execute LLM query with exponential backoff
    - process_llm_response: Parse and validate response
    - handle_rate_limit: Exponential backoff on rate limits
    - handle_context_length_error: Progressive chunk removal
    - handle_no_context: Return sensible default for empty context
"""

import logging
import time
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime

try:
    import openai
    from openai import OpenAI, RateLimitError, APIError, APIConnectionError
except ImportError:
    raise ImportError("openai library not found. Install with: pip install openai")

from .models import QueryResponse, Citation
from .prompt_builder import prepare_prompt_for_llm, count_tokens
from .citation_parser import build_citation_objects, parse_citations, clean_response_citations
from .confidence_scorer import (
    normalize_l2_distance,
    calculate_query_confidence,
    classify_confidence_level,
    create_confidence_level_object
)
from .exceptions import (
    CompletionError,
    APIError as APIErrorCustom,
    RateLimitError as RateLimitErrorCustom,
    AuthenticationError,
    ModelNotFoundError,
    CompletionTimeoutError,
    ResponseParseError,
    ContextLengthError as ContextLengthErrorCustom,
    EmptyContextError,
    TokenBudgetExceededError
)
from .constants import (
    GPT_MODEL,
    GPT_MODEL_FALLBACK,
    MODEL_TEMPERATURE,
    MODEL_TOP_P,
    MODEL_FREQUENCY_PENALTY,
    MODEL_PRESENCE_PENALTY,
    MAX_OUTPUT_TOKENS,
    MAX_CONTEXT_TOKENS,
    MAX_API_RETRIES,
    RETRY_BACKOFF_INITIAL,
    RETRY_BACKOFF_MAX,
    RETRY_BACKOFF_MULTIPLIER,
    API_TIMEOUT_SECONDS,
    FEATURE_EXPONENTIAL_BACKOFF,
    FEATURE_CITATIONS,
    DEBUG_PROMPT_BUILDING
)

logger = logging.getLogger(__name__)


class LLMQueryEngine:
    """Orchestrates LLM queries with all safety measures."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM query engine.
        
        Args:
            api_key (str, optional): OpenAI API key (uses OPENAI_API_KEY env var if not provided)
        """
        try:
            self.client = OpenAI(api_key=api_key)
            self.model = GPT_MODEL
        except Exception as e:
            raise AuthenticationError(f"Failed to initialize OpenAI client: {str(e)}")
    
    def query_llm(
        self,
        chunks: List[Dict],
        query: str,
        chunk_metadata: Dict[str, Dict],
        chunk_scores: Optional[List[float]] = None,
        contradiction_count: int = 0,
        user_id: Optional[str] = None
    ) -> QueryResponse:
        """
        Execute complete LLM query with all safety measures.
        
        Pipeline:
        1. Prepare prompt with token budget
        2. Call GPT-4o with exponential backoff
        3. Parse response for citations
        4. Calculate confidence scores
        5. Return structured QueryResponse
        
        Args:
            chunks (List[Dict]): Retrieved chunks [text, doc_name, page_number, jurisdiction]
            query (str): User question
            chunk_metadata (Dict[str, Dict]): Metadata lookup {chunk_id: {...}}
            chunk_scores (List[float], optional): L2 normalized scores for pieces
            contradiction_count (int): Detected contradictions (default: 0)
            user_id (str, optional): User identifier for logging
        
        Returns:
            QueryResponse: Complete structured response with citations and confidence
        
        Raises:
            EmptyContextError: If no chunks provided
            TokenBudgetExceededError: If context exceeds budget even with 1 chunk
            RateLimitErrorCustom: If API rate limited (already retried with backoff)
            APIErrorCustom: If other API error occurs
            ResponseParseError: If response parsing fails
        
        Example:
            >>> engine = LLMQueryEngine()
            >>> chunks = [{"text": "...", "doc_name": "contract.pdf", ...}]
            >>> metadata = {"chunk_0": {"doc_name": "contract.pdf", ...}}
            >>> response = engine.query_llm(chunks, "What is the cap?", metadata)
            >>> assert response.confidence_level in ["LOW", "MEDIUM", "HIGH"]
        """
        if not chunks:
            raise EmptyContextError("No context chunks provided for query")
        
        # Record start time for timing metrics
        start_time = datetime.now()
        search_time_end = start_time
        
        try:
            # Prepare prompt with token allocation
            try:
                estimated_confidence = (sum(chunk_scores) / len(chunk_scores)) if chunk_scores else 0.5
                prompt, token_allocation = prepare_prompt_for_llm(chunks, query, estimated_confidence)
            except TokenBudgetExceededError:
                # Try with fewer chunks
                if len(chunks) > 1:
                    return self.query_llm(
                        chunks[:-1],  # Remove least relevant chunk
                        query,
                        chunk_metadata,
                        chunk_scores[:-1] if chunk_scores else None,
                        contradiction_count,
                        user_id
                    )
                else:
                    raise
            
            search_time_end = datetime.now()
            search_time_ms = (search_time_end - start_time).total_seconds() * 1000
            
            if DEBUG_PROMPT_BUILDING:
                logger.debug(f"Prompt prepared: {token_allocation['total_tokens']} tokens")
            
            # Call LLM with retries
            llm_start_time = datetime.now()
            response_text = self._call_llm_with_retry(prompt, user_id)
            llm_end_time = datetime.now()
            llm_time_ms = (llm_end_time - llm_start_time).total_seconds() * 1000
            
            # Extract citations from response
            citations = []
            if FEATURE_CITATIONS:
                try:
                    citations = build_citation_objects(response_text, chunk_metadata)
                except Exception as e:
                    logger.warning(f"Failed to extract citations: {e}")
            
            # Clean citation markers from response for display
            clean_response, cited_chunks = clean_response_citations(response_text)
            
            # Calculate confidence
            if chunk_scores:
                confidence_score = calculate_query_confidence(
                    chunk_scores,
                    contradiction_count
                )
            else:
                # Estimate from chunk count and query complexity
                confidence_score = 0.5 + (min(len(chunks), 5) / 10)
            
            confidence_level = classify_confidence_level(confidence_score)
            
            # Build QueryResponse
            response = QueryResponse(
                answer=clean_response,
                citations=citations,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                query=query,
                search_time_ms=search_time_ms,
                llm_time_ms=llm_time_ms,
                model=self.model,
                user_id=user_id
            )
            
            logger.info(
                f"Query completed: {len(chunks)} chunks, "
                f"confidence={confidence_score:.2f}, "
                f"citations={len(citations)}, "
                f"total_time={(response.total_time_ms()):.0f}ms"
            )
            
            return response
        
        except (EmptyContextError, TokenBudgetExceededError, RateLimitErrorCustom, APIErrorCustom):
            raise
        except Exception as e:
            logger.error(f"Unexpected error in query_llm: {e}")
            raise CompletionError(f"Unexpected error: {str(e)}")
    
    def _call_llm_with_retry(
        self,
        prompt: str,
        user_id: Optional[str] = None,
        attempt: int = 0
    ) -> str:
        """
        Call GPT-4o API with exponential backoff retry strategy.
        
        Retry Strategy:
        - Max 3 attempts
        - Initial backoff: 2 seconds
        - Exponential: 2^attempt seconds
        - Max backoff: 32 seconds
        
        HTTP-level retries are handled by openai library internally.
        This adds application-level retry with backoff.
        
        Args:
            prompt (str): Complete prompt for LLM
            user_id (str, optional): User ID for logging
            attempt (int): Current attempt number (used recursively)
        
        Returns:
            str: LLM response text
        
        Raises:
            RateLimitErrorCustom: If rate limited after all retries
            APIErrorCustom: If other API error occurs
            CompletionTimeoutError: If API times out
        """
        try:
            # Call OpenAI API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=MODEL_TEMPERATURE,
                top_p=MODEL_TOP_P,
                max_tokens=MAX_OUTPUT_TOKENS,
                frequency_penalty=MODEL_FREQUENCY_PENALTY,
                presence_penalty=MODEL_PRESENCE_PENALTY,
                timeout=API_TIMEOUT_SECONDS
            )
            
            response_text = completion.choices[0].message.content
            
            if not response_text:
                raise ResponseParseError("Empty response from LLM")
            
            logger.info(f"LLM call successful (attempt {attempt+1})")
            return response_text
        
        except RateLimitError as e:
            # Rate limit error - retry with exponential backoff
            if not FEATURE_EXPONENTIAL_BACKOFF or attempt >= MAX_API_RETRIES:
                logger.error(f"Rate limit exceeded after {attempt+1} attempts")
                raise RateLimitErrorCustom(
                    f"API rate limit exceeded: {str(e)}",
                    retry_after_seconds=60
                )
            
            # Calculate backoff time
            backoff_time = min(
                RETRY_BACKOFF_INITIAL * (RETRY_BACKOFF_MULTIPLIER ** attempt),
                RETRY_BACKOFF_MAX
            )
            
            logger.warning(
                f"Rate limit error (attempt {attempt+1}), "
                f"retrying in {backoff_time} seconds..."
            )
            
            time.sleep(backoff_time)
            return self._call_llm_with_retry(prompt, user_id, attempt+1)
        
        except (APIConnectionError, TimeoutError) as e:
            # Connection or timeout error - retry
            if not FEATURE_EXPONENTIAL_BACKOFF or attempt >= MAX_API_RETRIES:
                logger.error(f"API connection error after {attempt+1} attempts: {e}")
                raise CompletionTimeoutError(
                    f"API timeout/connection error: {str(e)}",
                    timeout_seconds=API_TIMEOUT_SECONDS
                )
            
            backoff_time = min(
                RETRY_BACKOFF_INITIAL * (RETRY_BACKOFF_MULTIPLIER ** attempt),
                RETRY_BACKOFF_MAX
            )
            
            logger.warning(
                f"Connection error (attempt {attempt+1}), "
                f"retrying in {backoff_time} seconds..."
            )
            
            time.sleep(backoff_time)
            return self._call_llm_with_retry(prompt, user_id, attempt+1)
        
        except APIError as e:
            # Check for specific error types
            error_message = str(e)
            
            if "model_not_found" in error_message or "does not exist" in error_message:
                logger.error(f"Model {self.model} not found")
                raise ModelNotFoundError(
                    f"Model {self.model} is not available: {error_message}",
                    model_name=self.model
                )
            
            if "invalid_api_key" in error_message or "Incorrect API key" in error_message:
                logger.error("Invalid OpenAI API key")
                raise AuthenticationError("Invalid or missing OpenAI API key")
            
            if "exceeded" in error_message.lower() and "quota" in error_message.lower():
                logger.error("API quota exceeded")
                raise AuthenticationError(f"API quota exceeded: {error_message}")
            
            # Generic API error
            logger.error(f"API error: {error_message}")
            raise APIErrorCustom(
                f"OpenAI API error: {error_message}",
                status_code=getattr(e, 'status_code', None),
                api_error=e
            )


# Convenience function for simple use cases
def query_llm_simple(
    chunks: List[Dict],
    query: str,
    chunk_metadata: Dict[str, Dict],
    api_key: Optional[str] = None
) -> QueryResponse:
    """
    Simple wrapper for LLM queries.
    
    Args:
        chunks (List[Dict]): Retrieved chunks
        query (str): User question
        chunk_metadata (Dict[str, Dict]): Metadata lookup
        api_key (str, optional): OpenAI API key
    
    Returns:
        QueryResponse: Structured response
    
    Example:
        >>> response = query_llm_simple(chunks, "What is the cap?", metadata)
        >>> print(response.answer)
    """
    engine = LLMQueryEngine(api_key=api_key)
    return engine.query_llm(chunks, query, chunk_metadata)
