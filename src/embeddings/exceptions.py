"""
Custom exceptions for embeddings and vector store.
"""


class EmbeddingError(Exception):
    """Base exception for embedding-related errors."""
    pass


class APIError(EmbeddingError):
    """Base exception for API errors."""
    pass


class RateLimitError(APIError):
    """OpenAI rate limit exceeded."""
    pass


class APITimeoutError(APIError):
    """API request timeout."""
    pass


class InvalidAPIKeyError(APIError):
    """Invalid or missing OpenAI API key."""
    pass


class EmbeddingGenerationError(EmbeddingError):
    """Failed to generate embedding."""
    pass


class InvalidChunkError(EmbeddingError):
    """Chunk validation failed."""
    pass


class InvalidEmbeddingError(EmbeddingError):
    """Embedding vector is invalid (wrong dimension, NaN, etc.)."""
    pass


class IndexError(EmbeddingError):
    """Base exception for index-related errors."""
    pass


class IndexNotFoundError(IndexError):
    """FAISS index does not exist for user."""
    pass


class IndexAlreadyExistsError(IndexError):
    """Index already exists for user."""
    pass


class CorruptedIndexError(IndexError):
    """Index file is corrupted or invalid."""
    pass


class ChecksumError(IndexError):
    """Checksum mismatch (data integrity issue)."""
    pass


class StorageError(EmbeddingError):
    """Base exception for storage I/O errors."""
    pass


class FileNotFoundError_(StorageError):
    """Required file does not exist."""
    pass


class JSONDecodeError(StorageError):
    """Cannot parse JSON file."""
    pass


class BackupError(StorageError):
    """Failed to create or manage backup."""
    pass


class BackupNotFoundError(BackupError):
    """Backup does not exist."""
    pass


class CorruptedBackupError(BackupError):
    """Backup integrity check failed."""
    pass


class ConcurrencyError(EmbeddingError):
    """Base exception for concurrency issues."""
    pass


class LockTimeoutError(ConcurrencyError):
    """Failed to acquire lock within timeout."""
    pass


class DeadlockDetectedError(ConcurrencyError):
    """Potential deadlock detected."""
    pass
