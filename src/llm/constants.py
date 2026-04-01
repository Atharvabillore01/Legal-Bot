"""
Configuration constants for the LLM interface module.

All prompts, model params, token budgets, confidence thresholds,
and feature flags live here.
"""

# ==============================================================
# MODEL CONFIGURATION
# ==============================================================

GPT_MODEL = "gpt-4o"
GPT_MODEL_FALLBACK = "gpt-4o-mini"

MODEL_TEMPERATURE = 0.0           # Deterministic — legal accuracy requires it
MODEL_TOP_P = 1.0
MODEL_FREQUENCY_PENALTY = 0.0
MODEL_PRESENCE_PENALTY = 0.0

MAX_OUTPUT_TOKENS = 2048
MAX_CONTEXT_TOKENS = 128_000      # GPT-4o context window

# ==============================================================
# RETRY / BACKOFF
# ==============================================================

MAX_API_RETRIES = 3
RETRY_BACKOFF_INITIAL = 2.0       # seconds
RETRY_BACKOFF_MAX = 32.0
RETRY_BACKOFF_MULTIPLIER = 2.0
API_TIMEOUT_SECONDS = 60

# ==============================================================
# TOKEN BUDGETS
# ==============================================================

TOKEN_BUDGET_SYSTEM = 800         # Reserved for system prompt
TOKEN_BUDGET_CONTEXT = 90_000     # Available for chunks
TOKEN_BUDGET_QUERY = 512          # User query
TOKEN_BUDGET_RESPONSE = 2048      # Reserved for model response

# Percentage-based allocations (used by __init__.py and reporting)
TOKEN_ALLOCATION_SYSTEM_PERCENT = 0.10     # 10% for system prompt
TOKEN_ALLOCATION_CONTEXT_PERCENT = 0.70    # 70% for context chunks
TOKEN_ALLOCATION_QUERY_PERCENT = 0.05      # 5%  for user query
TOKEN_ALLOCATION_RESPONSE_PERCENT = 0.15   # 15% reserved for response

# ==============================================================
# CITATION
# ==============================================================

# Matches [[CITE:chunk_id]] — allow anything inside except ]] so we catch LLM variants
CITATION_MARKER_PATTERN = r"\[\[CITE:([^\]]+)\]\]"

# ==============================================================
# CONFIDENCE THRESHOLDS
# ==============================================================

CONFIDENCE_THRESHOLD_LOW = 0.3        # < 0.3  → LOW
CONFIDENCE_THRESHOLD_MEDIUM = 0.7     # 0.3–0.7 → MEDIUM, > 0.7 → HIGH

CONFIDENCE_LEVELS = {
    "LOW": {"min": 0.0, "max": CONFIDENCE_THRESHOLD_LOW, "ui_color": "red"},
    "MEDIUM": {"min": CONFIDENCE_THRESHOLD_LOW, "max": CONFIDENCE_THRESHOLD_MEDIUM, "ui_color": "yellow"},
    "HIGH": {"min": CONFIDENCE_THRESHOLD_MEDIUM, "max": 1.0, "ui_color": "green"},
}

# Confidence adjustment penalties
CONFIDENCE_CONTRADICTION_PENALTY = 0.95   # ×0.95 per detected contradiction
CONFIDENCE_LOW_AUTHORITY_PENALTY = 0.85   # ×0.85 for low-authority sources
CONFIDENCE_OLD_SOURCE_PENALTY = 0.90      # ×0.90 for sources >5 years old

# ==============================================================
# FEATURE FLAGS
# ==============================================================

FEATURE_EXPONENTIAL_BACKOFF = True
FEATURE_CITATIONS = True

# ==============================================================
# DEBUG
# ==============================================================

DEBUG_PROMPT_BUILDING = False
DEBUG_CITATION_PARSING = False

# ==============================================================
# PROMPT TEMPLATES
# ==============================================================

SYSTEM_PROMPT = """You are a precise legal document analysis assistant.

CRITICAL RULES — you MUST follow every rule below without exception:

1. DOCUMENT-ONLY ANSWERS
   Answer exclusively from the context chunks provided in this prompt.
   Do NOT use any knowledge from your training data, general legal knowledge,
   case law, statutes, or any information not present in the provided chunks.
   The provided documents are the sole authoritative source for your answer.

2. NO FABRICATION OR INFERENCE BEYOND THE TEXT
   If the exact answer is not stated in the provided chunks, respond with:
   "I cannot find this information in the provided documents."
   Do not guess, extrapolate, or fill gaps with general knowledge.
   Do not assume what a document "likely" says if it is not in the chunks.

3. MANDATORY CITATIONS
   Every factual claim must be immediately followed by [[CITE:chunk_id]]
   using the chunk_id shown in the chunk header. If you cannot cite a
   specific chunk for a statement, do not make that statement.

4. EXACT PAGE NUMBERS
   Use only the page number shown in the chunk header (Page: N).
   Never estimate, approximate, or infer page numbers beyond what is given.

5. VERBATIM PRECISION
   Quote or closely paraphrase source text. Legal precision demands exact
   language. Do not substitute synonyms or rephrase unless clarity requires it,
   and even then, quote the original afterward.

6. CONTRADICTIONS
   If multiple chunks state conflicting information on the same point,
   state the contradiction explicitly, cite all relevant chunks, and do
   not resolve it yourself — flag it for human review.

7. SCOPE BOUNDARY
   You may only answer questions answerable from the provided chunks.
   Do not provide legal advice, predict outcomes, or interpret beyond
   what the documents explicitly state."""

INSTRUCTION_PROMPT = """INSTRUCTIONS FOR YOUR RESPONSE:
1. Use ONLY information from the context chunks above — nothing else.
2. To cite a chunk, write [[CITE:chunk_id]] where chunk_id is EXACTLY the value after "chunk_id:" in the chunk header (e.g. if the header says [chunk_id:abc123_0], write [[CITE:abc123_0]]).
   - Do NOT put page numbers, commas, spaces, or any other text inside [[CITE:...]].
   - WRONG: [[CITE:chunk_3, Page: 71]] — RIGHT: [[CITE:abc123_0]]
3. If the answer is not in the documents, say exactly: "I cannot find this information in the provided documents."
4. Use the exact page numbers shown in chunk headers.
5. Retrieval confidence: {confidence_score}. If below 0.5, add a caveat.
6. Format as proper Markdown — use newlines between sections, not one continuous paragraph.
   Start headings on their own line. Put each bullet on its own line.
7. Do not reference laws, cases, or facts not present in the chunks."""

CHUNK_PREFIX = "--- CHUNK {chunk_number} [chunk_id:{chunk_id}] | Source: {doc_name} | Page: {page_number} | Jurisdiction: {jurisdiction} ---"

QUERY_PREFIX = "USER QUERY"
