# Embeddings & FAISS Vector Store Module — Technical Specification
**Legal RAG System | Module 2**

---

## 1. Overview

The **Embeddings & FAISS Vector Store Module** handles semantic embedding generation for document chunks and manages efficient vector-based retrieval via FAISS indices. Each user maintains isolated indices with metadata tracking for lineage and multi-tenancy.

### Key Objectives
- **OpenAI Integration**: Generate embeddings using `text-embedding-3-large` (3072 dims)
- **Efficient Batching**: Process 100 chunks per batch with exponential backoff retry
- **FAISS Indexing**: Create optimized indices with intelligent choice between IndexFlatL2 and IndexIVFFlat
- **Multi-user Isolation**: Separate `/indexes/{user_id}/` directory per user
- **Metadata Tracking**: JSON sidecar maps FAISS integer IDs → Chunk objects for provenance
- **Concurrency**: Read/write lock strategy for safe concurrent multi-user access
- **Index Lifecycle**: Create, add, save, load, delete, backup, recover
- **Recovery**: Point-in-time backups with checksums and rollback capability

---

## 2. Architecture & Data Flow

### 2.1 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                             │
│                                                                   │
│  (Chunks from Module 1)                                           │
│                                                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  EMBEDDING GENERATION        │
        │  (OpenAI API with batching)  │
        │  text-embedding-3-large      │
        │  3072D vectors               │
        │  Exponential backoff retry   │
        └──────────────────┬───────────┘
                           │
                           ▼
        ┌──────────────────────────────┐
        │  EMBEDDED CHUNK VALIDATION   │
        │  & DEDUPLICATION             │
        │                              │
        └──────────────────┬───────────┘
                           │
            ┌──────────────┴──────────────┐
            │                             │
            ▼                             ▼
  ┌─────────────────────┐    ┌──────────────────────┐
  │  USER INDEX MGMT    │    │  METADATA SIDECAR    │
  │  FAISS Index        │    │  JSON mapping        │
  │  ├─ Create          │    │  faiss_id → Chunk   │
  │  ├─ Add             │    │  + checksums        │
  │  ├─ Save            │    │                      │
  │  ├─ Load            │    │                      │
  │  └─ Delete          │    └──────────────────────┘
  │                     │
  │  IndexFlatL2        │
  │  OR IndexIVFFlat    │
  └─────────────────────┘
            │
            ▼
  ┌──────────────────────────────────┐
  │  DISK STORAGE                    │
  │  /indexes/{user_id}/              │
  │  ├─ index.faiss                  │
  │  ├─ index.pkl (legacy)           │
  │  ├─ metadata.json                │
  │  ├─ metadata.json.bak            │
  │  └─ backups/                     │
  │      └─ {timestamp}/             │
  │          ├─ index.faiss          │
  │          ├─ metadata.json        │
  │          └─ manifest.json        │
  └──────────────────────────────────┘
            │
            ▼
  ┌──────────────────────────────────┐
  │  RETRIEVAL (Vector Search)       │
  │  - Query embedding generation    │
  │  - FAISS similarity search       │
  │  - Metadata lookup & ranking     │
  │  - Return ranked Chunks          │
  └──────────────────────────────────┘
```

---

## 3. Module Structure

```
src/embeddings/
├── __init__.py                  # Public API exports
├── models.py                    # Pydantic: EmbeddedChunk, UserIndex, EmbeddingBatch
├── embedder.py                  # OpenAI embedding generation with batching
├── indexer.py                   # FAISS index creation, management, optimization
├── metadata.py                  # Metadata sidecar JSON handling
├── storage.py                   # Disk I/O: save, load, backup, recover
├── retriever.py                 # Vector search and ranking
├── concurrency.py               # Read/write locks, transaction management
├── exceptions.py                # Custom exceptions
├── constants.py                 # Configuration and thresholds
└── requirements.txt             # Dependencies
```

---

## 4. Data Models (Pydantic)

### 4.1 `EmbeddedChunk` Model
Chunk + word embedding vector.

```python
from pydantic import BaseModel, Field
from typing import Optional, List
import numpy as np

