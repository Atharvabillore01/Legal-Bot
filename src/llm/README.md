# LLM Interface & Prompt Builder Module

**Legal RAG System | Module 4**

Professional-grade LLM integration for legal question-answering with prompt templating, citation tracking, and confidence scoring.

## Features

✅ **Professional Prompt Engineering** - Exact template structure (SYSTEM/CONTEXT/QUERY/INSTRUCTIONS) with token budget management (128K max)

✅ **GPT-4o Integration** - Temperature=0.1 for low hallucination, exponential backoff retry on rate limits

✅ **Citation Tracking** - Automatic extraction of [[CITE:{chunk_id}]] markers with character offset mapping

✅ **Confidence Scoring** - L2 distance normalization → weighted average → LOW/MEDIUM/HIGH classification with multi-factor adjustments

✅ **Token Budget Allocation** - Automatic allocation (10% system, 70% context, 5% query, 15% buffer) with progressive chunk removal if exceeded

✅ **Structured Responses** - Pydantic QueryResponse with answer, citations, confidence, timing metrics

## Installation

```bash
# Install dependencies
pip install -r src/llm/requirements.txt

# Or install individual packages
pip install openai>=1.0.0 pydantic>=2.0.0 tiktoken>=0.5.0
```

## Quick Start

### Basic Query

```python
from src.llm import query_llm_simple, QueryResponse

# Retrieved chunks from Module 3
chunks = [
    {
        "text": "The liability cap is USD 5,000,000 per incident as stated in Section 10.",
        "doc_name": "indemnity_agreement.pdf",
        "page_number": 7,
        "jurisdiction": "NY",
        "section": "Limitations of Liability"
    }
]

# Metadata lookup for citations
metadata = {
    "chunk_0": {
        "doc_name": "indemnity_agreement.pdf",
        "page_number": 7,
        "jurisdiction": "NY",
        "section": "Limitations of Liability"
    }
}

# Query the LLM
response = query_llm_simple(
    chunks=chunks,
    query="What is the liability cap?",
    chunk_metadata=metadata
)

# Access response
print(response.answer)
print(f"Confidence: {response.confidence_level} ({response.confidence_score:.2f})")
print(f"Citations: {len(response.citations)}")
print(f"Total time: {response.total_time_ms():.0f}ms")
```

### Using LLMQueryEngine for Advanced Control

```python
from src.llm import LLMQueryEngine

engine = LLMQueryEngine(api_key="your-api-key")

# Query with confidence scores and contradiction count
response = engine.query_llm(
    chunks=chunks,
    query="What is the liability cap?",
    chunk_metadata=metadata,
    chunk_scores=[0.92, 0.85, 0.73],  # Normalized similarity scores
    contradiction_count=0,  # No contradictions detected
    user_id="user_123"
)

# Response details
for citation in response.citations:
    print(f"{citation.source_doc}, p.{citation.page_number}: {citation.text_excerpt}")
```

## Configuration Reference

### Key Constants (src/llm/constants.py)

#### LLM Model Configuration

```python
GPT_MODEL = "gpt-4o"                          # Model name
MODEL_TEMPERATURE = 0.1                       # 0.1 = deterministic, good for legal
MODEL_TOP_P = 0.95                            # Use most confident tokens
MAX_OUTPUT_TOKENS = 2000                      # Max response length
```

#### Token Budget (128K total)

```python
MAX_CONTEXT_TOKENS = 128000                   # Overall limit

# Allocation percentages
TOKEN_ALLOCATION_SYSTEM_PERCENT = 0.10        # 10% (~12.8K tokens)
TOKEN_ALLOCATION_CONTEXT_PERCENT = 0.70       # 70% (~89.6K tokens)
TOKEN_ALLOCATION_QUERY_PERCENT = 0.05         # 5% (~6.4K tokens)
TOKEN_ALLOCATION_RESPONSE_PERCENT = 0.15      # 15% (~19.2K tokens)
```

#### Confidence Thresholds

```python
CONFIDENCE_THRESHOLD_LOW = 0.3                # < 0.3 = LOW
CONFIDENCE_THRESHOLD_MEDIUM = 0.7             # 0.3-0.7 = MEDIUM
                                              # >= 0.7 = HIGH

CONFIDENCE_LEVELS = {
    "LOW": {"ui_color": "red", ...},
    "MEDIUM": {"ui_color": "yellow", ...},
    "HIGH": {"ui_color": "green", ...}
}
```

#### Retry Configuration

```python
MAX_API_RETRIES = 3                           # Max retry attempts
RETRY_BACKOFF_INITIAL = 2                     # Initial backoff (2s)
RETRY_BACKOFF_MAX = 32                        # Max backoff (32s)
# Exponential: wait = 2^attempt seconds
```

