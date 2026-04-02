"""
Configuration constants for embeddings and vector store.
"""

# OpenAI Embedding Model
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536D — 4× smaller responses, same quality for legal RAG
EMBEDDING_DIMENSION = 1536
EMBEDDING_MAX_TOKENS = 8192  # Hard API limit
EMBEDDING_COST_PER_1M_TOKENS = 0.02  # USD

# Batching — keep small to avoid MemoryError on large documents
BATCH_SIZE = 20
MAX_BATCH_SIZE = 20
MIN_BATCH_SIZE = 1
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # exponential: 2^n seconds

# OpenAI API
OPENAI_API_TIMEOUT = 60  # seconds
OPENAI_API_MAX_CONCURRENT = 10

# FAISS Index Configuration
FAISS_FLAT_THRESHOLD = 100_000  # Use flat for <100K chunks
FAISS_IVF_NLIST_FORMULA = "sqrt(N) / 4"  # Scaled IVF
FAISS_IVF_PROBE_BASE = 8  # Probe factor
FAISS_INDEX_VERSION = 1

# Index Types
INDEX_TYPE_FLAT = "flat"
INDEX_TYPE_IVF = "ivf"

# Indexing Parameters (for IVFFlat)
IVF_NLIST_MIN = 16  # Minimum clusters
IVF_NLIST_MAX = 1000  # Maximum clusters
IVF_PROBE_MIN = 1
IVF_PROBE_MAX = 256  # Can search all clusters

# Storage Paths
INDEXES_BASE_DIR = "./indexes"
METADATA_FILE = "metadata.json"
METADATA_BACKUP_FILE = "metadata.json.bak"
INDEX_FILE = "index.faiss"
INDEX_PICKLE_FILE = "index.pkl"  # Legacy
MANIFEST_FILE = "manifest.json"
TRANSACTION_LOG_FILE = "transaction_log.jsonl"
BACKUPS_DIR = "backups"

# Checksum Algorithm
CHECKSUM_ALGORITHM = "sha256"

# Backup Policy
BACKUPS_KEEP_COUNT = 10  # Keep last N backups per user
BACKUPS_KEEP_DAYS = 30  # Keep for N days

# Concurrency
LOCK_TIMEOUT_SECONDS = 30
READ_LOCK_TYPE = "read"
WRITE_LOCK_TYPE = "write"

# Retrieval
DEFAULT_K = 10
MAX_K = 100
DEFAULT_DISTANCE_THRESHOLD = 1000.0  # Max L2 distance

# Metadata Sidecar
METADATA_VERSION = 1

# Performance Targets
EMBEDDING_LATENCY_MS_PER_100 = 1000  # 1s for 100 chunks
SEARCH_LATENCY_MS_FLAT = 500  # Flat index search (100K vectors)
SEARCH_LATENCY_MS_IVF = 50  # IVF index search (1M vectors)
SAVE_INDEX_LATENCY_MS = 500  # Save to disk

# Validation
MIN_CHUNK_FOR_INDEX = 1
MAX_EMBEDDING_QUEUE = 10_000

# Checksums
TEXT_CHECKSUM_ALGORITHM = "md5"

# Timestamps
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
