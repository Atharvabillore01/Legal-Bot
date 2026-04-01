"""
src/llm/models.py

Pydantic data models for the LLM interface and prompt builder module.

Models represent the interface between retrieval layer (Module 3) and generation layer (Module 4).
All models use Pydantic v2 for validation and serialization.

Classes:
    - Citation: Single citation source for a claim in the response
    - SourceMetadata: Metadata about the source document
    - ConfidenceLevel: Enumeration of confidence levels (LOW, MEDIUM, HIGH)
    - QueryResponse: Complete structured response from LLM query

Data Flow:
    RetrievedChunk (Module 3) → QueryResponse (Module 4)
"""

from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator


class Citation(BaseModel):
    """
    A single citation to a source document within the LLM response.
    
    Fields:
        chunk_id (str): Reference ID for the chunk cited (format: chunk_XXXXXX)
        source_doc (str): Document name (e.g., "indemnity_agreement.pdf")
        page_number (int): Page number where citation appears (1-indexed)
        text_excerpt (str): The exact text cited (max 500 chars)
        character_offset_start (int): Start position in LLM response text
        character_offset_end (int): End position in LLM response text
        jurisdiction (str, optional): Legal jurisdiction of source
        section (str, optional): Section within document cited
    
    Example:
        Citation(
            chunk_id="chunk_15",
            source_doc="indemnity_agreement.pdf",
            page_number=7,
            text_excerpt="The liability cap in Section 10 is USD 5,000,000",
            character_offset_start=234,
            character_offset_end=289,
            jurisdiction="NY",
            section="Sections & Liabilities"
        )
    """
    chunk_id: str = Field(..., description="Reference chunk ID")
    source_doc: str = Field(..., description="Source document name")
    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    text_excerpt: str = Field(..., max_length=500, description="Exact cited text")
    character_offset_start: int = Field(..., ge=0, description="Start position in response")
    character_offset_end: int = Field(..., ge=0, description="End position in response")
    jurisdiction: Optional[str] = Field(None, description="Legal jurisdiction")
    section: Optional[str] = Field(None, description="Document section")

    @validator('character_offset_end')
    def end_after_start(cls, v, values):
        """Ensure end offset is after start offset."""
        if 'character_offset_start' in values and v <= values['character_offset_start']:
            raise ValueError("character_offset_end must be after character_offset_start")
        return v


class SourceMetadata(BaseModel):
    """
    Metadata about a source document.
    
    Fields:
        doc_name (str): Name of the document
        doc_type (str): Type (PDF, DOCX, TXT)
        jurisdiction (str): Legal jurisdiction
        source_authority (str): Authority level (binding, precedent, informational)
        published_date (datetime, optional): When document was published
        section (str, optional): Section within document
    """
    doc_name: str = Field(..., description="Document name")
    doc_type: str = Field(..., description="Document type (PDF, DOCX, TXT)")
    jurisdiction: str = Field(..., description="Legal jurisdiction")
    source_authority: str = Field(..., description="Authority level")
    published_date: Optional[datetime] = Field(None, description="Publication date")
    section: Optional[str] = Field(None, description="Document section")


class ConfidenceLevel(BaseModel):
    """
    Confidence level classification with thresholds and UI guidance.
    
    Fields:
        level (Literal): LOW | MEDIUM | HIGH
        score (float): Numerical confidence [0, 1]
        interpretation (str): Human-readable interpretation
        ui_color (str): Suggested UI color (red, yellow, green)
    """
    level: Literal["LOW", "MEDIUM", "HIGH"] = Field(..., description="Confidence level")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0,1]")
    interpretation: str = Field(..., description="Human-readable interpretation")
    ui_color: str = Field(..., description="Suggested UI color")

    @validator('interpretation')
    def validate_interpretation(cls, v, values):
        """Ensure interpretation matches level."""
        if 'level' in values:
            level = values['level']
            if level == "LOW" and "low" not in v.lower():
                raise ValueError("LOW level must have 'low' in interpretation")
            if level == "MEDIUM" and "medium" not in v.lower():
                raise ValueError("MEDIUM level must have 'medium' in interpretation")
            if level == "HIGH" and "high" not in v.lower():
                raise ValueError("HIGH level must have 'high' in interpretation")
        return v


