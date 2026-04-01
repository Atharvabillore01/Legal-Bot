# Document Ingestion & Chunking Module — Technical Specification
**Legal RAG System | Module 1**

---

## 1. Overview

The **Document Ingestion & Chunking Module** handles the pipeline for loading, parsing, cleaning, and chunking legal documents (PDFs, DOCX, TXT) into semantically meaningful units ready for embedding and vector storage.

### Key Objectives
- **Multi-format support**: PDF (native + OCR fallback), DOCX, TXT
- **Text cleaning**: Remove headers/footers, encoding normalization, whitespace standardization
- **Intelligent chunking**: 750-token chunks with 150-token overlap using LangChain's `RecursiveCharacterTextSplitter`
- **Rich metadata**: Document source, page/section info, jurisdiction, user context
- **Type safety**: Pydantic models for validation and serialization
- **Error resilience**: Graceful handling of corrupted files, empty documents, mixed encodings

---

## 2. Module Structure

```
src/ingestion/
├── __init__.py                      # Public API exports
├── models.py                        # Pydantic data models
├── loaders.py                       # File format loaders (PDF, DOCX, TXT)
├── cleaners.py                      # Text cleaning & preprocessing
├── chunker.py                       # Chunking logic & metadata tagging
├── exceptions.py                    # Custom exceptions
└── constants.py                     # Configuration & constants
```

---

## 3. Data Models (Pydantic)

### 3.1 `Chunk` Model
Primary output unit for embedding.

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Chunk(BaseModel):
    """A single text chunk ready for embedding."""
    
    id: str = Field(
        description="Unique identifier: f'{doc_id}_{chunk_index}'"
    )
    text: str = Field(
        min_length=1, 
        description="Clean chunk text (trimmed, normalized)"
    )
    token_count: int = Field(
        ge=1, 
        description="Token count via tiktoken (approximate)"
    )
    
    # Metadata
    doc_name: str = Field(description="Original filename (with extension)")
    doc_id: str = Field(description="Unique document identifier (UUID)")
    chunk_index: int = Field(ge=0, description="0-based chunk sequence number")
    page_number: Optional[int] = Field(
        ge=1, 
        default=None, 
        description="Page number (PDF/DOCX only, 1-indexed)"
    )
    section: Optional[str] = Field(
        default=None, 
        description="Section heading/context (extracted or 'Unknown')"
    )
    jurisdiction: Optional[str] = Field(
        default=None, 
        description="Legal jurisdiction (e.g., 'CA', 'NY', 'Federal')"
    )
    upload_timestamp: datetime = Field(
        description="ISO 8601 upload datetime"
    )
    user_id: str = Field(description="User who uploaded the document")
    
    # Quality metrics
    has_ocr: bool = Field(
        default=False, 
        description="True if text extracted via OCR (pytesseract)"
    )
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
```

### 3.2 `Document` Model
Represents a loaded, parsed document before chunking.

```python
class Document(BaseModel):
    """A parsed document ready for chunking."""
    
    doc_id: str
    doc_name: str
    file_type: str  # 'pdf', 'docx', 'txt'
    raw_text: str
    page_count: Optional[int] = None
    encoding: str = Field(default='utf-8')
    has_ocr: bool = Field(default=False)
    metadata: dict = Field(default_factory=dict)
```

### 3.3 `IngestionRequest` Model
Input validation for document ingestion.

```python
class IngestionRequest(BaseModel):
    """Parameters for document ingestion."""
    
    file_path: str = Field(description="Absolute path to document file")
    user_id: str = Field(description="Uploading user's ID")
    jurisdiction: Optional[str] = Field(
        default=None, 
        description="Legal jurisdiction hint"
    )
    custom_metadata: Optional[dict] = Field(
        default_factory=dict, 
        description="Additional metadata key-value pairs"
    )
    enable_ocr: bool = Field(
        default=True, 
        description="OCR fallback for scanned PDFs"
    )
```

---

## 4. Function Contracts

### 4.1 Loaders (`loaders.py`)

#### `load_pdf(file_path: str, enable_ocr: bool = True) → Document`
**Purpose**: Load PDF, extract text, apply OCR if needed.

**Signature**:
```python
def load_pdf(file_path: str, enable_ocr: bool = True) -> Document:
    """
    Load and parse PDF file.
    
    Args:
        file_path: Absolute path to PDF file
        enable_ocr: If True, apply pytesseract OCR to scanned pages
    
    Returns:
        Document: Parsed document with raw_text, page_count, has_ocr flag
    
    Raises:
        FileNotFoundError: PDF file does not exist
        CorruptedPDFError: PDF unreadable or structurally invalid
        PyTeseractNotInstalledError: OCR required but tesseract unavailable
        TextExtractionError: Generic PDF parsing failure
    """
