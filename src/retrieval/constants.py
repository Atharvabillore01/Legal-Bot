"""
src/retrieval/constants.py

Configuration constants for the retrieval and reranking module.

All configuration is centralized here for easy modification and testing.
Organized by functional area.
"""

# ============================================================
# SEMANTIC SEARCH
# ============================================================

SEMANTIC_K_DEFAULT = 7                          # Top-K for semantic search
SEMANTIC_K_MAX = 50                             # Max k for FAISS
SEMANTIC_K_RETRIEVAL_MULTIPLIER = 7             # Retrieve 7x k for filtering

SEMANTIC_DISTANCE_THRESHOLD = 1000.0            # Max L2 distance to include
SEMANTIC_SCORE_FORMULA = "1 / (1 + l2_distance)"  # Conversion to [0,1]

# ============================================================
# KEYWORD SEARCH (BM25)
# ============================================================

KEYWORD_K_DEFAULT = 50                          # Top-K for BM25
KEYWORD_MIN_SCORE = 0.1                         # Min BM25 score threshold

# BM25 parameters (Okapi BM25)
BM25_K1 = 1.5                                   # Term frequency saturation
BM25_B = 0.75                                   # Length normalization
BM25_AVG_DOC_LENGTH = 750                       # Average chunk length (words)

# ============================================================
# HYBRID SEARCH
# ============================================================

HYBRID_ALPHA_DEFAULT = 0.7                      # Weight for semantic
HYBRID_ALPHA_MIN = 0.0                          # All keyword
HYBRID_ALPHA_MAX = 1.0                          # All semantic

# ============================================================
# METADATA FILTERING
# ============================================================

FILTER_EXCLUDE_OVERLAPPING_DEFAULT = False      # Allow multiple per doc
FILTER_MIN_CONFIDENCE_DEFAULT = 0.0             # No minimum confidence

# Known jurisdictions (for validation)
KNOWN_JURISDICTIONS = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
    "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
    "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    "Wisconsin", "Wyoming", "District of Columbia",
    # International
    "England", "Scotland", "Wales", "Northern Ireland",
    "Canada", "Ontario", "Quebec", "British Columbia",
    "Australia", "New South Wales", "Victoria",
    "Germany", "France", "Japan", "Singapore", "Hong Kong",
}

# ============================================================
# CONTRADICTION DETECTION
# ============================================================

CONTRADICTION_DETECTION_ENABLED = True
CONTRADICTION_MIN_CONFIDENCE = 0.5              # Min to report

# Severity scoring thresholds
CONTRADICTION_VALUE_DIFF_THRESHOLD = 0.05       # 5% = negligible
CONTRADICTION_SEVERITY_LOW_THRESHOLD = 0.2      # <20% = low
CONTRADICTION_SEVERITY_MEDIUM_THRESHOLD = 0.6   # 20-60% = medium
# >60% = high

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
    "Representations",
    "Force Majeure",
    "Dispute Resolution",
    "Arbitration",
    "Attorney Fees",
    "Survival",
}

# ============================================================
# RERANKING
# ============================================================

RERANK_CONFLICT_PENALTY_PER_ISSUE = 0.15        # 15% per conflict
RERANK_AUTHORITY_BONUS_BINDING = 0.10           # Binding documents
RERANK_AUTHORITY_BONUS_PRECEDENT = 0.05         # Precedent documents
RERANK_AUTHORITY_BONUS_REFERENCE = 0.0          # Reference (no bonus)

RERANK_RECENCY_BONUS_MAX = 0.10                 # Max 10% bonus
RERANK_RECENCY_DECAY_DAYS = 365                 # Linear decay over 1 year

RERANK_UNIQUENESS_BONUS = 0.05                  # Sole doc result bonus

# ============================================================
# FALLBACK STRATEGY
# ============================================================

FALLBACK_MODE_DEFAULT = "return_all"            # or "relax_filters"

# Order to relax filters (least to most restrictive)
FALLBACK_FILTER_RELAX_ORDER = [
    "date_range",                                # Most relaxable
    "authority_levels",
    "jurisdictions",
    "exclude_overlapping",                       # Least relaxable
]

# Confidence thresholds for fallback lowering
FALLBACK_MIN_CONFIDENCE_THRESHOLDS = [0.6, 0.5, 0.4, 0.3, 0.2, 0.1]

# ============================================================
# PERFORMANCE SLAs
# ============================================================

LATENCY_SEMANTIC_SEARCH_MS = 50                 # FAISS knn()
LATENCY_KEYWORD_SEARCH_MS = 30                  # BM25 search
LATENCY_FILTER_MS = 20                          # Metadata filtering
LATENCY_CONTRADICTION_DETECTION_MS = 60         # Conflict detection
LATENCY_RERANKING_MS = 30                       # Score adjustment
LATENCY_TOTAL_BUDGET_MS = 200                   # E2E SLA