#### Citation Configuration

```python
CITATION_MARKER_FORMAT = "[[CITE:{chunk_id}]]"
CITATION_MARKER_PATTERN = r"\[\[CITE:([a-z0-9_]+)\]\]"
MAX_CITATIONS = 100
MIN_CITATION_LENGTH = 10
MAX_CITATION_LENGTH = 500
```

## Function Reference

### Query Functions

#### `query_llm_simple(chunks, query, chunk_metadata, api_key=None) → QueryResponse`

Simple wrapper for basic LLM queries.

**Args:**
- `chunks` (List[Dict]): Retrieved chunks with text, doc_name, page_number, jurisdiction
- `query` (str): User question
- `chunk_metadata` (Dict): Metadata lookup {chunk_id: {...}}
- `api_key` (str, optional): OpenAI API key

**Returns:** QueryResponse with answer, citations, confidence

**Example:**
```python
response = query_llm_simple(chunks, "What are the payment terms?", metadata)
```

#### `LLMQueryEngine.query_llm(chunks, query, chunk_metadata, chunk_scores=None, contradiction_count=0, user_id=None) → QueryResponse`

Full-featured LLM query with confidence scoring and multi-factor adjustments.

**Args:**
- `chunks` (List[Dict]): Retrieved chunks
- `query` (str): User question
- `chunk_metadata` (Dict): Metadata lookup
- `chunk_scores` (List[float], optional): L2 normalized scores [0, 1]
- `contradiction_count` (int): Detected contradictions
- `user_id` (str, optional): User identifier

**Returns:** QueryResponse with detailed timing and confidence

**Raises:**
- `EmptyContextError` if no chunks provided
- `TokenBudgetExceededError` if context exceeds 128K
- `RateLimitError` if rate limited (after retries)
- `APIError` if other API error

### Prompt Functions

#### `prepare_prompt_for_llm(chunks, query, confidence_score=0.5) → (prompt_str, allocation_dict)`

Orchestrates complete prompt preparation with token budget.

**Args:**
- `chunks` (List[Dict]): Retrieved chunks
- `query` (str): User question
- `confidence_score` (float): Estimated confidence [0, 1]

**Returns:** Tuple of (complete_prompt, token_allocation_dict)

**Allocation dict keys:**
- `system_tokens`: Tokens for system prompt
- `context_tokens`: Tokens for chunks
- `query_tokens`: Tokens for user query
- `response_tokens`: Reserved for response
- `chunks_to_include`: Number of chunks that fit in budget

**Example:**
```python
prompt, allocation = prepare_prompt_for_llm(chunks, query, confidence_score=0.85)
print(f"Using {allocation['chunks_to_include']} chunks")
print(f"Token budget: {allocation['total_tokens']}/{MAX_CONTEXT_TOKENS}")
```

#### `count_tokens(text: str) → int`

Count tokens in text using tiktoken (gpt-3.5-turbo encoding).

**Args:**
- `text` (str): Text to count

**Returns:** Token count

**Example:**
```python
tokens = count_tokens("What is the liability cap?")
```

### Confidence Functions

#### `calculate_query_confidence(chunk_scores, contradiction_count=0, authority_levels=None, published_dates=None) → float`

Calculate comprehensive confidence with multi-factor adjustments.

**Args:**
- `chunk_scores` (List[float]): Normalized scores [0, 1]
- `contradiction_count` (int): Contradictions detected
- `authority_levels` (List[str]): Authority for each chunk
- `published_dates` (List[datetime]): Publication dates

**Returns:** Confidence score [0, 1]

**Scoring Formula:**
```
base_confidence = weighted_average(chunk_scores)
adjusted = base_confidence
adjusted *= (0.95 ^ contradiction_count)  # Contradiction penalty
adjusted *= (0.85 ^ low_authority_count)  # Authority penalty
adjusted *= (0.90 ^ old_source_count)     # Recency penalty
return clamp(adjusted, 0, 1)
```

**Example:**
```python
scores = [0.92, 0.87, 0.73]
contradictions = 1
confidence = calculate_query_confidence(scores, contradiction_count=contradictions)
# Result: ~0.81 (with contradiction penalty)
```

#### `classify_confidence_level(confidence_score: float) → Literal["LOW", "MEDIUM", "HIGH"]`

Classify confidence into levels.

**Thresholds:**
- LOW: < 0.3
- MEDIUM: 0.3 to 0.7
- HIGH: >= 0.7

### Citation Functions

#### `build_citation_objects(response_text, metadata_lookup) → List[Citation]`