```

**Behavior**:
- Try native PDF text extraction (PyPDF2/pdfplumber)
- If page yields <5% text density → apply OCR with pytesseract
- Page-break boundaries preserved in raw_text as `\n[PAGE BREAK]\n`
- Return `has_ocr=True` if any page used OCR

---

#### `load_docx(file_path: str) → Document`
**Purpose**: Extract text from DOCX, preserve table structure hints.

**Signature**:
```python
def load_docx(file_path: str) -> Document:
    """
    Load and parse DOCX file.
    
    Args:
        file_path: Absolute path to DOCX file
    
    Returns:
        Document: Parsed document with raw_text, page_count (estimated)
    
    Raises:
        FileNotFoundError: DOCX file does not exist
        CorruptedDOCXError: DOCX structure invalid or unreadable
        TextExtractionError: Generic DOCX parsing failure
    """
```

**Behavior**:
- Extract text from paragraphs, tables (converted to markdown-like format)
- Preserve heading hierarchy as plaintext structure
- Page count estimated by paragraph density
- Returns `has_ocr=False` (DOCX is digital-native)

---

#### `load_txt(file_path: str) → Document`
**Purpose**: Load plain text with encoding detection.

**Signature**:
```python
def load_txt(file_path: str) -> Document:
    """
    Load and parse TXT file with encoding detection.
    
    Args:
        file_path: Absolute path to TXT file
    
    Returns:
        Document: Parsed document with raw_text, detected encoding
    
    Raises:
        FileNotFoundError: TXT file does not exist
        EmptyFileError: File is empty or contains only whitespace
        EncodingDetectionError: Cannot determine valid encoding
    """
```

**Behavior**:
- Detect encoding via `chardet` library
- Fallback: UTF-8 → Latin-1 → ASCII with errors='ignore'
- Set `page_count=1` for TXT
- Returns `has_ocr=False`

---

#### `infer_file_type(file_path: str) → str`
**Purpose**: Determine file type from extension.

```python
def infer_file_type(file_path: str) -> str:
    """
    Infer file type from extension.
    
    Returns:
        str: One of ['pdf', 'docx', 'txt']
    
    Raises:
        UnsupportedFileTypeError: Extension not in supported list
    """
```

---

### 4.2 Cleaners (`cleaners.py`)

#### `clean_text(raw_text: str, file_type: str) → str`
**Purpose**: Normalize and sanitize text.

**Signature**:
```python
def clean_text(raw_text: str, file_type: str = 'pdf') -> str:
    """
    Clean and normalize text content.
    
    Args:
        raw_text: Unprocessed text from loader
        file_type: 'pdf', 'docx', or 'txt' (affects cleaning heuristics)
    
    Returns:
        str: Cleaned, normalized text
    
    Side effects:
        - Removes null bytes, control characters
        - Collapses multiple whitespace/newlines (max 2 consecutive)
        - Strips leading/trailing whitespace per block
        - Fixes common encoding artifacts (smart quotes, etc.)
        - Removes page headers/footers (heuristic-based)
        - Normalizes line endings to \n
    """
```

**Cleaning steps**:
1. **Encoding normalization**: Convert smart quotes/dashes to ASCII equivalents
2. **Control character removal**: Strip NUL bytes, other C0/C1 controls
3. **Whitespace normalization**: Collapse 3+ consecutive spaces/newlines to single
4. **Header/footer removal** (PDF/DOCX):
   - Lines matching page number patterns (e.g., "Page 5", "5")
   - Short lines at document start/end (heuristic)
5. **Trim per-paragraph**: Strip leading/trailing whitespace from logical blocks

---

#### `remove_headers_footers(text: str, file_type: str) → str`
**Purpose**: Remove repetitive headers and footers.

```python
def remove_headers_footers(text: str, file_type: str = 'pdf') -> str:
    """
    Heuristically remove document headers and footers.
    
    Strategy:
        - Identify lines appearing at document boundaries
        - Remove page number patterns (e.g., "Page 3", "3", "III")
        - Remove common legal headers (e.g., document titles on every page)
        - Preserve intentional section markers (e.g., "SECTION 1")
    
    Returns:
        str: Text with headers/footers removed
    """
