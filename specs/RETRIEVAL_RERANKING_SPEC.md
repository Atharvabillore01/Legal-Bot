# Module 3: Retrieval & Reranking

**Legal RAG System | Technical Specification**

**Version**: 1.0  
**Date**: March 29, 2026  
**Status**: Complete Specification  
**Audience**: Engineers, Architects, QA

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Data Models](#3-data-models)
4. [Function Contracts](#4-function-contracts)
5. [Semantic Search Layer](#5-semantic-search-layer)
6. [Metadata Filtering](#6-metadata-filtering)
7. [Hybrid Search (Semantic + BM25)](#7-hybrid-search-semantic--bm25)
8. [Contradiction Detection](#8-contradiction-detection)
9. [Reranking Strategy](#9-reranking-strategy)
10. [Fallback & Error Handling](#10-fallback--error-handling)
11. [Configuration & Constants](#11-configuration--constants)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Edge Cases & Decision Table](#13-edge-cases--decision-table)

---

## 1. Overview & Goals

### Purpose

Module 3 provides intelligent retrieval and reranking of legal document chunks from a FAISS vector index. It extends the vector search capabilities of Module 2 with:

- **Semantic search**: Top-7 cosine similarity search via FAISS
- **Metadata filtering**: Post-retrieval filtering by jurisdiction, doc_name, date_range
- **Hybrid search**: Weighted combination of semantic (FAISS) + keyword (BM25) scoring
- **Contradiction detection**: Identify conflicting clauses across chunks
- **Intelligent reranking**: Prefer recent, authoritative, and non-contradictory results

### User Stories

1. **Enterprise Legal Team**: Query contract library → retrieve top 7 semantically similar clauses → filter by jurisdiction → identify contradictions → present ranked results with confidence scores

2. **Compliance Officer**: Search for "indemnification clauses" → hybrid search combines semantic relevance ("loss of profits") + exact keyword matches ("indemnify") → reranked by recency and authority level

3. **Due Diligence**: Find liability caps across 50 contracts → detect when same clause has conflicting values → surface most recent/binding version → flag for manual review

### Success Criteria

- **Retrieval Latency**: <200ms for top-7 semantic search
- **Reranking Latency**: <100ms for contradiction detection + reranking
- **Accuracy**: Contradiction detection ≥95% F1-score (manual validation on 100 samples)
- **Hybrid Search Coverage**: ≥80% retrieval recall with BM25 + semantic
- **Contradiction Clarity**: Clearly flag contradictions with confidence score + evidence

---

## 2. Architecture & Data Flow

### 2.1 Retrieval Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                       USER QUERY                                     │
│                    "liability caps"                                  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
    ┌───▼─────┐                          ┌───▼─────┐
    │ SEMANTIC│                          │ KEYWORD │
    │ SEARCH  │                          │ SEARCH  │
    └───┬─────┘                          └───┬─────┘
        │                                     │
    ┌───▼──────────────────┐          ┌──────▼────────┐
    │ FAISS Top-K (k=50)   │          │ BM25 Top-K    │
    │ cosine distance      │          │ TF-IDF + term │
    │ knn = 50             │          │ frequency     │
    └───┬──────────────────┘          └──────┬────────┘
        │                                     │
        └──────────────────┬──────────────────┘
                           │
                      ┌────▼─────┐
                      │  MERGE   │
                      │ SCORES   │
                      │ (if hybrid)
                      └────┬─────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
    ┌───▼──────────────────┐          ┌──────▼────────┐
    │ METADATA FILTERING   │          │ DEDUPLICATION │
    │ - jurisdiction       │          │ - same doc    │
    │ - doc_name           │          │ - same chunk  │
    │ - date_range         │          │ - same text   │
    └───┬──────────────────┘          └──────┬────────┘
        │                                     │
        └──────────────────┬──────────────────┘
                           │
                    ┌──────▼─────────┐
                    │ CONTRADICTION  │
                    │ DETECTION      │
                    │ - text parsing │
                    │ - clause match │
                    │ - value diff   │
                    └──────┬─────────┘
                           │
                    ┌──────▼──────────┐
                    │ RERANKING       │
                    │ - recent bias  │
                    │ - authority    │
                    │ - no conflict  │
                    │ - final score  │
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────┐
                    │ SELECT TOP-7    │
                    │ RetrievedChunk  │
                    │ objects         │
                    └──────┬──────────┘
                           │
            ┌──────────────┴──────────────┐
         ┌──▼──┐                      ┌──▼──┐
         │ <7  │ Return all          │ ≥7  │ Return top-7
         └─────┘ (fallback)           └─────┘
                 + explanation
```

### 2.2 Key Stages

| Stage | Input | Processing | Output | Latency SLA |
|-------|-------|-----------|--------|------------|
| **Semantic Search** | Query (str) + user_id | FAISS cosine knn | 50 results + distances | <50ms |
| **Keyword Search** | Query (str) | BM25 scoring | Top results + TF-IDF | <30ms |
| **Score Merge** | Semantic + keyword scores | Weighted average | Hybrid scores | <10ms |
| **Metadata Filter** | Results + filters (optional) | Field matching | Filtered results | <20ms |
| **Contradiction Detection** | Chunk pairs | NLP parsing + value diff | Conflict matrix | <60ms |
| **Reranking** | Chunks + conflicts + metadata | Authority + recency weights | Final scores | <30ms |
| **Top-K Selection** | All processed chunks | Sort by score | Top-7 RetrievedChunk | <5ms |
| **Total E2E** | - | - | **RetrievedChunk list** | **<200ms** |

---

## 3. Data Models

### 3.1 RetrievedChunk (Output)

```python
class RetrievedChunk(BaseModel):
    """
    Single retrieved and ranked chunk with full provenance and scoring.
    """
    
    # Identity
    chunk_id: str                           # "doc_5_chunk_12"
    doc_id: str                             # "550e8400-e29b-41d4-a716-446655440000"
    doc_name: str                           # "contract_A.pdf"
    chunk_index: int                        # 12
    
    # Content
    text: str                               # Actual chunk text
    section: str                            # "Article 5: Liability"
    
    # Metadata
    page_number: int                        # 5
    jurisdiction: str                       # "California"
    doc_uploaded_at: datetime               # ISO timestamp
    doc_last_modified: datetime             # ISO timestamp when chunked/updated
    doc_authority_level: str                # "binding" | "precedent" | "reference"
    
    # Scoring
    semantic_score: float                   # [0, 1] cosine similarity
    keyword_score: float                    # [0, 1] BM25 TF-IDF normalized
    hybrid_score: float                     # [0, 1] weighted merge of above
    final_rank_score: float                 # [0, 1] after reranking adjustments
    rank_position: int                      # 1-7 (or >7 if fallback)
    
    # Contradiction Detection
    has_contradictions: bool                # True if conflicts detected
    contradictions: List[ContradictionInfo] # Details of conflicts
    conflict_severity: str                  # "low" | "medium" | "high"
    
    # Explainability
    match_highlights: List[str]             # ["liability", "caps", "5000000"]
    retrieval_method: str                   # "semantic" | "hybrid" | "keyword"
    confidence_score: float                 # [0, 1] overall confidence
    
    # Timestamps
    retrieved_at: datetime                  # When this was retrieved
    reranked_at: datetime                   # When reranking was applied

class ContradictionInfo(BaseModel):
    """
    Details about a contradiction detected between chunks.
    """
    
    conflicting_chunk_id: str               # Other chunk with conflict
    conflicting_doc_name: str
    conflict_type: str                      # "value_mismatch" | "clause_conflict" | "temporal_conflict"
    clause_name: str                        # "Liability Cap"
    value_my: str                           # "5,000,000"
    value_other: str                        # "2,000,000"
    severity: str                           # "low" | "medium" | "high"
    resolution: str                         # "prefer_newer" | "prefer_binding" | "manual_review"
    detected_at: datetime

class SearchFilter(BaseModel):
    """
    Optional filtering criteria applied after retrieval.
    """
    
    jurisdictions: Optional[List[str]] = None           # ["California", "NY"]
    doc_names: Optional[List[str]] = None               # ["contract_A.pdf"]
    doc_ids: Optional[List[str]] = None                 # Specific documents
    date_range: Optional[DateRange] = None              # from/to dates
    authority_levels: Optional[List[str]] = None        # ["binding", "precedent"]
    exclude_overlapping: bool = False                   # Exclude same-doc chunks
    min_confidence: float = 0.0                         # [0, 1]

class DateRange(BaseModel):
    """Date range for filtering."""
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class SearchOptions(BaseModel):
    """
    Configuration for a single search request.
    """
    
    k: int = 7                              # Top-K results (max 50)
    use_semantic: bool = True               # Enable FAISS cosine search
    use_keyword: bool = False               # Enable BM25 search
    hybrid_alpha: float = 0.7               # [0, 1] weight for semantic
    filters: Optional[SearchFilter] = None  # Post-retrieval filtering
    detect_contradictions: bool = True      # Run contradiction detection
    rerank: bool = True                     # Apply reranking
    return_all_matches: bool = False        # Return <7 if fewer found
    explain_scores: bool = False            # Include score breakdowns

class RetrievalResult(BaseModel):
    """Wrapper for retrieval response."""
    
    query: str                              # Original query
    results: List[RetrievedChunk]          # Top-K results
    result_count: int                       # Number of results
    covered_docs: int                       # Unique docs in results
    has_contradictions: bool                # Any conflicts found
    execution_time_ms: float                # Total latency
    fallback_applied: bool                  # True if <7 results
    fallback_reason: Optional[str]          # Why fallback triggered
    search_method: str                      # "semantic" | "hybrid" | "keyword"

---

## 4. Function Contracts

### High-Level API

```python
# MAIN ENTRY POINT
def retrieve_and_rerank(
    user_id: str,
    query: str,
    options: SearchOptions = SearchOptions(),
) -> RetrievalResult:
    """
    Complete retrieval and reranking pipeline.
    
    Pipeline:
    1. Parse query and validate
    2. Generate query embedding (via Module 2 embedder)
    3. Execute semantic search (FAISS)
    4. Optionally execute keyword search (BM25)
    5. Merge scores if hybrid
    6. Apply metadata filters
    7. Detect contradictions
    8. Rerank results
    9. Select top-K
    10. Return RetrievalResult
    
    Args:
        user_id: User ID for accessing FAISS index
        query: Natural language query
        options: SearchOptions with k, filters, flags
    
    Returns:
        RetrievalResult with ranked RetrievedChunk list
    
    Raises:
        UserIndexNotFound: No index for user_id
        InvalidQueryError: Query is empty or invalid
        SearchTimeoutError: Search exceeded time budget
        RerankerError: Reranking failed
    
    Latency: <200ms (50ms semantic + 30ms BM25 + 20ms filter + 60ms rerank + 30ms merge)
    Cost: 1x OpenAI embedding call for query (varies by query length)
    
    Example:
        >>> result = retrieve_and_rerank(
        ...     user_id="user_123",
        ...     query="What are liability caps?",
        ...     options=SearchOptions(k=7, use_semantic=True, detect_contradictions=True)
        ... )
        >>> for chunk in result.results:
        ...     print(f"{chunk.rank_position}. {chunk.final_rank_score:.2%}: {chunk.text[:60]}")
    """
```

---

## 5. Semantic Search Layer

### 5.1 FAISS Cosine Similarity

**Algorithm**: L2 Distance → Cosine Similarity Conversion

```python
def semantic_search(
    user_id: str,
    query_embedding: np.ndarray,  # 3072-D from Module 2
    k: int = 50,
    threshold: float = 1000.0,    # Max L2 distance
) -> List[SemanticResult]:
    """
    Execute FAISS cosine similarity search.
    
    FAISS IndexFlatL2 stores L2 distance.
    Conversion: cosine_sim = 1 / (1 + l2_distance)
    
    Args:
        user_id: Index owner
        query_embedding: 3072-D query vector
        k: Number of results (default 50 for hybrid, override with k=7 for semantic only)
        threshold: Max L2 distance (lower = more similar)
    
    Returns:
        List[SemanticResult] sorted by distance (ascending = most similar first)
        {
            "chunk_id": "doc_5_12",
            "doc_id": "550e8400-...",
            "distance": 0.234,                    # L2 distance (lower = better)
            "similarity_score": 0.810,             # 1/(1+distance)
            "faiss_id": 42
        }
    
    Raises:
        UserIndexNotFound: Index does not exist
        InvalidEmbeddingError: Query embedding is malformed
    
    Latency: <50ms for k=50
    
    Scoring Formula:
        cosine_similarity = 1 / (1 + l2_distance)
        
        Example:
            l2_distance = 0.234
            cosine_sim = 1 / (1 + 0.234) = 0.810
    
    Notes:
        - FAISS IndexFlatL2 returns distances, not similarities
        - Conversion formula accounts for L2 metric properties
        - Results already sorted by distance (closest first)
    """
```

### 5.2 Semantic Score Computation

```python
class SemanticResult(BaseModel):
    chunk_id: str
    doc_id: str
    faiss_id: int
    l2_distance: float                      # Raw FAISS output
    semantic_score: float                   # Normalized [0, 1]
    
def normalize_semantic_score(l2_distance: float) -> float:
    """
    Convert L2 distance to [0, 1] similarity score.
    
    Formula:
        semantic_score = 1 / (1 + l2_distance)
    
    Properties:
        - Monotonic decreasing with distance
        - Range [0, 1]
        - Distance 0 → score 1.0 (identical)
        - Distance ∞ → score 0.0 (completely different)
    
    Examples:
        distance=0.1  → score=0.909
        distance=0.5  → score=0.667
        distance=1.0  → score=0.500
        distance=2.0  → score=0.333
    
    Args:
        l2_distance: L2 distance from FAISS
    
    Returns:
        float in [0, 1]
    """
    return 1.0 / (1.0 + l2_distance)
```

---

## 6. Metadata Filtering

### 6.1 Post-Retrieval Filtering

Applied **after** semantic/keyword search to reduce results:

```python
def apply_metadata_filters(
    chunks: List[SemanticResult],
    filters: SearchFilter,
) -> List[SemanticResult]:
    """
    Filter chunks by metadata criteria (post-retrieval).
    
    Filter Priority (applied in order):
    1. Jurisdictions (if specified)
    2. Document names (if specified)
    3. Document IDs (if specified)
    4. Date range (if specified)
    5. Authority levels (if specified)
    6. Confidence threshold (if specified)
    7. Deduplication (remove same-doc overlaps)
    
    Args:
        chunks: Pre-filtered semantic/keyword results
        filters: SearchFilter with criteria
    
    Returns:
        Filtered chunks list (may be <k)
    
    Raises:
        NoResultsAfterFilteringError: All chunks filtered out
    
    Example Filter Application:
        
        Input: 50 semantic results
        
        1. Filter by jurisdiction=["California", "NY"]
           → Keep only docs with jurisdiction in list
           → Result: 40 chunks
        
        2. Filter by doc_names=["contract_A.pdf"]
           → Keep only from specific document
           → Result: 12 chunks
        
        3. Filter by date_range (after 2023-01-01)
           → Keep only recent documents
           → Result: 10 chunks
        
        4. Filter by authority_levels=["binding"]
           → Keep only binding/authoritative clauses
           → Result: 8 chunks
        
        5. Deduplication: exclude_overlapping=True
           → Remove chunks from same document if >1 per doc
           → Result: 7 chunks (mixed documents)
    
    Fallback: If filtering removes all results, return unfiltered top-K
    """
```

### 6.2 Filter Specification

```python
# Example: Search for liability clauses in California contracts
filter_spec = SearchFilter(
    jurisdictions=["California"],           # Must match jurisdiction field
    doc_names=None,                         # No doc name restriction
    date_range=DateRange(
        date_from=datetime(2020, 1, 1),    # After 2020
        date_to=None                        # No upper limit
    ),
    authority_levels=["binding", "precedent"],  # Prefer authoritative
    exclude_overlapping=True,               # One chunk per document
    min_confidence=0.6                      # Confidence score ≥60%
)

results = retrieve_and_rerank(
    user_id="user_123",
    query="liability caps",
    options=SearchOptions(
        filters=filter_spec,
        k=7
    )
)
```

---

## 7. Hybrid Search (Semantic + BM25)

### 7.1 BM25 Keyword Scoring

For queries with specific legal terms (e.g., "indemnification", "force majeure"):

```python
def keyword_search_bm25(
    user_id: str,
    query: str,
    k: int = 50,
    min_score: float = 0.1,
) -> List[KeywordResult]:
    """
    Execute BM25 (Best Matching 25) keyword search.
    
    BM25 is probabilistic ranking function combining:
    - Term frequency (TF): How often term appears in chunk
    - Inverse document frequency (IDF): How rare the term is
    - Document length normalization: Adjust for chunk length
    
    Implementation:
        - Tokenize query into terms: ["indemnification", "clause"]
        - For each chunk in user's index:
            - Compute BM25 score using TF, IDF, chunk length
            - Store (chunk_id, score)
        - Sort by score (descending)
        - Return top-k
    
    Args:
        user_id: User ID with indexed chunks
        query: Keyword query string
        k: Number of results
        min_score: Minimum score threshold
    
    Returns:
        List[KeywordResult] sorted by score (high to low)
        {
            "chunk_id": "doc_5_12",
            "text": "...",
            "keyword_score": 0.456,  # BM25 normalized to [0, 1]
            "matched_terms": ["indemnification", "clause"]
        }
    
    Raises:
        NoIndexError: User has no index
        InvalidQueryError: Query is empty
    
    Latency: <30ms for k=50 (BM25 is faster than embedding)
    
    BM25 Formula:
        
        For each chunk d and query q:
        
        BM25(D, Q) = Σ(i=1 to n) IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D|/avgdl))
        
        Where:
            qi = i-th query term
            f(qi, D) = frequency of qi in document D
            |D| = length of document D (in words)
            avgdl = average document length in collection
            k1 = term frequency saturation parameter (typically 1.5)
            b = length normalization parameter (typically 0.75)
            IDF(qi) = log((N - n(qi) + 0.5) / (n(qi) + 0.5))
            N = total number of documents
            n(qi) = number of documents containing qi
    
    Example:
        
        Query: "liability cap 5 million"
        
        Chunk A: "Liability cap is USD 5,000,000"
        - TF("liability") = 1, TF("cap") = 1, TF("5") = 1, TF("million") = 1
        - BM25 score = 0.65
        
        Chunk B: "Indemnification and liability limitations, cap at 2 million"
        - NF("liability") = 1, TF("cap") = 1, TF("million") = 1, TF("indemnification") = 1
        - BM25 score = 0.58
        
        Result: Chunk A ranked higher due to exact "5,000,000" match
    
    Notes:
        - BM25 ignores semantic meaning (exact keyword matching)
        - Complements semantic search for specific clauses
        - Can catch exact values/numbers that embeddings may miss
        - Requires pre-built BM25 index from all chunks
    """

class KeywordResult(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    keyword_score: float                    # BM25 normalized to [0, 1]
    matched_terms: List[str]               # ["indemnification", "clause"]
    match_positions: List[int]              # Character positions of matches
```

### 7.2 Hybrid Score Merge

```python
def merge_hybrid_scores(
    semantic_results: List[SemanticResult],
    keyword_results: List[KeywordResult],
    alpha: float = 0.7,  # Weight for semantic (1-alpha for keyword)
) -> List[HybridResult]:
    """
    Merge semantic and keyword scores.
    
    Strategy:
    1. Deduplicate: Find chunks present in both lists (by chunk_id)
    2. For common chunks: weighted average
    3. For semantic-only chunks: keep semantic score (keyword weight = 0)
    4. For keyword-only chunks: keep keyword score (semantic weight = 0)
    5. Sort by merged score
    6. Return top-k
    
    Args:
        semantic_results: FAISS cosine results (with semantic_score)
        keyword_results: BM25 TF-IDF results (with keyword_score)
        alpha: Weight for semantic [0, 1] (typically 0.7)
               Total: semantic_weight + keyword_weight = 1.0
    
    Returns:
        List[HybridResult] sorted by hybrid_score (descending)
    
    Formula (when both present):
        hybrid_score = alpha * semantic_score + (1 - alpha) * keyword_score
    
    Formula (when only one present):
        hybrid_score = available_score
    
    Default weights:
        alpha=0.7  → 70% semantic, 30% keyword
        (Semantic search captures semantic meaning; BM25 catches exact terms)
    
    Example:
        
        Chunk A: semantic=0.85, keyword=0.60
        → hybrid = 0.7 * 0.85 + 0.3 * 0.60 = 0.775
        
        Chunk B: semantic=0.78, keyword=0.90 (exact match on "liability cap")
        → hybrid = 0.7 * 0.78 + 0.3 * 0.90 = 0.816 (bumped up)
        
        Chunk C: semantic=0.55, keyword only
        → hybrid = 0.55 (use keyword score if keyword not available in semantic)
    
    Deduplication Logic:
        
        semantic_ids = {r.chunk_id for r in semantic_results}
        keyword_ids = {r.chunk_id for r in keyword_results}
        
        common_ids = semantic_ids ∩ keyword_ids
        semantic_only = semantic_ids - keyword_ids
        keyword_only = keyword_ids - semantic_ids
        
        For each common chunk:
            hybrid_score = alpha * sem_score + (1-alpha) * kw_score
        
        For semantic_only:
            hybrid_score = sem_score (keyword contributes 0)
        
        For keyword_only:
            hybrid_score = kw_score (semantic contributes 0)
    """

class HybridResult(BaseModel):
    chunk_id: str
    doc_id: str
    semantic_score: float                   # From FAISS (or 0 if keyword-only)
    keyword_score: float                    # From BM25 (or 0 if semantic-only)
    hybrid_score: float                     # Weighted merge
    merge_method: str                       # "both" | "semantic_only" | "keyword_only"
```

---

## 8. Contradiction Detection

### 8.1 Algorithm Overview

Detect when chunks contain conflicting information about the same legal concept.

```python
def detect_contradictions(
    chunks: List[RetrievedChunk],
    user_id: str,
) -> ContradictionMatrix:
    """
    Identify contradictions between chunks (same clause, different values).
    
    Three-stage detection:
    
    Stage 1: CLAUSE MATCHING
        - Extract clause names from text (via NLP/regex)
        - Group chunks by clause name
        - Only compare chunks in same clause group
    
    Stage 2: VALUE EXTRACTION
        - Extract values from clause text using regex patterns
        - Example: "Liability cap is USD 5,000,000" → values=["5000000", "USD"]
        - Handle variations (5M, 5,000,000, 5e6, etc.)
    
    Stage 3: CONFLICT SCORING
        - Compare values: if different → conflict
        - Score conflict severity (low/medium/high) based on:
            - Magnitude of difference
            - Document authority levels
            - Temporal gap (older vs newer)
    
    Args:
        chunks: List of RetrievedChunk to compare
        user_id: For metadata lookup
    
    Returns:
        ContradictionMatrix with:
        {
            "chunk_pair": ("chunk_id_1", "chunk_id_2"),
            "clause_name": "Liability Cap",
            "value_chunk1": "5,000,000",
            "value_chunk2": "2,000,000",
            "conflict_type": "value_mismatch",
            "severity": "high",
            "confidence": 0.95,
            "resolution": "prefer_newer"
        }
    
    Raises:
        ExtractionError: Could not parse chunk text
    
    Latency: <60ms for 50 chunks (<2ms per pair on average)
    
    Notes:
        - Must balance precision (avoid false positives) with recall
        - Focus on high-confidence extractions
        - Flag low-confidence extractions for manual review
    """
```

### 8.2 Contradiction Detection Rules

#### Rule 1: Clause Name Matching

```python
def extract_clause_names(text: str) -> List[str]:
    """
    Extract legal clause names from chunk text.
    
    Patterns (regex):
    1. "Article N:" → "Article N"
    2. "Section N.M:" → "Section N.M"
    3. "\b(Liability|Indemnification|Confidentiality|..." → matched term
    4. "(^|\\n)(\\d+\\.\\d+\\s+[A-Z][^:]*:)" → section heading
    
    Dictionary of known legal clauses:
        - Liability Cap
        - Indemnification
        - Confidentiality
        - Limitation of Liability
        - Force Majeure
        - Termination
        - Dispute Resolution
        - Governing Law
        - Warranties & Representations
        - Limitation Period
        - Breach Remedies
        - ...
    
    Args:
        text: Chunk text
    
    Returns:
        List[str] of extracted clause names
    
    Examples:
        "Article 5: Liability Limitations" → ["Article 5", "Liability"]
        "5.2 Cap on Damages" → ["Section 5.2", "Cap on Damages"]
    """
```

#### Rule 2: Value Extraction

```python
def extract_values(text: str, clause_name: str) -> ExtractedValues:
    """
    Extract numeric/categorical values from clause text.
    
    Pattern-based extraction by clause type:
    
    MONETARY (Liability Cap):
        Regex: r'(USD|EUR|GBP|¥|\$|€)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d+)?)[[:space:]]*(million|thousand|billion|M|K|B)?'
        Examples:
            "USD 5,000,000" → 5000000
            "5M dollars" → 5000000
            "$2.5B" → 2500000000
    
    PERCENTAGE (Liability as % of contract value):
        Regex: r'(\d+(?:\.\d+)?)\s*%'
        Examples:
            "50% of contract value" → 0.50
    
    TEMPORAL (Survival period, limitation period):
        Regex: r'(\d+)\s*(year|month|day|week)s?'
        Examples:
            "3 years" → PT3Y
            "30 days" → P30D
    
    CATEGORICAL (Governing law):
        Regex: r'(?:governed|law|state|jurisdiction).*?(California|New York|Delaware|...)'
        Examples:
            "Governed by California law" → "California"
    
    Args:
        text: Clause text
        clause_name: Type of clause (affects which patterns to use)
    
    Returns:
        ExtractedValues
        {
            "clause_name": "Liability Cap",
            "values": ["5000000", "USD"],
            "value_types": ["monetary", "currency"],
            "confidence": 0.95,
            "normalized": 5000000 (numeric representation)
        }
    
    Confidence scoring:
        - Exact match of known pattern: 0.95+
        - Partial match / single occurrence: 0.70-0.95
        - Ambiguous or multiple values: 0.50-0.70
        - No value found: 0.0
    
    Notes:
        - Return both raw and normalized representations
        - Include confidence scores
        - Flag ambiguous extractions (e.g., "between 1 and 10 million")
    """

class ExtractedValues(BaseModel):
    clause_name: str
    values: List[str]                      # Raw extracted values
    value_types: List[str]                 # ["monetary", "percentage", "temporal"]
    normalized: Optional[float] = None     # Numeric representation if applicable
    confidence: float                      # [0, 1]
    ambiguous: bool = False                # True if multiple values found
    extraction_method: str                 # "regex" | "ml_model" | "fuzzy"
```

#### Rule 3: Conflict Scoring

```python
def score_contradiction(
    value1: ExtractedValues,
    value2: ExtractedValues,
    chunk1_metadata: dict,  # doc_authority_level, doc_uploaded_at, etc.
    chunk2_metadata: dict,
) -> ContradictionScore:
    """
    Score the severity and confidence of a contradiction.
    
    Scoring formula:
    
    1. VALUE DIFFERENCE SCORE
        - If values identical → diff_score = 0 (no conflict)
        - If values differ:
            - For numeric: diff_score = |value1 - value2| / max(value1, value2)
            - For categorical: diff_score = 1.0 (different = conflict)
            - For temporal: diff_score = duration_difference / max_duration
        
        - Interpretation:
            - diff_score < 0.05 → negligible (0.1-0.2 rounding variation)
            - 0.05-0.2 → low conflict (minor variation, e.g., 5% difference)
            - 0.2-0.5 → medium conflict (significant, e.g., 30% difference)
            - >0.5 → high conflict (major difference, e.g., 100% or opposite)
    
    2. AUTHORITY WEIGHT
        - binding > precedent > reference
        - If both chunks have same authority: equal weight
        - If different: prefer higher authority document
        - authority_weight: higher_authority_level - lower_authority_level
    
    3. RECENCY WEIGHT
        - Newer document preferred (more recent overrides older)
        - recency_weight = max(0, 1 - days_difference / 365)
        - If <1 year apart: recency_weight ≈ 1.0
        - If >1 year apart: recency_weight decays linearly
    
    4. EXTRACTION CONFIDENCE
        - Both values extracted with high confidence → trust result
        - If either value low confidence → lower conflict score
        - conflict_confidence = min(conf1, conf2)
    
    Final score:
        contradiction_score = diff_score * conflict_confidence * (1 - authority_weight)
        severity = classify(contradiction_score):
            - <0.2 → "low"
            - 0.2-0.6 → "medium"
            - >0.6 → "high"
    
    Args:
        value1, value2: Extracted values from two chunks
        chunk1_metadata, chunk2_metadata: Metadata for authority/recency
    
    Returns:
        ContradictionScore
        {
            "diff_score": 0.80,              # 80% different
            "conflict_confidence": 0.92,    # 92% confident
            "severity": "high",
            "resolution_preference": "prefer_newer",
            "explanation": "Liability cap differs by 60% (5M vs 2M); newer doc overrides"
        }
    
    Examples:
        
        Example 1: Value mismatch (neutral resolution)
        value1 = 5000000, confidence=0.95
        value2 = 2000000, confidence=0.95
        diff_score = |5M - 2M| / 5M = 0.60
        conflict_confidence = min(0.95, 0.95) = 0.95
        severity = "high"
        resolution = "prefer_newer" (check doc dates)
        
        Example 2: Rounding variation (low severity)
        value1 = 5000000, confidence=0.95
        value2 = 5000001, confidence=0.95
        diff_score = 1 / 5000000 = 0.0002
        conflict_confidence = 0.95
        severity = "low" (negligible difference)
        explanation = "Essentially same value (rounding variation)"
        
        Example 3: Authority override
        chunk1: "5M cap", binding, 2025
        chunk2: "2M cap", reference, 2023
        contradiction_score = 0.60 * 0.95 * 0.5 = 0.285 → "medium"
        resolution = "prefer_binding" (binding document overrides)
    
    Notes:
        - Return both score and human-readable explanation
        - Provide resolution suggestion (manual review if ambiguous)
        - Consider temporal and authority context, not just values
    """

class ContradictionScore(BaseModel):
    diff_score: float                       # [0, 1] magnitude of difference
    conflict_confidence: float              # [0, 1] confidence in contradiction
    severity: str                           # "low" | "medium" | "high"
    resolution_preference: str              # "prefer_newer" | "prefer_binding" | "manual_review"
    explanation: str                        # Human-readable explanation
```

---

## 9. Reranking Strategy

### 9.1 Reranking Algorithm

Apply adjustments to scores based on contradictions, authority, and recency.

```python
def rerank_chunks(
    chunks: List[RetrievedChunk],
    contradiction_matrix: ContradictionMatrix,
) -> List[RetrievedChunk]:
    """
    Adjust scores based on contradictions, authority, and recency.
    
    Reranking pipeline:
    
    Stage 1: CONFLICT PENALTY
        For each chunk:
            - Count contradictions it has
            - severity_penalties = sum of conflict severities
            - conflict_penalty_score = 1.0 - (severity_penalties * 0.15)
            - (Each conflict reduces score by up to 15%)
    
    Stage 2: AUTHORITY BOOST
        For each chunk:
            - if authority_level == "binding" → boost +0.10
            - elif authority_level == "precedent" → boost +0.05
            - else → no boost
    
    Stage 3: RECENCY BOOST
        For each chunk:
            - age_days = days since doc_uploaded_at
            - recency_boost = max(0, (365 - age_days) / 3650)
            - (Max 10% boost for documents <1 year old)
            - (Decays to 0 for documents >10 years old)
    
    Stage 4: UNIQUENESS BOOST
        For each chunk:
            - If it's the only result from its document: boost +0.05
            - (Encourage diverse document coverage)
    
    Stage 5: FINAL SCORE COMPUTATION
        final_score = base_score * conflict_penalty * (1 + authority_boost + recency_boost + uniqueness_boost)
        final_score = min(1.0, final_score)  # Clamp to [0, 1]
    
    Args:
        chunks: Pre-ranked chunks with base scores
        contradiction_matrix: Results from detect_contradictions()
    
    Returns:
        List[RetrievedChunk] with updated final_rank_score and rank_position
    
    Latency: <30ms for 50 chunks
    
    Example (Reranking Application):
    
        Before Reranking:
        1. Chunk A: semantic=0.85, keyword=0.60, hybrid=0.775
           - Authority: binding
           - Age: 30 days
           - Contradictions: 0
        
        2. Chunk B: semantic=0.80, keyword=0.90, hybrid=0.816
           - Authority: reference
           - Age: 500 days
           - Contradictions: 1 (medium severity vs Chunk A)
        
        Reranking Adjustments:
        
        Chunk A:
            - conflict_penalty = 1.0 (no conflicts)
            - authority_boost = +0.10 (binding)
            - recency_boost = +0.10 (30 days old)
            - uniqueness_boost = +0.05
            - final_score = 0.775 * 1.0 * (1 + 0.25) = 0.969
        
        Chunk B:
            - conflict_penalty = 1.0 - (0.5 * 0.15) = 0.925 (medium conflict)
            - authority_boost = 0 (reference)
            - recency_boost = 0 (500 days, decayed)
            - uniqueness_boost = 0 (already have Chunk A from same doc)
            - final_score = 0.816 * 0.925 * 1.0 = 0.755
        
        After Reranking:
        1. Chunk A: score=0.969 (boosted by authority + recency)
        2. Chunk B: score=0.755 (penalized by conflicts + age)
        
        ✓ Chunk A now correctly ranked #1 (more reliable, no conflicts)
    """
```

### 9.2 Reranking Decision Table

| Scenario | Conflict? | Authority | Age | Decision | Score Adjustment |
|----------|-----------|-----------|-----|----------|------------------|
| **High semantic, no conflicts, binding** | No | Binding | <6mo | Rank at top | +0.25 (boost 25%) |
| **High semantic, contradictions, reference** | Yes | Reference | >2yr | Rank lower | -0.15 (penalty 15%) |
| **Medium semantic, sole result from doc** | No | Precedent | 1yr | Rank up | +0.10 (boost 10%) |
| **Low semantic, high keyword match, exact term** | No | Binding | Recent | Rank up | +0.15 |
| **Detects value mismatch (same section)** | Yes | Mixed | Mixed | Flag & manual review | -0.20, confidence=low |
| **Multiple same-clause conflicts across docs** | Yes | Mixed | Mixed | Return all with conflict details | Each: -0.10 per conflict |
| **Newer doc overrides older (same clause)** | Yes | Equal | Old→New | Keep newer | Penalize old by -0.20 |

---

## 10. Fallback & Error Handling

### 10.1 Fewer Than 7 Results

When metadata filtering or contradiction detection reduces results below k=7:

```python
def apply_fallback_strategy(
    results: List[RetrievedChunk],
    original_query: str,
    k: int = 7,
    fallback_mode: str = "return_all",  # or "relax_filters"
) -> RetrievalResult:
    """
    Handle case when <k results remain after processing.
    
    Fallback Strategies:
    
    Strategy 1: RETURN ALL
        - Return whatever results survived (even if <7)
        - Include fallback_reason explaining why fewer results
        - Trust that quality is preserved despite quantity
        
        When to use: Metadata filters are strict (e.g., one specific jurisdiction)
        Example: User filters to Delaware law only, only 3 results found
        → Return 3 results with note "Filtered to Delaware only"
    
    Strategy 2: RELAX FILTERS
        - Remove least restrictive filter, re-apply filtering
        - Order of relaxation:
            1. Remove date range filter
            2. Remove authority level filter
            3. Remove jurisdiction filter (broaden to all)
            4. Disable deduplication (allow multiple chunks per doc)
        
        When to use: Filters are too strict, losing data
        Example: User filters California + 2025, only 2 results
        → Relax to all jurisdictions + 2020+, get 7 results
    
    Strategy 3: LOWER CONFIDENCE THRESHOLD
        - Include results with lower confidence scores
        - Lower min_confidence threshold progressively
        - 0.6 → 0.5 → 0.4 → 0.3
        
        When to use: Confidence threshold too high
        Example: min_confidence=0.8, only 2 results
        → Lower to 0.5, get 7 results
    
    Strategy 4: HYBRID → SEMANTIC ONLY
        - If hybrid search returns <7, fall back to semantic only
        - Removes keyword match requirement
        
        When to use: BM25 too restrictive
        Example: Hybrid search finds 4 results
        → Repeat semantic search, get 7+ results
    
    Args:
        results: Current results list
        original_query: Original query for re-search if needed
        k: Target k value
        fallback_mode: Which strategy to apply
    
    Returns:
        RetrievalResult with fallback_applied=True and fallback_reason
    
    Raises:
        NoResultsError: All strategies exhausted, 0 results found
    
    Example:
        
        User query: "liability caps in technology service agreements"
        Filters: jurisdiction=Delaware, date_from=2024
        Result: 3 chunks found (too few)
        
        Fallback reason: "Only 3 results after filtering. "
                        "Expanded: relaxed jurisdiction filter (all states), "
                        "now showing 7 results."
        
        Response:
        {
            "results": [7 chunks],
            "fallback_applied": True,
            "fallback_reason": "Relaxed jurisdiction and date filters due to limited initial results",
            "filtering_notes": "Originally filtered to Delaware + 2024; expanded to all jurisdictions + 2020+"
        }
    """

class FallbackResult(BaseModel):
    fallback_applied: bool
    fallback_reason: Optional[str]
    filters_relaxed: List[str]              # Which filters were relaxed
    original_filter_count: int              # How many filters applied originally
    final_filter_count: int                 # How many filters active in fallback
    filtering_explanation: str              # Human-readable: "expanded jurisdiction", etc.
```

### 10.2 Error Handling

```python
# Exception Hierarchy for Module 3

class RetrievalError(Exception):
    """Base exception for retrieval module."""
    pass

# User/Input Errors
class InvalidQueryError(RetrievalError):
    """Query is empty, too long, or malformed."""
    pass

class InvalidFilterError(RetrievalError):
    """Filter specification is invalid."""
    pass

# Index/Data Errors
class UserIndexNotFound(RetrievalError):
    """User has no FAISS index (Module 2 not run)."""
    pass

class CorruptedIndexError(RetrievalError):
    """FAISS index is corrupted or incomplete."""
    pass

class MetadataError(RetrievalError):
    """Metadata sidecar is missing or malformed."""
    pass

# Search Errors
class SemanticSearchError(RetrievalError):
    """FAISS search failed."""
    pass

class KeywordSearchError(RetrievalError):
    """BM25 search failed."""
    pass

class SearchTimeoutError(RetrievalError):
    """Search exceeded time budget (>200ms)."""
    pass

# Processing Errors
class RerankerError(RetrievalError):
    """Reranking failed."""
    pass

class ContradictionDetectionError(RetrievalError):
    """Contradiction detection failed."""
    pass

class FilteringError(RetrievalError):
    """Metadata filtering failed."""
    pass

# Fallback Errors
class NoResultsError(RetrievalError):
    """No results found after all fallback strategies."""
    pass

class AllResultsFilteredError(RetrievalError):
    """All results removed by filters; fallback failed."""
    pass

# Error Handling Pattern
def retrieve_and_rerank(
    user_id: str,
    query: str,
    options: SearchOptions,
) -> RetrievalResult:
    """
    Error handling with specific recovery strategies.
    
    try:
        # Validate inputs
        if not query or len(query) > 1000:
            raise InvalidQueryError("Query must be 1-1000 characters")
        
        # Load index
        try:
            index = get_index(user_id)
        except IndexNotFoundError:
            raise UserIndexNotFound(f"No index for user {user_id}")
        
        # Execute search with timeout
        timeout_seconds = 0.2  # 200ms SLA
        
        try:
            results = execute_search_with_timeout(
                index, query, options, timeout_seconds
            )
        except TimeoutError:
            # Fallback: return fewer results faster
            logger.warning(f"Search timeout for {user_id}; reducing k")
            results = execute_search_with_timeout(
                index, query, 
                SearchOptions(k=3), 
                timeout_seconds / 2
            )
            if not results:
                raise SearchTimeoutError("Search exceeded budget")
        
        # Process results
        try:
            final_results = apply_all_processing(results, options)
        except ProcessingError as e:
            logger.error(f"Processing failed: {e}")
            raise RerankerError(str(e))
        
        # Check fallback
        if len(final_results) < options.k:
            final_results = apply_fallback_strategy(
                final_results,
                query,
                options.k
            )
        
        return RetrievalResult(
            results=final_results,
            execution_time_ms=elapsed_ms
        )
    
    except RetrievalError as e:
        # Log and re-raise with user-friendly message
        logger.error(f"Retrieval failed: {e}")
        raise
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected retrieval error: {e}", exc_info=True)
        raise RetrievalError(f"Unexpected error: {str(e)}")
    """
```

---

## 11. Configuration & Constants

### 11.1 Constants Module

```python
# src/retrieval/constants.py

# ============================================================
# SEMANTIC SEARCH
# ============================================================

SEMANTIC_K_DEFAULT = 7              # Top-K for semantic search
SEMANTIC_K_MAX = 50                 # Max k (higher = lower latency)
SEMANTIC_DISTANCE_THRESHOLD = 1000.0  # Max L2 distance to include
SEMANTIC_SCORE_FORMULA = "1 / (1 + l2_distance)"  # Conversion formula

# ============================================================
# KEYWORD SEARCH (BM25)
# ============================================================

KEYWORD_K_DEFAULT = 50              # Top-K for BM25
KEYWORD_MIN_SCORE = 0.1             # Min BM25 score threshold
BM25_K1 = 1.5                       # Term frequency saturation param
BM25_B = 0.75                       # Length normalization param
BM25_AVG_DOC_LENGTH = 750           # Average chunk length (words)

# ============================================================
# HYBRID SEARCH
# ============================================================

HYBRID_ALPHA_DEFAULT = 0.7          # Weight for semantic vs keyword
HYBRID_ALPHA_MIN = 0.0              # Min semantic weight (all keyword)
HYBRID_ALPHA_MAX = 1.0              # Max semantic weight (all semantic)

# ============================================================
# METADATA FILTERING
# ============================================================

FILTER_EXCLUDE_OVERLAPPING_DEFAULT = False  # Dedup same-doc chunks
FILTER_MIN_CONFIDENCE_DEFAULT = 0.0         # Min chunk confidence

# ============================================================
# CONTRADICTION DETECTION
# ============================================================

CONTRADICTION_DETECTION_ENABLED = True
CONTRADICTION_VALUE_DIFF_THRESHOLD = 0.05     # 5% = negligible
CONTRADICTION_SEVERITY_LOW = 0.2              # Diff score <20%
CONTRADICTION_SEVERITY_MEDIUM = 0.6           # Diff score 20-60%
CONTRADICTION_SEVERITY_HIGH = 0.6             # Diff score >60%

CONTRADICTION_CONFIDENCE_MIN = 0.5            # Min to report

# Clauses to monitor for contradictions
CONTRADICTION_CLAUSES = {
    "Liability Cap",
    "Indemnification",
    "Limitation of Liability",
    "Confidentiality",
    "Termination",
    "Payment Terms",
    "Governing Law",
    "Limitation Period",
    "Warranties",
}

# ============================================================
# RERANKING
# ============================================================

RERANK_CONFLICT_PENALTY_PER_ISSUE = 0.15     # 15% per conflict
RERANK_AUTHORITY_BONUS_BINDING = 0.10        # Binding docs
RERANK_AUTHORITY_BONUS_PRECEDENT = 0.05      # Precedent docs
RERANK_RECENCY_BONUS_MAX = 0.10              # Max 10% bonus
RERANK_RECENCY_DECAY_DAYS = 365              # Decay over 1 year
RERANK_UNIQUENESS_BONUS = 0.05               # Bonus for sole doc result

# ============================================================
# FALLBACK STRATEGY
# ============================================================

FALLBACK_MODE_DEFAULT = "return_all"         # or "relax_filters"
FALLBACK_FILTER_RELAX_ORDER = [              # Order to relax
    "date_range",
    "authority_levels",
    "jurisdictions",
    "exclude_overlapping",
]
FALLBACK_MIN_CONFIDENCE_THRESHOLDS = [0.6, 0.5, 0.4, 0.3]

# ============================================================
# PERFORMANCE SLAs
# ============================================================

LATENCY_SEMANTIC_SEARCH_MS = 50              # FAISS search
LATENCY_KEYWORD_SEARCH_MS = 30               # BM25 search
LATENCY_FILTER_MS = 20                       # Metadata filtering
LATENCY_CONTRADICTION_DETECTION_MS = 60      # Conflict detection
LATENCY_RERANKING_MS = 30                    # Score adjustment
LATENCY_TOTAL_BUDGET_MS = 200                # E2E SLA

# ============================================================
# QUERY VALIDATION
# ============================================================

QUERY_MIN_LENGTH = 1                         # At least 1 char
QUERY_MAX_LENGTH = 1000                      # Max 1000 chars
QUERY_MIN_TOKENS = 1                         # At least 1 token
QUERY_MAX_TOKENS = 128                       # Max 128 tokens (via tokenizer)

# ============================================================
# RESULT LIMITS
# ============================================================

RESULT_K_DEFAULT = 7                         # Default top-K
RESULT_K_MIN = 1
RESULT_K_MAX = 50                            # Hard limit
```

---

## 12. Implementation Roadmap

### Phase 1: Semantic + Basic Filters (MVP) — Week 1-2

- ✅ Semantic search via FAISS (Module 2 integration)
- ✅ Basic metadata filtering (jurisdiction, doc_name, date_range)
- ✅ Result formatting (RetrievedChunk model)
- ✅ Error handling & fallback (return_all)

### Phase 2: Hybrid Search + Contradiction Detection — Week 3-4

- ✅ BM25 keyword search infrastructure
- ✅ Hybrid score merging (alpha-weighted)
- ✅ Contradiction detection algorithm
- ✅ Contradiction matrix computation
- ✅ Visual conflict reporting

### Phase 3: Intelligent Reranking — Week 5

- ✅ Authority/recency/uniqueness scoring
- ✅ Conflict-aware reranking
- ✅ Final score computation
- ✅ Decision table testing

### Phase 4: Production Hardening — Week 6

- ✅ Comprehensive error handling
- ✅ Fallback strategy testing
- ✅ Performance optimization (<200ms SLA)
- ✅ Logging & monitoring
- ✅ Unit & integration tests

---

## 13. Edge Cases & Decision Table

### 13.1 Edge Case Matrix

| Case | Input | Expected Behavior | Handling |
|------|-------|-------------------|----------|
| **Empty Query** | query="" | Raise InvalidQueryError | Validate before search |
| **Very Long Query** | query with 2000 chars | Truncate to 1000 or raise error | Input validation |
| **No Results** | Query matches 0 chunks | Return empty list with reason | Fallback: relax filters |
| **All Filtered Out** | k=7, filters match only 1 result | Apply fallback strategy | Progressively relax |
| **Conflicting Values** | Same clause, 5M vs 2M caps | Flag as high-severity conflict | Penalize score, prefer newer |
| **Rounding Variation** | Same clause, 5,000,000 vs 5,000,001 | Treat as negligible (diff <0.1%) | Ignore, no conflict |
| **Mixed Authority** | One binding, one reference, conflict | Prefer binding, penalize reference less | Authority override (+0.10) |
| **Old vs New** | Same clause, doc 2020 vs 2025 | Prefer newer by default | Recency boost (+0.10) |
| **Timeout** | Search exceeds 200ms | Return partial results (k<7) | Fallback: reduce k, return fastest |
| **Corrupted Index** | FAISS index file missing/corrupt | Raise CorruptedIndexError | Return error, suggest re-indexing |
| **Metadata Mismatch** | FAISS ID not in metadata.json | Log warning, skip chunk | Graceful degradation |
| **Ambiguous Value** | "Between 1 and 10 million" | Extract both, flag ambiguous | Lower confidence score |
| **Multiple Contradictions** | Chunk A conflicts with B and C | Report all pairs separately | Conflict matrix, sort by severity |
| **Authority Level Unknown** | doc_authority_level not set | Default to "reference" | Safe fallback, no bonus |
| **No BM25 Index** | BM25 search requested, no index | Skip keyword search, use semantic | Graceful degradation |
| **Query contains legal terms** | "indemnification" exact match | BM25 score boosts this chunk | Hybrid merging helps |
| **Cross-jurisdiction conflicts** | California vs NY law, same clause | Flag jurisdiction mismatch warning | Note in conflict report |

### 13.2 Decision Rules for Contradictions

```
IF chunk_A and chunk_B have SAME clause_name:
    IF values are identical:
        → NO CONFLICT
    ELIF |value_A - value_B| / max(value_A, value_B) < 0.05:
        → LOW SEVERITY (rounding variation)
        action: ignore
    ELIF doc_A.authority > doc_B.authority:
        → MEDIUM SEVERITY (conflict but clear winner)
        action: keep doc_A, penalize doc_B slightly (-0.05)
    ELIF doc_A.date > doc_B.date:
        → MEDIUM SEVERITY (newer overrides)
        action: keep doc_A, note temporal mismatch
    ELSE:
        → HIGH SEVERITY (true conflict, unclear winner)
        action: flag for manual review, include both with warnings
```

### 13.3 Query Validation Checklist

```
✓ Query length is 1-1000 characters
✓ Query is not null/empty
✓ Query tokenizes to 1-128 tokens
✓ Query does not contain only punctuation/numbers
✓ User exists and has FAISS index
✓ SearchOptions.k is 1-50
✓ SearchOptions.alpha is 0.0-1.0
✓ Filter specifications are valid (dates parseable, etc.)
✓ No conflicting options (e.g., use_semantic=False and use_keyword=False)
```

---

## 14. Success Metrics & KPIs

### 14.1 Functional KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Semantic Search Latency** | <50ms | FAISS knn() execution time |
| **Total E2E Latency** | <200ms | retrieve_and_rerank() wall-clock time |
| **Contradiction Detection F1** | >0.95 | Manual validation on 100 samples |
| **Fallback Success Rate** | >98% | % of <7 results that resolve via fallback |
| **Hybrid Search Recall** | >0.80 | Fraction of relevant chunks retrieved |
| **False Positive Contradictions** | <5% | Manual review of detected conflicts |
| **Reranking Accuracy** | >0.90 | User preference validation (A/B testing) |

### 14.2 Non-Functional KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Availability** | >99.5% | Uptime excluding planned maintenance |
| **Error Rate** | <1% | Errors / total queries |
| **Timeout Rate** | <0.5% | Queries exceeding 200ms |
| **Code Coverage** | >90% | Unit + integration test coverage |

---

## 15. Testing Strategy

### 15.1 Unit Tests

- `test_semantic_search_basic.py` — FAISS integration, scoring formula
- `test_keyword_search_bm25.py` — BM25 computation, TF-IDF normalization
- `test_hybrid_merging.py` — Score merging, alpha weighting
- `test_metadata_filtering.py` — Filter application, deduplication
- `test_contradiction_detection.py` — Clause matching, value extraction, conflict scoring
- `test_reranking.py` — Authority/recency/uniqueness adjustments
- `test_fallback_strategies.py` — Filter relaxation, result recovery

### 15.2 Integration Tests

- `test_e2e_retrieval_pipeline.py` — Full semantic → reranking pipeline
- `test_hybrid_search_e2e.py` — BM25 + semantic combination
- `test_contradiction_detection_e2e.py` — Multi-chunk conflict scenarios
- `test_error_handling.py` — Invalid queries, missing indices, timeouts

### 15.3 Benchmark Tests

- `bench_latency_semantic_search.py` — <50ms semantic search
- `bench_latency_total_e2e.py` — <200ms end-to-end
- `bench_contradiction_detection.py` — <60ms detection for 50 chunks

---

## Appendix A: Scoring Formula Reference

### A.1 Semantic Score

```
semantic_score = 1 / (1 + l2_distance)

Range: [0, 1]
Examples:
    l2_distance=0.0   → score=1.000 (identical)
    l2_distance=0.1   → score=0.909
    l2_distance=0.5   → score=0.667
    l2_distance=1.0   → score=0.500
    l2_distance=2.0   → score=0.333
```

### A.2 Hybrid Merge

```
hybrid_score = alpha * semantic_score + (1 - alpha) * keyword_score

With alpha=0.7 (default):
    hybrid_score = 0.7 * semantic + 0.3 * keyword

Example:
    semantic=0.85, keyword=0.60
    hybrid = 0.7 * 0.85 + 0.3 * 0.60 = 0.595 + 0.180 = 0.775
```

### A.3 Reranking Final Score

```
final_score = base_score * conflict_penalty * (1 + authority_boost + recency_boost + uniqueness_boost)

Components:
    base_score = hybrid or semantic score [0, 1]
    conflict_penalty = 1.0 - (conflict_count * 0.15)  [0.85-1.0]
    authority_boost = 0.10 (binding) | 0.05 (precedent) | 0 (reference)
    recency_boost = max(0, (365 - age_days) / 3650)  [0-0.10]
    uniqueness_boost = 0.05 if sole result | 0 otherwise
    
Example:
    base_score = 0.80
    conflict_penalty = 0.85 (1 conflict)
    authority_boost = 0.10 (binding)
    recency_boost = 0.08 (50 days old)
    uniqueness_boost = 0.05
    
    final_score = 0.80 * 0.85 * (1 + 0.10 + 0.08 + 0.05)
                = 0.80 * 0.85 * 1.23
                = 0.835
```

---

**End of Technical Specification**

---

**Document Metadata**
- **Version**: 1.0
- **Last Updated**: March 29, 2026
- **Status**: Complete
- **Audience**: Engineering Team, Product, QA
- **Review Checklist**:
  - ✅ Data models defined with Pydantic
  - ✅ Function contracts with args/returns/raises
  - ✅ Scoring formulas with examples
  - ✅ Contradiction detection algorithm detailed
  - ✅ Reranking rules with decision table
  - ✅ Error handling and fallback strategies
  - ✅ Edge cases documented
  - ✅ Performance SLAs specified
  - ✅ Configuration constants enumerated
  - ✅ Architecture diagrams included (ASCII)
  - ✅ Testing strategy outlined
  - ✅ Success metrics and KPIs defined