class EmbeddedChunk(BaseModel):
    """A chunk with computed embedding vector."""
    
    # Original chunk data (from Module 1)
    chunk_id: str = Field(description="Unique chunk identifier (doc_id_chunk_index)")
    text: str = Field(description="Chunk text content")
    token_count: int = Field(ge=1, description="Token count")
    
    # Document metadata
    doc_name: str = Field(description="Original document filename")
    doc_id: str = Field(description="Document ID")
    chunk_index: int = Field(ge=0, description="Chunk sequence number")
    page_number: Optional[int] = Field(default=None, description="Page number if available")
    section: Optional[str] = Field(default=None, description="Section heading")
    jurisdiction: Optional[str] = Field(default=None, description="Legal jurisdiction")
    user_id: str = Field(description="Owning user ID")
    has_ocr: bool = Field(default=False, description="OCR indicator")
    
    # Embedding
    embedding: List[float] = Field(
        description="3072-D embedding vector from text-embedding-3-large"
    )
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="OpenAI embedding model used"
    )
    
    # Metadata
    uploaded_at: str = Field(description="ISO 8601 upload timestamp")
    embedded_at: str = Field(description="ISO 8601 embedding generation timestamp")
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            np.ndarray: lambda v: v.tolist()
        }


class MetadataEntry(BaseModel):
    """Single entry in metadata sidecar."""
    
    faiss_id: int = Field(ge=0, description="FAISS integer ID in index")
    chunk_id: str = Field(description="Chunk identifier")
    doc_id: str = Field(description="Document ID")
    doc_name: str = Field(description="Document filename")
    chunk_index: int = Field(ge=0, description="Chunk sequence")
    page_number: Optional[int] = Field(default=None, description="Page number")
    section: Optional[str] = Field(default=None, description="Section heading")
    jurisdiction: Optional[str] = Field(default=None, description="Jurisdiction")
    user_id: str = Field(description="Owning user ID")
    has_ocr: bool = Field(default=False, description="OCR indicator")
    token_count: int = Field(ge=1, description="Token count")
    uploaded_at: str = Field(description="Upload timestamp")
    embedded_at: str = Field(description="Embedding timestamp")
    text_checksum: str = Field(description="MD5 checksum of chunk text for integrity")


class UserIndex(BaseModel):
    """Metadata about a user's FAISS index."""
    
    user_id: str = Field(description="Index owner user ID")
    index_type: str = Field(
        description="Type: 'flat' (IndexFlatL2) or 'ivf' (IndexIVFFlat)"
    )
    embedding_dimension: int = Field(
        default=3072,
        description="Vector dimensionality"
    )
    chunk_count: int = Field(
        ge=0,
        default=0,
        description="Number of chunks in index"
    )
    created_at: str = Field(description="Index creation timestamp")
    last_modified: str = Field(description="Last modification timestamp")
    last_backup: Optional[str] = Field(default=None, description="Last backup timestamp")
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Underlying embedding model"
    )
    checksum: str = Field(
        description="SHA256 checksum of index file (for integrity verification)"
    )
    metadata_version: int = Field(
        default=1,
        description="Metadata schema version"
    )
    notes: Optional[str] = Field(default=None, description="Optional notes/tags")


class EmbeddingBatch(BaseModel):
    """A batch of chunks ready for embedding."""
    
    batch_id: str = Field(description="Unique batch identifier")
    chunk_ids: List[str] = Field(description="List of chunk IDs in batch")
    texts: List[str] = Field(description="List of texts to embed")
    batch_size: int = Field(ge=1, description="Number of items in batch")
    
    class Config:
        json_encoders = {list: lambda v: v}
```

---

## 5. Index Selection: IndexFlatL2 vs IndexIVFFlat

### 5.1 Comparison Table

| Aspect | IndexFlatL2 | IndexIVFFlat |
|--------|-------------|--------------|
| **Type** | Exhaustive search | Approximate search (IVF) |
| **Accuracy** | 100% (gold standard) | ~99% (configurable) |
| **Build Time** | O(1) - trivial | O(n) - train on subset |
| **Search Time** | O(n*d) - linear | O(nlist*probe*d) - sublinear |
| **Memory** | n * 3072 * 4 bytes | Same + nlist vectors |
| **Index Size** | ~12 MB per 1K chunks | ~12.5 MB per 1K chunks |
| **Query Latency** | ~100-500ms (100K vectors) | ~5-50ms (100K vectors) |
| **Throughput** | 200+ QPS | 1000+ QPS |
| **Scalability** | <500K chunks good | >500K chunks excellent |
| **Implementation** | Simple, no training | Requires clustering |
| **Use Case** | <500K vectors | >500K vectors |

### 5.2 Recommendation Strategy

```
IF chunk_count < 100K:
    USE IndexFlatL2
    REASON: Speed/accuracy tradeoff negligible for small indices
    BENEFIT: No training overhead, simpler code, 100% recall

IF 100K <= chunk_count < 1M:
    USE IndexIVFFlat with nlist=sqrt(N)/4 (scaled IVF)
    REASON: Balance speed and accuracy
    PARAMS: nlist=~80 (for 100K), probe=16-32

IF chunk_count >= 1M:
    USE IndexIVFFlat with nlist=sqrt(N) (standard)
    REASON: Necessary for scalability
    PARAMS: nlist=~1000 (for 1M), probe=32-64
