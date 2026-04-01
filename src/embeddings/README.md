# Embeddings & FAISS Vector Store Module

**Legal RAG System | Module 2**

Production-ready Python module for generating semantic embeddings and managing efficient vector-based retrieval via FAISS indices with multi-user support and concurrency control.

## Features

✅ **OpenAI Integration**: text-embedding-3-large (3072D) with batching (max 100/batch) and exponential backoff retry  
✅ **FAISS Indexing**: Intelligent choice between IndexFlatL2 (<100K chunks) and IndexIVFFlat (>100K chunks)  
✅ **Multi-user Isolation**: Separate `/indexes/{user_id}/` per user with independent indices  
✅ **Metadata Tracking**: JSON sidecar mapping FAISS IDs to chunk metadata for provenance  
✅ **Concurrency Control**: Reader-writer locks for safe multi-threaded access  
✅ **Semantic Search**: Vector similarity search with configurable thresholds  
✅ **Backup & Recovery**: Point-in-time snapshots with integrity verification  
✅ **Type Safety**: Pydantic models for validation and serialization  

## Installation

### 1. Install Package Dependencies

```bash
pip install -r src/embeddings/requirements.txt
```

### 2. Configure OpenAI API

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or in Python:

```python
import openai
openai.api_key = "sk-..."
```

### 3. Verify FAISS Installation

```bash
python -c "import faiss; print(faiss.__version__)"
```

For GPU support (optional):

```bash
pip install faiss-gpu
```

## Quick Start

### Create Index and Embed Chunks

```python
from src.embeddings import (
    embed_chunks,
    create_user_index,
    add_chunks_to_index,
)
from src.ingestion import ingest_document

# Step 1: Ingest and chunk document (Module 1)
chunks = ingest_document(
    file_path="/data/contract.pdf",
    user_id="user_123"
)

# Step 2: Generate embeddings
embedded_chunks = embed_chunks(chunks, user_id="user_123")
print(f"Embedded {len(embedded_chunks)} chunks")

# Step 3: Create user's FAISS index
index = create_user_index(user_id="user_123")
print(f"Created index: {index.index_type} with {index.chunk_count} chunks")

# Step 4: Add embeddings to index
updated_index = add_chunks_to_index(
    user_id="user_123",
    embedded_chunks=embedded_chunks
)
print(f"Added chunks. Total: {updated_index.chunk_count}")
```

### Retrieve Semantically Similar Chunks

```python
from src.embeddings import retrieve

# Query the index
results = retrieve(
    user_id="user_123",
    query="What are the payment terms?",
    k=10  # Top 10 results
)

for result in results:
    print(f"Score: {result.similarity_score:.3f}")
    print(f"Doc: {result.doc_name} [page {result.page_number}]")
    print(f"Text: {result.text[:100]}...")
    print()
```

### Backup and Recovery

```python
from src.embeddings import backup_index, recover_from_backup, list_backups

# Create backup
backup_path = backup_index(
    user_id="user_123",
    description="Pre-bulk-add checkpoint"
)
print(f"Backup created: {backup_path}")

# List all backups
backups = list_backups(user_id="user_123")
for backup in backups:
    print(f"- {backup.backup_timestamp}: {backup.chunk_count} chunks")

# Recover from backup
metadata = recover_from_backup(
    user_id="user_123",
    backup_timestamp="2026-03-29T14:00:00Z"
)
print(f"Recovered {metadata['chunk_count']} chunks")
```

## Module Structure

```
src/embeddings/
├── __init__.py              # Public API exports
├── models.py                # Pydantic: EmbeddedChunk, UserIndex, RetrievalResult
├── embedder.py              # OpenAI embedding generation with batching/retry
├── indexer.py               # FAISS index creation and management
├── metadata.py              # Metadata sidecar JSON (lineage tracking)
├── storage.py               # Disk I/O: save, load, backup, recover
├── retriever.py             # Vector search and ranking
├── concurrency.py           # Read/write locks for multi-user access
├── exceptions.py            # Custom exception hierarchy
├── constants.py             # Configuration and thresholds
└── requirements.txt         # Dependencies
```