Extract and structure citations from LLM response.

**Args:**
- `response_text` (str): Response with [[CITE:chunk_id]] markers
- `metadata_lookup` (Dict): Metadata {chunk_id: {...}}

**Returns:** List of Citation objects with offsets

**Example:**
```python
response = "The cap is $5M [[CITE:chunk_15]]."
citations = build_citation_objects(response, metadata)
for c in citations:
    print(f"{c.source_doc}, p.{c.page_number}")
```

#### `parse_citations(response_text: str) → List[str]`

Extract [[CITE:...]] markers from response.

**Returns:** List of chunk_ids in order of appearance

**Example:**
```python
text = "First claim [[CITE:chunk_15]]. Second [[CITE:chunk_23]]."
chunks = parse_citations(text)
# Result: ["chunk_15", "chunk_23"]
```

## Token Budget Management

The module automatically manages a 128K token budget:

```
Total Budget: 128,000 tokens

Breakdown:
- System Prompt:   12,800 (10%)
- Context Chunks:  89,600 (70%)
- User Query:       6,400 (5%)
- Response Buffer: 19,200 (15%)
```

**How it works:**

1. **Allocation Phase:** Calculate available tokens for context
2. **Chunk Selection:** Add chunks until context budget exhausted
3. **Progressive Removal:** If needed, remove least-relevant chunks
4. **Prompt Assembly:** Build final prompt with allocated chunks

**Example breakdown:**
```
Query: "What is the liability cap?" (50 tokens)
Retrieved 5 chunks: [850, 720, 680, 550, 420 tokens]

Available context budget: 89,600 tokens
After system + query reserved: ~82,700 tokens

Chunks added:
1. Chunk 0: 850 tokens (total: 850)
2. Chunk 1: 720 tokens (total: 1,570)
3. Chunk 2: 680 tokens (total: 2,250)
4. Chunk 3: 550 tokens (total: 2,800)
5. Chunk 4: 420 tokens (total: 3,220)

Result: All 5 chunks fit
Final prompt: ~15,320 tokens of 128K limit
```

## Confidence Scoring Details

### Confidence Score Components

1. **Base Score** - Weighted average of chunk similarity scores
   - 1st chunk: 3x weight
   - 2nd chunk: 2x weight
   - 3rd+ chunks: 1x weight

2. **Contradiction Penalty** - ×0.95 per contradiction detected
   - Each conflicting source reduces confidence
   - Example: 1 contradiction → ×0.95, 2 contradictions → ×0.9025

3. **Authority Adjustment** - Penalties for low-authority sources
   - 'binding' → no adjustment
   - 'precedent' → no adjustment
   - 'informational' → ×0.85 per source

4. **Recency Penalty** - ×0.90 for sources >5 years old
   - Recent sources (<1 year) → no adjustment
   - Old sources (>5 years) → ×0.90 per source

### Example: Multi-Factor Calculation

```python
chunks = [
    {"text": "...", "similarity_score": 0.92, "authority": "binding", "published": "2024-01-01"},
    {"text": "...", "similarity_score": 0.78, "authority": "precedent", "published": "2019-01-01"},
]
contradictions_detected = 1

# Calculation:
base_score = (0.92*3 + 0.78*2) / (3+2) = 0.868  # Weighted average
adjusted = 0.868 * 0.95 = 0.8246               # Contradiction penalty (-5%)
adjusted = 0.8246 * 0.90 = 0.7421              # Recency penalty (-10% for 5-year-old source)

Result: confidence_level = "MEDIUM" (0.7421, which is > 0.7, actually HIGH)
```

## Citation Parsing

Citations are extracted using regex pattern: `\[\[CITE:([a-z0-9_]+)\]\]`

### Response with Citations

```
The liability cap in Section 10 is USD 5,000,000 [[CITE:chunk_15]].
This is consistent with the indemnity agreement [[CITE:chunk_23]].
```

### Extracted Citations

```python
[
    Citation(
        chunk_id="chunk_15",
        source_doc="indemnity_agreement.pdf",
        page_number=7,
        text_excerpt="The liability cap in Section 10 is USD 5,000,000",
        character_offset_start=40,
        character_offset_end=93
    ),
    Citation(
        chunk_id="chunk_23",
        source_doc="indemnity_agreement.pdf",
        page_number=12,
        text_excerpt="consistent with the indemnity agreement",
        character_offset_start=105,
        character_offset_end=144
    )
]
```

## Error Handling

### Rate Limits

The module handles OpenAI API rate limits with exponential backoff:

