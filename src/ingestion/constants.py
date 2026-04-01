"""
Configuration constants for document ingestion pipeline.
"""

# Chunking parameters
CHUNK_SIZE_TOKENS = 750
CHUNK_OVERLAP_TOKENS = 150
RECURSIVE_SPLITTERS = ["\n\n", "\n", " ", ""]

# File type support
SUPPORTED_FILE_TYPES = {"pdf", "docx", "txt"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx", ".doc"}
TXT_EXTENSIONS = {".txt"}

# File size limits
PDF_MAX_PAGES = 1000
PDF_MAX_SIZE_MB = 200
DOCX_MAX_SIZE_MB = 100
TXT_MAX_SIZE_MB = 50

# Encoding
ENCODING_FALLBACK_CHAIN = ["utf-8", "latin-1", "ascii"]
TIKTOKEN_MODEL = "gpt-3.5-turbo"

# OCR
OCR_CONFIDENCE_THRESHOLD = 0.7
SCANNED_PAGE_THRESHOLD = 0.05  # <5% text density → OCR attempt

# Text cleaning
EMPTY_THRESHOLD = 10  # minimum character count
MAX_CONSECUTIVE_NEWLINES = 2
MAX_CONSECUTIVE_SPACES = 1

# Chunk validation
MIN_CHUNK_TOKENS = 1
MAX_CHUNK_TOKENS = CHUNK_SIZE_TOKENS * 2  # 1500 max

# Small document threshold — documents whose total token count fits within this
# limit are NOT split into chunks; the full text is sent as a single embedding.
# Constrained by the embedding model (text-embedding-3-large) max of 8192 tokens.
# Using 8000 as a safe margin below the API hard limit.
SMALL_DOCUMENT_TOKEN_THRESHOLD = 8_000

# Heuristic thresholds
FOOTER_MARKER_PATTERNS = {
    r"^\s*page\s+\d+\s*$",  # "page 5"
    r"^\s*\d+\s*$",  # "5"
    r"^[\s\d\.\-]+$",  # page number only
    r"©.*\d{4}",  # copyright
}

# Date/timestamp format
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