# Warnings if latency exceeded
LATENCY_WARNING_THRESHOLD = 0.8                 # Warn if >80% of budget used

# ============================================================
# QUERY VALIDATION
# ============================================================

QUERY_MIN_LENGTH = 1                            # At least 1 char
QUERY_MAX_LENGTH = 1000                         # Max 1000 chars
QUERY_MIN_TOKENS = 1                            # At least 1 token
QUERY_MAX_TOKENS = 128                          # Max 128 tokens

# Characters to strip from query
QUERY_STRIP_CHARS = " \t\n\r"

# ============================================================
# RESULT LIMITS
# ============================================================

RESULT_K_DEFAULT = 7                            # Default top-K
RESULT_K_MIN = 1
RESULT_K_MAX = 50                               # Hard limit

# ============================================================
# SCORING NORMALIZATION
# ============================================================

# Semantic to [0, 1]
SEMANTIC_SCORE_MIN = 0.0                        # Minimum score
SEMANTIC_SCORE_MAX = 1.0                        # Maximum score

# Keyword (BM25) to [0, 1]
KEYWORD_SCORE_MIN = 0.0
KEYWORD_SCORE_MAX = 1.0

# Hybrid merge
HYBRID_SCORE_MIN = 0.0
HYBRID_SCORE_MAX = 1.0

# Final rank score (after reranking)
FINAL_SCORE_MIN = 0.0
FINAL_SCORE_MAX = 1.0

# ============================================================
# AUTHORITY LEVELS
# ============================================================

AUTHORITY_LEVELS = {
    "binding",                                   # Contract, statute, binding ruling
    "precedent",                                 # Case law, established precedent
    "reference",                                 # General reference, discussion
}

AUTHORITY_LEVEL_DEFAULT = "reference"

# Authority ordering (for preference)
AUTHORITY_RANKING = {
    "binding": 3,
    "precedent": 2,
    "reference": 1,
}

# ============================================================
# CONTRADICTION RESOLUTION
# ============================================================

RESOLUTION_STRATEGIES = {
    "prefer_newer",                              # Use newer document
    "prefer_binding",                            # Use binding authority
    "manual_review",                             # Flag for human review
}

RESOLUTION_DEFAULT = "manual_review"

# ============================================================
# LOGGING & MONITORING
# ============================================================

LOG_LEVEL_DEFAULT = "INFO"                      # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Log events to track
LOG_EMPTY_QUERY = True
LOG_NO_RESULTS = True
LOG_TIMEOUT = True
LOG_FALLBACK_APPLIED = True
LOG_CONTRADICTIONS_DETECTED = True
LOG_RERANKING_ADJUSTMENTS = False               # Can be verbose

# ============================================================
# CACHE SETTINGS (if caching enabled)
# ============================================================

ENABLE_QUERY_CACHE = False                      # Cache frequent queries
CACHE_TTL_SECONDS = 3600                        # Cache for 1 hour
CACHE_MAX_SIZE = 1000                           # Max 1000 cached queries

# ============================================================
# FEATURE FLAGS
# ============================================================

ENABLE_SEMANTIC_SEARCH = True
ENABLE_KEYWORD_SEARCH = False                   # Requires BM25 index
ENABLE_HYBRID_SEARCH = False                    # Requires both
ENABLE_CONTRADICTION_DETECTION = True
ENABLE_RERANKING = True
ENABLE_FALLBACK_STRATEGIES = True

# ============================================================
# DEFAULT SEARCH OPTIONS
# ============================================================

DEFAULT_SEARCH_OPTIONS = {
    "k": RESULT_K_DEFAULT,
    "use_semantic": ENABLE_SEMANTIC_SEARCH,
    "use_keyword": ENABLE_KEYWORD_SEARCH,
    "hybrid_alpha": HYBRID_ALPHA_DEFAULT,
    "filters": None,
    "detect_contradictions": ENABLE_CONTRADICTION_DETECTION,
    "rerank": ENABLE_RERANKING,
    "return_all_matches": False,
    "explain_scores": False,
}

# ============================================================
# BOUNDARY CONDITIONS
# ============================================================

# If fewer results than k after all processing, apply fallback
FALLBACK_TRIGGER_THRESHOLD = 0.9                # 90% of k

# Max chunks to load for deduplication and filtering
MAX_CHUNKS_TO_PROCESS = 1000                    # Safety limit

# Max contradiction pairs to compute
MAX_CONTRADICTION_PAIRS = 500                   # Limit O(n^2) complexity

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def is_valid_jurisdiction(jurisdiction: str) -> bool:
    """Check if jurisdiction is in known list."""
    return jurisdiction in KNOWN_JURISDICTIONS


def is_valid_authority_level(level: str) -> bool:
    """Check if authority level is valid."""
    return level in AUTHORITY_LEVELS


def get_authority_rank(level: str) -> int:
    """Get numeric rank for authority level."""
    return AUTHORITY_RANKING.get(level, 0)
