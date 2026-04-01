# Document Ingestion & Chunking Module

**Legal RAG System | Module 1**

Production-ready Python module for ingesting, parsing, cleaning, and chunking legal documents (PDF, DOCX, TXT) into semantically meaningful units with rich metadata.

## Features

✅ **Multi-format support**: PDF (native + OCR fallback), DOCX, TXT  
✅ **Intelligent chunking**: 750-token chunks with 150-token overlap (configurable)  
✅ **Rich metadata**: Document lineage, page numbers, sections, jurisdiction, user context  
✅ **Type safety**: Pydantic models for validation and serialization  
✅ **OCR fallback**: pytesseract for scanned/image-based PDFs  
✅ **Error resilience**: Graceful handling of corrupted files, empty documents, encoding issues  
✅ **Comprehensive logging**: Audit trail with document-level context  
✅ **Batch processing**: Multi-document ingestion with per-document error handling  

## Installation

### 1. Install Package Dependencies

```bash
pip install -r src/ingestion/requirements.txt
```

### 2. Install System Dependencies (OCR Support)

**Linux**:
```bash
sudo apt-get install tesseract-ocr
```

**macOS**:
```bash
brew install tesseract
```

**Windows**:
- Download installer: [GitHub ultralytics/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
- Or use: `choco install tesseract` (if using Chocolatey)

**Note**: If OCR is not needed, pytesseract can be skipped, but PDFs must have extractable text.

## Quick Start

### Basic Usage

```python
from src.ingestion import ingest_document

# Ingest a single document
chunks = ingest_document(
    file_path="/data/contracts/agreement.pdf",
    user_id="user_123",
    jurisdiction="California",
    enable_ocr=True
)

print(f"Extracted {len(chunks)} chunks")
print(f"First chunk:\n{chunks[0].text[:200]}")
```

### Batch Ingestion

```python
from src.ingestion import batch_ingest_documents

files = [
    "/data/contract1.pdf",
    "/data/agreement2.docx",
    "/data/notes.txt"
]

results = batch_ingest_documents(
    file_paths=files,
    user_id="user_123",
    jurisdiction="California"
)

for result in results:
    if result.success:
        print(f"✓ {result.doc_id}: {result.chunk_count} chunks")
    else:
        print(f"✗ Error: {result.error}")
```

### Custom Chunking Parameters

```python
chunks = ingest_document(
    file_path="/data/long_contract.pdf",
    user_id="user_123",
    chunk_size_tokens=1000,      # Larger chunks
    chunk_overlap_tokens=200,     # More overlap
    enable_ocr=True
)
```

## Module Structure

```
src/ingestion/
├── __init__.py              # Public API: ingest_document(), batch_ingest_documents()
├── models.py                # Pydantic: Chunk, Document, IngestionRequest, IngestionResult
├── loaders.py               # Loaders: load_pdf(), load_docx(), load_txt()
├── cleaners.py              # Cleaning: clean_text(), remove_headers_footers(), detect_section()
├── chunker.py               # Chunking: chunk_document(), estimate_token_count()
├── exceptions.py            # Custom exception hierarchy
├── constants.py             # Configuration and thresholds
└── requirements.txt         # Dependencies
```

## Data Models

### `Chunk` (Output)
Primary unit for embedding:
```python
{
    "id": "doc_id_0",
    "text": "Section text content...",
    "token_count": 745,
    "doc_name": "contract.pdf",
    "doc_id": "550e8400-e29b-41d4-a716-446655440000",
    "chunk_index": 0,
    "page_number": 1,
    "section": "Article 1. Definitions",
    "jurisdiction": "California",
    "upload_timestamp": "2026-03-29T14:30:00Z",
    "user_id": "user_123",
    "has_ocr": false
}
```

### `Document` (Intermediate)
Parsed document before chunking:
```python
{
    "doc_id": "550e8400-e29b-41d4-a716-446655440000",
    "doc_name": "contract.pdf",
    "file_type": "pdf",
    "raw_text": "Full document text...",
    "page_count": 5,
    "encoding": "utf-8",
    "has_ocr": false,
    "metadata": {...}
}
```

### `IngestionRequest` (Input)
Encapsulates all ingestion parameters:
```python
{
    "file_path": "/data/contract.pdf",
    "user_id": "user_123",
    "jurisdiction": "California",
    "custom_metadata": {"department": "legal"},
    "enable_ocr": true,
    "chunk_size_tokens": 750,
    "chunk_overlap_tokens": 150
}
```

## Function Reference

### Main Entry Point

#### `ingest_document(file_path, user_id, **kwargs) -> List[Chunk]`
Load, clean, chunk, and validate a document.

**Parameters**:
- `file_path` (str): Absolute path to document
- `user_id` (str): Uploading user ID
- `jurisdiction` (str, optional): Legal jurisdiction hint
- `custom_metadata` (dict, optional): Additional metadata
- `enable_ocr` (bool): OCR fallback for scanned PDFs (default: True)
- `chunk_size_tokens` (int): Target tokens per chunk (default: 750)
- `chunk_overlap_tokens` (int): Overlap tokens (default: 150)

**Returns**: `List[Chunk]` — Ready-to-embed chunks with full metadata

**Raises**:
- `FileNotFoundError`: File does not exist
- `EmptyFileError`: File is empty or yields no readable text
- `CorruptedPDFError` / `CorruptedDOCXError`: File structure invalid
- `UnsupportedFileTypeError`: Extension not supported
- `PyTeseractNotInstalledError`: OCR needed but not available
- `ChunkingError`: Splitting or processing failed
- `IngestionError`: Base exception for any failure

### Loaders

#### `load_pdf(file_path, enable_ocr=True) -> Document`
Load PDF with native text extraction + OCR fallback for scanned pages.

#### `load_docx(file_path) -> Document`
Load DOCX with paragraph and table extraction.

#### `load_txt(file_path) -> Document`
Load TXT with automatic encoding detection.

#### `infer_file_type(file_path) -> str`
Infer file type ('pdf', 'docx', 'txt') from extension.

### Cleaners

#### `clean_text(raw_text, file_type='pdf') -> str`
Normalize text: remove controls, fix encoding, collapse whitespace, remove headers/footers.

#### `remove_headers_footers(text, file_type='pdf') -> str`
Remove repetitive headers and footers using heuristic patterns.

#### `detect_section(text) -> Optional[str]`
Extract section heading/context from text snippet.

### Chunking

#### `chunk_document(document, request, config=None) -> List[Chunk]`
Split document into chunks with metadata using RecursiveCharacterTextSplitter.

#### `estimate_token_count(text) -> int`
Count tokens using tiktoken (gpt-3.5-turbo encoding).

## Configuration

Edit `src/ingestion/constants.py` to customize:

```python
# Chunking
CHUNK_SIZE_TOKENS = 750
CHUNK_OVERLAP_TOKENS = 150
RECURSIVE_SPLITTERS = ["\n\n", "\n", " ", ""]

# File limits
PDF_MAX_PAGES = 1000
DOCX_MAX_SIZE_MB = 100
TXT_MAX_SIZE_MB = 50

# OCR
SCANNED_PAGE_THRESHOLD = 0.05  # <5% text density → OCR

# Validation
MIN_CHUNK_TOKENS = 1
MAX_CHUNK_TOKENS = 1500
```

## Error Handling

All errors inherit from `IngestionError` base class:

```python
from src.ingestion import ingest_document, IngestionError

try:
    chunks = ingest_document("/data/contract.pdf", "user_123")
except FileNotFoundError as e:
    print(f"File error: {e}")
except IngestionError as e:
    print(f"Ingestion failed: {e}")
```

## Logging

Module logs at INFO/DEBUG/WARNING/ERROR levels:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("src.ingestion")
```

Example output:
```
INFO:src.ingestion.loaders:Loading PDF file: /data/contract.pdf
DEBUG:src.ingestion.loaders:Page 2 sparse; attempting OCR
INFO:src.ingestion.chunker:Chunking document: contract.pdf (15234 chars)
INFO:src.ingestion.chunker:Split document into 12 chunks
INFO:src.ingestion:Document ingestion complete: 12 chunks, 8940 total tokens
```

## Edge Cases Handled

| Case | Behavior |
|------|----------|
| Empty file | Raise `EmptyFileError` |
| Scanned PDF | Apply OCR (if enabled); set `has_ocr=True` |
| Mixed encoding | Detect dominant; use fallback chain for outliers |
| Very large file | Process normally; monitor memory (v1) |
| Mixed language | Treat as single stream; language detection per-chunk (future) |
| No section detectable | `section=None` in metadata |
| Short document (<100 tokens) | Return single chunk without overlap issues |
| Corrupt PDF/DOCX | Raise `CorruptedFileError`; option to soft-fail |

## Performance Targets

| Scenario | Target | Notes |
|----------|--------|-------|
| PDF (5 pages, native) | <500ms | I/O dependent |
| PDF (5 pages, OCR) | <3s | OCR is slower |
| DOCX (50 KB) | <200ms | Efficient parsing |
| TXT (1 MB) | <100ms | Simple I/O |
| Memory per document | <500MB | For 500-page PDFs |

## Testing

Run unit and integration tests:

```bash
pytest tests/ingestion/ -v --cov=src/ingestion
```

Test fixtures include:
- Sample PDFs (native + scanned)
- DOCX files (simple + complex)
- TXT files (various encodings)
- Corrupted/edge-case files

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | >=2.0.0 | Type validation & serialization |
| langchain | >=0.0.200 | RecursiveCharacterTextSplitter |
| pdfplumber | >=0.9.0 | PDF text extraction |
| PyPDF2 | >=3.0.0 | PDF fallback parsing |
| python-docx | >=0.8.11 | DOCX parsing |
| pytesseract | >=0.3.10 | OCR (optional) |
| tiktoken | >=0.4.0 | Token counting |
| chardet | >=5.0.0 | Encoding detection |
| pillow | >=9.0.0 | Image handling (OCR) |

## Future Enhancements

1. **Streaming mode**: Process very large documents without full memory load
2. **Language detection**: Per-chunk language identification
3. **Table extraction**: Native table semantics (not text fallback)
4. **ML-based jurisdiction inference**: From content analysis
5. **Document caching**: Avoid re-ingesting identical documents
6. **Structured metadata**: Document tree with section hierarchy
7. **Batch progress tracking**: Real-time progress for large batches

## API Stability

This module follows semantic versioning:
- **v1.0.0**: Initial release, stable public API
- **v1.x.x**: Backwards-compatible bug fixes and features
- **v2.0.0**: Breaking changes to come

## Support

For issues or questions:
1. Check [technical spec](../specs/DOCUMENT_INGESTION_CHUNKING_SPEC.md) for detailed design
2. Review error messages and logs
3. Consult test fixtures for usage examples
4. File GitHub issue with reproducible example

---

**Last updated**: March 29, 2026  
**License**: Proprietary (Legal Bot System)