```

### 5.3 Index Creation Logic

```python
def select_index_type(chunk_count: int) -> str:
    """
    Select optimal index type based on chunk count.
    
    Args:
        chunk_count: Current number of chunks in index
    
    Returns:
        str: 'flat' or 'ivf'
    """
    if chunk_count < 100_000:
        return "flat"  # IndexFlatL2
    else:
        return "ivf"   # IndexIVFFlat
```

---

## 6. Function Contracts

### 6.1 Embedder Module (`embedder.py`)

#### `embed_chunks(chunks: List[Chunk], user_id: str) -> List[EmbeddedChunk]`
**Purpose**: Generate embeddings for a list of chunks with batching and retry.

**Signature**:
```python
def embed_chunks(
    chunks: List[Chunk],
    user_id: str,
    batch_size: int = 100,
    timeout_seconds: int = 60,
) -> List[EmbeddedChunk]:
    """
    Generate OpenAI embeddings for chunks with batching & exponential backoff.
    
    Args:
        chunks: List of Chunk objects from Module 1
        user_id: Owning user ID
        batch_size: Chunks per API call (max 100)
        timeout_seconds: Overall timeout for request
    
    Returns:
        List[EmbeddedChunk]: Chunks with embedding vectors
    
    Raises:
        EmbeddingError: API call failed
        RateLimitError: OpenAI rate limit exceeded
        APITimeoutError: Request timeout
        InvalidChunkError: Chunk validation failed
    
    Strategy:
        1. Validate all chunks and deduplicate
        2. Split into batches of ≤100
        3. For each batch:
            a. Call OpenAI API
            b. Handle rate limit with exponential backoff (2^n seconds)
            c. Retry up to 3 times
            d. Map responses to chunks
        4. Return EmbeddedChunk objects sorted by original order
    
    Cost:
        - OpenAI: $0.02 per 1M input tokens (text-embedding-3-large)
        - For legal doc chunks (750 tokens avg): ~$15 per 1M chunks
    
    Latency:
        - Per batch (100 chunks): ~500-2000ms (depends on API congestion)
        - For 1000 chunks: ~5-20 seconds total
    """
```

**Batching Strategy**:
```
Request: [chunk1, chunk2, ..., chunk100]
OpenAI API (rate limit: 500K tokens/min for paid users)
         ↓
Response: [embedding1, embedding2, ..., embedding100]
         ↓
Map back: [(chunk1, emb1), (chunk2, emb2), ...]
         ↓
Exponential backoff on rate limit:
  Attempt 1: immediate
  Attempt 2: wait 2^1 = 2s
  Attempt 3: wait 2^2 = 4s
  Attempt 4: wait 2^3 = 8s (then fail)
```

---

#### `embed_query(query: str, user_id: str) -> np.ndarray`
**Purpose**: Embed a single query string for retrieval.

**Signature**:
```python
def embed_query(query: str, user_id: str) -> np.ndarray:
    """
    Generate embedding for a query string.
    
    Args:
        query: Query text
        user_id: User making query (for logging)
    
    Returns:
        np.ndarray: 3072-D embedding vector
    
    Raises:
        EmbeddingError: API call failed
        RateLimitError: Rate limit exceeded
    
    Note:
        Queries use same embedding model as chunks (text-embedding-3-large)
        for consistency in vector space.
    """
```

---

#### `batch_embed_chunks(chunks: List[Chunk], user_id: str) -> List[EmbeddedChunk]`
**Purpose**: Optimized batching wrapper.

```python
def batch_embed_chunks(
    chunks: List[Chunk],
    user_id: str,
    batch_size: int = 100,
    max_retries: int = 3,
) -> List[EmbeddedChunk]:
    """
    Internal: Orchestrate batched embedding with retry logic.
    
    Process:
        1. Split chunks into batches of batch_size
        2. For each batch, call embed_batch()
        3. On rate limit, sleep and retry
        4. Combine results, preserving order
    
    Returns:
        List[EmbeddedChunk]: All chunks with embeddings
    """
