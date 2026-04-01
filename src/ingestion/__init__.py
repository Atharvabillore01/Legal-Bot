"""
Document Ingestion & Chunking Module for Legal RAG System

Module 1: Load, parse, clean, and chunk legal documents (PDF, DOCX, TXT)
into semantically meaningful units with rich metadata, ready for embedding.

Main entry point:
    ingest_document(file_path, user_id, ...) -> List[Chunk]

Exports public API for document ingestion pipeline.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from .models import Document, Chunk, IngestionRequest, IngestionResult
from .loaders import load_document, infer_file_type
from .cleaners import clean_text
from .chunker import chunk_document, ChunkerConfig
from .exceptions import IngestionError
from .constants import SMALL_DOCUMENT_TOKEN_THRESHOLD, TIKTOKEN_MODEL

# Configure module logger
logger = logging.getLogger(__name__)

# Public API
__all__ = [
    # Data models
    "Chunk",
    "Document",
    "IngestionRequest",
    "IngestionResult",
    # Functions
    "ingest_document",
    "batch_ingest_documents",
    "ChunkerConfig",
    # Exceptions
    "IngestionError",
]


def ingest_document(
    file_path: str,
    user_id: str,
    jurisdiction: Optional[str] = None,
    custom_metadata: Optional[dict] = None,
    enable_ocr: bool = True,
    chunk_size_tokens: int = 750,
    chunk_overlap_tokens: int = 150,
) -> List[Chunk]:
    """
    Load, parse, clean, chunk, and validate a document in one call.
    
    High-level entry point combining all ingestion pipeline steps.
    
    Args:
        file_path: Absolute path to document (PDF, DOCX, or TXT)
        user_id: ID of uploading user
        jurisdiction: Optional legal jurisdiction hint
        custom_metadata: Optional additional metadata key-value pairs
        enable_ocr: Enable OCR fallback for scanned PDFs (default: True)
        chunk_size_tokens: Target tokens per chunk (default: 750)
        chunk_overlap_tokens: Overlap tokens between chunks (default: 150)
    
    Returns:
        List[Chunk]: Ready-to-embed chunks with full metadata
    
    Raises:
        FileNotFoundError: File does not exist
        EmptyFileError: File is empty or yields no readable text
        CorruptedFileError: File structure is invalid
        UnsupportedFileTypeError: File format not supported
        PyTeseractNotInstalledError: OCR required but not available
        TextExtractionError: Text extraction failed
        ChunkingError: Chunking process failed
        IngestionError: Base exception for any ingestion failure
    
    Example:
        >>> chunks = ingest_document(
        ...     file_path="/data/contract.pdf",
        ...     user_id="user_123",
        ...     jurisdiction="California",
        ...     enable_ocr=True
        ... )
        >>> len(chunks)
        12
        >>> chunks[0].token_count
        745
    
    Process:
        1. Infer file type from extension
        2. Load via appropriate loader (PDF → pdfplumber + OCR,
           DOCX → python-docx, TXT → chardet-based)
        3. Clean text (normalize, remove headers/footers, etc.)
        4. Chunk with RecursiveCharacterTextSplitter
        5. Enrich with metadata (section, page, jurisdiction, etc.)
        6. Validate all chunks
        7. Return list of Chunk objects
    """
    logger.info(
        f"Starting document ingestion: {file_path} "
        f"(user={user_id}, jurisdiction={jurisdiction})"
    )
    
    try:
        # Create ingestion request
        request = IngestionRequest(
            file_path=file_path,
            user_id=user_id,
            jurisdiction=jurisdiction,
            custom_metadata=custom_metadata or {},
            enable_ocr=enable_ocr,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
        )
        
        # Step 1-3: Load, clean
        logger.debug(f"Loading document: {file_path}")
        document = load_document(file_path, enable_ocr=enable_ocr)
        logger.debug(f"Document loaded: {len(document.raw_text)} chars, has_ocr={document.has_ocr}")

        # Count tokens to decide whether to chunk
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(TIKTOKEN_MODEL)
            total_tokens = len(enc.encode(document.raw_text))
        except Exception:
            total_tokens = len(document.raw_text) // 4  # ~4 chars per token fallback

        # Small document fast-path: skip chunking, feed full text as one chunk
        if total_tokens <= SMALL_DOCUMENT_TOKEN_THRESHOLD:
            logger.info(
                f"Small document ({total_tokens} tokens ≤ {SMALL_DOCUMENT_TOKEN_THRESHOLD}) "
                f"— skipping chunking, using full text as single chunk"
            )
            now = datetime.now(timezone.utc)
            chunk = Chunk(
                id=f"{document.doc_id}_0",
                text=document.raw_text,
                token_count=max(total_tokens, 1),
                doc_name=document.doc_name,
                doc_id=document.doc_id,
                chunk_index=0,
                page_number=1,
                section=None,
                jurisdiction=jurisdiction,
                upload_timestamp=now,
                user_id=user_id,
                has_ocr=document.has_ocr,
            )
            return [chunk]

        # Step 4-7: Chunk and enrich (large documents only)
        logger.debug(f"Large document ({total_tokens} tokens) — starting chunking...")
        config = ChunkerConfig(
            chunk_size=chunk_size_tokens,
            chunk_overlap=chunk_overlap_tokens,
        )
        chunks = chunk_document(document, request, config)

        logger.info(
            f"Document ingestion complete: {len(chunks)} chunks, "
            f"{sum(c.token_count for c in chunks)} total tokens"
        )

        return chunks
        
    except IngestionError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during ingestion: {e}")
        raise IngestionError(f"Document ingestion failed: {e}") from e


def batch_ingest_documents(
    file_paths: List[str],
    user_id: str,
    **kwargs
) -> List[IngestionResult]:
    """
    Ingest multiple documents, returning individual results.
    
    Non-blocking for one document's failure; processes all files
    even if some fail.
    
    Args:
        file_paths: List of absolute paths to documents
        user_id: ID of uploading user
        **kwargs: Additional args passed to ingest_document()
    
    Returns:
        List[IngestionResult]: One result per file (success or error)
    
    Example:
        >>> results = batch_ingest_documents(
        ...     file_paths=["/data/doc1.pdf", "/data/doc2.docx"],
        ...     user_id="user_123"
        ... )
        >>> successful = [r for r in results if r.success]
        >>> len(successful)
        2
    """
    logger.info(f"Starting batch ingestion of {len(file_paths)} documents")
    
    results = []
    for i, file_path in enumerate(file_paths, 1):
        logger.info(f"Processing {i}/{len(file_paths)}: {file_path}")
        
        try:
            chunks = ingest_document(file_path, user_id, **kwargs)
            
            result = IngestionResult(
                success=True,
                doc_id=chunks[0].doc_id if chunks else None,
                chunks=chunks,
                chunk_count=len(chunks),
                total_tokens=sum(c.token_count for c in chunks),
            )
            results.append(result)
            logger.info(f"✓ Successfully ingested: {file_path}")
            
        except IngestionError as e:
            logger.warning(f"✗ Failed to ingest: {file_path}: {e}")
            
            result = IngestionResult(
                success=False,
                error=str(e),
            )
            results.append(result)
            
        except Exception as e:
            logger.error(f"✗ Unexpected error ingesting: {file_path}: {e}")
            
            result = IngestionResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
            )
            results.append(result)
    
    successful = sum(1 for r in results if r.success)
    logger.info(
        f"Batch ingestion complete: {successful}/{len(file_paths)} successful"
    )
    
    return results
