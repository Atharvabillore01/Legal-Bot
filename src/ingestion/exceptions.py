"""
Custom exceptions for document ingestion pipeline.

Exception hierarchy:
    IngestionError (base)
    ├── FileError
    ├── LoaderError
    ├── CleaningError
    ├── ChunkingError
    └── ValidationError
"""


class IngestionError(Exception):
    """Base exception for all ingestion-related errors."""
    pass


class FileError(IngestionError):
    """Base exception for file-related errors."""
    pass


class FileNotFoundError_(FileError):
    """Raised when file path does not exist."""
    pass


class EmptyFileError(FileError):
    """Raised when file is empty or contains only whitespace."""
    pass


class CorruptedFileError(FileError):
    """Base exception for corrupted files."""
    pass


class CorruptedPDFError(CorruptedFileError):
    """Raised when PDF structure is invalid or unreadable."""
    pass


class CorruptedDOCXError(CorruptedFileError):
    """Raised when DOCX structure is invalid or unreadable."""
    pass


class LoaderError(IngestionError):
    """Base exception for loader errors."""
    pass


class UnsupportedFileTypeError(LoaderError):
    """Raised when file extension is not supported."""
    pass


class TextExtractionError(LoaderError):
    """Raised when text extraction from file fails."""
    pass


class EncodingDetectionError(LoaderError):
    """Raised when encoding cannot be detected."""
    pass


class PyTeseractNotInstalledError(LoaderError):
    """Raised when tesseract-ocr is required but not available."""
    pass


class CleaningError(IngestionError):
    """Base exception for text cleaning errors."""
    pass


class EncodingNormalizationError(CleaningError):
    """Raised when encoding normalization fails."""
    pass


class ChunkingError(IngestionError):
    """Base exception for chunking errors."""
    pass


class EmptyDocumentError(ChunkingError):
    """Raised when document text is empty after cleaning."""
    pass


class MetadataExtractionError(ChunkingError):
    """Raised when required metadata cannot be extracted."""
    pass


class TokenCountError(ChunkingError):
    """Raised when token counting fails."""
    pass


class ValidationError(IngestionError):
    """Base exception for validation errors."""
    pass


class InvalidChunkError(ValidationError):
    """Raised when chunk fails validation."""
    pass
