"""
Embeddings & FAISS Vector Store Module for Legal RAG System

Module 2: Generate embeddings and manage semantic vector search via FAISS indices.

Entry points:
    - embed_chunks(): Embed document chunks with OpenAI
    - create_user_index(): Create FAISS index for user
    - add_chunks_to_index(): Add embeddings to index
    - retrieve(): Semantic vector search
    - backup_index(): Create index backup
    - recover_from_backup(): Restore from backup

Features:
    - OpenAI text-embedding-3-large (3072D) with batching & retry
    - FAISS IndexFlatL2 (small) and IndexIVFFlat (large) indices
    - Multi-user isolation with separate indices per user
    - Metadata sidecar JSON for chunk lineage
    - Reader-writer lock concurrency control
    - Backup/recovery with point-in-time snapshots
"""

import logging

# Configure module logger
logger = logging.getLogger(__name__)

# Public API
from .models import (
    EmbeddedChunk,
    MetadataEntry,
    UserIndex,
    EmbeddingBatch,
    RetrievalResult,
    BackupInfo,
)
from .embedder import embed_chunks, embed_query
from .indexer import create_user_index, add_chunks_to_index, get_index
from .retriever import retrieve, retrieve_with_reranking, batch_retrieve
from .metadata import (
    load_metadata,
    load_metadata_for_user,
    save_metadata,
    resolve_faiss_id,
    resolve_chunk_ids_by_doc,
    add_entries_to_metadata,
    remove_entries_from_metadata,
)
from .storage import (
    save_index,
    load_index_files,
    backup_index,
    recover_from_backup,
    list_backups,
)
from .concurrency import (
    UserIndexLock,
    LockManager,
    get_user_lock,
    read_lock,
    write_lock,
)
from .exceptions import (
    EmbeddingError,
    APIError,
    RateLimitError,
    APITimeoutError,
    InvalidAPIKeyError,
    EmbeddingGenerationError,
    InvalidChunkError,
    InvalidEmbeddingError,
    IndexError,
    IndexNotFoundError,
    IndexAlreadyExistsError,
    CorruptedIndexError,
    ChecksumError,
    StorageError,
    FileNotFoundError_,
    JSONDecodeError,
    BackupError,
    BackupNotFoundError,
    CorruptedBackupError,
    ConcurrencyError,
    LockTimeoutError,
    DeadlockDetectedError,
)

__all__ = [
    # Models
    "EmbeddedChunk",
    "MetadataEntry",
    "UserIndex",
    "EmbeddingBatch",
    "RetrievalResult",
    "BackupInfo",
    # Embedder
    "embed_chunks",
    "embed_query",
    # Indexer
    "create_user_index",
    "add_chunks_to_index",
    "get_index",
    # Retriever
    "retrieve",
    "retrieve_with_reranking",
    "batch_retrieve",
    # Metadata
    "load_metadata",
    "load_metadata_for_user",
    "save_metadata",
    "resolve_faiss_id",
    "resolve_chunk_ids_by_doc",
    "add_entries_to_metadata",
    "remove_entries_from_metadata",
    # Storage
    "save_index",
    "load_index_files",
    "backup_index",
    "recover_from_backup",
    "list_backups",
    # Concurrency
    "UserIndexLock",
    "LockManager",
    "get_user_lock",
    "read_lock",
    "write_lock",
    # Exceptions (all)
    "EmbeddingError",
    "APIError",
    "RateLimitError",
    "APITimeoutError",
    "InvalidAPIKeyError",
    "EmbeddingGenerationError",
    "InvalidChunkError",
    "InvalidEmbeddingError",
    "IndexError",
    "IndexNotFoundError",
    "IndexAlreadyExistsError",
    "CorruptedIndexError",
    "ChecksumError",
    "StorageError",
    "FileNotFoundError_",
    "JSONDecodeError",
    "BackupError",
    "BackupNotFoundError",
    "CorruptedBackupError",
    "ConcurrencyError",
    "LockTimeoutError",
    "DeadlockDetectedError",
]

logger.info("Embeddings & FAISS Vector Store Module initialized")
