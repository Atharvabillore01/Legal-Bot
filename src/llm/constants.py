"""
Configuration constants for the LLM interface module.

All prompts, model params, token budgets, and feature flags live here.
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

# ==============================================================
# CITATION
# ==============================================================

# Matches [[CITE:some_chunk_id_123]]
CITATION_MARKER_PATTERN = r"\[\[CITE:([a-zA-Z0-9_\-]+)\]\]"

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

INSTRUCTION_PROMPT = """INSTRUCTIONS:
- Base your entire answer on the context chunks above and nothing else.
- Cite every factual claim immediately: [[CITE:chunk_id]].
- If the answer is not in the provided documents, say exactly:
  "I cannot find this information in the provided documents."
- Use the exact page numbers from chunk headers — never guess page numbers.
- Retrieval confidence for this query: {confidence_score} (0=low, 1=high).
  If confidence is below 0.5, explicitly caveat that coverage may be incomplete.
- Format your response in clear, structured Markdown.
- Do not reference any law, regulation, case, or fact absent from the chunks."""

CHUNK_PREFIX = "--- CHUNK {chunk_number} | Source: {doc_name} | Page: {page_number} | Jurisdiction: {jurisdiction} ---"

QUERY_PREFIX = "USER QUERY"