class QueryResponse(BaseModel):
    """
    Complete structured response from an LLM query.
    
    Represents the final output of the retrieval-generation pipeline.
    Contains the answer, all citations, confidence metrics, and timing information.
    
    Fields:
        answer (str): The LLM-generated answer (may contain inline [[CITE:...]] markers)
        citations (List[Citation]): All sources cited in the answer
        confidence_score (float): Overall confidence [0, 1]
        confidence_level (Literal): LOW | MEDIUM | HIGH
        query (str): The original user query
        search_time_ms (float): Time to retrieve and rerank chunks
        llm_time_ms (float): Time for LLM API call
        created_at (datetime): Timestamp of response generation
        model (str): Model used (e.g., "gpt-4o")
        user_id (str, optional): User who made the query
    
    Example:
        QueryResponse(
            answer="The liability cap in Section 10 is USD 5,000,000 [[CITE:chunk_15]].",
            citations=[
                Citation(
                    chunk_id="chunk_15",
                    source_doc="indemnity_agreement.pdf",
                    page_number=7,
                    text_excerpt="The liability cap in Section 10 is USD 5,000,000",
                    character_offset_start=40,
                    character_offset_end=93
                )
            ],
            confidence_score=0.92,
            confidence_level="HIGH",
            query="What is the liability cap in Section 10?",
            search_time_ms=245,
            llm_time_ms=1320,
            model="gpt-4o"
        )
    """
    answer: str = Field(..., description="LLM-generated answer", min_length=1)
    citations: List[Citation] = Field(default_factory=list, description="List of citations")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence [0,1]")
    confidence_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(..., description="Confidence classification")
    query: str = Field(..., description="Original user query")
    search_time_ms: float = Field(..., ge=0, description="Retrieval time (ms)")
    llm_time_ms: float = Field(..., ge=0, description="LLM API time (ms)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")
    model: str = Field(default="gpt-4o", description="LLM model used")
    user_id: Optional[str] = Field(None, description="User ID (if tracked)")

    @validator('answer')
    def validate_answer_length(cls, v):
        """Ensure answer is not excessively long."""
        if len(v) > 10000:
            raise ValueError("Answer exceeds maximum length of 10000 characters")
        return v

    @validator('citations')
    def validate_citation_count(cls, v):
        """Ensure citation count is reasonable."""
        if len(v) > 100:
            raise ValueError("Citation count exceeds maximum of 100")
        return v

    def confidence_interpretation(self) -> str:
        """Return human-readable interpretation of confidence level."""
        if self.confidence_level == "HIGH":
            return "High confidence - answer is well-supported by sources"
        elif self.confidence_level == "MEDIUM":
            return "Medium confidence - answer has reasonable support"
        else:
            return "Low confidence - limited supporting evidence"

    def total_time_ms(self) -> float:
        """Return total time for entire query processing."""
        return self.search_time_ms + self.llm_time_ms

    def to_json(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "answer": self.answer,
            "citations": [
                {
                    "chunk_id": c.chunk_id,
                    "source_doc": c.source_doc,
                    "page_number": c.page_number,
                    "text_excerpt": c.text_excerpt,
                    "character_offset": {
                        "start": c.character_offset_start,
                        "end": c.character_offset_end
                    },
                    "jurisdiction": c.jurisdiction,
                    "section": c.section
                }
                for c in self.citations
            ],
            "confidence": {
                "score": self.confidence_score,
                "level": self.confidence_level,
                "interpretation": self.confidence_interpretation()
            },
            "query": self.query,
            "timing": {
                "search_ms": self.search_time_ms,
                "llm_ms": self.llm_time_ms,
                "total_ms": self.total_time_ms()
            },
            "model": self.model,
            "timestamp": self.created_at.isoformat()
        }