```

---

#### `detect_section(text: str) → Optional[str]`
**Purpose**: Extract section heading from chunk context.

```python
def detect_section(text: str) -> Optional[str]:
    """
    Extract section/heading context from text snippet.
    
    Heuristics:
        - Lines in ALL CAPS followed by content (legal style)
        - Markdown-style headers (# Heading)
        - Numbered sections (e.g., "1. Introduction", "1.1 Overview")
    
    Returns:
        Optional[str]: Extracted section name, or None if undetectable
    """
```

---

### 4.3 Chunker (`chunker.py`)

#### `chunk_document(document: Document, request: IngestionRequest) → List[Chunk]`
**Purpose**: Main chunking pipeline: split document, apply metadata, validate.

**Signature**:
```python
def chunk_document(
    document: Document, 
    request: IngestionRequest,
    chunk_size: int = 750,
    chunk_overlap: int = 150
) -> List[Chunk]:
    """
    Chunk document into semantically meaningful units with metadata.
    
    Args:
        document: Parsed Document object
        request: IngestionRequest with user/jurisdiction context
        chunk_size: Target tokens per chunk (default 750)
        chunk_overlap: Overlap tokens between chunks (default 150)
    
    Returns:
        List[Chunk]: Ready-to-embed chunks with metadata
    
    Raises:
        EmptyDocumentError: document.raw_text is empty or whitespace-only
        ChunkingError: Recursive splitter fails
        MetadataExtractionError: Cannot extract required metadata
    
    Process:
        1. Validate: document is non-empty, request has required fields
        2. Split: Use RecursiveCharacterTextSplitter (LangChain)
        3. Enrich: Extract section, page number, calculate token count
        4. Validate: Each chunk ≥1 token, ≤2x chunk_size
        5. Return: List of Chunk objects with unique IDs
    """
```

**Algorithm**:
- Use `LangChain.RecursiveCharacterTextSplitter`:
  - Separators: `["\n\n", "\n", " ", ""]` (paragraph → sentence → word → char)
  - Chunk size = 750 tokens (char-level estimate, verified post-split)
  - Overlap = 150 tokens
- Token counting via `tiktoken.encoding_for_model('gpt-3.5-turbo')`
- **Metadata assignment**:
  - `doc_id`: UUID from document
  - `doc_name`: From `request.file_path` basename
  - `chunk_index`: 0-based sequence
  - `page_number`: Inferred from chunk position (PDF/DOCX); None for TXT
  - `section`: From `detect_section()` heuristic
  - `jurisdiction`: From `request.jurisdiction` or heuristic detection
  - `upload_timestamp`: Current UTC time
  - `user_id`: From `request.user_id`
  - `has_ocr`: From `document.has_ocr`

---

#### `estimate_token_count(text: str) → int`
**Purpose**: Estimate token count (fast, approximate).

```python
def estimate_token_count(text: str) -> int:
    """
    Estimate token count using tiktoken.
    
    Uses: 'gpt-3.5-turbo' encoding (4k/16k compatible)
    
    Returns:
        int: Approximate token count
    """
```

---

#### `infer_page_number(text: str, chunk_index: int, doc: Document) → Optional[int]`
**Purpose**: Estimate page number from chunk context.

```python
def infer_page_number(
    text: str, 
    chunk_index: int, 
    doc: Document
) -> Optional[int]:
    """
    Infer which page a chunk originates from.
    
    Heuristics:
        - For PDF: Look for [PAGE BREAK] markers, use chunk position
        - For DOCX: Estimate via paragraph markers
        - For TXT: Always return None
    
    Returns:
        Optional[int]: 1-indexed page number, or None if indeterminate
    """
