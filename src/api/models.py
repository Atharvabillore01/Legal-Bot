"""
Pydantic request/response models for the FastAPI layer.
"""

from __future__ import annotations
from typing import List, Optional, Literal, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Documents ────────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    jurisdiction: Optional[str]
    authority_level: str
    error_message: Optional[str]
    uploaded_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DeleteDocumentResponse(BaseModel):
    message: str
    document_id: str


# ─── Ingestion ────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    document_id: str
    status: str
    message: str
    filename: str


# ─── Query ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    k: int = Field(default=7, ge=1, le=50)
    jurisdiction: Optional[str] = None
    doc_ids: Optional[List[str]] = None
    detect_contradictions: bool = True
    rerank: bool = True


class CitationOut(BaseModel):
    chunk_id: str
    source_doc: str
    page_number: Optional[int]
    text_excerpt: str
    jurisdiction: Optional[str]
    section: Optional[str]
    character_offset_start: int
    character_offset_end: int


class SourceChunkOut(BaseModel):
    """A retrieved context chunk shown alongside the answer for transparency."""
    chunk_id: str
    doc_name: str
    page_number: Optional[int]
    section: Optional[str]
    jurisdiction: Optional[str]
    text: str
    relevance_score: float
    rank: int


class QueryResponse(BaseModel):
    answer: str
    citations: List[CitationOut]
    source_chunks: List[SourceChunkOut] = []
    confidence_score: float
    confidence_level: Literal["LOW", "MEDIUM", "HIGH"]
    query: str
    search_time_ms: float
    llm_time_ms: float
    total_time_ms: float
    model: str
    created_at: datetime
    has_contradictions: bool


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    id: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    status: str
    latency_ms: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    page: int
    page_size: int


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Error ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None
