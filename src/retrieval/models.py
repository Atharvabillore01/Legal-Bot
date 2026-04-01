"""
src/retrieval/models.py

Pydantic data models for the retrieval and reranking module.

Exports:
    - RetrievedChunk: Output model with full provenance and scores
    - ContradictionInfo: Details about detected conflicts
    - SearchFilter: Filtering criteria
    - DateRange: Date range specification
    - SearchOptions: Configuration for a retrieval request
    - RetrievalResult: Wrapper for retrieval response
    - SemanticResult: Internal FAISS search result
    - KeywordResult: Internal BM25 search result
    - HybridResult: Internal merged score result
    - ExtractedValues: Values extracted by contradiction detector
    - ContradictionScore: Scored contradiction details
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ContradictionInfo(BaseModel):
    """Details about a contradiction detected between chunks."""
    
    conflicting_chunk_id: str                          # Other chunk with conflict
    conflicting_doc_name: str
    conflict_type: str = Field(
        ..., pattern="^(value_mismatch|clause_conflict|temporal_conflict)$"
    )
    clause_name: str                                   # "Liability Cap"
    value_my: str                                      # "5,000,000"
    value_other: str                                   # "2,000,000"
    severity: str = Field(
        ..., pattern="^(low|medium|high)$"
    )
    resolution: str = Field(
        default="manual_review",
        pattern="^(prefer_newer|prefer_binding|manual_review)$"
    )
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "conflicting_chunk_id": "doc_2_chunk_5",
                "conflicting_doc_name": "contract_B.pdf",
                "conflict_type": "value_mismatch",
                "clause_name": "Liability Cap",
                "value_my": "5,000,000",
                "value_other": "2,000,000",
                "severity": "high",
                "resolution": "prefer_newer",
                "detected_at": "2026-03-29T15:30:00Z"
            }
        }


class RetrievedChunk(BaseModel):
    """Single retrieved and ranked chunk with full provenance and scoring."""
    
    # Identity
    chunk_id: str                                      # "doc_5_chunk_12"
    doc_id: str                                        # UUID
    doc_name: str                                      # "contract_A.pdf"
    chunk_index: int                                   # Position in document
    
    # Content
    text: str                                          # Actual chunk text
    section: str                                       # "Article 5: Liability"
    
    # Metadata
    page_number: int
    jurisdiction: str
    doc_uploaded_at: datetime
    doc_last_modified: datetime
    doc_authority_level: str = Field(
        default="reference",
        pattern="^(binding|precedent|reference)$"
    )
    
    # Scoring
    semantic_score: float = Field(..., ge=0, le=1)     # [0, 1]
    keyword_score: float = Field(..., ge=0, le=1)      # [0, 1]
    hybrid_score: float = Field(..., ge=0, le=1)       # [0, 1]
    final_rank_score: float = Field(..., ge=0, le=1)   # [0, 1]
    rank_position: int = Field(..., ge=1)              # 1-N
    
    # Contradiction Detection
    has_contradictions: bool = False
    contradictions: List[ContradictionInfo] = Field(default_factory=list)
    conflict_severity: str = Field(
        default="low",
        pattern="^(low|medium|high)$"
    )
    
    # Explainability
    match_highlights: List[str] = Field(default_factory=list)
    retrieval_method: str = Field(
        default="semantic",
        pattern="^(semantic|hybrid|keyword)$"
    )
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    
    # Timestamps
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    reranked_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "contract_1_0",
                "doc_id": "550e8400-e29b-41d4-a716-446655440000",
                "doc_name": "service_agreement.pdf",
                "chunk_index": 0,
                "text": "Article 1: Definitions. Customer means...",
                "section": "Article 1",
                "page_number": 1,
                "jurisdiction": "California",
                "doc_uploaded_at": "2026-03-29T10:00:00Z",
                "doc_last_modified": "2026-03-29T10:00:00Z",
                "doc_authority_level": "binding",
                "semantic_score": 0.85,
                "keyword_score": 0.60,
                "hybrid_score": 0.775,
                "final_rank_score": 0.969,
                "rank_position": 1,
                "has_contradictions": False,
                "contradictions": [],
                "conflict_severity": "low",
                "match_highlights": ["liability", "definitions"],
                "retrieval_method": "hybrid",
                "confidence_score": 0.92,
                "retrieved_at": "2026-03-29T15:30:00Z",
                "reranked_at": "2026-03-29T15:30:01Z"
            }
        }


class DateRange(BaseModel):
    """Date range for filtering."""
    
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    
    @field_validator('date_to')
    def validate_date_range(cls, v, info):
        if v and 'date_from' in info.data and info.data['date_from']:
            if v < info.data['date_from']:
                raise ValueError('date_to must be >= date_from')
        return v


class SearchFilter(BaseModel):
    """Optional filtering criteria applied after retrieval."""
    
    jurisdictions: Optional[List[str]] = None         # ["California", "NY"]
    doc_names: Optional[List[str]] = None             # ["contract_A.pdf"]
    doc_ids: Optional[List[str]] = None               # Specific documents
    date_range: Optional[DateRange] = None            # from/to dates
    authority_levels: Optional[List[str]] = None      # ["binding", "precedent"]
    exclude_overlapping: bool = False                 # Exclude same-doc chunks
    min_confidence: float = Field(default=0.0, ge=0, le=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "jurisdictions": ["California"],
                "doc_names": None,
                "doc_ids": None,
                "date_range": {
                    "date_from": "2020-01-01T00:00:00Z",
                    "date_to": None
                },
                "authority_levels": ["binding", "precedent"],
                "exclude_overlapping": True,
                "min_confidence": 0.6
            }
        }


class SearchOptions(BaseModel):
    """Configuration for a single search request."""
    
    k: int = Field(default=7, ge=1, le=50)            # Top-K results
    use_semantic: bool = True                          # Enable FAISS
    use_keyword: bool = False                          # Enable BM25
    hybrid_alpha: float = Field(default=0.7, ge=0, le=1)  # Semantic weight
    filters: Optional[SearchFilter] = None            # Post-retrieval filtering
    detect_contradictions: bool = True                # Run contradiction detection
    rerank: bool = True                               # Apply reranking
    return_all_matches: bool = False                  # Return <7 if fewer found
    explain_scores: bool = False                      # Include score breakdowns
    
    @field_validator('k')
    def validate_k(cls, v):
        if v < 1 or v > 50:
            raise ValueError('k must be 1-50')
        return v
    
    @field_validator('hybrid_alpha')
    def validate_alpha(cls, v):
        if v < 0 or v > 1:
            raise ValueError('hybrid_alpha must be 0-1')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "k": 7,
                "use_semantic": True,
                "use_keyword": False,
                "hybrid_alpha": 0.7,
                "filters": None,
                "detect_contradictions": True,
                "rerank": True,
                "return_all_matches": False,
                "explain_scores": False
            }
        }


class RetrievalResult(BaseModel):
    """Wrapper for retrieval response."""
    
    query: str                                         # Original query
    results: List[RetrievedChunk]                     # Top-K results
    result_count: int                                  # Number of results
    covered_docs: int                                  # Unique docs in results
    has_contradictions: bool = False                  # Any conflicts found
    execution_time_ms: float = Field(..., ge=0)      # Total latency
    fallback_applied: bool = False                    # True if <k results
    fallback_reason: Optional[str] = None             # Why fallback triggered
    search_method: str = Field(                       # "semantic" | "hybrid"
        default="semantic",
        pattern="^(semantic|hybrid|keyword)$"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "liability caps",
                "results": [],
                "result_count": 7,
                "covered_docs": 5,
                "has_contradictions": False,
                "execution_time_ms": 145.3,
                "fallback_applied": False,
                "fallback_reason": None,
                "search_method": "semantic"
            }
        }


# Internal models (not exposed to users)

class SemanticResult(BaseModel):
    """Internal FAISS search result."""
    
    chunk_id: str
    doc_id: str
    faiss_id: int                                      # FAISS integer ID
    l2_distance: float                                 # Raw FAISS output
    semantic_score: float = Field(ge=0, le=1)


class KeywordResult(BaseModel):
    """Internal BM25 search result."""
    
    chunk_id: str
    doc_id: str
    text: str
    keyword_score: float = Field(ge=0, le=1)          # BM25 normalized
    matched_terms: List[str] = Field(default_factory=list)
    match_positions: List[int] = Field(default_factory=list)


class HybridResult(BaseModel):
    """Internal merged score result."""
    
    chunk_id: str
    doc_id: str
    semantic_score: float = Field(ge=0, le=1)         # 0 if keyword-only
    keyword_score: float = Field(ge=0, le=1)          # 0 if semantic-only
    hybrid_score: float = Field(ge=0, le=1)           # Weighted merge
    merge_method: str = Field(                        # "both", "semantic_only", etc.
        pattern="^(both|semantic_only|keyword_only)$"
    )


class ExtractedValues(BaseModel):
    """Values extracted by contradiction detector."""
    
    clause_name: str
    values: List[str]                                  # Raw extracted values
    value_types: List[str]                             # ["monetary", "percentage"]
    normalized: Optional[float] = None                 # Numeric representation
    confidence: float = Field(ge=0, le=1)
    ambiguous: bool = False                            # Multi-value interpretation
    extraction_method: str = Field(                    # "regex", "ml_model", etc.
        pattern="^(regex|ml_model|fuzzy)$"
    )


class ContradictionScore(BaseModel):
    """Scored contradiction details."""
    
    diff_score: float = Field(ge=0, le=1)              # Magnitude of difference
    conflict_confidence: float = Field(ge=0, le=1)     # Confidence in conflict
    severity: str = Field(pattern="^(low|medium|high)$")
    resolution_preference: str = Field(
        pattern="^(prefer_newer|prefer_binding|manual_review)$"
    )
    explanation: str                                    # Human-readable explanation