## Data Models

### `EmbeddedChunk` (Embedding + Chunk)

```python
{
    "chunk_id": "doc1_5",
    "text": "Article 1: Definitions...",
    "embedding": [0.123, 0.456, ...],  # 3072-D vector
    "embedding_model": "text-embedding-3-large",
    "doc_name": "contract.pdf",
    "doc_id": "550e8400-e29b-41d4-a716-446655440000",
    "chunk_index": 5,
    "page_number": 2,
    "section": "Article 1",
    "jurisdiction": "California",
    "token_count": 720,
    "has_ocr": false,
    "uploaded_at": "2026-03-29T10:00:00Z",
    "embedded_at": "2026-03-29T10:15:00Z",
    "user_id": "user_123"
}
```

### `UserIndex` (Index Metadata)

```python
{
    "user_id": "user_123",
    "index_type": "flat",  # or "ivf" for large indices
    "embedding_dimension": 3072,
    "chunk_count": 150,
    "created_at": "2026-03-29T10:00:00Z",
    "last_modified": "2026-03-29T14:30:00Z",
    "last_backup": "2026-03-29T14:00:00Z",
    "embedding_model": "text-embedding-3-large",
    "checksum": "sha256:abc123...",
    "metadata_version": 1
}
```

### `RetrievalResult` (Search Result)

```python
{
    "chunk_id": "doc1_5",
    "text": "Article 1: Definitions...",
    "doc_name": "contract.pdf",
    "doc_id": "550e8400-e29b-41d4-a716-446655440000",
    "chunk_index": 5,
    "page_number": 2,
    "section": "Article 1",
    "jurisdiction": "California",
    "distance": 0.234,  # L2 distance (lower = more similar)
    "similarity_score": 0.876,  # Normalized [0, 1]
    "token_count": 720,
    "has_ocr": false
}
```

## Function Reference

### Embedding Generation

#### `embed_chunks(chunks: List[Chunk], user_id: str, **kwargs) -> List[EmbeddedChunk]`

Generate OpenAI embeddings for document chunks.

**Parameters**:
- `chunks`: List of Chunk objects (from Module 1)
- `user_id`: Owning user ID
- `batch_size`: Chunks per API call (max 100, default 100)
- `timeout_seconds`: API timeout (default 60)

**Returns**: `List[EmbeddedChunk]` — Chunks with 3072-D embedding vectors

**Raises**:
- `RateLimitError`: OpenAI rate limit exceeded (retries with exponential backoff)
- `APITimeoutError`: Request timeout
- `EmbeddingGenerationError`: API call failed
- `InvalidChunkError`: Chunk validation failed

**Cost**: ~$0.02 per 1M tokens (for text-embedding-3-large)

**Latency**: ~500-2000ms per 100 chunks (depends on OpenAI congestion)


#### `embed_query(query: str, user_id: str) -> np.ndarray`

Embed a query string for retrieval.

**Parameters**:
- `query`: Query text
- `user_id`: User making query

**Returns**: `np.ndarray` — 3072-D embedding vector

### Index Management

#### `create_user_index(user_id: str, index_type: Optional[str] = None) -> UserIndex`

Create a new FAISS index for a user.

**Parameters**:
- `user_id`: Index owner
- `index_type`: 'flat' (IndexFlatL2) or 'ivf' (IndexIVFFlat), auto-selected if None

**Returns**: `UserIndex` — Index metadata

**Raises**:
- `IndexAlreadyExistsError`: Index already exists for user

**Recommendation**:
- <100K chunks: Use IndexFlatL2 (100% accurate, 500ms queries)
- ≥100K chunks: Use IndexIVFFlat (99% accurate, 50ms queries)


#### `add_chunks_to_index(user_id: str, embedded_chunks: List[EmbeddedChunk]) -> UserIndex`

Add embedded chunks to user's index.

**Parameters**:
- `user_id`: Index owner
- `embedded_chunks`: List of EmbeddedChunk objects

