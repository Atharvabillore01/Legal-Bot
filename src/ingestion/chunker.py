"""
Document chunking logic and metadata tagging.

Splits cleaned text into semantically meaningful chunks using LangChain's
RecursiveCharacterTextSplitter and enriches with metadata.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List
import uuid

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        HAS_LANGCHAIN = True
    except ImportError:
        HAS_LANGCHAIN = False

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

from .models import Document, Chunk, IngestionRequest
from .cleaners import detect_section, clean_text
from .exceptions import (
    ChunkingError,
    EmptyDocumentError,
    MetadataExtractionError,
    TokenCountError,
    InvalidChunkError,
)
from .constants import (
    CHUNK_SIZE_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    RECURSIVE_SPLITTERS,
    MIN_CHUNK_TOKENS,
    MAX_CHUNK_TOKENS,
    TIKTOKEN_MODEL,
)

logger = logging.getLogger(__name__)


class ChunkerConfig:
    """Configuration for chunking behavior."""
    
    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE_TOKENS,
        chunk_overlap: int = CHUNK_OVERLAP_TOKENS,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or RECURSIVE_SPLITTERS
        
        if chunk_overlap >= chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        if chunk_size < 10:
            raise ValueError("Chunk size must be at least 10 tokens")


def estimate_token_count(text: str) -> int:
    """
    Estimate token count using tiktoken.
    
    Uses: 'gpt-3.5-turbo' encoding (cl100k_base)
    
    Args:
        text: Text to count tokens for
    
    Returns:
        int: Approximate token count
    
    Raises:
        TokenCountError: If token counting fails
    """
    if not HAS_TIKTOKEN:
        raise TokenCountError(
            "tiktoken not installed. Install via: pip install tiktoken"
        )
    
    try:
        encoding = tiktoken.encoding_for_model(TIKTOKEN_MODEL)
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        raise TokenCountError(f"Failed to count tokens: {e}") from e


def estimate_char_to_token_ratio() -> float:
    """
    Estimate character-to-token ratio for fast chunking.
    
    Uses sample text to establish rough conversion factor.
    
    Returns:
        float: Ratio of characters per token (typically ~4-5)
    """
    sample = "The quick brown fox jumps over the lazy dog. " * 10
    try:
        token_count = estimate_token_count(sample)
        char_count = len(sample)
        return char_count / token_count if token_count > 0 else 4.0
    except TokenCountError:
        return 4.0  # Fallback default


def _create_splitter(config: ChunkerConfig) -> 'RecursiveCharacterTextSplitter':
    """
    Create a LangChain RecursiveCharacterTextSplitter.
    
    Args:
        config: ChunkerConfig with size/overlap/separators
    
    Returns:
        RecursiveCharacterTextSplitter configured instance
    
    Raises:
        ChunkingError: If LangChain not available
    """
    if not HAS_LANGCHAIN:
        raise ChunkingError(
            "langchain not installed. Install via: pip install langchain"
        )
    
    try:
        # Character-level size estimation (rough)
        char_to_token = estimate_char_to_token_ratio()
        chunk_size_chars = int(config.chunk_size * char_to_token)
        chunk_overlap_chars = int(config.chunk_overlap * char_to_token)
        
        logger.debug(
            f"Splitter config: {config.chunk_size} tokens ≈ {chunk_size_chars} chars, "
            f"overlap {config.chunk_overlap} tokens ≈ {chunk_overlap_chars} chars"
        )
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size_chars,
            chunk_overlap=chunk_overlap_chars,
            separators=config.separators,
            length_function=len,
        )
        return splitter
        
    except Exception as e:
        raise ChunkingError(f"Failed to create text splitter: {e}") from e


def infer_page_number(
    chunk_text: str,
    chunk_start_pos: int,
    clean_doc_text: str,
    doc: Document,
) -> Optional[int]:
    """
    Determine which page a chunk originates from using exact position tracking.

    Strategy:
    - For PDF: count '[PAGE BREAK]' markers in clean_doc_text before chunk_start_pos.
    - For DOCX: estimate from page_boundaries if available, else heuristic.
    - For TXT: always None.

    Args:
        chunk_text: The chunk's text content.
        chunk_start_pos: Character offset of the chunk's start in clean_doc_text.
        clean_doc_text: The full cleaned document text used for splitting.
        doc: Original Document object.

    Returns:
        Optional[int]: 1-indexed page number, or None if indeterminate.
    """
    if doc.file_type == "txt":
        return None

    if chunk_start_pos >= 0:
        # Count [PAGE BREAK] markers before this chunk's position
        prefix = clean_doc_text[:chunk_start_pos]
        page_num = prefix.count("[PAGE BREAK]") + 1
        # Clamp to actual page count if known
        if doc.page_count:
            page_num = min(page_num, doc.page_count)
        return page_num

    return None


def chunk_document(
    document: Document,
    request: IngestionRequest,
    config: Optional[ChunkerConfig] = None,
) -> List[Chunk]:
    """
    Chunk document into semantically meaningful units with metadata.
    
    Main chunking pipeline:
    1. Validate document is non-empty
    2. Clean text
    3. Split into chunks using RecursiveCharacterTextSplitter
    4. Calculate token counts
    5. Extract metadata (section, page, jurisdiction, etc.)
    6. Validate each chunk
    7. Return list of Chunk objects
    
    Args:
        document: Parsed Document object from loader
        request: IngestionRequest with user/context info
        config: Optional ChunkerConfig; uses defaults if None
    
    Returns:
        List[Chunk]: Ready-to-embed chunks with full metadata
    
    Raises:
        EmptyDocumentError: Document is empty after cleaning
        ChunkingError: Recursive splitter fails
        MetadataExtractionError: Cannot extract required metadata
        InvalidChunkError: Chunk validation fails
    
    Example:
        >>> doc = load_pdf("contract.pdf")
        >>> req = IngestionRequest(file_path="contract.pdf", user_id="user_1")
        >>> chunks = chunk_document(doc, req)
        >>> len(chunks)
        7
    """
    logger.info(
        f"Chunking document: {document.doc_name} "
        f"({len(document.raw_text)} chars)"
    )
    
    # Initialize config
    if config is None:
        config = ChunkerConfig(
            chunk_size=request.chunk_size_tokens,
            chunk_overlap=request.chunk_overlap_tokens,
        )
    
    # Step 1: Validate document is non-empty
    clean_doc_text = clean_text(document.raw_text, document.file_type)
    if not clean_doc_text or not clean_doc_text.strip():
        raise EmptyDocumentError(
            f"Document '{document.doc_name}' yields no text after cleaning"
        )
    
    logger.debug(f"Cleaned text: {len(clean_doc_text)} chars")
    
    # Step 2: Split into chunks
    try:
        splitter = _create_splitter(config)
        text_chunks = splitter.split_text(clean_doc_text)
    except ChunkingError:
        raise
    except Exception as e:
        raise ChunkingError(f"Text splitting failed: {e}") from e
    
    if not text_chunks:
        raise ChunkingError("Splitter returned no chunks")
    
    logger.info(f"Split document into {len(text_chunks)} chunks")
    
    # Step 3-7: Process chunks
    chunks = []
    now = datetime.now(timezone.utc)
    # Sequential search offset: advance after each chunk so overlapping chunks
    # resolve to the correct position rather than always finding the first match.
    search_offset = 0

    for i, chunk_text in enumerate(text_chunks):
        try:
            # Validate chunk text
            if not chunk_text or not chunk_text.strip():
                logger.warning(f"Skipping empty chunk at index {i}")
                continue

            # Calculate token count
            try:
                token_count = estimate_token_count(chunk_text)
            except TokenCountError:
                logger.warning(f"Failed to count tokens for chunk {i}; using estimate")
                token_count = len(chunk_text) // 4  # Rough fallback

            # Validate token count in range
            if token_count < MIN_CHUNK_TOKENS:
                logger.warning(
                    f"Chunk {i} has {token_count} tokens (min {MIN_CHUNK_TOKENS}); skipping"
                )
                continue

            if token_count > MAX_CHUNK_TOKENS:
                logger.warning(
                    f"Chunk {i} has {token_count} tokens (max {MAX_CHUNK_TOKENS}); may indicate issue"
                )

            # Locate chunk in the full cleaned text for accurate page detection.
            # Search forward from search_offset to handle overlapping windows.
            chunk_start = clean_doc_text.find(chunk_text.strip(), search_offset)
            if chunk_start == -1:
                # Fallback: search from beginning (handles edge cases)
                chunk_start = clean_doc_text.find(chunk_text.strip())
            # Advance offset past non-overlapping portion for next chunk
            if chunk_start >= 0:
                advance = max(1, len(chunk_text) - config.chunk_overlap * 4)
                search_offset = chunk_start + advance

            # Extract metadata
            section = detect_section(chunk_text)
            page_num = infer_page_number(chunk_text, chunk_start, clean_doc_text, document)
            jurisdiction = request.jurisdiction or None
            
            # Create Chunk object
            chunk_id = f"{document.doc_id}_{i}"
            chunk = Chunk(
                id=chunk_id,
                text=chunk_text.strip(),
                token_count=token_count,
                doc_name=document.doc_name,
                doc_id=document.doc_id,
                chunk_index=i,
                page_number=page_num,
                section=section,
                jurisdiction=jurisdiction,
                upload_timestamp=now,
                user_id=request.user_id,
                has_ocr=document.has_ocr,
            )
            
            chunks.append(chunk)
            logger.debug(
                f"Created chunk {i}: {token_count} tokens, "
                f"page {page_num}, section '{section}'"
            )
            
        except InvalidChunkError as e:
            logger.warning(f"Chunk {i} validation failed: {e}")
            continue
        except Exception as e:
            logger.warning(f"Error processing chunk {i}: {e}")
            continue
    
    if not chunks:
        raise ChunkingError("No valid chunks produced after processing")
    
    logger.info(
        f"Chunking complete: {len(chunks)} valid chunks, "
        f"{sum(c.token_count for c in chunks)} total tokens"
    )
    
    return chunks


def validate_chunk(chunk: Chunk) -> bool:
    """
    Validate a Chunk object for readiness.
    
    Checks:
    - Token count in valid range
    - Text non-empty and reasonable length
    - Required metadata present
    - IDs are non-empty
    
    Args:
        chunk: Chunk to validate
    
    Returns:
        bool: True if chunk passes validation
    
    Raises:
        InvalidChunkError: If chunk fails validation
    """
    if not chunk.text or not chunk.text.strip():
        raise InvalidChunkError("Chunk text is empty")
    
    if chunk.token_count < MIN_CHUNK_TOKENS or chunk.token_count > MAX_CHUNK_TOKENS:
        raise InvalidChunkError(
            f"Chunk token count {chunk.token_count} out of range "
            f"[{MIN_CHUNK_TOKENS}, {MAX_CHUNK_TOKENS}]"
        )
    
    if not chunk.id or not chunk.doc_id or not chunk.doc_name:
        raise InvalidChunkError("Missing required chunk metadata")
    
    if not chunk.user_id:
        raise InvalidChunkError("Missing user_id in chunk")
    
    return True