```

---

### 4.4 Orchestration

#### `ingest_document(file_path: str, user_id: str, **kwargs) → List[Chunk]`
**Purpose**: High-level entry point combining all steps.

**Signature**:
```python
def ingest_document(
    file_path: str,
    user_id: str,
    jurisdiction: Optional[str] = None,
    enable_ocr: bool = True,
    chunk_size: int = 750,
    chunk_overlap: int = 150
) -> List[Chunk]:
    """
    Load, parse, clean, chunk, and validate a document in one call.
    
    Args:
        file_path: Absolute path to document
        user_id: Uploading user ID
        jurisdiction: Optional legal jurisdiction hint
        enable_ocr: Enable OCR fallback for scanned PDFs
        chunk_size: Tokens per chunk
        chunk_overlap: Overlap tokens
    
    Returns:
        List[Chunk]: Ready-to-embed chunks
    
    Raises:
        IngestionError: Base exception (see detailed error types below)
    
    Flow:
        1. infer_file_type(file_path)
        2. Load via appropriate loader (pdf/docx/txt)
        3. clean_text()
        4. chunk_document()
        5. Validate all chunks
        6. Return
    """
```

---

## 5. Error Handling & Custom Exceptions

**Base Exception Hierarchy**:

```
IngestionError (base)
├── FileError
│   ├── FileNotFoundError
│   ├── EmptyFileError
│   └── CorruptedFileError (base)
│       ├── CorruptedPDFError
│       └── CorruptedDOCXError
├── LoaderError
│   ├── UnsupportedFileTypeError
│   ├── TextExtractionError
│   ├── EncodingDetectionError
│   └── PyTeseractNotInstalledError
├── CleaningError
│   └── EncodingNormalizationError
├── ChunkingError
│   ├── EmptyDocumentError
│   ├── MetadataExtractionError
│   └── TokenCountError
└── ValidationError
    └── InvalidChunkError
```

**Error Handling Strategy**:

| Exception | Triggered When | Recovery | Logged At |
|-----------|----------------|-----------|----|
| `FileNotFoundError` | File path invalid | Return `None`, abort | ERROR |
| `CorruptedPDFError` | PDF unreadable | Soft-fail: return empty chunks | WARNING |
| `PyTeseractNotInstalledError` | OCR requested but `tesseract` unavailable | Skip OCR if `enable_ocr=False`, fail if `True` | WARNING/ERROR |
| `EmptyFileError` | File size 0 or whitespace-only | Raise, no recovery | ERROR |
| `EncodingDetectionError` | Cannot detect valid encoding | Fallback to latin-1 | WARNING |
| `EmptyDocumentError` | Clean text is empty | Raise after cleaning | ERROR |
| `ChunkingError` | Splitter fails (rare) | Fallback: simple split by newlines | ERROR |
| `InvalidChunkError` | Chunk validation fails (token count out of range) | Log & filter out | WARNING |

**Logging**:
- All exceptions logged with stacktrace
- Document name, user_id included in context
- OCR fallbacks and encoding issues noted for audit trail

---

## 6. Edge Cases & Handling

| Edge Case | Input/Scenario | Expected Behavior | Status Code |
|-----------|----------------|----|------|
| **Empty file** | 0 bytes or whitespace-only | Raise `EmptyFileError`; abort chunking | ❌ ERROR |
| **Corrupt PDF** | PDF header invalid, pages unreadable | Raise `CorruptedPDFError` if critical; log warning and soft-fail (return 0 chunks) | ⚠️ WARNING→ERROR |
| **Scanned PDF (image-only)** | PDF contains only images, no text | Attempt OCR; if succeeds, set `has_ocr=True`; if fails or OCR disabled, soft-fail | ⚠️ WARNING |
| **tesseract not installed** | OCR required but `pytesseract` cannot find tesseract | Raise `PyTeseractNotInstalledError` if `enable_ocr=True`; skip if `False` | ❌ ERROR / ⚠️ SKIP |
| **Mixed encoding** | DOCX/TXT with mixed UTF-8 + Latin-1 | Detect dominant encoding; use errors='ignore' for outliers | ✅ HANDLE |
| **Encoding artifacts** | Smart quotes, em-dashes preserved as UTF-8 | Normalize to ASCII equivalents (e.g., `"` → `"`, `–` → `-`) | ✅ NORMALIZE |
| **Very large file** | >500 MB document | Process in streaming mode (not implemented v1); chunk normally; monitor memory | ⚠️ PERFORMANCE |
| **Mixed language** (e.g. English + Spanish) | Document with multiple languages | Treat as single text stream; chunk by separator; language detection per-chunk (future enhancement) | ✅ TRANSPARENT |
| **Malformed headers/footers** | Inconsistent pagination, footer patterns | Heuristic removal may miss some; prioritize content preservation | ⚠️ PARTIAL |
| **Very short document** | <100 tokens | Return single chunk; avoid overlap > document size | ✅ HANDLE |
| **No section detectable** | Document lacks heading structure | `section=None` in metadata | ✅ NULL |
| **Jurisdiction unspecified** | Request has no jurisdiction hint | `jurisdiction=None` or infer from content (future ML model) | ✅ NULL |
| **Duplicate chunks** | Two consecutive chunks identical (edge of overlap) | Keep both (duplicate != error); deduplication at embedding stage | ✅ ALLOW |

---

## 7. Input/Output Types Summary

### Input
```python
IngestionRequest(
    file_path: str,
    user_id: str,
    jurisdiction: Optional[str],
    custom_metadata: dict,
    enable_ocr: bool
)
```

### Output
```python
List[Chunk] = [
    Chunk(
        id, text, token_count,
        doc_name, doc_id, chunk_index,
        page_number, section, jurisdiction,
        upload_timestamp, user_id,
        has_ocr
    ),
    ...
]
```

### Internal Intermediate
- `Document` (loader output)
- `str` (raw_text, cleaned_text)

---

## 8. Configuration & Constants

**`constants.py`**:

```python
# Chunking
CHUNK_SIZE_TOKENS = 750
CHUNK_OVERLAP_TOKENS = 150
RECURSIVE_SPLITTERS = ["\n\n", "\n", " ", ""]