**Returns**: `UserIndex` — Updated index metadata

**Raises**:
- `IndexNotFoundError`: Index does not exist for user
- `EmbeddingError`: Embedding validation failed

**Concurrency**: Uses write lock (exclusive) during add


#### `get_index(user_id: str) -> faiss.Index`

Load FAISS index from disk.

**Parameters**:
- `user_id`: Index owner

**Returns**: `faiss.Index` — Ready-to-search FAISS index

**Raises**:
- `IndexNotFoundError`: Index does not exist
- `CorruptedIndexError`: Index file corrupted

### Vector Search

#### `retrieve(user_id: str, query: str, k: int = 10, threshold: float = 1000.0) -> List[RetrievalResult]`

Query chunks semantically.

**Parameters**:
- `user_id`: Index owner
- `query`: Query text
- `k`: Number of results (default 10, max 100)
- `threshold`: Max L2 distance (lower = more similar)

**Returns**: `List[RetrievalResult]` — Top-k chunks ranked by similarity

**Raises**:
- `IndexNotFoundError`: User's index does not exist
- `EmbeddingError`: Cannot embed query

**Concurrency**: Uses read lock (shared) during search

**Example**:
```python
results = retrieve(
    user_id="user_123",
    query="payment terms",
    k=10,
    threshold=1000.0
)

for result in results:
    print(f"{result.similarity_score:.2%}: {result.text[:100]}")
```


#### `retrieve_with_reranking(user_id: str, query: str, k_initial: int = 50, k_final: int = 10) -> List[RetrievalResult]`

Retrieve with optional re-ranking (future: cross-encoder).

### Backup & Recovery

#### `backup_index(user_id: str, description: Optional[str] = None) -> str`

Create point-in-time backup.

**Parameters**:
- `user_id`: Index owner
- `description`: Backup description (e.g., "pre-bulk-add")

**Returns**: `str` — Path to backup directory

**Backup Structure**:
```
/indexes/{user_id}/backups/{timestamp}/
├── index.faiss
├── metadata.json
└── manifest.json
```

**Retention Policy**:
- Keep last 10 backups per user
- Keep daily backups for 30 days


#### `recover_from_backup(user_id: str, backup_timestamp: str) -> dict`

Restore index from backup.

**Parameters**:
- `user_id`: Index owner
- `backup_timestamp`: Backup timestamp (ISO format)

**Returns**: `dict` — Restored metadata

**Raises**:
- `BackupNotFoundError`: Backup does not exist
- `CorruptedBackupError`: Backup integrity check failed


#### `list_backups(user_id: str) -> List[BackupInfo]`

List all backups.

**Returns**: `List[BackupInfo]` — Backup information (timestamp, description, size, checksum)

## Concurrency Control

### Read Lock (Multiple Readers)

```python
from src.embeddings import read_lock

# Context manager
with read_lock(user_id="user_123", timeout=30):
    results = retrieve(user_id="user_123", query="...")
    # Multiple threads can read concurrently
```

### Write Lock (Exclusive)

```python
from src.embeddings import write_lock

# Context manager
with write_lock(user_id="user_123", timeout=30):
    add_chunks_to_index(user_id="user_123", embedded_chunks=[...])
    # Blocks all other readers and writers
```

### Manual Lock Management

```python
from src.embeddings import get_user_lock

lock = get_user_lock(user_id="user_123")

# Read lock
lock.acquire_read(timeout=30)
try:
    results = retrieve(user_id="user_123", query="...")
finally:
    lock.release_read()

# Write lock
lock.acquire_write(timeout=30)
try:
    add_chunks_to_index(user_id="user_123", embedded_chunks=[...])
finally:
    lock.release_write()
```

## Index Selection Guide

### When to Use IndexFlatL2

- **Chunk count**: <100K
- **Query latency**: 50-500ms acceptable
- **Accuracy**: 100% required
- **Setup complexity**: Minimal
- **Example**: Small legal team (<5M documents)

