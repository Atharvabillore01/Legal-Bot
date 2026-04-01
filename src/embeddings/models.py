"""
Pydantic data models for embeddings and vector store.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import numpy as np


class EmbeddedChunk(BaseModel):
    """A chunk with computed embedding vector."""
    
    # Original chunk data (from Module 1)
    chunk_id: str = Field(description="Unique chunk identifier (doc_id_chunk_index)")
    text: str = Field(min_length=1, description="Chunk text content")
    token_count: int = Field(ge=1, description="Token count")
    
    # Document metadata
    doc_name: str = Field(description="Original document filename")
    doc_id: str = Field(description="Document ID")
    chunk_index: int = Field(ge=0, description="Chunk sequence number")
    page_number: Optional[int] = Field(default=None, description="Page number if available")
    section: Optional[str] = Field(default=None, description="Section heading")
    jurisdiction: Optional[str] = Field(default=None, description="Legal jurisdiction")
    user_id: str = Field(description="Owning user ID")
    has_ocr: bool = Field(default=False, description="OCR indicator")
    
    # Embedding
    embedding: List[float] = Field(
        description="3072-D embedding vector from text-embedding-3-large"
    )
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="OpenAI embedding model used"
    )
    
    # Metadata
    uploaded_at: str = Field(description="ISO 8601 upload timestamp")
    embedded_at: str = Field(description="ISO 8601 embedding generation timestamp")
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            np.ndarray: lambda v: v.tolist() if isinstance(v, np.ndarray) else v
        }
    
    def to_numpy(self) -> np.ndarray:
        """Convert embedding to numpy array."""
        return np.array(self.embedding, dtype=np.float32)


class MetadataEntry(BaseModel):
    """Single entry in metadata sidecar."""
    
    faiss_id: int = Field(ge=0, description="FAISS integer ID in index")
    chunk_id: str = Field(description="Chunk identifier")
    doc_id: str = Field(description="Document ID")
    doc_name: str = Field(description="Document filename")
    chunk_index: int = Field(ge=0, description="Chunk sequence")
    page_number: Optional[int] = Field(default=None, description="Page number")
    section: Optional[str] = Field(default=None, description="Section heading")
    jurisdiction: Optional[str] = Field(default=None, description="Jurisdiction")
    user_id: str = Field(description="Owning user ID")
    has_ocr: bool = Field(default=False, description="OCR indicator")
    token_count: int = Field(ge=1, description="Token count")
    uploaded_at: str = Field(description="Upload timestamp")
    embedded_at: str = Field(description="Embedding timestamp")
    text_checksum: str = Field(description="MD5 checksum of chunk text for integrity")
    text_length: int = Field(ge=1, description="Length of chunk text")
    text: Optional[str] = Field(default=None, description="Full chunk text content")


class UserIndex(BaseModel):
    """Metadata about a user's FAISS index."""
    
    user_id: str = Field(description="Index owner user ID")
    index_type: str = Field(
        description="Type: 'flat' (IndexFlatL2) or 'ivf' (IndexIVFFlat)"
    )
    embedding_dimension: int = Field(
        default=3072,
        description="Vector dimensionality"
    )
    chunk_count: int = Field(
        ge=0,
        default=0,
        description="Number of chunks in index"
    )
    created_at: str = Field(description="Index creation timestamp")
    last_modified: str = Field(description="Last modification timestamp")
    last_backup: Optional[str] = Field(default=None, description="Last backup timestamp")
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Underlying embedding model"
    )
    checksum: str = Field(
        description="SHA256 checksum of index file (for integrity verification)"
    )
    metadata_version: int = Field(
        default=1,
        description="Metadata schema version"
    )
    notes: Optional[str] = Field(default=None, description="Optional notes/tags")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user_123",
                "index_type": "flat",
                "embedding_dimension": 3072,
                "chunk_count": 150,
                "created_at": "2026-03-29T10:00:00Z",
                "last_modified": "2026-03-29T14:30:00Z",
                "last_backup": "2026-03-29T14:00:00Z",
                "embedding_model": "text-embedding-3-large",
                "checksum": "sha256:abc123def456...",
                "metadata_version": 1,
                "notes": "Legal document collection"
            }
        }


class EmbeddingBatch(BaseModel):
    """A batch of chunks ready for embedding."""
    
    batch_id: str = Field(description="Unique batch identifier")
    chunk_ids: List[str] = Field(description="List of chunk IDs in batch")
    texts: List[str] = Field(description="List of texts to embed")
    batch_size: int = Field(ge=1, description="Number of items in batch")
    
    class Config:
        json_encoders = {list: lambda v: v}


class RetrievalResult(BaseModel):
    """Result of a vector search query."""
    
    chunk_id: str = Field(description="Retrieved chunk ID")
    text: str = Field(description="Chunk text content")
    doc_name: str = Field(description="Source document name")
    doc_id: str = Field(description="Source document ID")
    chunk_index: int = Field(description="Position in document")
    page_number: Optional[int] = Field(default=None, description="Page number")
    section: Optional[str] = Field(default=None, description="Section heading")
    jurisdiction: Optional[str] = Field(default=None, description="Jurisdiction")
    distance: float = Field(description="L2 distance from query (lower = more similar)")
    similarity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized similarity [0, 1] (higher = more similar)"
    )
    token_count: int = Field(description="Chunk token count")
    has_ocr: bool = Field(default=False, description="OCR indicator")
    
    class Config:
        schema_extra = {
            "example": {
                "chunk_id": "doc1_5",
                "text": "Article 1: Definitions. As used in this Agreement...",
                "doc_name": "contract.pdf",
                "doc_id": "550e8400-e29b-41d4-a716-446655440000",
                "chunk_index": 5,
                "page_number": 2,
                "section": "Article 1: Definitions",
                "jurisdiction": "California",
                "distance": 0.234,
                "similarity_score": 0.876,
                "token_count": 720,
                "has_ocr": False
            }
        }


class BackupInfo(BaseModel):
    """Information about an index backup."""
    
    backup_timestamp: str = Field(description="Backup creation timestamp")
    description: Optional[str] = Field(default=None, description="Backup description")
    chunk_count: int = Field(description="Number of chunks in backup")
    size_mb: float = Field(ge=0, description="Backup size in MB")
    checksum: str = Field(description="Checksum for integrity verification")
    integrity_status: str = Field(
        description="Verification status: 'verified', 'unverified', 'corrupted'"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "backup_timestamp": "2026-03-29T14:00:00Z",
                "description": "Pre-bulk-add checkpoint",
                "chunk_count": 150,
                "size_mb": 12.5,
                "checksum": "sha256:abc123...",
                "integrity_status": "verified"
            }
        }