```
Attempt 1: Immediate call
Attempt 2: Wait 2 seconds, retry
Attempt 3: Wait 4 seconds, retry
Attempt 4: Wait 8 seconds, retry (max 3, so this is the limit)

After 3 attempts: Raise RateLimitError
```

### Context Length

If context exceeds 128K tokens:

```
1. Remove least-relevant chunk
2. Recalculate token allocation
3. Retry if ≥1 chunk remains
4. Raise TokenBudgetExceededError if no chunks fit
```

### Empty Context

If no chunks retrieved:

```
Raise EmptyContextError with message:
"No context chunks provided for query"
```

## Performance SLAs

| Operation | Target | Typical Range |
|-----------|--------|---------------|
| Prompt preparation | <100ms | 50-150ms |
| Token counting | <10ms | 5-20ms |
| LLM API call | <5s | 1-10s |
| Citation extraction | <50ms | 20-100ms |
| End-to-end query | <10s | 2-15s |

## Advanced Usage

### Custom Confidence Thresholds

```python
from src.llm import classify_confidence_level
from src.llm.constants import CONFIDENCE_LEVELS

# Check confidence level
score = 0.65
level = classify_confidence_level(score)
print(level)  # "MEDIUM"

# Get interpretation
interpretation = CONFIDENCE_LEVELS[level]["interpretation"]
ui_color = CONFIDENCE_LEVELS[level]["ui_color"]
```

### Validate Citations

```python
from src.llm import validate_citations_in_chunks

citations = response.citations
original_chunks = {"chunk_15": "...", "chunk_23": "..."}

valid = validate_citations_in_chunks(citations, original_chunks)
for chunk_id, is_valid in valid.items():
    print(f"{chunk_id}: {'✓' if is_valid else '✗'}")
```

### Manual Prompt Assembly

```python
from src.llm import (
    build_system_prompt,
    build_context_prompt,
    build_instruction_prompt,
    construct_full_prompt
)

system = build_system_prompt()
context = build_context_prompt(chunks)
instructions = build_instruction_prompt(confidence_score=0.85)

full = construct_full_prompt(system, context, query, instructions)
print(full)
```

## Integration with Other Modules

### From Module 3 (Retrieval & Reranking)

Module 3 returns `retrieve_and_rerank()` which provides:
- `chunks`: List[RetrievedChunk]
- `reranker_results`: List[RerankerResult]

**Convert to Module 4 format:**

```python
from src.retrieval import retrieve_and_rerank
from src.llm import LLMQueryEngine

# Get chunks from Module 3
chunks, reranker_results = retrieve_and_rerank(
    user_id="user_123",
    query="What is the liability cap?",
    search_params=SearchParams(k=7)
)

# Build metadata lookup
metadata = {
    c.chunk_id: {
        "doc_name": c.doc_name,
        "page_number": c.page_number,
        "jurisdiction": c.jurisdiction,
        "section": c.section
    }
    for c in chunks
}

# Extract scores
scores = [c.base_score for c in chunks]

# Query LLM
engine = LLMQueryEngine()
response = engine.query_llm(
    chunks=[{"text": c.text, "doc_name": c.doc_name, ...} for c in chunks],
    query="What is the liability cap?",
    chunk_metadata=metadata,
    chunk_scores=scores,
    contradiction_count=len([c for c in chunks if c.conflicts]),
    user_id="user_123"
)

print(response.answer)
```

## Troubleshooting

### "OpenAI API key not found"

Set your API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or pass directly:

```python
response = query_llm_simple(chunks, query, metadata, api_key="sk-...")
```

### "Rate limit exceeded"

The module retries automatically with exponential backoff. If you still exceed the limit:
- Reduce batch frequency
- Use smaller chunks
- Increase delay between queries

### "Token budget exceeded"

The module progressively removes least-relevant chunks. This is normal behavior. You'll see:
- Fewer chunks included
- Slightly lower confidence
- Still a valid response

### "Model gpt-4o not found"

Ensure you have access to gpt-4o in your OpenAI account. Fallback to gpt-4-turbo:

```python
from src.llm import LLMQueryEngine
from src.llm.constants import GPT_MODEL_FALLBACK

engine = LLMQueryEngine()
engine.model = GPT_MODEL_FALLBACK
```

## Testing

```bash
# Run tests (when available)
pytest tests/test_llm_module.py -v

# Test specific functions
pytest tests/test_llm_module.py::test_token_counting -v
```

## Related Modules

- **Module 1**: Document Ingestion & Chunking
- **Module 2**: Embeddings & FAISS Vector Store
- **Module 3**: Retrieval & Reranking
- **Module 4**: LLM Interface & Prompt Builder (this module)

## License

MIT License
