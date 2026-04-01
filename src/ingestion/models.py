"""
Pydantic data models for document ingestion pipeline.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
import json


class Chunk(BaseModel):
    """
    A single text chunk ready for embedding.
    
    Represents a semantically meaningful unit extracted from a document,
    with rich metadata for tracking lineage and context.
    """
    
    # Core content
    id: str = Field(
        description="Unique identifier: f'{doc_id}_{chunk_index}'"
    )
    text: str = Field(
        min_length=1, 
        description="Clean chunk text (trimmed, normalized)"
    )
    token_count: int = Field(
        ge=1, 
        description="Token count via tiktoken (approximate, gpt-3.5-turbo encoding)"
    )
    
    # Document lineage
    doc_name: str = Field(
        description="Original filename with extension"
    )
    doc_id: str = Field(
        description="Unique document identifier (UUID)"
    )
    chunk_index: int = Field(
        ge=0, 
        description="0-based chunk sequence number within document"
    )
    
    # Positional metadata
    page_number: Optional[int] = Field(
        ge=1, 
        default=None, 
        description="Page number (PDF/DOCX only, 1-indexed; None for TXT)"
    )
    section: Optional[str] = Field(
        default=None, 
        description="Section heading or document structure context"
    )
    
    # Context metadata
    jurisdiction: Optional[str] = Field(
        default=None, 
        description="Legal jurisdiction (e.g., 'CA', 'NY', 'Federal')"
    )
    upload_timestamp: datetime = Field(
        description="ISO 8601 upload datetime (UTC)"
    )
    user_id: str = Field(
        description="ID of user who uploaded the document"
    )
    
    # Quality indicators
    has_ocr: bool = Field(
        default=False, 
        description="True if text extracted via OCR (indicates scanned content)"
    )
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {datetime: lambda v: v.isoformat()}
        schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000_0",
                "text": "Section 1: Definitions. As used in this Agreement...",
                "token_count": 720,
                "doc_name": "contract.pdf",
                "doc_id": "550e8400-e29b-41d4-a716-446655440000",
                "chunk_index": 0,
                "page_number": 1,
                "section": "Section 1: Definitions",
                "jurisdiction": "California",
                "upload_timestamp": "2026-03-29T14:30:00Z",
                "user_id": "user_123",
                "has_ocr": False
            }
        }
    
    def to_json_string(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json()
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.model_dump()


class Document(BaseModel):
    """
    A parsed document representation before chunking.
    
    Intermediate data structure produced by loaders, ready for cleaning
    and subsequent chunking operations.
    """
    
    doc_id: str = Field(
        description="Unique document identifier (UUID)"
    )
    doc_name: str = Field(
        description="Original filename with extension"
    )
    file_type: str = Field(
        description="File format: 'pdf', 'docx', or 'txt'"
    )
    raw_text: str = Field(
        description="Unprocessed text extracted from file"
    )
    page_count: Optional[int] = Field(
        ge=1,
        default=None,
        description="Number of pages (PDF/DOCX); None for TXT"
    )
    encoding: str = Field(
        default="utf-8",
        description="Text encoding detected/used during loading"
    )
    has_ocr: bool = Field(
        default=False,
        description="True if any page used OCR extraction (PDF only)"
    )
    page_boundaries: Optional[List[int]] = Field(
        default=None,
        description="Character offsets in raw_text where each page starts (index 0 = page 1). PDF only."
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional loader-specific metadata"
    )
    
    class Config:
        """Pydantic configuration."""
        schema_extra = {
            "example": {
                "doc_id": "550e8400-e29b-41d4-a716-446655440000",
                "doc_name": "contract.pdf",
                "file_type": "pdf",
                "raw_text": "This is the full text of the document...",
                "page_count": 5,
                "encoding": "utf-8",
                "has_ocr": False,
                "metadata": {"source": "upload"}
            }
        }


class IngestionRequest(BaseModel):
    """
    Request parameters for document ingestion.
    
    Encapsulates all inputs needed for the ingestion pipeline:
    file location, user context, optional metadata, and processing flags.
    """
    
    file_path: str = Field(
        description="Absolute path to document file (must exist and be readable)"
    )
    user_id: str = Field(
        description="ID of user uploading the document"
    )
    jurisdiction: Optional[str] = Field(
        default=None, 
        description="Legal jurisdiction hint (e.g., 'California', 'New York', 'Federal')"
    )
    custom_metadata: Optional[dict] = Field(
        default_factory=dict, 
        description="Additional application-specific metadata key-value pairs"
    )
    enable_ocr: bool = Field(
        default=True, 
        description="Whether to enable OCR fallback for scanned PDFs"
    )
    chunk_size_tokens: int = Field(
        default=750,
        ge=10,
        description="Target token count per chunk"
    )
    chunk_overlap_tokens: int = Field(
        default=150,
        ge=0,
        le=500,
        description="Token overlap between adjacent chunks"
    )
    
    class Config:
        """Pydantic configuration."""
        schema_extra = {
            "example": {
                "file_path": "/data/contracts/agreement_2026_01.pdf",
                "user_id": "user_123",
                "jurisdiction": "California",
                "custom_metadata": {"department": "legal", "case_id": "2026-001"},
                "enable_ocr": True,
                "chunk_size_tokens": 750,
                "chunk_overlap_tokens": 150
            }
        }


class IngestionResult(BaseModel):
    """Result of a document ingestion operation."""
    
    success: bool = Field(description="Whether ingestion succeeded")
    doc_id: Optional[str] = Field(default=None, description="Document ID if successful")
    chunks: list[Chunk] = Field(default_factory=list, description="List of extracted chunks")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings")
    chunk_count: int = Field(default=0, description="Total number of chunks extracted")
    total_tokens: int = Field(default=0, description="Sum of all chunk tokens")
    
    class Config:
        """Pydantic configuration."""
        schema_extra = {
            "example": {
                "success": True,
                "doc_id": "550e8400-e29b-41d4-a716-446655440000",
                "chunks": [],  # List of Chunk objects
                "error": None,
                "warnings": ["PDF was scanned; OCR was applied to 2 pages"],
                "chunk_count": 7,
                "total_tokens": 5040
            }
        }