```

---

#### `embed_batch(texts: List[str]) -> List[List[float]]`
**Purpose**: Low-level API call for embedding batch.

```python
def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Call OpenAI API to embed batch of texts.
    
    Args:
        texts: List of texts (len ≤ 100)
    
    Returns:
        List[List[float]]: List of 3072-D vectors
    
    Raises:
        EmbeddingError: API call failed
        RateLimitError: Rate limit hit
        APITimeoutError: Timeout exceeded
    
    OpenAI API:
        POST https://api.openai.com/v1/embeddings
        model: "text-embedding-3-large"
        input: ["text1", "text2", ...]
        Response: {"data": [{"embedding": [...]}, ...]}
    """
```

---

### 6.2 Indexer Module (`indexer.py`)

#### `create_user_index(user_id: str) -> UserIndex`
**Purpose**: Initialize a new FAISS index for a user.

**Signature**:
```python
def create_user_index(
    user_id: str,
    index_type: Optional[str] = None,
    embedding_dim: int = 3072,
) -> UserIndex:
    """
    Create a new FAISS index for a user.
    
    Args:
        user_id: Index owner
        index_type: 'flat', 'ivf', or None (auto-select). Default uses flat.
        embedding_dim: Vector dimensionality (3072 for text-embedding-3-large)
    
    Returns:
        UserIndex: Metadata about created index
    
    Raises:
        IndexError: Index already exists
        StorageError: Cannot create directory /indexes/{user_id}/
    
    Side effects:
        - Creates directory: /indexes/{user_id}/
        - Initializes FAISS index in memory (NOT saved to disk yet)
        - Creates empty metadata.json
    """
```

---

#### `add_chunks_to_index(user_id: str, embedded_chunks: List[EmbeddedChunk]) -> UserIndex`
**Purpose**: Add embedded chunks to a user's index.

**Signature**:
```python
def add_chunks_to_index(
    user_id: str,
    embedded_chunks: List[EmbeddedChunk],
) -> UserIndex:
    """
    Add embedded chunks to user's FAISS index.
    
    Args:
        user_id: Index owner
        embedded_chunks: Chunks with embedding vectors
    
    Returns:
        UserIndex: Updated index metadata
    
    Raises:
        IndexNotFoundError: Index does not exist for user
        EmbeddingError: Embedding vector invalid
        StorageError: Cannot write to disk
    
    Process:
        1. Load user's FAISS index from disk (or memory if cached)
        2. Convert embeddings to numpy array
        3. Call index.add() to append vectors
        4. Update metadata.json with FAISS IDs
        5. Save index to disk
        6. Calculate checksums
        7. Update UserIndex metadata
    
    FAISS ID assignment:
        new_faiss_id = next_id = current_index.ntotal
        For each chunk: faiss_id = next_id + i
    
    Deduplication:
        - Check if chunk_id already in metadata.json
        - Skip duplicates (warn in log)
        - Track in metadata: deduplicated_count
    """
```

---

#### `get_index(user_id: str) -> 'faiss.Index'`
**Purpose**: Load FAISS index from disk.

**Signature**:
```python
def get_index(user_id: str) -> 'faiss.Index':
    """
    Load FAISS index from disk for a user.
    
    Args:
        user_id: Index owner
    
    Returns:
        faiss.Index: Ready-to-search index
    
    Raises:
        IndexNotFoundError: Index does not exist
        CorruptedIndexError: Index file corrupted or invalid format
        StorageError: Disk read error
    
    Caching:
        Optionally caches index in process memory for repeated queries.
        Cache invalidation on write operations (add_chunks, delete, etc.)
    """
```

---

#### `search_index(user_id: str, query_embedding: np.ndarray, k: int = 10) -> List[tuple]`
**Purpose**: Semantic vector search in user's index.

**Signature**:
```python
def search_index(
    user_id: str,
    query_embedding: np.ndarray,
    k: int = 10,
    threshold: float = 0.0
) -> List[tuple]:
    """
    Search FAISS index and return top-k similar chunks.
    
    Args:
        user_id: Index owner
        query_embedding: Query vector (3072-D)
        k: Number of results to return (default 10)
        threshold: Minimum similarity score (optional filter)
    
    Returns:
        List[tuple]: [(faiss_id, distance), ...] for top-k
    
    Raises:
        IndexNotFoundError: Index does not exist
        InvalidEmbeddingError: Query embedding invalid shape
    
    FAISS Search:
        - Load index
        - Call index.search(query_vector.reshape(1, -1), k)
        - Returns: (distances, faiss_ids)
        - Lower distance = higher similarity (L2 metric)
    
    Note:
        Distance in L2 space: smaller = more similar
        For dot-product similarity: use 1 - normalized_distance
    """
```

---

### 6.3 Metadata Module (`metadata.py`)

#### `load_metadata(user_id: str) -> dict`
**Purpose**: Load metadata.json sidecar.

**Signature**:
```python
def load_metadata(user_id: str) -> dict:
    """
    Load metadata sidecar for a user's index.
    
    Returns:
        dict: {
            "version": 1,
            "user_id": str,
            "created_at": str,
            "modified_at": str,
            "entries": [
                {
                    "faiss_id": int,
                    "chunk_id": str,
                    "doc_id": str,
                    "text_checksum": str,
                    ...
                },
                ...
            ]
        }
    
    Raises:
        FileNotFoundError: metadata.json does not exist
        JSONDecodeError: Corrupted JSON file
    """
```

---

#### `save_metadata(user_id: str, metadata: dict) -> None`
**Purpose**: Write metadata.json and backup.

**Signature**:
```python
def save_metadata(user_id: str, metadata: dict) -> None:
    """
    Save metadata to disk with atomic write and backup.
    
    Process:
        1. Write to temporary file
        2. Calculate checksum
        3. Atomic rename to metadata.json
        4. Keep previous version as metadata.json.bak
    
    Raises:
        StorageError: Cannot write to disk
    """
```

---

#### `metadata_entry_from_embedded_chunk(embedded_chunk: EmbeddedChunk, faiss_id: int) -> MetadataEntry`
**Purpose**: Create metadata entry from embedded chunk.

```python
def metadata_entry_from_embedded_chunk(
    embedded_chunk: EmbeddedChunk,
    faiss_id: int
) -> MetadataEntry:
    """
    Convert EmbeddedChunk to MetadataEntry with FAISS ID.
    
    Adds:
        - faiss_id (mapped by indexer)
        - text_checksum (MD5 of chunk text for integrity)
    """
```

---

#### `resolve_faiss_id(user_id: str, chunk_id: str) -> Optional[int]`
**Purpose**: Look up FAISS integer ID from chunk_id.

```python
def resolve_faiss_id(user_id: str, chunk_id: str) -> Optional[int]:
    """
    Resolve chunk_id → faiss_id via metadata.json.
    
    Returns:
        Optional[int]: FAISS ID if found, None otherwise
    
    Use case:
        When deleting a chunk, need to know which FAISS ID to remove.
    """
```

---

### 6.4 Storage Module (`storage.py`)

#### `save_index(user_id: str, index: 'faiss.Index', metadata: dict) -> str`
**Purpose**: Persist index and metadata to disk.

**Signature**:
```python
def save_index(
    user_id: str,
    index: 'faiss.Index',
    metadata: dict,
) -> str:
    """
    Save FAISS index and metadata to disk.
    
    Process:
        1. Create /indexes/{user_id}/ if not exists
        2. Write index to index.faiss (binary)
        3. Write metadata.json (JSON)
        4. Calculate checksums (SHA256)
        5. Create manifest.json with version info
    
    File layout:
        /indexes/{user_id}/
        ├── index.faiss          # FAISS index (binary)
        ├── metadata.json        # Metadata sidecar (JSON)
        ├── metadata.json.bak    # Previous metadata (backup)
        └── manifest.json        # Version, checksum, timestamp
    
    Returns:
        str: Path to saved index
    
    Raises:
        StorageError: Cannot write to disk
    """
```

---

#### `load_index(user_id: str) -> tuple`
**Purpose**: Load index and metadata from disk.

**Signature**:
```python
def load_index(user_id: str) -> tuple:
    """
    Load FAISS index and metadata from disk.
    
    Returns:
        tuple: (index, metadata, user_index_obj)
    
    Raises:
        FileNotFoundError: Index does not exist
        CorruptedIndexError: Index file corrupted
        ChecksumError: Checksum mismatch (data integrity issue)
    
    Validation:
        1. Verify index.faiss exists
        2. Verify metadata.json exists
        3. Load and parse both files
        4. Verify checksums
        5. Validate metadata schema version
    """
```

---

#### `backup_index(user_id: str, description: Optional[str] = None) -> str`
**Purpose**: Create timestamped backup of index.

**Signature**:
```python
def backup_index(
    user_id: str,
    description: Optional[str] = None,
) -> str:
    """
    Create point-in-time backup of user's index.
    
    Backup structure:
        /indexes/{user_id}/backups/{timestamp}/
        ├── index.faiss
        ├── metadata.json
        ├── manifest.json          # Contains: timestamp, checksum, description
        └── integrity_check.json   # Verification info
    
    Args:
        user_id: Index owner
        description: Optional backup description (e.g., "pre-bulk-add", "recovery-point")
    
    Returns:
        str: Path to backup directory
    
    Raises:
        StorageError: Cannot create backup
        IndexNotFoundError: Index does not exist
    
    Retention policy:
        - Keep last 10 backups per user
        - Keep daily backups for 30 days
        - Clean old backups automatically
    """
```

---

#### `recover_from_backup(user_id: str, backup_timestamp: str) -> UserIndex`
**Purpose**: Restore index from backup.

**Signature**:
```python
def recover_from_backup(
    user_id: str,
    backup_timestamp: str,
) -> UserIndex:
    """
    Restore index from timestamped backup.
    
    Args:
        user_id: Index owner
        backup_timestamp: Backup timestamp (e.g., "2026-03-29T14:30:00Z")
    
    Returns:
        UserIndex: Restored index metadata
    
    Process:
        1. Verify backup exists
        2. Validate backup integrity
        3. Copy backup files to current index location
        4. Verify checksums match
        5. Update last_modified timestamp
    
    Raises:
        BackupNotFoundError: Backup does not exist
        CorruptedBackupError: Backup integrity check failed
        StorageError: Cannot restore
    """
```

---

#### `list_backups(user_id: str) -> List[BackupInfo]`
**Purpose**: List all backups for a user.

```python
def list_backups(user_id: str) -> List[dict]:
    """
    List all backups for user with timestamps and descriptions.
    
    Returns:
        List[dict]: Each with keys: timestamp, description, size_mb, checksum
    """
```

---

### 6.5 Concurrency Module (`concurrency.py`)

#### `UserIndexLock`
**Purpose**: Multi-threaded read/write lock for index access.

**Signature**:
```python
class UserIndexLock:
    """
    Reader-writer lock for FAISS index access.
    
    Semantics:
        - Multiple concurrent readers allowed
        - Exclusive writer access (blocks readers, prevented by readers)
        - FIFO fairness (readers/writers queued fairly)
    """
    
    def __init__(self, user_id: str):
        """Initialize lock for a user."""
    
    def acquire_read(self, timeout: float = 30.0) -> None:
        """
        Acquire read lock (blocks until available, shared).
        
        Args:
            timeout: Max seconds to wait
        
        Raises:
            TimeoutError: Lock not acquired within timeout
        """
    
    def release_read(self) -> None:
        """Release read lock."""
    
    def acquire_write(self, timeout: float = 30.0) -> None:
        """
        Acquire write lock (blocks readers and writers, exclusive).
        
        Args:
            timeout: Max seconds to wait
        
        Raises:
            TimeoutError: Lock not acquired within timeout
        """
    
    def release_write(self) -> None:
        """Release write lock."""
    
    def __enter__(self) -> 'UserIndexLock':
        """Context manager support (acquires write lock)."""
    
    def __exit__(self, *args) -> None:
        """Context manager support (releases write lock)."""
```

**Usage**:
```python
lock = UserIndexLock(user_id="user_123")

# Read lock (shared)
lock.acquire_read()
try:
    results = search_index(user_id)
finally:
    lock.release_read()

# Write lock (exclusive)
with UserIndexLock(user_id) as lock:
    add_chunks_to_index(user_id, chunks)
    # Auto-releases on context exit
```

---

#### `TransactionLog`
**Purpose**: Log index modifications for recovery.

**Signature**:
```python
class TransactionLog:
    """
    Write-ahead transaction log for index modifications.
    
    Enables recovery after crashes mid-operation.
    """
    
    def __init__(self, user_id: str):
        """Initialize transaction log."""
    
    def begin_transaction(self, operation: str) -> str:
        """
        Begin transaction, return transaction ID.
        
        Args:
            operation: 'add_chunks', 'delete_chunks', 'rebuild', etc.
        
        Returns:
            str: Transaction ID
        """
    
    def log_entry(self, txn_id: str, entry: dict) -> None:
        """Log operation entry."""
    
    def commit_transaction(self, txn_id: str) -> None:
        """Mark transaction as committed."""
    
    def rollback_transaction(self, txn_id: str) -> None:
        """Mark transaction as rolled back."""
    
    def recover_incomplete(self) -> List[str]:
        """
        List incomplete transactions (crash recovery).
        
        Returns:
            List[str]: Transaction IDs to recover
        """
```

---

### 6.6 Retriever Module (`retriever.py`)

#### `retrieve(user_id: str, query: str, k: int = 10, threshold: float = 0.0) -> List[RetrievalResult]`
**Purpose**: Query chunks semantically.

**Signature**:
```python
def retrieve(
    user_id: str,
    query: str,
    k: int = 10,
    threshold: float = 0.0,
) -> List['RetrievalResult']:
    """
    Retrieve semantically similar chunks for query.
    
    Args:
        user_id: Index owner
        query: Query string
        k: Number of results
        threshold: Max distance (lower = more similar)
    
    Returns:
        List[RetrievalResult]: Ranked chunks with similarity scores
    
    Raises:
        IndexNotFoundError: User's index does not exist
        EmbeddingError: Cannot embed query
    
    Process:
        1. Embed query using embed_query()
        2. Search FAISS index: index.search()
        3. Look up metadata for each result
        4. Rank by similarity
        5. Apply threshold filter
        6. Return RetrievalResult objects
    """
```

---

#### `retrieve_with_reranking(user_id: str, query: str, k_initial: int = 50, k_final: int = 10) -> List[RetrievalResult]`
**Purpose**: Retrieve with optional re-ranking (future: cross-encoder).

**Signature**:
```python
def retrieve_with_reranking(
    user_id: str,
    query: str,
    k_initial: int = 50,
    k_final: int = 10,
) -> List['RetrievalResult']:
    """
    Retrieve with optional semantic re-ranking.
    
    Process:
        1. Get k_initial results from FAISS (fast)
        2. [OPTIONAL] Re-rank with cross-encoder (slower, more accurate)
        3. Return top k_final
    
    Can reduce k_initial when re-ranking is expensive.
    """
```

---

## 7. Concurrency Design

### 7.1 Concurrent Access Patterns

**Problem**: Multiple users/threads may access indices simultaneously.

**Solution**: Per-user read/write locks + file-level locking.

```
User A (read)     User B (write)     User C (read)
    │                  │                  │
    ├──[lock A read]───┤                  │
    │                  ├──[lock B write]──┤
    │                  │  (blocks C)      │
    │                  │                  │
    │  [search OK]     │                  │
    │                  │  [add chunks]    │
    │                  │  [save index]    │
    │                  │  [unlock B]      │
    │                  │                  ├──[lock C read]───┤
    │                  │                  │                  │
    │  [release A]     │                  │  [search OK]     │
    │                  │                  │  [release C]     │
    ▼                  ▼                  ▼
```

### 7.2 Lock Strategy

1. **Read Operations** (search, retrieve):
   - Acquire read lock (shared)
   - Load index from cache or disk
   - Search FAISS
   - Release read lock

2. **Write Operations** (add_chunks, delete, rebuild):
   - Acquire write lock (exclusive)
   - Load index
   - Modify index
   - Update metadata
   - Save to disk
   - Release write lock

3. **Backup/Restore**:
   - Backup: Acquire read lock (snapshots current state)
   - Recover: Acquire write lock (exclusive restore)

### 7.3 Deadlock Prevention

- **Timeout on locks**: All `acquire_*` calls have timeout (default 30s)
- **Lock ordering**: Always acquire in order user_id → faiss_id (if multiple)
- **Transaction log**: Enables recovery if process crashes with locks held

---

## 8. Metadata Sidecar Schema

### 8.1 `metadata.json` Format

```json
{
  "version": 1,
  "schema_version": 1,
  "user_id": "user_123",
  "embedding_model": "text-embedding-3-large",
  "embedding_dimension": 3072,
  "created_at": "2026-03-29T10:00:00Z",
  "modified_at": "2026-03-29T14:30:00Z",
  "chunk_count": 150,
  "index_type": "flat",
  "checksum": "sha256:abc123def456...",
  "entries": [
    {
      "faiss_id": 0,
      "chunk_id": "doc1_0",
      "doc_id": "550e8400-e29b-41d4-a716-446655440000",
      "doc_name": "contract.pdf",
      "chunk_index": 0,
      "page_number": 1,
      "section": "Article 1: Definitions",
      "jurisdiction": "California",
      "user_id": "user_123",
      "has_ocr": false,
      "token_count": 745,
      "uploaded_at": "2026-03-29T10:00:00Z",
      "embedded_at": "2026-03-29T10:15:00Z",
      "text_checksum": "md5:9d8c7b6e5a4f3d2c1b0a9f8e7d6c5b4a",
      "text_length": 3450
    },
    {
      "faiss_id": 1,
      "chunk_id": "doc1_1",
      ...
    }
  ],
  "lookup_index": {
    "chunk_id_to_faiss": {
      "doc1_0": 0,
      "doc1_1": 1,
      ...
    },
    "doc_id_to_chunk_ids": {
      "550e8400-e29b-41d4-a716-446655440000": ["doc1_0", "doc1_1", ...],
      ...
    }
  }
}
```

### 8.2 `manifest.json` Format

```json
{
  "version": "1.0",
  "user_id": "user_123",
  "created_at": "2026-03-29T10:00:00Z",
  "modified_at": "2026-03-29T14:30:00Z",
  "index_type": "flat",
  "chunk_count": 150,
  "file_checksums": {
    "index.faiss": "sha256:abc123...",
    "metadata.json": "sha256:def456..."
  },
  "embedding_model": "text-embedding-3-large",
  "embedding_dimension": 3072,
  "index_size_bytes": 1843200,
  "metadata_size_bytes": 245600,
  "last_backup": "2026-03-29T14:00:00Z"
}
```

### 8.3 `backups/{timestamp}/manifest.json`

```json
{
  "backup_timestamp": "2026-03-29T14:00:00Z",
  "snapshot_from": "2026-03-29T14:00:00Z",
  "created_at": "2026-03-29T14:05:00Z",
  "description": "Pre-bulk-add checkpoint",
  "user_id": "user_123",
  "chunk_count": 150,
  "file_checksums": {
    "index.faiss": "sha256:abc123...",
    "metadata.json": "sha256:def456..."
  },
  "integrity_status": "verified",
  "integrity_timestamp": "2026-03-29T14:05:00Z"
}
```

---

## 9. Directory Structure

```
/indexes/
├── user_123/
│   ├── index.faiss              # FAISS index (binary)
│   ├── metadata.json            # Current metadata sidecar
│   ├── metadata.json.bak        # Previous version backup
│   ├── manifest.json            # Version & checksum info
│   ├── transaction_log.jsonl    # Transaction log (append-only)
│   └── backups/
│       ├── 2026-03-29T10:00:00Z/
│       │   ├── index.faiss
│       │   ├── metadata.json
│       │   ├── manifest.json
│       │   └── integrity_check.json
│       ├── 2026-03-29T12:00:00Z/
│       │   ├── index.faiss
│       │   ├── metadata.json
│       │   ├── manifest.json
│       │   └── integrity_check.json
│       └── ... (keep last 10)
├── user_456/
│   ├── index.faiss
│   ├── metadata.json
│   └── backups/
│       └── ...
└── user_789/
    ├── index.faiss
    ├── metadata.json
    └── backups/
        └── ...
```

---

## 10. Edge Cases & Handling

| Edge Case | Scenario | Handling |
|-----------|----------|----------|
| **Duplicate chunks** | Same chunk_id added twice | Detect in metadata lookup, skip duplicate (warn log) |
| **Index corruption** | Index file damaged after write | Checksum validation on load, restore from backup |
| **Metadata-index mismatch** | Metadata entries > actual vectors | Rebuild metadata from index (validate ntotal) |
| **Concurrent writes** | Two threads call add_chunks simultaneously | Write lock ensures serialization; 2nd waits |
| **Lock timeout** | Process acquires lock, crashes | Transaction log used for recovery; timeout = 30s |
| **Storage full** | Cannot write backup | Graceful fail: log warning, skip backup (index still updated) |
| **Very large index** | 1M+ chunks (40+ GB) | Use IndexIVFFlat, increase probe for accuracy |
| **Slow embedding API** | OpenAI rate limit, high latency | Exponential backoff retry (max 3x), batch retry loop |
| **Mixed embedding models** | Index created with model A, query with model B | Fail with error (models must match) |
| **Restore old backup** | Restore from 2-week-old backup | User loses recent chunks; restore overwrites current |

---

## 11. API Stability & Versioning

### 11.1 Semantic Versioning

- **v1.0.0**: Initial release
  - IndexFlatL2 only
  - Single embedding model (text-embedding-3-large)
  - Basic metadata sidecar (JSON)

- **v1.1.0**: Planned enhancements
  - IndexIVFFlat support with auto-tuning
  - Batch API optimization
  - Advanced query re-ranking

- **v2.0.0**: Future major features
  - Multiple embedding models
  - Hierarchical indices
  - GPU acceleration (FAISS-GPU)

---

## 12. Performance & Cost

### 12.1 OpenAI Costs

- **Model**: text-embedding-3-large
- **Cost**: $0.02 per 1M input tokens
- **For legal docs** (avg 750 tokens/chunk):
  - 1,000 chunks: 750K tokens = $0.015
  - 1,000,000 chunks: 750M tokens = $15.00

### 12.2 Latency (target)

| Operation | Scale | Latency |
|-----------|-------|---------|
| Embed 100 chunks | - | 500-2000ms (API dependent) |
| Add to FAISS | 100 vectors | <10ms |
| Search (flat) | 100K vectors | 50-500ms |
| Search (IVF) | 1M vectors | 10-100ms |
| Load index | 100K vectors | 50-200ms |
| Save index | 100K vectors | 100-500ms |

---

## 13. Future Enhancements

1. **GPU Acceleration**: FAISS-GPU for million-scale indices
2. **Hybrid Search**: Combine dense embeddings + sparse BM25
3. **Cross-encoder Re-ranking**: LLM-based semantic re-ranking
4. **Incremental Indexing**: IVF Faiss index rebuilding (without full re-index)
5. **Distance Metrics**: Cosine, IP (dot product) in addition to L2
6. **Query Expansion**: Pseudo-relevance feedback with query reformulation
7. **Caching**: Memcached/Redis for popular queries
8. **Monitoring**: Prometheus metrics (embedding latency, search performance)

---