# File type support
SUPPORTED_FILE_TYPES = {"pdf", "docx", "txt"}
PDF_MAX_PAGES = 1000
DOCX_MAX_SIZE_MB = 100
TXT_MAX_SIZE_MB = 50

# Encoding
ENCODING_FALLBACK_CHAIN = ["utf-8", "latin-1", "ascii"]
TIKTOKEN_MODEL = "gpt-3.5-turbo"

# OCR
OCR_CONFIDENCE_THRESHOLD = 0.7
SCANNED_PAGE_THRESHOLD = 0.05  # <5% text density → OCR

# Validation
MIN_CHUNK_TOKENS = 1
MAX_CHUNK_TOKENS = CHUNK_SIZE_TOKENS * 2  # 1500
EMPTY_THRESHOLD = 10  # chars
```

---

## 9. Dependencies

```
langchain>=0.0.200
PyPDF2>=3.0.0
pdfplumber>=0.9.0
pytesseract>=0.3.10  # Optional (OCR)
python-docx>=0.8.11
chardet>=5.0.0
pydantic>=2.0.0
tiktoken>=0.4.0
```

**System Requirements**:
- `tesseract-ocr` (apt/brew install) for OCR support

---

## 10. Testing Strategy (Outline)

### Unit Tests
- `test_load_pdf`: Valid PDF, scanned PDF, corrupt PDF
- `test_load_docx`: Valid DOCX, empty sections, tables
- `test_load_txt`: UTF-8, Latin-1, mixed encoding
- `test_clean_text`: Normalization, header/footer removal
- `test_chunk_document`: Overlap correctness, metadata tagging
- `test_edge_cases`: Empty files, large files, mixed language

### Integration Tests
- `test_ingest_document_complete`: End-to-end pipeline
- `test_error_handling`: All exception types

### Test Data
- Fixtures: Sample PDFs (native + scanned), DOCX, TXT files
- Ground truth: Gold-standard chunks with verified metadata

---

## 11. Performance & SLAs

| Metric | Target | Notes |
|--------|--------|-------|
| **PDF (5 pages, native text)** | <500ms | Depends on system I/O |
| **PDF (5 pages, scanned, OCR)** | <3s | OCR is slower |
| **DOCX (50 KB)** | <200ms | Efficient parsing |
| **TXT (1 MB)** | <100ms | Simple I/O |
| **Memory (per document)** | <500MB | For 500-page PDFs |
| **Chunk validation** | <10ms | Per 10 chunks |

---

## 12. Future Enhancements

1. **Streaming mode**: Process large documents without loading entirely into memory
2. **Language detection**: Per-chunk language identification
3. **Section hierarchy preservation**: Structured metadata for document tree
4. **Table extraction**: Native table semantics instead of text fallback
5. **ML-based jurisdiction inference**: From content analysis
6. **Caching**: Avoid re-ingesting identical documents
7. **Batch ingestion**: Multiple files with progress tracking

---

