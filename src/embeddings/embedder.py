"""
OpenAI embedding generation with batching and exponential backoff retry.
"""

import logging
import time
import os
from typing import List, Optional
import numpy as np

try:
    from openai import OpenAI, APIError, RateLimitError as OpenAIRateLimitError
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from src.ingestion.models import Chunk
from .models import EmbeddedChunk, EmbeddingBatch
from .exceptions import (
    EmbeddingGenerationError,
    RateLimitError,
    APITimeoutError,
    InvalidAPIKeyError,
    InvalidChunkError,
)
from .constants import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    EMBEDDING_MAX_TOKENS,
    BATCH_SIZE,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    OPENAI_API_TIMEOUT,
)
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _validate_api_key() -> None:
    """
    Validate OpenAI API key is configured.
    
    Raises:
        InvalidAPIKeyError: API key not found or invalid
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise InvalidAPIKeyError("OpenAI API key not configured in OPENAI_API_KEY environment variable")


def embed_chunks(
    chunks: List[Chunk],
    user_id: str,
    batch_size: int = BATCH_SIZE,
    timeout_seconds: int = OPENAI_API_TIMEOUT,
) -> List[EmbeddedChunk]:
    """
    Generate OpenAI embeddings for chunks with batching & exponential backoff.
    
    Args:
        chunks: List of Chunk objects from Module 1
        user_id: Owning user ID
        batch_size: Chunks per API call (max 100)
        timeout_seconds: Overall timeout for request
    
    Returns:
        List[EmbeddedChunk]: Chunks with embedding vectors
    
    Raises:
        EmbeddingGenerationError: API call failed
        RateLimitError: OpenAI rate limit exceeded
        APITimeoutError: Request timeout
        InvalidChunkError: Chunk validation failed
    
    Process:
        1. Validate all chunks and deduplicate
        2. Split into batches of ≤100
        3. For each batch:
            a. Call OpenAI API
            b. Handle rate limit with exponential backoff (2^n seconds)
            c. Retry up to 3 times
            d. Map responses to chunks
        4. Return EmbeddedChunk objects sorted by original order
    """
    if not HAS_OPENAI:
        raise EmbeddingGenerationError(
            "openai not installed. Install via: pip install openai"
        )
    
    # Get OpenAI API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise InvalidAPIKeyError("OpenAI API key not found in OPENAI_API_KEY environment variable")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    logger.info(f"Embedding {len(chunks)} chunks for user {user_id}")
    
    # Validate chunks
    if not chunks:
        return []
    
    for chunk in chunks:
        if not chunk.text or not chunk.text.strip():
            raise InvalidChunkError(f"Empty chunk text: {chunk.id}")
        if chunk.token_count < 1:
            raise InvalidChunkError(f"Invalid token count: {chunk.id}")
    
    # Truncate chunks that exceed the embedding model's token limit
    try:
        import tiktoken
        _enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

        def _truncate_to_limit(text: str) -> str:
            tokens = _enc.encode(text)
            if len(tokens) > EMBEDDING_MAX_TOKENS:
                logger.warning(
                    f"Chunk exceeds embedding limit ({len(tokens)} tokens); "
                    f"truncating to {EMBEDDING_MAX_TOKENS}"
                )
                return _enc.decode(tokens[:EMBEDDING_MAX_TOKENS])
            return text

    except Exception:
        def _truncate_to_limit(text: str) -> str:  # type: ignore[misc]
            # Rough char-based fallback: ~4 chars per token
            limit_chars = EMBEDDING_MAX_TOKENS * 4
            if len(text) > limit_chars:
                logger.warning(f"Chunk too long; truncating to ~{EMBEDDING_MAX_TOKENS} tokens")
                return text[:limit_chars]
            return text

    # Deduplicate by chunk_id
    seen_ids = set()
    unique_chunks = []
    for chunk in chunks:
        if chunk.id not in seen_ids:
            unique_chunks.append(chunk)
            seen_ids.add(chunk.id)
        else:
            logger.warning(f"Skipping duplicate chunk: {chunk.id}")
    
    # Create batches (truncate any text exceeding the embedding model's token limit)
    batches = []
    for i in range(0, len(unique_chunks), batch_size):
        batch_chunks = unique_chunks[i:i + batch_size]
        batch = EmbeddingBatch(
            batch_id=f"batch_{user_id}_{i}",
            chunk_ids=[c.id for c in batch_chunks],
            texts=[_truncate_to_limit(c.text) for c in batch_chunks],
            batch_size=len(batch_chunks),
        )
        batches.append((batch, batch_chunks))
    
    logger.info(f"Created {len(batches)} batches for embedding")
    
    # Process batches
    all_embedded = []
    for batch_idx, (batch, batch_chunks) in enumerate(batches, 1):
        logger.debug(f"Processing batch {batch_idx}/{len(batches)}")
        
        try:
            embeddings = _embed_batch_with_retry(
                client=client,
                texts=batch.texts,
                batch_id=batch.batch_id,
                timeout_seconds=timeout_seconds,
            )
            
            # Create embedded chunks
            now = datetime.now(timezone.utc).isoformat() + "Z"
            for chunk, embedding in zip(batch_chunks, embeddings):
                # Convert upload_timestamp to ISO string format
                if isinstance(chunk.upload_timestamp, str):
                    uploaded_at_str = chunk.upload_timestamp
                else:
                    uploaded_at_str = chunk.upload_timestamp.isoformat() + "Z"
                
                embedded = EmbeddedChunk(
                    chunk_id=chunk.id,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    doc_name=chunk.doc_name,
                    doc_id=chunk.doc_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    jurisdiction=chunk.jurisdiction,
                    user_id=user_id,
                    has_ocr=chunk.has_ocr,
                    embedding=embedding,
                    embedding_model=EMBEDDING_MODEL,
                    uploaded_at=uploaded_at_str,
                    embedded_at=now,
                )
                all_embedded.append(embedded)
            
        except (RateLimitError, APITimeoutError) as e:
            logger.error(f"Failed to embed batch {batch_idx}: {e}")
            raise
        except Exception as e:
            raise EmbeddingGenerationError(
                f"Failed to embed batch {batch_idx}: {e}"
            ) from e
    
    logger.info(
        f"Successfully embedded {len(all_embedded)} chunks "
        f"for user {user_id}"
    )
    
    return all_embedded


def _embed_batch_with_retry(
    client: OpenAI,
    texts: List[str],
    batch_id: str,
    timeout_seconds: int = OPENAI_API_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> List[List[float]]:
    """
    Call OpenAI API with exponential backoff retry.
    
    Args:
        client: OpenAI client instance (v1.0.0+)
        texts: List of texts to embed (len ≤ 100)
        batch_id: Batch identifier for logging
        timeout_seconds: Request timeout
        max_retries: Max retry attempts
    
    Returns:
        List[List[float]]: List of embedding vectors
    
    Raises:
        RateLimitError: Rate limit exceeded after retries
        APITimeoutError: Timeout exceeded
        EmbeddingGenerationError: Other API errors
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(
                f"Embedding batch {batch_id} (attempt {attempt}/{max_retries}, "
                f"{len(texts)} texts)"
            )
            
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
            )
            
            # Extract embeddings from response (v1.0.0+ object format)
            embeddings = [item.embedding for item in response.data]
            
            if len(embeddings) != len(texts):
                raise EmbeddingGenerationError(
                    f"Response size mismatch: got {len(embeddings)}, "
                    f"expected {len(texts)}"
                )
            
            logger.debug(f"Successfully embedded batch {batch_id}")
            return embeddings
            
        except OpenAIRateLimitError as e:
            if attempt < max_retries:
                wait_time = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    f"Rate limit hit on batch {batch_id} "
                    f"(attempt {attempt}/{max_retries}); "
                    f"retry in {wait_time}s"
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Rate limit exceeded after {max_retries} retries")
                raise RateLimitError(
                    f"OpenAI rate limit exceeded after {max_retries} retries"
                ) from e
        
        except APIError as e:
            # Handle various API errors (includes AuthenticationError, Timeout, etc.)
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                logger.error(f"API timeout on batch {batch_id}")
                raise APITimeoutError(f"OpenAI API timeout: {e}") from e
            elif "authentication" in error_str or "unauthorized" in error_str:
                logger.error(f"Authentication error: {e}")
                raise InvalidAPIKeyError(f"OpenAI authentication failed: {e}") from e
            else:
                logger.error(f"OpenAI API error: {e}")
                raise EmbeddingGenerationError(f"OpenAI API error: {e}") from e
        
        except Exception as e:
            logger.error(f"Unexpected error embedding batch {batch_id}: {e}")
            raise EmbeddingGenerationError(
                f"Unexpected error: {e}"
            ) from e
    
    raise EmbeddingGenerationError("Exhausted all retry attempts")


def embed_query(query: str, user_id: str) -> np.ndarray:
    """
    Generate embedding for a single query string.
    
    Args:
        query: Query text
        user_id: User making query (for logging)
    
    Returns:
        np.ndarray: 3072-D embedding vector
    
    Raises:
        EmbeddingGenerationError: API call failed
        RateLimitError: Rate limit exceeded
    
    Note:
        Queries use same embedding model as chunks (text-embedding-3-large)
        for consistency in vector space.
    """
    if not query or not query.strip():
        raise InvalidChunkError("Query text is empty")
    
    logger.debug(f"Embedding query for user {user_id}")
    
    # Get OpenAI API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise InvalidAPIKeyError("OpenAI API key not found in OPENAI_API_KEY environment variable")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    try:
        embeddings = _embed_batch_with_retry(
            client=client,
            texts=[query],
            batch_id=f"query_{user_id}",
        )
        embedding_vector = np.array(embeddings[0], dtype=np.float32)
        
        return embedding_vector
        
    except (RateLimitError, APITimeoutError):
        raise
    except Exception as e:
        raise EmbeddingGenerationError(f"Failed to embed query: {e}") from e
