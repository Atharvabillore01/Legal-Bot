# Audit Logs, Confidence & Citations Specification

**Legal RAG System | Module 6**

Observability layer providing immutable audit trails, confidence scoring, and citation highlighting for legal document queries.

**Version**: 1.0.0  
**Author**: Observability & Compliance Team  
**Date**: 2024-01-15  
**Status**: Final Specification

---

## Table of Contents

1. [Overview & Design Goals](#overview--design-goals)
2. [Architecture Diagram](#architecture-diagram)
3. [Audit Log System](#audit-log-system)
4. [AuditEntry JSON Schema](#auditentry-json-schema)
5. [Storage & File Rotation](#storage--file-rotation)
6. [Tamper-Evidence via Chained Hashing](#tamper-evidence-via-chained-hashing)
7. [Confidence Scoring System](#confidence-scoring-system)
8. [Confidence Thresholds & Disclaimers](#confidence-thresholds--disclaimers)
9. [Citation Highlighting System](#citation-highlighting-system)
10. [Citation Parsing & Mapping](#citation-parsing--mapping)
11. [GET /audit-log Endpoint Specification](#get-auditlog-endpoint-specification)
12. [CSV Export Functionality](#csv-export-functionality)
13. [Data Structures & Algorithms](#data-structures--algorithms)
14. [Integration with Modules 1-5](#integration-with-modules-1-5)
15. [Edge Cases & Error Handling](#edge-cases--error-handling)
16. [Performance & Scalability](#performance--scalability)

---

## 1. Overview & Design Goals

### Purpose

Provide comprehensive observability, compliance, and user-facing citation tracking for a legal document RAG system. Enable users to:
- View complete audit trail of queries and results
- Understand confidence scores attached to answers
- Click on citations to highlight source text in original documents
- Export audit logs for compliance audits
- Detect tampered or modified audit entries

### Design Principles

1. **Immutable** - Append-only audit logs with chained hashing prevent modification
2. **User-Centric** - Each user sees only their own audit data
3. **Transparent** - Confidence scores and citations visible to end users
4. **Compliant** - Complete traceability for legal discovery
5. **Performant** - O(1) append, O(n log n) filtering on date ranges
6. **Scalable** - File rotation prevents unbounded file growth

### Technology Stack

- **Storage**: JSONL (one JSON object per line) for immutable append-only format
- **Compression**: Gzip for rotated files (30-day retention)
- **Hashing**: SHA-256 for tamper-evidence chaining
- **Serialization**: JSON for cross-platform compatibility
- **Querying**: In-memory filtering + pagination for audit logs
- **Export**: CSV generation via Python csv module

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODULE 5: FASTAPI LAYER                      │
│                                                                   │
│  POST /query                                                     │
│    ↓ (user_id, query_text)                                      │
├─────────────────────────────────────────────────────────────────┤
│  MODULE 4: LLM INTERFACE                                         │
│    ↓ (returns QueryResponse with citations, confidence)         │
├─────────────────────────────────────────────────────────────────┤
│                    MODULE 6: OBSERVABILITY LAYER                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ AUDIT LOGGING COMPONENT                                 │  │
│  │                                                           │  │
│  │ 1. Build AuditEntry from QueryResponse                 │  │
│  │    - timestamp, user_id, query, retrieved_chunk_ids     │  │
│  │    - confidence_score, llm_response_hash                │  │
│  │    - latency_ms, model_version, doc_names_accessed      │  │
│  │                                                           │  │
│  │ 2. Read previous entry hash from /audit/{user_id}/log   │  │
│  │    → chain new entry hash to previous                   │  │
│  │                                                           │  │
│  │ 3. Append AuditEntry JSON to /audit/{user_id}/log.jsonl│  │
│  │    in append-only mode (atomic write)                   │  │
│  │                                                           │  │
│  │ 4. Check file rotation trigger (30-day age or 500MB)   │  │
│  │    → Compress + archive old file                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CONFIDENCE SCORING COMPONENT                            │  │
│  │                                                           │  │
│  │ Input: chunk_scores from Module 3 (L2 distances)        │  │
│  │                                                           │  │
│  │ 1. Normalize L2 distances: d_norm = d / (1 + d)         │  │
│  │                                                           │  │
│  │ 2. Convert to similarity: sim = 1 - d_norm              │  │
│  │                                                           │  │
│  │ 3. Weighted average (top-7 chunks, rank weights 3:2:1): │  │
│  │    conf = (3*s₁ + 2*s₂ + 1*s₃ + ...) / 12               │  │
│  │                                                           │  │
│  │ 4. Apply penalties:                                      │  │
│  │    - contradiction: × 0.95^count                         │  │
│  │    - low_authority: × 0.85^count                        │  │
│  │    - recency: × 0.90^old_count                          │  │
│  │                                                           │  │
│  │ 5. Classify: LOW (<0.4) / MEDIUM (0.4-0.7) / HIGH (>0.7)│  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CITATION HIGHLIGHTING COMPONENT                         │  │
│  │                                                           │  │
│  │ Input: LLM response text containing [[CITE:chunk_id]]   │  │
│  │                                                           │  │
│  │ 1. Regex parse: r"\[\[CITE:([a-z0-9_]+)\]\]"           │  │
│  │    → extract chunk_id list in order                      │  │
│  │                                                           │  │
│  │ 2. Map chunk_id → metadata (doc_name, page, offsets)    │  │
│  │    via Module 2's metadata.json                          │  │
│  │                                                           │  │
│  │ 3. Validate chunk_id exists + has source text           │  │
│  │    → log warning + strip marker if not found            │  │
│  │                                                           │  │
│  │ 4. Output JSON for frontend:                            │  │
│  │    {citations: [{chunk_id, doc_name, page, char_start,  │  │
│  │     char_end, text_excerpt, is_valid}]}                 │  │
│  │                                                           │  │
│  │ 5. Return cleaned response (markers removed)             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
└───────────────────────────┼──────────────────────────────────────┘
                            │
                            ▼
                ┌─────────────────────────┐
                │  Return to Module 5     │
                │  (FastAPI endpoint)     │
                │  with augmented         │
                │  QueryResponse          │
                └─────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Client sees: │
                    │  - Answer     │
                    │  - Citations  │
                    │  - Confidence │
                    │  - Highlights │
                    └───────────────┘
```

---

## 3. Audit Log System

### Purpose

Create an immutable, tamper-evident log of all user queries, results, and system interactions. Enable:
- **Compliance**: Complete audit trail for legal discovery
- **Debugging**: Reproduce any query result
- **Analytics**: User behavior patterns, model performance
- **Security**: Detect unauthorized access or modification

### Design

- **One JSONL file per user**: `/audit/{user_id}/log.jsonl`
- **Append-only**: No overwrites, no deletes (enforced by file mode)
- **Chained hashing**: Each entry includes hash of previous entry → tamper-proof chain
- **30-day rotation**: New file created every 30 days; old files compressed
- **Indexing**: Optional: SQLite index table for fast date-range queries

### File Structure

```
/audit/
  └── user_123/
      ├── log.jsonl                    (current active log, <30 days, <500MB)
      ├── log.jsonl.1.gz               (2024-01-15 to 2024-02-13, compressed)
      ├── log.jsonl.2.gz               (2023-12-16 to 2024-01-14, compressed)
      └── manifest.json                (index of rotated files, deletion timeline)
```

### Append-Only Enforcement

```python
# File opened in append mode only (never read + write simultaneously)
with open(f"/audit/{user_id}/log.jsonl", mode="a") as f:
    json.dump(audit_entry, f)
    f.write("\n")
```

This ensures:
- No overwriting existing entries
- No deletion of entries
- Atomic write (OS-level guarantees)
- Sequential file access (fast disk I/O)

---

## 4. AuditEntry JSON Schema

### Schema Definition

```json
{
  "entry_id": "audit_entry_abc123xyz",
  "version": "1.0",
  
  "timestamp": "2024-01-15T10:30:45.123Z",
  "user_id": "user_123",
  
  "query_text": "What is the liability cap?",
  "query_tokens": 12,
  
  "retrieved_chunk_ids": [
    "chunk_15",
    "chunk_23",
    "chunk_8"
  ],
  "chunks_count": 3,
  
  "doc_names_accessed": [
    "indemnity_agreement.pdf",
    "payment_terms.pdf"
  ],
  
  "llm_response": "The liability cap is USD 5,000,000 per occurrence.",
  "llm_response_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  
  "confidence_score": 0.92,
  "confidence_level": "HIGH",
  "confidence_components": {
    "base_score": 0.94,
    "contradiction_penalty": 1.0,
    "authority_penalty": 1.0,
    "recency_penalty": 0.98
  },
  
  "model_version": "gpt-4o (2024-01-15)",
  "model_temperature": 0.1,
  
  "citations_extracted": 2,
  "citations_valid": 2,
  
  "latency_ms": {
    "retrieval_ms": 245,
    "llm_call_ms": 1320,
    "audit_log_ms": 15,
    "total_ms": 1580
  },
  
  "filters_applied": {
    "jurisdiction": "NY",
    "doc_name": null,
    "date_range": null
  },
  
  "status": "success",
  "error_message": null,
  
  "previous_entry_hash": "7c4a8d09ca3762af61e59520943dc26494f8941b",
  "entry_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
}
```

### Field Specifications

| Field | Type | Description | Immutable | Indexed |
|-------|------|-------------|-----------|---------|
| `entry_id` | UUID | Unique entry identifier | Yes | Yes |
| `version` | str | Schema version (1.0) | Yes | No |
| `timestamp` | ISO8601 | Query submission time | Yes | Yes |
| `user_id` | UUID | User who submitted query | Yes | Yes |
| `query_text` | str | User's question (full text) | Yes | No |
| `query_tokens` | int | Token count for query | Yes | No |
| `retrieved_chunk_ids` | str[] | Chunk IDs used in response | Yes | No |
| `chunks_count` | int | Number of chunks retrieved | Yes | No |
| `doc_names_accessed` | str[] | Document names queried | Yes | Yes |
| `llm_response` | str | Full LLM-generated answer | Yes | No |
| `llm_response_hash` | str | SHA-256 hash of response | Yes | No |
| `confidence_score` | float | 0.0-1.0 confidence | Yes | Yes |
| `confidence_level` | str | LOW/MEDIUM/HIGH classification | Yes | Yes |
| `confidence_components` | dict | Breakdown of scoring factors | Yes | No |
| `model_version` | str | LLM model + version date | Yes | No |
| `model_temperature` | float | LLM temperature param | Yes | No |
| `citations_extracted` | int | Number of citations found | Yes | No |
| `citations_valid` | int | Number of valid citations | Yes | No |
| `latency_ms` | dict | Timing breakdown by component | Yes | No |
| `filters_applied` | dict | Query filters (jurisdiction, etc.) | Yes | No |
| `status` | str | success / error / timeout | Yes | Yes |
| `error_message` | str | Error details (if status=error) | Yes | No |
| `previous_entry_hash` | str | SHA-256 of previous entry | Yes | Yes |
| `entry_hash` | str | SHA-256 of this entry | Yes | Yes |

### Validation Rules

```python
class AuditEntry(BaseModel):
    """Pydantic validation for audit entries."""
    
    entry_id: str = Field(..., pattern=r"^audit_[a-z0-9]{24}$")
    version: str = Field(..., pattern=r"^1\.\d+$")
    
    timestamp: datetime = Field(..., description="Must be ISO8601 with Z suffix")
    user_id: str = Field(..., pattern=r"^user_[a-z0-9]{20}$")
    
    query_text: str = Field(..., min_length=1, max_length=2000)
    query_tokens: int = Field(..., ge=1, le=2000)
    
    retrieved_chunk_ids: List[str] = Field(default_factory=list, max_items=100)
    chunks_count: int = Field(..., ge=0, le=100)
    
    doc_names_accessed: List[str] = Field(default_factory=list, max_items=50)
    
    llm_response: str = Field(..., max_length=10000)
    llm_response_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")  # SHA-256
    
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_level: Literal["LOW", "MEDIUM", "HIGH"]
    confidence_components: Dict[str, float] = Field(...)
    
    model_version: str = Field(..., min_length=5)
    model_temperature: float = Field(..., ge=0.0, le=2.0)
    
    citations_extracted: int = Field(..., ge=0, le=100)
    citations_valid: int = Field(..., ge=0, le=100)
    
    latency_ms: Dict[str, int] = Field(...)
    filters_applied: Dict[str, Optional[str]] = Field(...)
    
    status: Literal["success", "error", "timeout"] = Field(...)
    error_message: Optional[str] = Field(None, max_length=500)
    
    previous_entry_hash: Optional[str] = Field(None, pattern=r"^[a-f0-9]{40}$")  # SHA-1 truncated
    entry_hash: str = Field(..., pattern=r"^[a-f0-9]{40}$")
    
    @validator('timestamp')
    def validate_timestamp_not_future(cls, v):
        if v > datetime.utcnow() + timedelta(seconds=5):
            raise ValueError("Timestamp cannot be in the future")
        return v
    
    @validator('citations_valid')
    def citations_valid_lte_extracted(cls, v, values):
        if 'citations_extracted' in values and v > values['citations_extracted']:
            raise ValueError("Valid citations cannot exceed extracted citations")
        return v
```

---

## 5. Storage & File Rotation

### Directory Structure

```
/audit/
  ├── user_123/
  │   ├── log.jsonl                           (current, 5 days old, 120MB)
  │   ├── log.jsonl.1.gz                      (30 days ago → 1 day ago, 45MB)
  │   ├── log.jsonl.2.gz                      (60 days ago → 31 days ago, 52MB)
  │   ├── log.jsonl.3.gz                      (90 days ago → 61 days ago, 38MB)
  │   ├── manifest.json                       (rotation timestamp + file list)
  │   └── index.sqlite                        (optional: fast date-range queries)
  │
  ├── user_456/
  │   ├── log.jsonl                           (7 days old, 95MB)
  │   ├── log.jsonl.1.gz                      (30 days old, 41MB)
  │   └── manifest.json
  │
  └── archive/                                (removed after 7 years per compliance)
      ├── user_789_2023-Q1.tar.gz
      ├── user_789_2023-Q2.tar.gz
      └── ...
```

### Rotation Policy

**Trigger Conditions** (either one):
1. **Time-based**: File creation time is ≥30 days old
2. **Size-based**: File size exceeds 500MB

**Rotation Process**:

```
1. Check log.jsonl creation date and size
   
2. If (age ≥ 30 days) OR (size > 500MB):
     a. Rename current log.jsonl:
        timestamp = file creation time (YYYY-MM-DD)
        final_name = /audit/{user_id}/log.{timestamp}.jsonl
        
     b. Create new log.jsonl with first entry
        set creation_time = now()
     
     c. Compress archived file:
        gzip -9 log.{timestamp}.jsonl
        → log.jsonl.{sequence}.gz
        (sequence = 1, 2, 3, ... based on age)
     
     d. Update manifest.json with rotation timestamp
        increment sequence numbers for older files
     
     e. If age > 7 years:
        Move to /audit/archive/ and mark for eventual deletion

3. Continue appending to new log.jsonl
```

### Manifest Format

```json
{
  "user_id": "user_123",
  "current_file": {
    "filename": "log.jsonl",
    "created_at": "2024-01-15T10:30:45Z",
    "byte_size": 125874456,
    "line_count": 1247,
    "status": "active"
  },
  "archived_files": [
    {
      "sequence": 1,
      "filename": "log.jsonl.1.gz",
      "date_range": {
        "start": "2023-12-16T00:00:00Z",
        "end": "2024-01-14T23:59:59Z"
      },
      "created_at": "2024-01-15T10:30:45Z",
      "uncompressed_size_bytes": 215643200,
      "compressed_size_bytes": 41532100,
      "line_count": 3421,
      "compression_ratio": 0.193
    },
    {
      "sequence": 2,
      "filename": "log.jsonl.2.gz",
      "date_range": {
        "start": "2023-11-16T00:00:00Z",
        "end": "2023-12-15T23:59:59Z"
      },
      "created_at": "2023-12-16T10:15:20Z",
      "uncompressed_size_bytes": 198547300,
      "compressed_size_bytes": 38754200,
      "line_count": 3156,
      "compression_ratio": 0.195
    }
  ],
  "retention_policy": {
    "active_retention_days": 30,
    "archive_retention_years": 7,
    "deletion_schedule": [
      {
        "sequence": 10,
        "filename": "log.jsonl.10.gz",
        "deletion_date": "2031-01-15"
      }
    ]
  }
}
```

### File Encoding

Every line is a valid JSON object (JSONL format):

```
{"entry_id":"audit_entry_1","timestamp":"2024-01-15T10:30:00Z","user_id":"user_123",...}{"entry_id":"audit_entry_2","timestamp":"2024-01-15T10:31:00Z","user_id":"user_123",...}
```

**Advantages**:
- Streaming-friendly: read line-by-line
- Append-friendly: no JSON array structure to maintain
- Corruption-resistant: one bad line doesn't break entire file
- Searchable: grep/awk compatible
- Suitable for log aggregate tools (ELK, Splunk, DataDog)

---

## 6. Tamper-Evidence via Chained Hashing

### Objective

Create a **blockchain-like chain of hashes** such that:
- Modifying **any** entry invalidates all subsequent entries' hashes
- Detecting tampering requires checking only the first and last entries
- Complete chain can be verified in O(n) time

### Algorithm

#### Entry Hash Computation

```
hash(entry) = SHA-256(
    entry_id +
    timestamp +
    user_id +
    query_text +
    confidence_score +
    llm_response_hash +
    latency_ms +
    status +
    previous_entry_hash
)
```

**Order matters**: Deterministic hash depends on fixed field ordering.

#### Initialization (First Entry)

```
Entry 1:
  previous_entry_hash = null
  entry_hash = SHA-256(all fields except previous_entry_hash)
```

#### Chaining (Subsequent Entries)

```
Entry N:
  previous_entry_hash = entry_hash[N-1]
  entry_hash = SHA-256(all fields including previous_entry_hash)

Example chain:
┌─────────────────────┐
│ Entry 1             │
│ prev_hash: null     │
│ hash: abc123...     │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Entry 2             │
│ prev_hash: abc123...│
│ hash: def456...     │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Entry 3             │
│ prev_hash: def456...│
│ hash: ghi789...     │
└─────────────────────┘
```

### Tamper Detection

#### Scenario 1: Modify Entry 2's Query

```
ORIGINAL:
Entry 1: hash=abc123
Entry 2: prev=abc123, query="What is X?", hash=def456
Entry 3: prev=def456, hash=ghi789

ATTACKER MODIFIES Entry 2:
Entry 2: prev=abc123, query="What is Y?", hash=def456 (not updated!)

DETECTION:
When verifying, compute:
  expected_hash = SHA-256(entry_2_with_new_query)
  actual_hash = def456
  MISMATCH! → Tampering detected
```

#### Scenario 2: Insert New Entry Between 2 & 3

```
MODIFIED LOG:
Entry 2: prev=abc123, hash=def456
Entry 2.5: prev=def456, query="...", hash=new_hash  ← INSERTED
Entry 3: prev=def456, hash=ghi789  ← hash is wrong! (expects new_hash)

DETECTION:
When reading Entry 3:
  expected prev = actual Entry_2.5's hash = new_hash
  actual prev = def456 (points to Entry 2)
  MISMATCH! → Insertion detected
```

#### Scenario 3: Delete Entry 2

```
ORIGINAL:
Entry 2: prev=abc123, hash=def456
Entry 3: prev=def456, hash=ghi789

AFTER DELETION:
Entry 3: prev=?, hash=ghi789  ← no parent!

DETECTION:
Entry 3's previous_entry_hash (def456) doesn't match
  actual previous entry (Entry 1's hash = abc123)
  MISMATCH! → Deletion detected
```

### Verification Algorithm

```python
async def verify_audit_chain(user_id: str) -> VerificationResult:
    """
    Verify entire audit log chain for tampering.
    
    Returns:
      VerificationResult
        - is_valid: bool (entire chain valid?)
        - tampered_entries: List[int] (entry numbers with hash mismatches)
        - chain_length: int (total entries verified)
        - verification_time_ms: int
    """
    
    # Read all entries from current log.jsonl
    entries = []
    with open(f"/audit/{user_id}/log.jsonl", "r") as f:
        for line in f:
            entries.append(json.loads(line))
    
    tampered = []
    
    for i, entry in enumerate(entries):
        stored_hash = entry["entry_hash"]
        
        # Recompute hash
        entry_copy = entry.copy()
        del entry_copy["entry_hash"]  # Remove stored hash for computation
        
        computed_hash = compute_entry_hash(entry_copy)
        
        if computed_hash != stored_hash:
            tampered.append(i)
        
        # Check chain linkage
        if i > 0:
            prev_entry_hash = entry["previous_entry_hash"]
            expected_prev = entries[i-1]["entry_hash"]
            
            if prev_entry_hash != expected_prev:
                tampered.append(i)
    
    return VerificationResult(
        is_valid=(len(tampered) == 0),
        tampered_entries=tampered,
        chain_length=len(entries),
        verification_time_ms=elapsed
    )
```

### Hash Storage Strategy

Store previous entry hash in two ways:

1. **In Entry JSON**: `previous_entry_hash` (for chaining)
2. **In Redis Cache** (optional): `audit_chain_head:{user_id}` = last_entry_hash
   - Enables fast validation on new entry appends
   - Survives application restart
   - Can be rebuilt from log file

---

## 7. Confidence Scoring System

### Formula Derivation

#### Step 1: Normalize L2 Distance

FAISS returns L2 (Euclidean) distances in 3072-dimensional space.

```
d = L2_distance (from FAISS knn query)

Normalization: d_norm = d / (1 + d)

This maps:
  d=0   → d_norm=0
  d=1   → d_norm=0.5
  d=∞   → d_norm=1.0

Range: [0, 1]
```

#### Step 2: Convert to Similarity

```
similarity = 1 - d_norm

This maps:
  d_norm=0   → similarity=1.0 (perfect match)
  d_norm=0.5 → similarity=0.5 (moderate)
  d_norm=1.0 → similarity=0.0 (no match)

Range: [0, 1]
```

#### Step 3: Weighted Average Across Top-7 Chunks

LLM generates response using top-7 retrieved chunks (ranks 1-7).

Apply **rank-weighted averaging** to emphasize top matches:

```
weights = [3, 2, 1, 1, 1, 1, 1]  (sum=10)

base_confidence = (
    3*sim₁ + 
    2*sim₂ + 
    1*sim₃ + 
    1*sim₄ + 
    1*sim₅ + 
    1*sim₆ + 
    1*sim₇
) / 10

Example:
  sim = [0.95, 0.87, 0.72, 0.68, 0.55, 0.48, 0.42]
  
  base = (3*0.95 + 2*0.87 + 1*0.72 + 1*0.68 + 1*0.55 + 1*0.48 + 1*0.42) / 10
       = (2.85 + 1.74 + 0.72 + 0.68 + 0.55 + 0.48 + 0.42) / 10
       = 7.44 / 10
       = 0.744
```

#### Step 4: Apply Penalties

**Contradiction Penalty** (Module 3 detection):
```
contradiction_penalty = 0.95 ^ contradiction_count

Example:
  0 contradictions: × 0.95^0 = × 1.00
  1 contradiction:  × 0.95^1 = × 0.95
  2 contradictions: × 0.95^2 = × 0.9025
  3 contradictions: × 0.95^3 = × 0.8574
```

**Authority Penalty** (Module 3 classification):
```
authority_penalty = 0.85 ^ low_authority_count

Where low_authority_count = number of chunks from non-authoritative sources:
  - Binding authority (precedent, statute): authority_level = 1.0 (no penalty)
  - Persuasive authority (law review, guidance): authority_level = 0.9
  - Non-authoritative (blog, comment): authority_level = 0.5

Example:
  3 chunks: [1.0, 0.9, 0.5]
  low_authority_count = 1 (only 0.5 is low)
  authority_penalty = 0.85^1 = 0.85
```

**Recency Penalty** (Source publication date):
```
recency_penalty = PRODUCT of individual chunk recency adjustments

For each chunk:
  days_old = (now - published_date).days
  
  if days_old < 365:
    chunk_recency = 1.0 (fresh)
  else:
    chunk_recency = 0.90 ^ ((days_old - 365) / 365)
    
    Example:
      1 year old:    days_old=365   → 0.90^0   = 1.0
      2 years old:   days_old=730   → 0.90^1   = 0.90
      3 years old:   days_old=1095  → 0.90^2   = 0.81
      5 years old:   days_old=1825  → 0.90^4   = 0.6561

recency_penalty = PRODUCT(all chunk_recency values)

Example (3 chunks, ages 2, 4, 6 years):
  chunk_1: 0.90^1 = 0.90
  chunk_2: 0.90^3 = 0.729
  chunk_3: 0.90^5 = 0.5905
  recency_penalty = 0.90 × 0.729 × 0.5905 = 0.3878
```

#### Step 5: Final Confidence Score

```
confidence_score = (
    base_confidence × 
    contradiction_penalty × 
    authority_penalty × 
    recency_penalty
)

Clamped to [0.0, 1.0]

Example:
  base = 0.744
  contradiction_penalty = 0.95 (1 contradiction)
  authority_penalty = 0.85 (1 low-authority source)
  recency_penalty = 0.92 (chunks 2-3 years old)
  
  score = 0.744 × 0.95 × 0.85 × 0.92
        = 0.744 × 0.7410
        = 0.551

Result: MEDIUM confidence (0.4-0.7)
```

### Confidence Scoring Table

| Factor | Input | Formula | Output | Impact |
|--------|-------|---------|--------|--------|
| Base (7 chunks) | L2 distances | Weighted avg (3:2:1) | 0.0-1.0 | Primary |
| Contradictions | Count | 0.95^n | 0.54-1.0 | -5% each |
| Authority | Levels | 0.85^n_low | 0.58-1.0 | -15% each low |
| Recency | Age in years | 0.90^((yrs-1)) | 0.59-1.0 | -10% per year after 1y |
| **Final** | All above | Multiply all | **0.0-1.0** | **Composite** |

---

## 8. Confidence Thresholds & Disclaimers

### Classification Thresholds

| Threshold | Score Range | Level | Color | Disclaimer |
|-----------|-------------|-------|-------|-----------|
| LOW | 0.0 - 0.39 | LOW | 🔴 Red | Required |
| MEDIUM | 0.40 - 0.69 | MEDIUM | 🟡 Yellow | Optional |
| HIGH | 0.70 - 1.0 | HIGH | 🟢 Green | None |

### Disclaimer Text

#### LOW Confidence Disclaimer

```
⚠️ **LOW CONFIDENCE ANSWER**

This answer has LOW confidence (score: {score:.0%}). 
The retrieved documents may not fully support this answer,
or there are contradictory statements in the sources.

**Do NOT rely on this answer for legal decisions.**
Always consult with qualified legal counsel and review
the source documents directly.

Source documents: {doc_names}
Confidence breakdown: {components}
```

**When to prepend**:
- When `confidence_score < 0.40`
- When `confidence_level == "LOW"`
- Before returning answer text

#### MEDIUM Confidence Disclaimer

```
ℹ️ **MEDIUM CONFIDENCE ANSWER**

This answer has MEDIUM confidence (score: {score:.0%}). 
The sources partially support the answer, but you should
review the source documents to ensure accuracy.

Source documents: {doc_names}
```

**When to show** (optional):
- Display as modal/tooltip on frontend
- Only if user enables "Show Confidence Info"
- Do NOT block response display

#### HIGH Confidence Disclaimer

```
✓ **HIGH CONFIDENCE ANSWER**

This answer has HIGH confidence (score: {score:.0%})
and is well-supported by the source documents.
```

**When to show** (optional):
- Display as badge on frontend
- Reassure user of answer quality
- Do NOT make user feel overconfident

### Rendering Logic

```python
def build_confidence_disclaimer(confidence_score: float, doc_names: List[str]) -> Optional[str]:
    """
    Return disclaimer text based on confidence level.
    
    Returns None if HIGH confidence (no disclaimer needed).
    """
    
    if confidence_score < 0.40:
        components = calculate_confidence_components(...)
        return f"""⚠️ **LOW CONFIDENCE ANSWER**
        
This answer has LOW confidence (score: {confidence_score:.0%}). 
The retrieved documents may not fully support this answer,
or there are contradictory statements in the sources.

**Do NOT rely on this answer for legal decisions.**
Always consult with qualified legal counsel and review
the source documents directly.

Source documents: {', '.join(doc_names)}
Confidence breakdown: base={components['base']:.2f}, 
  contradiction_penalty={components['contradiction_penalty']:.2f},
  authority_penalty={components['authority_penalty']:.2f},
  recency_penalty={components['recency_penalty']:.2f}
"""
    
    elif confidence_score < 0.70:
        return f"""ℹ️ **MEDIUM CONFIDENCE ANSWER**

This answer has MEDIUM confidence (score: {confidence_score:.0%}). 
The sources partially support the answer, but you should
review the source documents to ensure accuracy.

Source documents: {', '.join(doc_names)}
"""
    
    else:  # HIGH confidence
        return None  # No disclaimer needed
```

---

## 9. Citation Highlighting System

### Purpose

Enable frontend to highlight cited text in original documents:
- Parse `[[CITE:chunk_id]]` markers from LLM response
- Map chunk_id → source document metadata
- Provide character offsets for HTML highlighting
- Validate citations exist (hallucination check)
- Return fallback if citation missing

### Data Flow

```
LLM Response:
"The liability cap is USD 5,000,000 per occurrence. [[CITE:chunk_15]]
 This applies annually. [[CITE:chunk_23]]"
    │
    ▼
Citation Parser:
  Regex extract: ["chunk_15", "chunk_23"]
    │
    ▼
Citation Mapper:
  chunk_15 → {doc_id, page_number, char_start, char_end, text_excerpt}
  chunk_23 → {doc_id, page_number, char_start, char_end, text_excerpt}
    │
    ▼
JSON Output (for frontend):
[
  {
    "chunk_id": "chunk_15",
    "doc_name": "indemnity.pdf",
    "page_number": 7,
    "char_start": 234,
    "char_end": 289,
    "text_excerpt": "The liability cap... is USD 5,000,000...",
    "is_valid": true
  },
  {
    "chunk_id": "chunk_23",
    "doc_name": "indemnity.pdf",
    "page_number": 12,
    "char_start": 456,
    "char_end": 512,
    "text_excerpt": "Total liability shall not exceed...",
    "is_valid": true
  }
]

Cleaned Response:
"The liability cap is USD 5,000,000 per occurrence.
 This applies annually."
(markers removed for display)
```

---

## 10. Citation Parsing & Mapping

### Citation Extraction Regex

```
Pattern: r"\[\[CITE:([a-z0-9_]+)\]\]"

Matches:
  [[CITE:chunk_15]] → captures: chunk_15
  [[CITE:chunk_abc123]] → captures: chunk_abc123

Non-matches:
  [CITE:chunk_15] → no match (need double brackets)
  [[cite:chunk_15]] → no match (case-sensitive)
  [[CITE:chunk-15]] → no match (no hyphens allowed)
```

### Citation Extraction Algorithm

```python
import re
from typing import List, Tuple

def extract_citation_chunk_ids(response_text: str) -> List[str]:
    """
    Extract all [[CITE:chunk_id]] markers from LLM response.
    
    Returns:
        List of chunk_ids in order of appearance, with duplicates
        
    Example:
        "Answer [[CITE:chunk_1]]. [[CITE:chunk_1]] again."
        → ["chunk_1", "chunk_1"]
    """
    
    pattern = r"\[\[CITE:([a-z0-9_]+)\]\]"
    matches = re.findall(pattern, response_text)
    
    return matches
```

### Citation Offset Calculation

Find character positions where each citation marker appears:

```python
def find_citation_offsets(
    response_text: str,
    chunk_id: str
) -> List[Tuple[int, int]]:
    """
    Find all character offsets of [[CITE:chunk_id]] marker in response.
    
    Returns:
        List of (start, end) tuples for marker positions
        
    Example:
        response = "Text [[CITE:chunk_1]] more text [[CITE:chunk_1]]"
        chunk_id = "chunk_1"
        → [(5, 26), (37, 58)]
    """
    
    pattern = r"\[\[CITE:" + re.escape(chunk_id) + r"\]\]"
    
    offsets = []
    for match in re.finditer(pattern, response_text):
        offsets.append((match.start(), match.end()))
    
    return offsets
```

### Citation Mapping: Chunk ID → Metadata

Module 2 (Embeddings) maintains metadata.json:

```json
{
  "chunk_to_metadata": {
    "chunk_15": {
      "doc_id": "doc_550e8400",
      "doc_name": "indemnity_agreement.pdf",
      "page_number": 7,
      "section": "Limitations of Liability",
      "chunk_text": "The liability cap in Section 10...",
      "char_start_in_doc": 234,
      "char_end_in_doc": 289,
      "embedding": [0.123, 0.456, ...]
    },
    "chunk_23": {
      "doc_id": "doc_550e8400",
      "doc_name": "indemnity_agreement.pdf",
      "page_number": 12,
      "section": "General Provisions",
      "chunk_text": "Total liability shall not exceed...",
      "char_start_in_doc": 456,
      "char_end_in_doc": 512,
      "embedding": [0.234, 0.567, ...]
    }
  },
  "doc_to_chunks": {
    "doc_550e8400": ["chunk_15", "chunk_23", ...]
  }
}
```

Lookup function:

```python
async def resolve_chunk_metadata(
    user_id: str,
    chunk_id: str
) -> Optional[ChunkMetadata]:
    """
    Resolve chunk_id → doc_name, page, offsets via Module 2 metadata.
    
    Returns None if chunk_id not found (hallucination detected).
    """
    
    metadata_path = f"/indexes/{user_id}/metadata.json"
    
    try:
        with open(metadata_path) as f:
            metadata = json.load(f)
        
        if chunk_id in metadata["chunk_to_metadata"]:
            return ChunkMetadata(**metadata["chunk_to_metadata"][chunk_id])
        else:
            logger.warning(f"Chunk {chunk_id} not found in metadata (hallucination?)")
            return None
    
    except FileNotFoundError:
        logger.error(f"Metadata file not found for user {user_id}")
        return None
```

### Citation Validation

Ensure cited text actually appears in original chunk:

```python
def validate_citation_in_chunk(
    chunk_id: str,
    chunk_text: str,
    cited_text: str
) -> bool:
    """
    Verify that cited_text appears in original chunk_text.
    
    Handles fuzzy matching for minor differences.
    
    Returns True if ≥90% match, False otherwise.
    """
    
    # Normalize both strings (lowercase, remove extra whitespace)
    chunk_norm = " ".join(chunk_text.lower().split())
    cited_norm = " ".join(cited_text.lower().split())
    
    # Check if cited appears in chunk
    if cited_norm in chunk_norm:
        return True
    
    # Fuzzy match using difflib (>90% similarity)
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, chunk_norm, cited_norm).ratio()
    
    return ratio >= 0.90
```

---

## 11. GET /audit-log Endpoint Specification

### Endpoint Details

**Method**: GET  
**Path**: `/audit-log`  
**Auth**: Required (JWT token in Authorization header)  
**Rate Limit**: 30 requests/hour per user

### Query Parameters

| Parameter | Type | Required | Default | Max | Description |
|-----------|------|----------|---------|-----|-------------|
| `page` | int | No | 1 | N/A | Page number (1-indexed) |
| `page_size` | int | No | 20 | 100 | Results per page |
| `start_date` | ISO8601 | No | 30d ago | N/A | Filter: start of date range |
| `end_date` | ISO8601 | No | now | N/A | Filter: end of date range |
| `doc_name` | str | No | null | 255 | Filter by document name (substring match) |
| `confidence_band` | str | No | null | N/A | Filter: LOW, MEDIUM, HIGH, or comma-separated |
| `status` | str | No | null | N/A | Filter: success, error, timeout |
| `sort_by` | str | No | timestamp | N/A | Sort field: timestamp, confidence_score, latency_ms |
| `sort_order` | str | No | desc | N/A | asc or desc |
| `export_format` | str | No | null | N/A | csv (returns CSV download, not JSON) |

### Request Examples

#### Example 1: Recent queries

```
GET /audit-log?page=1&page_size=20&sort_by=timestamp&sort_order=desc
```

#### Example 2: Queries in date range with filtering

```
GET /audit-log?start_date=2024-01-01&end_date=2024-01-15&doc_name=indemnity&confidence_band=LOW,MEDIUM
```

#### Example 3: Export as CSV

```
GET /audit-log?start_date=2024-01-01&export_format=csv
```

### Response Schema (200 OK)

```json
{
  "page": 1,
  "page_size": 20,
  "total_count": 147,
  "total_pages": 8,
  "records": [
    {
      "entry_id": "audit_entry_abc123xyz",
      "timestamp": "2024-01-15T10:30:45.123Z",
      "query_text": "What is the liability cap?",
      "retrieved_chunk_ids": ["chunk_15", "chunk_23"],
      "doc_names_accessed": ["indemnity_agreement.pdf"],
      "confidence_score": 0.92,
      "confidence_level": "HIGH",
      "model_version": "gpt-4o (2024-01-15)",
      "status": "success",
      "latency_ms": {
        "retrieval_ms": 245,
        "llm_call_ms": 1320,
        "total_ms": 1580
      },
      "citations_extracted": 2,
      "citations_valid": 2
    },
    {
      "entry_id": "audit_entry_def456uvw",
      "timestamp": "2024-01-15T09:45:20.456Z",
      "query_text": "Payment terms conditions?",
      "retrieved_chunk_ids": ["chunk_41", "chunk_58", "chunk_12"],
      "doc_names_accessed": ["payment_terms.pdf", "contract.pdf"],
      "confidence_score": 0.58,
      "confidence_level": "MEDIUM",
      "model_version": "gpt-4o (2024-01-15)",
      "status": "success",
      "latency_ms": {
        "retrieval_ms": 312,
        "llm_call_ms": 1456,
        "total_ms": 1768
      },
      "citations_extracted": 3,
      "citations_valid": 3
    }
  ],
  "filters_applied": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-15",
    "doc_name": null,
    "confidence_band": null,
    "status": null
  }
}
```

### Implementation

```python
@app.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    doc_name: Optional[str] = Query(None),
    confidence_band: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("timestamp"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    export_format: Optional[str] = Query(None),
    request: Request,
) -> Union[Dict, StreamingResponse]:
    """
    Retrieve paginated audit log with filtering and sorting.
    """
    
    user_id = request.state.user_id
    
    # Parse dates
    start_dt = parse_iso8601(start_date) if start_date else datetime.utcnow() - timedelta(days=30)
    end_dt = parse_iso8601(end_date) if end_date else datetime.utcnow()
    
    # Read all entries from audit log
    entries = []
    log_path = f"/audit/{user_id}/log.jsonl"
    
    try:
        with open(log_path) as f:
            for line in f:
                entry = json.loads(line)
                entries.append(entry)
    except FileNotFoundError:
        return {"records": [], "total_count": 0, "total_pages": 1}
    
    # Filter by date range
    filtered = [
        e for e in entries
        if start_dt <= parse_iso8601(e["timestamp"]) <= end_dt
    ]
    
    # Filter by doc_name (substring match)
    if doc_name:
        filtered = [
            e for e in filtered
            if any(doc_name.lower() in d.lower() for d in e.get("doc_names_accessed", []))
        ]
    
    # Filter by confidence_band
    if confidence_band:
        bands = confidence_band.split(",")
        filtered = [
            e for e in filtered
            if e.get("confidence_level") in bands
        ]
    
    # Filter by status
    if status:
        filtered = [
            e for e in filtered
            if e.get("status") == status
        ]
    
    # Sort
    sort_key = lambda e: e.get(sort_by, 0)
    filtered.sort(key=sort_key, reverse=(sort_order == "desc"))
    
    # Paginate
    total_count = len(filtered)
    total_pages = (total_count + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    page_records = filtered[start_idx:end_idx]
    
    # Export as CSV if requested
    if export_format == "csv":
        return export_audit_log_csv(
            records=filtered,
            user_id=user_id
        )
    
    # Return JSON
    return {
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "records": page_records,
        "filters_applied": {
            "start_date": start_date,
            "end_date": end_date,
            "doc_name": doc_name,
            "confidence_band": confidence_band,
            "status": status
        }
    }
```

---

## 12. CSV Export Functionality

### CSV Schema

```csv
Entry ID,Timestamp,Query Text,Chunk IDs,Doc Names,Confidence Score,Confidence Level,Model Version,Status,Retrieval Time (ms),LLM Time (ms),Total Time (ms),Citations Extracted,Citations Valid,Error Message
audit_entry_abc123,2024-01-15T10:30:45Z,What is the liability cap?,"chunk_15, chunk_23","indemnity_agreement.pdf",0.92,HIGH,gpt-4o (2024-01-15),success,245,1320,1580,2,2,
audit_entry_def456,2024-01-15T09:45:20Z,Payment terms?,,"payment_terms.pdf, contract.pdf",0.58,MEDIUM,gpt-4o (2024-01-15),success,312,1456,1768,3,3,
```

### Implementation

```python
def export_audit_log_csv(
    records: List[Dict],
    user_id: str
) -> StreamingResponse:
    """
    Generate CSV export of audit log records.
    """
    
    import io
    import csv
    from datetime import datetime
    
    # Create in-memory CSV
    output = io.StringIO()
    
    fieldnames = [
        "Entry ID",
        "Timestamp",
        "Query Text",
        "Chunk IDs",
        "Doc Names",
        "Confidence Score",
        "Confidence Level",
        "Model Version",
        "Status",
        "Retrieval Time (ms)",
        "LLM Time (ms)",
        "Total Time (ms)",
        "Citations Extracted",
        "Citations Valid",
        "Error Message"
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for record in records:
        writer.writerow({
            "Entry ID": record.get("entry_id"),
            "Timestamp": record.get("timestamp"),
            "Query Text": record.get("query_text"),
            "Chunk IDs": ", ".join(record.get("retrieved_chunk_ids", [])),
            "Doc Names": ", ".join(record.get("doc_names_accessed", [])),
            "Confidence Score": f"{record.get('confidence_score', 0):.2f}",
            "Confidence Level": record.get("confidence_level"),
            "Model Version": record.get("model_version"),
            "Status": record.get("status"),
            "Retrieval Time (ms)": record.get("latency_ms", {}).get("retrieval_ms"),
            "LLM Time (ms)": record.get("latency_ms", {}).get("llm_call_ms"),
            "Total Time (ms)": record.get("latency_ms", {}).get("total_ms"),
            "Citations Extracted": record.get("citations_extracted"),
            "Citations Valid": record.get("citations_valid"),
            "Error Message": record.get("error_message", "")
        })
    
    # Prepare response
    filename = f"audit_log_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
```

---

## 13. Data Structures & Algorithms

### ConfidenceScore Data Model

```python
class ConfidenceComponents(BaseModel):
    """Breakdown of confidence score factors."""
    base_score: float = Field(..., ge=0.0, le=1.0, description="Weighted chunk similarity")
    contradiction_penalty: float = Field(..., ge=0.54, le=1.0)
    authority_penalty: float = Field(..., ge=0.58, le=1.0)
    recency_penalty: float = Field(..., ge=0.0, le=1.0)

class ConfidenceScore(BaseModel):
    """Complete confidence information."""
    score: float = Field(..., ge=0.0, le=1.0)
    level: Literal["LOW", "MEDIUM", "HIGH"]
    components: ConfidenceComponents
    disclaimer: Optional[str] = None  # Only if LOW
    
    def interpretation(self) -> str:
        """Human-readable interpretation."""
        if self.level == "LOW":
            return f"Low confidence ({self.score:.0%}) - validate with sources"
        elif self.level == "MEDIUM":
            return f"Medium confidence ({self.score:.0%}) - review sources"
        else:
            return f"High confidence ({self.score:.0%}) - well-supported"
```

### CitationHighlight Data Model

```python
class CitationHighlight(BaseModel):
    """Citation highlighting information for frontend."""
    chunk_id: str = Field(..., description="Chunk reference")
    doc_name: str = Field(..., description="Source document")
    page_number: int = Field(..., ge=1)
    char_start: int = Field(..., ge=0, description="Character offset in document")
    char_end: int = Field(..., ge=0)
    text_excerpt: str = Field(..., max_length=500)
    section: Optional[str] = None
    jurisdiction: Optional[str] = None
    is_valid: bool = Field(..., description="True if text found in document")
    
class CitationHighlighting(BaseModel):
    """Collection of citation highlights."""
    citations: List[CitationHighlight]
    cleaned_response: str = Field(..., description="Response with markers removed")
    total_citations: int
    valid_citations: int
```

### AuditLog Reading Algorithm

```python
async def read_audit_log_window(
    user_id: str,
    start_date: datetime,
    end_date: datetime,
    load_archived: bool = False
) -> List[AuditEntry]:
    """
    Efficiently read audit log entries in date range.
    
    Strategy:
    1. Determine which log files span the date range
    2. Read compressed archived files as needed
    3. Read current log.jsonl
    4. Filter by date range
    5. Return to caller
    """
    
    entries = []
    
    # 1. Read manifest to find relevant archived files
    manifest_path = f"/audit/{user_id}/manifest.json"
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except FileNotFoundError:
        manifest = {"archived_files": [], "current_file": {}}
    
    # 2. Check archived files
    if load_archived:
        for archived in manifest.get("archived_files", []):
            file_date_start = parse_iso8601(archived["date_range"]["start"])
            file_date_end = parse_iso8601(archived["date_range"]["end"])
            
            # Check if file overlaps query range
            if file_date_end >= start_date and file_date_start <= end_date:
                # Read compressed file
                gz_path = f"/audit/{user_id}/{archived['filename']}"
                
                with gzip.open(gz_path, "rt") as f:
                    for line in f:
                        entry = AuditEntry(**json.loads(line))
                        
                        if start_date <= parse_iso8601(entry.timestamp) <= end_date:
                            entries.append(entry)
    
    # 3. Read current log
    log_path = f"/audit/{user_id}/log.jsonl"
    try:
        with open(log_path) as f:
            for line in f:
                entry = AuditEntry(**json.loads(line))
                
                if start_date <= parse_iso8601(entry.timestamp) <= end_date:
                    entries.append(entry)
    except FileNotFoundError:
        pass
    
    # 4. Sort by timestamp
    entries.sort(key=lambda e: parse_iso8601(e.timestamp))
    
    return entries
```

---

## 14. Integration with Modules 1-5

### Data Flow Diagram

```
┌────────────────────────────────────┐
│ MODULE 5: FASTAPI                  │
│ POST /query endpoint handles       │
│ 1. Extract user_id from JWT        │
│ 2. Call Module 3 (retrieval)       │
│ 3. Call Module 4 (LLM)             │
│ 4. Pass QueryResponse to Module 6  │
└────────┬─────────────────────────────┘
         │
         │ QueryResponse
         │ {answer, citations, confidence}
         ▼
┌────────────────────────────────────────┐
│ MODULE 6: OBSERVABILITY               │
│                                        │
│ ============ AUDIT LOGGING ============│
│ 1. Extract fields from QueryResponse  │
│ 2. Compute SHA-256(LLM response)      │
│ 3. Read previous entry hash           │
│ 4. Build new entry with chain hash    │
│ 5. Append to /audit/{user_id}/log.    │
│ 6. Check rotation trigger             │
│                                        │
│ =========== CONFIDENCE ================│
│ 1. Extract chunk_scores from Module 3 │
│ 2. Apply formula: L2 → confidence     │
│ 3. Apply penalties (contradiction, etc)
│ 4. Classify: LOW/MEDIUM/HIGH          │
│ 5. Add disclaimer if LOW              │
│                                        │
│ ====== CITATION HIGHLIGHTING ==========│
│ 1. Extract [[CITE:chunk_id]] markers  │
│ 2. Map chunk_id → metadata (Module 2) │
│ 3. Validate citations exist           │
│ 4. Return JSON for frontend highlights│
└────────┬────────────────────────────────┘
         │
         │ Enhanced QueryResponse
         │ {answer, citations, confidence,
         │  disclaimer, highlights}
         ▼
┌────────────────────────────────────┐
│ MODULE 5: FASTAPI                  │
│ Return to client with:             │
│ - Answer text                      │
│ - Citations + highlights           │
│ - Confidence badge                 │
│ - Disclaimer (if LOW)              │
└────────────────────────────────────┘
```

### Integration Points

#### With Module 3 (Retrieval)

```
Output from Module 3:
  RetrievedChunk {
    chunk_id: str,
    text: str,
    sim_score: float,  ← L2 distance
    authority: str,
    published_date: datetime
  }

Consumed by Module 6:
  confidence_scorer.calculate_confidence(
    chunk_scores=[0.85, 0.72, 0.65, ...],
    authority_levels=[1.0, 0.9, 0.5],
    published_dates=[2024-01-15, 2023-06-20, ...]
  ) → 0.62  (MEDIUM)
```

#### With Module 4 (LLM)

```
Output from Module 4:
  QueryResponse {
    answer: str,  ← "The cap is $5M. [[CITE:chunk_15]]"
    citations: [...],
    confidence: 0.92
  }

Consumed by Module 6:
  1. Parse citations from answer text
  2. Hash answer: SHA-256(answer)
  3. Build AuditEntry with parsed citations
```

#### With Module 2 (Embeddings)

```
Module 2 maintains:
  /indexes/{user_id}/metadata.json
  {
    "chunk_to_metadata": {
      "chunk_15": {
        "doc_name": "...",
        "page_number": 7,
        "char_start": 234,
        "char_end": 289,
        ...
      }
    }
  }

Module 6 reads:
  citation_mapper.map_chunk_id_to_metadata(
    user_id, "chunk_15"
  ) → ChunkMetadata
```

---

## 15. Edge Cases & Error Handling

### Edge Case 1: Hallucinated Citation

**Scenario**: LLM generates `[[CITE:chunk_999]]` but chunk_999 doesn't exist.

**Detection**:
```python
chunk_metadata = resolve_chunk_metadata(user_id, "chunk_999")
if chunk_metadata is None:
    logger.warning(f"Chunk chunk_999 not found (hallucination?)")
    is_valid = False
```

**Handling**:
```python
citation_highlight = {
    "chunk_id": "chunk_999",
    "is_valid": False,
    "doc_name": null,
    "text_excerpt": "[Citation not found]"
}

# Remove marker from response
cleaned_response = response.replace("[[CITE:chunk_999]]", "")
```

### Edge Case 2: No Confidence Components Available

**Scenario**: Module 3 returns empty result (no chunks retrieved).

**Detection**:
```
chunk_scores = []
base_confidence = 0.0  (no chunks to average)
confidence_score = 0.0
confidence_level = "LOW"
```

**Handling**:
```python
disclaimer = "⚠️ No source documents found for your query."
answer = "[No information available in uploaded documents]"
```

### Edge Case 3: Corrupted Audit Log Entry

**Scenario**: Audit log file contains invalid JSON on line 1000.

**Detection**:
```python
with open(log_path) as f:
    for line_num, line in enumerate(f, 1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON at line {line_num}: {e}")
            # Skip corrupted line
            continue
```

**Handling**:
- Log error with line number
- Skip corrupted entry
- Continue with next entry
- Alert admin about integrity issue

### Edge Case 4: File Rotation Race Condition

**Scenario**: Two requests try to rotate log file simultaneously.

**Solution**:
```python
# Use file locking (fcntl on Unix, msvcrt on Windows)
with open(log_path, "a") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
    
    # Safe to check size/age now
    stat = os.stat(log_path)
    
    if stat.st_size > 500_000_000:  # 500MB
        # Perform rotation (atomic rename)
        os.rename(log_path, f"{log_path}.{timestamp}")
        json.dump(first_entry, open(log_path, "w"))
    
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
```

### Edge Case 5: Confidence Score Edge Cases

| Input | Output | Rationale |
|-------|--------|-----------|
| All chunks have sim=1.0 | score=1.0 | Perfect match |
| All chunks have sim=0.0 | score=0.0 | No match |
| Mixed 0 contradictions | 0.95^0 = 1.0 | No penalty |
| 10 contradictions | 0.95^10 = 0.599 | Heavy penalty |
| All sources >10 years old | score *= 0.31 | Severe recency penalty |
| Empty chunk list | score=0.0 | Cannot calculate |

---

## 16. Performance & Scalability

### Audit Log Performance

| Operation | Time Complexity | Space | Notes |
|-----------|-----------------|-------|-------|
| Append entry | O(1) | 2-5KB per entry | Disk write only |
| Read all entries | O(n) | n × 3KB | Full file scan |
| Date-range filter | O(n) | n × 3KB | Linear scan (partition by date range possible) |
| Rotate file | O(1) | Compress old file | Move to background job |
| Verify chain | O(n) | n × 40 bytes | Hash all entries |

### Scaling Strategy

**Current Log Size Growth**:
```
Entries per user per day: ~50 (100 queries/hour × 24h × 50%)
Bytes per entry: 2-5KB
Daily growth: 50 × 3KB = 150KB per user per day

Rotation trigger (500MB / 3KB ≈ 166K entries):
  166K entries ÷ 50/day = 3,320 days ≈ 9 years
  OR 500MB file reaches 500MB (30-day rotation)
  
30 days of entries: 50 × 30 = 1,500 entries ≈ 4.5-7.5MB
After compression: ~1-2MB per 30-day archive
```

**Storage Requirements for 1,000 Users**:
```
1 year retention:
  (365 days / 30 days) × 12 archives = 146 archives
  × 1,000 users × 1.5MB avg = 219 GB

7 year retention (compliance):
  219 GB × 7 = 1.5 TB

Compressed: ~300 GB for 7 years of audit logs
```

**Query Performance** (GET /audit-log):
```
1,500 entries per user per month:
  Date-range filter: O(n) ≈ 200ms to scan + filter
  Pagination (20 per page): <10ms
  Total: <250ms
  
Note: Can optimize with SQLite index on timestamp + doc_name
```

### Optimization Opportunities

1. **SQLite Index** (optional):
   - Maintain parallel SQLite table with subset of fields
   - Index on (timestamp, doc_name, confidence_level)
   - Enable fast date-range + doc_name queries
   - Keep JSONL as source of truth

2. **Compression**:
   - gzip compression reduces 30-day archive from 7.5MB → 1.5MB (80% ratio)
   - Negligible CPU impact (background job)

3. **Partitioning**:
   - Split log.jsonl by month: log.2024-01.jsonl, log.2024-02.jsonl, etc.
   - Speed up date-range queries
   - Enables parallel archiving

4. **Caching**:
   - Cache manifest.json in Redis
   - Cache recent entries (last 100)
   - Reduce disk I/O on repeated queries

---

## Summary

This specification defines a production-ready observability layer for legal RAG systems:

✅ **Immutable audit logs** with JSONL storage and chained SHA-256 hashing  
✅ **Tamper-detection** by verifying hash chains  
✅ **30-day file rotation** with gzip compression  
✅ **Confidence scoring formula** (L2 → similarity → weighted avg → penalties)  
✅ **Three confidence levels** (LOW/MEDIUM/HIGH) with automatic disclaimers  
✅ **Citation highlighting** with chunk ID parsing and metadata mapping  
✅ **GET /audit-log endpoint** with filtering, sorting, pagination, CSV export  
✅ **Edge case handling** for hallucinations, corrupted logs, race conditions  
✅ **Integration diagrams** showing Module 1-5 data flow  
✅ **Performance analysis** and scaling strategy  
✅ **All Pydantic models** with validation rules  
✅ **Complete algorithms** for confidence scoring and citation mapping  

---

**Next Steps**:
1. Implement Module 6 Python package with audit logging, confidence scoring
2. Create citation highlighting service
3. Implement GET /audit-log endpoint
4. Add CSV export functionality
5. Deploy with audit log rotation monitoring
