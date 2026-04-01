# Module 4: LLM Interface & Prompt Builder

**Legal RAG System | Technical Specification**

**Version**: 1.0  
**Date**: March 29, 2026  
**Status**: Complete Specification  
**Audience**: Engineers, Prompt Engineers, QA

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Data Models](#3-data-models)
4. [Prompt Template Specification](#4-prompt-template-specification)
5. [Token Budget Management](#5-token-budget-management)
6. [LLM Integration](#6-llm-integration)
7. [Citation Extraction & Parsing](#7-citation-extraction--parsing)
8. [Confidence Scoring](#8-confidence-scoring)
9. [Response Validation & Parsing](#9-response-validation--parsing)
10. [Error Handling & Fallbacks](#10-error-handling--fallbacks)
11. [Configuration & Constants](#11-configuration--constants)
12. [Performance & SLAs](#12-performance--slas)
13. [Example Workflows](#13-example-workflows)

---

## 1. Overview & Goals

### Purpose

Module 4 transforms retrieved document chunks (from Module 3) into coherent, cited legal answers via OpenAI's GPT-4o LLM. It provides:

- **Structured Prompt Construction**: System + context + query → optimized for low hallucination
- **Token Budget Management**: Maximize context window (128K tokens) while preserving quality
- **Citation Tracking**: Inline markers `[[CITE:{chunk_id}]]` → full provenance (doc, page, char offset)
- **Confidence Scoring**: Map FAISS L2 distances → [0, 1] confidence scale with thresholds
- **Response Validation**: Parse GPT-4o output, extract citations, validate claims against context

### Success Criteria

- **Hallucination Rate**: <2% (claims not grounded in context)
- **Citation Accuracy**: 99%+ (citations correctly match sources)
- **Latency**: <5 seconds per query (including LLM inference)
- **Token Efficiency**: ≥80% utilization of context budget
- **Cost**: <$0.10 per query (GPT-4o pricing)

### User stories

1. **Legal Analyst**: Query contract library → get answer with citations → click citation → jump to source document
2. **Compliance Officer**: "Do we have liability caps?" → Answer with page numbers, severity indicators
3. **Due Diligence Team**: "Conflicting payment terms?" → Answer highlights contradictions + sources

---

## 2. Architecture & Data Flow

### End-to-End Pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│                    USER QUESTION                                      │
│                   "What are liability caps?"                          │
└──────────┬───────────────────────────────────────────────────────────┘
           │
        ┌──▼───────────────────────────────────┐
        │  Module 3: Retrieve & Rerank         │ ← Retrieved chunks
        │  (top-7 + contradictions + metadata)  │    with scores
        └──┬───────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │  1. TOKEN BUDGETING                       │
        │  Calculate: tokens_available = 128K       │
        │  Allocate: system + context + query + out │
        └──┬───────────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │  2. CONTEXT ASSEMBLY                      │
        │  Select top K chunks (fit within budget)  │
        │  Format with metadata + confidence        │
        └──┬───────────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │  3. PROMPT CONSTRUCTION                   │
        │  System prompt                            │
        │  CONTEXT: [chunk1] [chunk2] ...          │
        │  USER QUERY: {query}                     │
        │  INSTRUCTIONS: cite, inline markers      │
        └──┬───────────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │  4. LLM CALL (GPT-4o)                     │
        │  temperature=0.1 (low randomness)        │
        │  max_tokens=2000                         │
        │  structured_json_mode=True (enforce JSON)│
        └──┬───────────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │  5. RESPONSE PARSING                      │
        │  Extract JSON: answer + citations        │
        │  Parse [[CITE:{chunk_id}]] markers      │
        │  Validate structure                      │
        └──┬───────────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │  6. CITATION ENRICHMENT                   │
        │  Map chunk_id → doc metadata              │
        │  Find character offset of citation text  │
        │  Build Citation objects                  │
        └──┬───────────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │  7. CONFIDENCE SCORING                    │
        │  Compute from FAISS distances             │
        │  Classify: LOW/MEDIUM/HIGH                │
        │  Annotate response                       │
        └──┬───────────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │  8. VALIDATION & RETURN                   │
        │  Check hallucination risk                 │
        │  Build QueryResponse                     │
        │  Return with citation map                │
        └──▼────────────────────────────────────────┘
           │
        ┌──▼────────────────────────────────────────┐
        │       QueryResponse (to frontend)         │
        │  - answer_text (markdown)                 │
        │  - citations (array with source refs)    │
        │  - confidence_level                      │
        │  - coverage (% context matched)          │
        └─────────────────────────────────────────┘
```

---

## 3. Data Models

### 3.1 QueryResponse (Main Output)

```python
class QueryResponse(BaseModel):
    """Complete response to a legal query with citations and confidence."""
    
    query: str                                  # Original question
    answer: str                                 # LLM-generated answer (markdown)
    
    # Citations
    citations: List[Citation]                  # Extracted citations
    citation_count: int                         # Number of citations
    
    # Confidence & Quality
    confidence_level: str                      # "low" | "medium" | "high"
    confidence_score: float                    # [0, 1] aggregated from chunks
    
    # Source Coverage
    source_documents: List[SourceDocument]    # Unique docs referenced
    source_count: int                          # Number of unique sources
    context_coverage: float                    # % of retrieved context used
    
    # Hallucination Detection
    hallucination_risk: str                   # "low" | "medium" | "high"
    grounding_evidence: str                   # Explanation of confidence
    
    # Metadata
    model: str                                 # "gpt-4o"
    temperature: float                        # LLM temperature used
    tokens_used: TokenUsage                   # Actual token consumption
    latency_ms: float                         # End-to-end latency
    
    # Fallback info
    used_fallback: bool                       # True if insufficient context
    fallback_reason: Optional[str]


class Citation(BaseModel):
    """Single citation with full provenance."""
    
    citation_id: str                           # "chunk_5"
    claim: str                                 # Exact text cited (50-200 chars)
    
    # Source Identification
    doc_id: str
    doc_name: str
    page_number: int
    section: str
    
    # Location
    character_offset: int                      # Position in chunk text where claim found
    character_length: int                      # Length of claim in text
    
    # Quality
    confidence_score: float                    # [0, 1] from retrieval
    semantic_similarity: float                 # FAISS distance converted
    
    # Metadata
    jurisdiction: str
    doc_authority_level: str                  # "binding" | "precedent" | "reference"
    uploaded_date: datetime
    retrieved_rank: int                        # Position in Module 3 results (1-7)


class SourceDocument(BaseModel):
    """Reference to a source document."""
    
    doc_id: str
    doc_name: str
    jurisdiction: str
    authority_level: str
    citation_count: int                        # How many citations from this doc
    source_url: Optional[str]                  # URL to full document


class TokenUsage(BaseModel):
    """Token consumption breakdown."""
    
    system_tokens: int                         # System prompt
    context_tokens: int                        # Retrieved chunks
    query_tokens: int                          # User question
    response_tokens: int                       # LLM output
    total_tokens: int                          # Sum
    budget_tokens: int                         # Max available


class PromptRequest(BaseModel):
    """Request to generate and execute a query."""
    
    query: str                                 # User question
    retrieved_chunks: List[RetrievedChunk]    # From Module 3
    context_budget: int = 120_000              # Max tokens for context
    temperature: float = 0.1                   # LLM temperature
    max_output_tokens: int = 2000              # Max response length
    enforce_citations: bool = True             # Require citing sources
    detect_hallucination: bool = True          # Run hallucination detection


class PromptTemplate(BaseModel):
    """Structured prompt for LLM."""
    
    system_prompt: str                         # System instruction
    context_sections: List[ContextSection]    # Individual chunk sections
    user_query: str                            # User question
    instructions: str                          # Citation/format rules
    
    total_tokens: int                          # Calculated token count
    context_tokens: int                        # Tokens in CONTEXT section


class ContextSection(BaseModel):
    """Single document chunk in context."""
    
    chunk_id: str
    doc_name: str
    page_number: int
    section: str
    jurisdiction: str
    confidence_score: float
    text: str
```

---

## 4. Prompt Template Specification

### 4.1 Complete Prompt Structure

```python
SYSTEM_PROMPT = """You are a professional legal assistant AI specialized in contract analysis and legal document review.

CRITICAL RULES:
1. ANSWER ONLY FROM THE PROVIDED CONTEXT
2. Never speculate or use external knowledge
3. If information is not in context, respond: "Insufficient information in the provided documents."
4. Cite EVERY claim with inline markers: [[CITE:chunk_id]]
5. Use page numbers and document names for clarity
6. For contradictions, explain all viewpoints with citations
7. Distinguish between binding vs. precedent vs. reference documents
8. Flag assumptions or uncertainties

OUTPUT FORMAT (JSON):
{
    "answer": "Your response with [[CITE:chunk_id]] markers inline",
    "citations_required": boolean,
    "confidence_indicators": ["low", "medium", "high"],
    "contradictions_found": boolean,
    "hallucination_risk": "low|medium|high"
}

CONFIDENCE LEVELS:
- HIGH: Claim appears in multiple high-confidence chunks or binding documents
- MEDIUM: Claim in single-source or precedent documents
- LOW: Claim unclear, contradicted, or from reference documents
"""

CONTEXT_TEMPLATE = """CONTEXT: {context_count} source documents provided

{chunks_formatted}

"""

CHUNK_TEMPLATE = """[CHUNK {chunk_index}]
Source: {doc_name} | Page {page_number} | Section: {section} | Jurisdiction: {jurisdiction}
Authority Level: {authority_level} | Confidence: {confidence_score:.1%}
───────────────────────────────────────────────────────────────
{chunk_text}
───────────────────────────────────────────────────────────────

"""

USER_QUERY_TEMPLATE = """USER QUERY: {user_query}

INSTRUCTIONS:
1. Use [[CITE:chunk_id]] inline for every claim (e.g., [[CITE:contract_5_2]])
2. Refer to sources by doc_name and page number
3. If query mentions contradictions, cite all conflicting positions
4. Assess confidence: LOW/MEDIUM/HIGH based on source authority and agreement
5. Output valid JSON with answer and metadata
6. Maximum response: 2000 tokens
"""

CONFIDENCE_GUIDELINES = """CONFIDENCE ASSESSMENT:
- Confidence = f(authority_level, semantic_similarity, source_agreement)
- binding documents: weight = 1.00
- precedent documents: weight = 0.75
- reference documents: weight = 0.50
- conflicting sources: lower confidence
- single source: reduce confidence by 20%
- multiple independent sources: increase confidence by 15%
"""
```

### 4.2 Prompt Assembly Algorithm

```python
def assemble_prompt(
    query: str,
    retrieved_chunks: List[RetrievedChunk],
    context_budget: int = 120_000,
) -> PromptTemplate:
    """
    Build complete prompt from query and chunks.
    
    Algorithm:
    1. Start with system prompt (fixed)
    2. Select chunks that fit in context budget
    3. Format each chunk with metadata
    4. Assemble context section
    5. Add user query with instructions
    6. Calculate total tokens
    
    Args:
        query: User question
        retrieved_chunks: Top-7 from Module 3
        context_budget: Max tokens for context (default 120K)
    
    Returns:
        PromptTemplate with formatted sections
    
    Rules:
        - Always include top-1 chunk (highest score)
        - Prefer binding documents over reference
        - Include contradictions if present
        - Stop adding chunks when budget exhausted
        - Reserve 25% for LLM output
    
    Example:
        
        Query: "What are the payment terms?"
        Retrieved: 7 chunks (scores: 0.95, 0.87, 0.82, 0.78, 0.65, 0.55, 0.42)
        Budget: 120K tokens
        
        1. System prompt: 500 tokens
        2. User query + instructions: 200 tokens
        3. Available for context: 119_300 tokens
        4. Reserved for output: 30K tokens
        5. Actual context budget: 89_300 tokens
        
        - Add chunk 1 (2000 tokens) → total: 2000
        - Add chunk 2 (1800 tokens) → total: 3800
        - Add chunk 3 (1600 tokens) → total: 5400
        - ...continue until budget exhausted...
        - Final: 7 chunks, ~85K tokens used
    """
```

---

## 5. Token Budget Management

### 5.1 Token Allocation Strategy

```
Total Context Window: 128,000 tokens (GPT-4o limit)

Allocation:
├─ System Prompt               = ~500 tokens (fixed)
├─ User Query + Instructions   = ~300 tokens (fixed)
├─ CONTEXT (retrieved chunks)  = ~115,000 tokens (variable)
├─ LLM Output Buffer           = ~2,000 tokens (fixed)
├─ Safety Margin (5%)          = ~10,200 tokens (reserved)
└─ Total Budget                = 127,700 tokens

Context Allocation:
├─ Mandatory (chunk #1)        = Average 1,500 tokens
├─ High Priority (chunks 2-4)  = Average 4,500 tokens (3 × 1,500)
├─ Medium Priority (chunks 5-7)= Average 10,500 tokens (7 × 1,500)
└─ Total Available             = 115,000 tokens

Token Counting:
- System prompt: enc​ode and count (always fixed, pre-calculated)
- Query: encode and count (variable, 50-500 tokens)
- Each chunk: count tokens, check against budget
- Add sequentially until budget exhausted
```

### 5.2 Token Budget Function

```python
def calculate_token_budget(
    system_prompt: str,
    user_query: str,
    max_output_tokens: int = 2000,
    context_window: int = 128_000,
) -> TokenBudget:
    """
    Calculate token allocation for prompt.
    
    Args:
        system_prompt: System instruction text
        user_query: User question
        max_output_tokens: Max tokens for LLM output
        context_window: Total available tokens (128K for GPT-4o)
    
    Returns:
        TokenBudget with allocation
    
    Algorithm:
        1. Encode system prompt, count tokens
        2. Encode user query, count tokens
        3. Reserve tokens for output
        4. Reserve 5% safety margin
        5. Remaining = context budget
    
    Example:
        system = "You are a legal assistant..."  # 500 tokens
        query = "What are liability caps?"        # 8 tokens
        max_output = 2000 tokens
        safety_margin = 128K × 0.05 = 6400 tokens
        
        context_budget = 128_000 - 500 - 8 - 2000 - 6400 = 119_092 tokens
        
        Can fit ~80 chunks at 1500 tokens/chunk (with squeeze room)
    
    Formula:
        context_budget = context_window - system_tokens - query_tokens 
                        - max_output_tokens - (context_window × 0.05)
    """

class TokenBudget(BaseModel):
    """Token allocation breakdown."""
    
    total_available: int                    # 128K
    system_tokens: int                      # Actual count
    query_tokens: int                       # Actual count
    output_reserve: int                     # Max tokens for response
    safety_margin: int                      # 5% buffer
    context_budget: int                     # Remaining for chunks
```

### 5.3 Token Counting

```python
def estimate_chunk_tokens(chunk: RetrievedChunk) -> int:
    """
    Estimate tokens for a single chunk.
    
    Rough formula:
        tokens ≈ (char_count / 4) × 1.3
    
    Where:
        - 1 token ≈ 4 characters in English
        - Legal text (longer words) × 1.3 multiplier
    
    Example:
        chunk.text = 5000 characters
        tokens = (5000 / 4) × 1.3 ≈ 1625 tokens
    
    For accuracy, use tiktoken library:
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-4o")
        tokens = len(encoding.encode(chunk.text))
    """

def select_chunks_within_budget(
    chunks: List[RetrievedChunk],
    context_budget: int,
) -> List[RetrievedChunk]:
    """
    Select top K chunks that fit in token budget.
    
    Rules:
    1. Always include top-1 chunk (highest confidence)
    2. Prefer binding > precedent > reference authority
    3. Skip chunks with contradictions to top-1 (unless explicitly requested)
    4. Add chunks in rank order until budget exhausted
    5. Reserve 10% of budget for formatting overhead
    
    Args:
        chunks: Retrieved chunks sorted by score
        context_budget: Available tokens
    
    Returns:
        List[RetrievedChunk] that fit within budget
    
    Algorithm:
        selected = [chunks[0]]  # Always include best
        used_tokens = estimate_chunk_tokens(chunks[0])
        budget_remaining = context_budget × 0.9  # 10% overhead reserve
        
        for chunk in chunks[1:]:
            chunk_tokens = estimate_chunk_tokens(chunk)
            if used_tokens + chunk_tokens <= budget_remaining:
                selected.append(chunk)
                used_tokens += chunk_tokens
            else:
                break
        
        return selected
    """
```

---

## 6. LLM Integration

### 6.1 GPT-4o Call Configuration

```python
def call_gpt4o(
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 2000,
    response_format: Optional[Dict] = None,
) -> OpenAIResponse:
    """
    Call OpenAI GPT-4o with optimized parameters.
    
    Parameters:
        temperature: 0.1 (low randomness, deterministic)
        max_tokens: 2000 (legal answers typically 500-1500 tokens)
        response_format: JSON schema for structured output
        top_p: 0.95 (avoid tail probabilities)
        frequency_penalty: 0.5 (reduce repetition)
        presence_penalty: 0.5 (encourage diversity)
    
    Message Format:
        [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": "CONTEXT: [...]\n\nUSER QUERY: {...}"
            }
        ]
    
    Response Format (JSON mode):
        {
            "type": "json_schema",
            "json_schema": {
                "name": "legal_answer",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "citations_found": {"type": "integer"},
                        "confidence": {"type": "string"},
                        "hallucination_risk": {"type": "string"}
                    },
                    "required": ["answer", "confidence"]
                }
            }
        }
    
    Latency SLA: <5 seconds total (typical 2-3s)
    Cost: ~$0.008 per query (gpt-4o at $0.015/1K input, $0.06/1K output)
    
    Error Handling:
        - RateLimitError: Retry with exponential backoff
        - TokenLimitError: Reduce context and retry
        - APIError: Fall back to smaller model or cached response
    
    Example:
        
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt_template.as_string()
            }
        ]
        
        response = call_gpt4o(
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
            response_format={
                "type": "json_schema",
                "json_schema": {...}
            }
        )
        
        return parse_json_response(response.choices[0].message.content)
    """

class OpenAIResponse(BaseModel):
    """Response from GPT-4o API."""
    
    content: str                                # JSON response from LLM
    tokens_used: int                            # Actual token consumption
    finish_reason: str                          # "stop" | "length" | "error"
    model: str                                  # "gpt-4o"
    created_at: datetime
```

### 6.2 Response Parsing

```python
def parse_llm_response(
    response_text: str,
    expected_schema: Dict,
) -> Dict:
    """
    Parse and validate LLM JSON response.
    
    Steps:
    1. Extract JSON from response (handle markdown code blocks)
    2. Validate against schema
    3. Extract answer and metadata
    4. Parse [[CITE:chunk_id]] markers
    
    Args:
        response_text: Raw response from GPT-4o
        expected_schema: JSON schema to validate against
    
    Returns:
        Parsed response dict
    
    Example Input:
        ```json
        {
            "answer": "The liability cap is [[CITE:contract_5_2]] $5,000,000 USD, as stated [[CITE:contract_5_3]] in Article 5.",
            "citations_found": 2,
            "confidence": "high",
            "hallucination_risk": "low"
        }
        ```
    
    Example Output:
        {
            "answer": "The liability cap is ... $5,000,000 USD...",
            "citations": [
                {"chunk_id": "contract_5_2", "position": 32},
                {"chunk_id": "contract_5_3", "position": 98}
            ],
            "confidence": "high",
            "hallucination_risk": "low"
        }
    """
```

---

## 7. Citation Extraction & Parsing

### 7.1 Citation Format

Inline marker format: `[[CITE:{chunk_id}]]`

**Examples**:
- `[[CITE:contract_001_5]]` — Chunk 5 from contract_001
- `[[CITE:agreement_b_12]]` — Chunk 12 from agreement_b
- `[[CITE:doc_id_123]]` — Chunk 123 from doc_id

### 7.2 Citation Extraction Algorithm

```python
def extract_citations(
    answer_text: str,
    chunk_id_map: Dict[str, RetrievedChunk],
) -> List[Citation]:
    """
    Extract [[CITE:chunk_id]] markers from LLM response.
    
    Algorithm:
    1. Find all [[CITE:...]] markers with regex
    2. For each marker, resolve chunk_id to RetrievedChunk
    3. Find the cited claim in surrounding context
    4. Calculate character offset and length
    5. Build Citation objects
    
    Args:
        answer_text: LLM response with [[CITE:...]] markers
        chunk_id_map: Dict of chunk_id → RetrievedChunk
    
    Returns:
        List[Citation] with full provenance
    
    Regex Pattern:
        r'\[\[CITE:([^\]]+)\]\]'
    
    Extract Steps:
        1. text = "The cap is [[CITE:contract_5_2]] $5M..."
        2. Find pattern match: chunk_id = "contract_5_2"
        3. Look up chunk in map
        4. Search for nearby context in answer to identify claim
        5. Build Citation with offset
    
    Challenge: Citation might reference text not in answer.
    Solution: Extract 50-200 chars around marker as "claim"
    
    Example:
        
        Answer: "The liability cap is [[CITE:contract_5_2]] $5,000,000 USD."
        
        Regex match: [[CITE:contract_5_2]] at position 24
        
        Claim extraction: Get surrounding text within 50 chars
            claim = "$5,000,000 USD"
        
        Citation object:
        {
            "chunk_id": "contract_5_2",
            "claim": "$5,000,000 USD",
            "character_offset": 47,
            "character_length": 14,
            ...metadata from chunk...
        }
    """

def locate_claim_in_chunk(
    claim_text: str,
    chunk_text: str,
) -> Tuple[int, int]:
    """
    Find claim text position in chunk.
    
    Returns:
        (character_offset, character_length)
    
    Algorithm:
    1. Search for exact match of claim in chunk
    2. If not found, try fuzzy matching (90%+ similarity)
    3. If still not found, use position of marker in answer
    
    Args:
        claim_text: Text to find (extracted from answer)
        chunk_text: Full chunk to search
    
    Returns:
        (offset, length) in chunk
    
    Example:
        chunk = "The liability cap is $5,000,000 USD as defined..."
        claim = "$5,000,000"
        
        offset = 24  # Position in chunk
        length = 10  # Length of "$5,000,000"
    """
```

### 7.3 Citation Richment

```python
def enrich_citations(
    citations: List[Citation],
    chunk_map: Dict[str, RetrievedChunk],
) -> List[Citation]:
    """
    Add full metadata to extracted citations.
    
    Enrichment:
    1. Resolve chunk_id to chunk metadata
    2. Add doc_name, page_number, jurisdiction, etc.
    3. Map character offset to page (if available)
    4. Add confidence score from retrieval
    5. Determine citation authority level
    
    Args:
        citations: Extracted citations (minimal info)
        chunk_map: Dict chunk_id → RetrievedChunk
    
    Returns:
        Enriched Citation objects
    
    Example:
        
        Input:
        {
            "chunk_id": "contract_5_2",
            "claim": "$5,000,000",
            "character_offset": 24,
            "character_length": 10
        }
        
        After enrichment:
        {
            "chunk_id": "contract_5_2",
            "claim": "$5,000,000",
            "character_offset": 24,
            "character_length": 10,
            "doc_id": "550e8400-...",
            "doc_name": "Service Agreement A",
            "page_number": 2,
            "section": "Article 5: Liability",
            "jurisdiction": "California",
            "confidence_score": 0.85,
            "doc_authority_level": "binding",
            "retrieved_rank": 1
        }
    """
```

---

## 8. Confidence Scoring

### 8.1 Confidence Computation

```python
def compute_answer_confidence(
    chunks_used: List[RetrievedChunk],
    lien_concordance: Dict[str, int],  # chunk_id → citation_count
) -> Tuple[str, float]:
    """
    Compute overall answer confidence from source chunks.
    
    Formula:
        answer_confidence = weighted_avg(chunk_confidences)
    
    Where weights are:
        - authority_weight: binding=1.0, precedent=0.75, reference=0.5
        - frequency_weight: cited more = higher confidence
        - similarity_weight: higher FAISS score = higher confidence
    
    Args:
        chunks_used: Chunks included in context
        lien_concordance: How many times each chunk was cited
    
    Returns:
        (confidence_level, confidence_score)
        confidence_level ∈ {"low", "medium", "high"}
        confidence_score ∈ [0, 1]
    
    Algorithm:
        1. For each chunk, compute confidence score
        2. Weight by authority level + citation frequency
        3. Average weighted scores
        4. Classify into levels
    
    Component Scores:
    
    Authority Weight:
        binding ————— 1.0
        precedent ——— 0.75
        reference ——— 0.5
    
    Similarity Weight (from FAISS L2 distance):
        distance=0.1  → score=0.909 → weight=1.0
        distance=0.5  → score=0.667 → weight=0.8
        distance=1.0  → score=0.500 → weight=0.6
        distance=2.0  → score=0.333 → weight=0.4
    
    Citation Frequency:
        cited_count=1  → weight=1.0
        cited_count=2  → weight=1.2 (boost for frequent citations)
        cited_count≥3  → weight=1.5 (high consistency)
    
    Final formula:
        chunk_confidence = semantic_score × authority_weight × (1 + 0.2 × (cited_count - 1))
        answer_confidence = mean(chunk_confidence for all chunks)
    
    Thresholds:
        HIGH:    ≥0.85
        MEDIUM:  0.65-0.85
        LOW:     <0.65
    
    Example:
        
        Chunks used:
        - Chunk 1: semantic=0.95, authority=binding, cited 2x
            confidence = 0.95 × 1.0 × (1 + 0.2) = 1.14 → clamped to 1.0
        - Chunk 2: semantic=0.80, authority=precedent, cited 1x
            confidence = 0.80 × 0.75 × 1.0 = 0.60
        - Chunk 3: semantic=0.65, authority=reference, cited 1x
            confidence = 0.65 × 0.5 × 1.0 = 0.325
        
        answer_confidence = (1.0 + 0.60 + 0.325) / 3 = 0.642 → "MEDIUM"
    """

class ConfidenceComputation(BaseModel):
    """Breakdown of confidence scoring."""
    
    answer_confidence_score: float          # [0, 1]
    answer_confidence_level: str            # "low" | "medium" | "high"
    
    # Component scores
    semantic_similarity_avg: float           # Mean FAISS similarity
    authority_weight_avg: float              # Mean authority (binding > ref)
    citation_frequency_boost: float          # How much cited chunks help
    
    # Breakdown by chunk
    chunk_scores: List[float]                # Per-chunk confidence
    
    # Factors reducing confidence
    contradictions_found: bool
    single_source_penalty: bool              # Only one chunk used
    low_authority_penalty: bool              # Only reference docs
    
    # Overall assessment
    grounding_evidence: str                  # Explanation for user
    recommendation: str                      # "trust" | "verify" | "manual_review"
```

### 8.2 Confidence Thresholds & Actions

| Confidence Level | Score | User Action | System Action |
|------------------|-------|-------------|---------------|
| **HIGH** | ≥0.85 | Accept directly | Display as-is |
| **MEDIUM** | 0.65-0.85 | Accept with verification hints | Show confidence badge |
| **LOW** | <0.65 | Manual verification recommended | Flag for review, suggest expanding search |

```python
CONFIDENCE_THRESHOLDS = {
    "high": 0.85,
    "medium": 0.65,
    "low": 0.0,
}

CONFIDENCE_ACTIONS = {
    "high": {
        "display_confidence": False,         # Trust implicit
        "show_sources": True,
        "action": "accept"
    },
    "medium": {
        "display_confidence": True,          # Show score
        "show_sources": True,
        "highlight_confidence": True,        # Visual indicator
        "action": "accept_with_warning"
    },
    "low": {
        "display_confidence": True,
        "show_sources": True,
        "highlight_confidence": True,       # Large warning
        "suggest_manual_review": True,
        "action": "flag_for_review"
    }
}
```

---

## 9. Response Validation & Parsing

### 9.1 Hallucination Detection

```python
def detect_hallucinations(
    answer: str,
    chunks: List[RetrievedChunk],
    citations: List[Citation],
    similarity_threshold: float = 0.3,
) -> HallucinationReport:
    """
    Detect claims not grounded in context (hallucinations).
    
    Algorithm:
    1. Parse answer into sentences
    2. For each sentence, check if it's cited
    3. For cited sentences, verify claim exists in chunk
    4. For uncited sentences, check if claim is in any chunk
    5. Score hallucination risk
    
    Args:
        answer: LLM-generated text
        chunks: Retrieved chunks (context provided to LLM)
        citations: Extracted citations
        similarity_threshold: Min semantic similarity to context [0, 1]
    
    Returns:
        HallucinationReport with risk level and details
    
    Detection Steps:
        1. Uncited Claims Detection
            - Find sentences without [[CITE:...]]
            - Check if claim (or similar) appears in chunk texts
            - If not found → potential hallucination
        
        2. Citation Validation
            - For each [CITE:chunk_id], verify:
                - chunk_id exists in chunks_provided
                - claim text found in chunk (exact or fuzzy match)
                - character offset makes sense
        
        3. Out-of-Context Claims
            - Use embedding similarity to check
            - If claim has no close match in chunks → hallucination
        
        4. Risk Scoring
            - uncited_claims / total_claims = hallucination_rate
            - Classification:
                - <2% → "low"
                - 2-10% → "medium"
                - >10% → "high"
    
    Example:
        
        Answer: "The liability cap is $5,000,000 USD [[CITE:contract_5_2]] 
                and applies to all disputes [[CITE:contract_5_3]]. 
                The company must also provide insurance coverage."
        
        Sentences:
        1. "The liability cap is $5,000,000 USD" — cited ✓
        2. "applies to all disputes" — cited ✓
        3. "The company must also provide insurance coverage." — NOT cited ✗
        
        Hallucination detection:
            - Sentence 3 not in any chunk → potential hallucination
            - hallucination_rate = 1/3 = 33% → "high" risk
            
        Action: Flag for manual review, mark with ⚠️
    """

class HallucinationReport(BaseModel):
    """Hallucination detection results."""
    
    hallucination_risk: str                 # "low" | "medium" | "high"
    hallucination_rate: float               # % of claims without grounding
    
    uncited_claims: List[str]               # Claims without citations
    unverified_citations: List[str]         # Citations that couldn't verify
    
    report: str                             # Human-readable assessment
    recommendation: str                     # "trust" | "manual_review"
```

### 9.2 Response Validation

```python
def validate_response(
    response: Dict,
    schema: Dict,
) -> ValidationResult:
    """
    Validate LLM response against schema.
    
    Checks:
    1. Valid JSON structure
    2. Required fields present
    3. Field types correct
    4. Citations properly formatted
    5. Answer length reasonable (500-2000 tokens)
    6. No truncation (finish_reason = "stop")
    
    Args:
        response: Parsed LLM response
        schema: Expected JSON schema
    
    Returns:
        ValidationResult with status and errors
    
    Example valid response:
        {
            "answer": "The liability cap is... [[CITE:chunk_5_2]] $5,000,000",
            "citations_found": 1,
            "confidence": "high",
            "hallucination_risk": "low"
        }
    
    Validation failures:
    - answer is empty → error
    - confidence not in {low, medium, high} → error
    - citations don't match [[CITE:...]] markers → warning
    - answer > 3000 tokens → truncation warning
    """

class ValidationResult(BaseModel):
    """Response validation results."""
    
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    schema_compliant: bool
```

---

## 10. Error Handling & Fallbacks

### 10.1 Error Hierarchy

```python
# Base
class LLMError(Exception): pass

# Input Errors
class InvalidPromptError(LLMError): pass
class TokenBudgetError(LLMError): pass
class ContextEmptyError(LLMError): pass

# API Errors
class OpenAIAPIError(LLMError): pass
class RateLimitError(LLMError): pass
class APITimeoutError(LLMError): pass
class InvalidResponseError(LLMError): pass

# Processing Errors
class CitationParsingError(LLMError): pass
class HallucinationDetectedError(LLMError): pass
class ConfidenceComputationError(LLMError): pass

# Fallback Errors
class FallbackExhaustedError(LLMError): pass
```

### 10.2 Fallback Strategies

```python
def handle_llm_error(
    error: Exception,
    query: str,
    chunks: List[RetrievedChunk],
) -> QueryResponse:
    """
    Fallback when LLM fails.
    
    Strategy Priority:
    1. Rate limit → Retry with exponential backoff
    2. Timeout → Reduce context, retry with smaller model
    3. Invalid response → Parse best-effort, mark uncertainty
    4. Hallucination detected → Return with high-risk warning
    5. All else failed → Return context summary (fallback response)
    
    Args:
        error: LLM error
        query: Original query
        chunks: Retrieved chunks
    
    Returns:
        QueryResponse (either formatted or fallback)
    
    Fallback Response (when LLM fails completely):
        {
            "answer": "Unable to process with AI assistant. 
                      Here are the relevant documents:\n\n
                      " + format_chunk_summary(chunks),
            "citations": extract_key_statements(chunks),
            "confidence_level": "low",
            "used_fallback": True,
            "fallback_reason": "LLM service unavailable"
        }
    """
```

---

## 11. Configuration & Constants

### 11.1 Constants Module

```python
# LLM Model
LLM_MODEL = "gpt-4o"
LLM_TEMPERATURE = 0.1                       # Low hallucination
LLM_MAX_OUTPUT_TOKENS = 2000
LLM_TOP_P = 0.95
LLM_FREQUENCY_PENALTY = 0.5
LLM_PRESENCE_PENALTY = 0.5

# Token Budget
TOKEN_CONTEXT_LIMIT = 128_000               # GPT-4o limit
TOKEN_SAFETY_MARGIN = 0.05                  # 5% reserved
TOKEN_OUTPUT_RESERVE = 2000
TOKEN_SYSTEM_PROMPT = 500                   # Pre-calculated
TOKEN_QUERY_ESTIMATE = 300                  # Average query

# Confidence Thresholds
CONFIDENCE_THRESHOLD_HIGH = 0.85
CONFIDENCE_THRESHOLD_MEDIUM = 0.65
CONFIDENCE_THRESHOLD_LOW = 0.0

# Hallucination Detection
HALLUCINATION_RATE_LOW = 0.02               # <2%
HALLUCINATION_RATE_MEDIUM = 0.10            # 2-10%

# Citation Parsing
CITATION_MARKER_REGEX = r'\[\[CITE:([^\]]+)\]\]'
CITATION_CLAIM_CONTEXT = 50                  # Chars to extract context

# Authority Weights
AUTHORITY_WEIGHT_BINDING = 1.0
AUTHORITY_WEIGHT_PRECEDENT = 0.75
AUTHORITY_WEIGHT_REFERENCE = 0.5

# Latency SLA
LATENCY_LLM_CALL_MS = 3000                  # GPT-4o inference
LATENCY_TOTAL_QUERY_MS = 5000               # Total end-to-end

# Cost (OpenAI pricing)
COST_PER_1K_INPUT_TOKENS = 0.015            # GPT-4o input cost
COST_PER_1K_OUTPUT_TOKENS = 0.060           # GPT-4o output cost
```

---

## 12. Performance & SLAs

### 12.1 Latency Breakdown

| Stage | Target | Notes |
|-------|--------|-------|
| Prompt assembly | <100ms | Token counting, formatting |
| LLM call | <3000ms | GPT-4o inference (typical 1-2s) |
| Response parsing | <100ms | JSON parsing, citation extraction |
| Citation enrichment | <100ms | Metadata lookup |
| Confidence scoring | <100ms | Calculation |
| **Total E2E** | **<5000ms** | All stages combined |

### 12.2 Token Efficiency

- **Target**: ≥80% utilization of 128K context window
- **Metrics**: Average tokens used / 128K
- **Goal**: Fit 100+ documents per query at ~1500 tokens/doc

### 12.3 Cost Profile

```
Per Query Cost:
├─ Input tokens: ~40K avg × $0.015/1K = $0.60
├─ Output tokens: ~800 avg × $0.060/1K = $0.048
└─ Total: ~$0.065/query

Annual Volume: 1M queries
Annual Cost: $65,000
Cost per query: <$0.10 ✓
```

---

## 13. Example Workflows

### Example 1: Basic Query

**User Query**: "What are the payment terms?"

**Retrieved Chunks** (from Module 3):
- Chunk 1: "Payment shall be made within 30 days of invoice date" (confidence 0.95)
- Chunk 2: "Late payment penalties accrue at 1.5% per month" (confidence 0.88)
- Chunk 3: "Currency must be USD unless otherwise specified" (confidence 0.82)

**Prompt Assembly**:
- System prompt: ~500 tokens
- Context (3 chunks): ~4,500 tokens
- Query: "What are the payment terms?" (~10 tokens)
- Instructions: ~200 tokens
- **Total used**: ~5,210 tokens of 128K

**LLM Call**:
```json
{
    "answer": "Payment terms require [[CITE:chunk_1]] payment within 30 days of invoice date. If payment is late, [[CITE:chunk_2]] penalties accrue at 1.5% per month. All payments must be [[CITE:chunk_3]] in USD unless otherwise specified.",
    "citations_found": 3,
    "confidence": "high",
    "hallucination_risk": "low"
}
```

**Citation Extraction**:
```json
{
    "chunk_id": "chunk_1",
    "claim": "payment within 30 days of invoice date",
    "character_offset": 142,
    "doc_name": "Master Agreement",
    "page_number": 3,
    "confidence_score": 0.95
}
```

**Confidence Computation**:
- Chunk 1: semantic=0.95, authority=binding → confidence=0.95
- Chunk 2: semantic=0.88, authority=precedent → confidence=0.88×0.75=0.66
- Chunk 3: semantic=0.82, authority=reference → confidence=0.82×0.5=0.41
- **Answer**: (0.95 + 0.66 + 0.41) / 3 = 0.67 → **MEDIUM confidence**

**Final Response**:
```json
{
    "answer": "Payment terms require [[CITE:chunk_1]] payment within 30 days of invoice date...",
    "citations": [
        {
            "citation_id": "chunk_1",
            "claim": "payment within 30 days of invoice date",
            "doc_name": "Master Agreement",
            "page_number": 3
        },
        ...
    ],
    "confidence_level": "medium",
    "confidence_score": 0.67,
    "source_documents": [
        {
            "doc_name": "Master Agreement",
            "citation_count": 1
        },
        "Agreement B",
        "Service Terms"
    ],
    "source_count": 3,
    "hallucination_risk": "low",
    "tokens_used": {
        "input": 4710,
        "output": 120,
        "total": 4830
    },
    "latency_ms": 2300
}
```

### Example 2: Contradictory Query

**User Query**: "What is the liability cap across all agreements?"

**Retrieved Chunks**: 7 chunks with contradictions detected by Module 3
- Chunk 1: "Liability cap: $5,000,000" (binding, 2025)
- Chunk 2: "Liability cap: $2,000,000" (precedent, 2023)
- Chunk 3: "No liability cap" (reference, 2022)

**LLM Response**:
```json
{
    "answer": "Liability caps vary across agreements: [[CITE:chunk_1]] $5,000,000 in the primary agreement (binding, 2025), [[CITE:chunk_2]] $2,000,000 in a previous version (precedent, 2023), and [[CITE:chunk_3]] no liability cap in reference documents (2022). The current binding authority is [[CITE:chunk_1]] $5,000,000.",
    "citations_found": 3,
    "confidence": "medium",
    "contradictions_found": true
}
```

**Hallucination Check**: All claims cited and verified ✓

**Confidence Scoring**:
- Multiple sources with contradictions → MEDIUM confidence
- Binding document (chunk_1) provides clear answer
- Older precedent/reference sources secondary
- **Overall**: 0.72 → **MEDIUM**

---

**End of Technical Specification**

---

**Document Metadata**
- **Version**: 1.0
- **Last Updated**: March 29, 2026
- **Status**: Complete
- **Review Checklist**:
  - ✅ Exact prompt template provided
  - ✅ Token budget allocation detailed
  - ✅ GPT-4o configuration specified
  - ✅ Citation extraction algorithm defined
  - ✅ Confidence scoring formula with examples
  - ✅ Hallucination detection rules
  - ✅ Data models (Pydantic) specified
  - ✅ Error handling and fallbacks
  - ✅ Performance SLAs defined
  - ✅ Example workflows with full details