```python
index = create_user_index(user_id, index_type="flat")
```

### When to Use IndexIVFFlat

- **Chunk count**: ≥100K
- **Query latency**: <100ms required
- **Accuracy**: 99% acceptable
- **Dataset size**: Million-scale
- **Example**: Enterprise legal library

```python
index = create_user_index(user_id, index_type="ivf")
```

## Configuration

Edit `src/embeddings/constants.py` to customize:

```python
# OpenAI
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSION = 3072
BATCH_SIZE = 100
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

# FAISS
FAISS_FLAT_THRESHOLD = 100_000  # Switch to IVF above this
INDEX_TYPE_FLAT = "flat"
INDEX_TYPE_IVF = "ivf"

# Concurrency
LOCK_TIMEOUT_SECONDS = 30

# Retrieval
DEFAULT_K = 10
MAX_K = 100

# Backup
BACKUPS_KEEP_COUNT = 10
BACKUPS_KEEP_DAYS = 30
```

## Error Handling

All errors inherit from `EmbeddingError` base class:

```python
from src.embeddings import (
    embed_chunks,
    EmbeddingError,
    RateLimitError,
    APITimeoutError,
    IndexNotFoundError,
)

try:
    embedded = embed_chunks(chunks, user_id)
except RateLimitError as e:
    print(f"Rate limited; retry in {e.retry_after}s")
except APITimeoutError as e:
    print(f"OpenAI timeout: {e}")
except IndexNotFoundError as e:
    print(f"User has no index yet")
except EmbeddingError as e:
    print(f"Embedding failed: {e}")
```

## Performance & SLAs

### Embedding Latency

| Scale | Model | Latency | Cost |
|-------|-------|---------|------|
| 100 chunks | text-embedding-3-large | 500ms | $0.00002 |
| 1,000 chunks | text-embedding-3-large | 5s | $0.00015 |
| 1M chunks | text-embedding-3-large | ~1.5h | $15 |

### Search Latency

| Scenario | Index Type | Latency | Throughput |
|----------|-----------|---------|-----------|
| 100K chunks, k=10 | Flat | 100-500ms | 200 QPS |
| 100K chunks, k=10 | IVF | 10-50ms | 1000 QPS |
| 1M chunks, k=10 | IVF | 50-100ms | 500 QPS |

### Storage

| Scenario | Size |
|----------|------|
| 1K chunks (3072D) | 12 MB |
| 10K chunks | 120 MB |
| 100K chunks | 1.2 GB |
| 1M chunks | 12 GB |

## Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("src.embeddings")
```

Example output:
```
INFO:src.embeddings.embedder:Embedding 150 chunks for user user_123
DEBUG:src.embeddings.embedder:Created 2 batches for embedding
DEBUG:src.embeddings.embedder:Processing batch 1/2
INFO:src.embeddings.embedder:Successfully embedded 150 chunks
INFO:src.embeddings.indexer:Added 150 chunks to index for user_123
INFO:src.embeddings.retriever:Retrieved 10 results for user user_123
```

## Future Enhancements

1. **GPU Acceleration**: FAISS-GPU for million-scale indices
2. **Hybrid Search**: Dense + sparse (BM25) search combination
3. **Cross-encoder Re-ranking**: LLM-based semantic ranking
4. **Incremental Indexing**: IVF index rebuilding without full re-index
5. **Distance Metrics**: Cosine, IP (dot product) in addition to L2
6. **Query Expansion**: Pseudo-relevance feedback
7. **Caching**: Redis/Memcached for popular queries
8. **Monitoring**: Prometheus metrics (latency, throughput, errors)

## Testing

```bash
pytest tests/embeddings/ -v --cov=src/embeddings
```

Test coverage:
- Embedding generation (batching, retry, errors)
- Index creation (flat, IVF)
- Add/search operations
- Metadata sidecar
- Concurrency (read/write locks)
- Backup/recovery
- Edge cases (corrupted files, missing metadata)

---

**Last updated**: March 29, 2026  
**License**: Proprietary (Legal Bot System)
