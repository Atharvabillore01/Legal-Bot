"""
Document loaders for PDF, DOCX, and TXT formats.

Each loader handles format-specific extraction and returns a Document object
with raw text and metadata.
"""

import logging
import os
from pathlib import Path
from typing import Optional
import uuid

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import pytesseract
    from PIL import Image
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

try:
    from docx import Document as DoxDocument
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False

import chardet

from .models import Document
from .exceptions import (
    FileNotFoundError_,
    EmptyFileError,
    CorruptedPDFError,
    CorruptedDOCXError,
    TextExtractionError,
    EncodingDetectionError,
    PyTeseractNotInstalledError,
    UnsupportedFileTypeError,
)
from .constants import (
    SUPPORTED_FILE_TYPES,
    PDF_EXTENSIONS,
    DOCX_EXTENSIONS,
    TXT_EXTENSIONS,
    SCANNED_PAGE_THRESHOLD,
    ENCODING_FALLBACK_CHAIN,
)

logger = logging.getLogger(__name__)


def infer_file_type(file_path: str) -> str:
    """
    Infer file type from extension.
    
    Args:
        file_path: Path to file
    
    Returns:
        str: One of ['pdf', 'docx', 'txt']
    
    Raises:
        UnsupportedFileTypeError: If extension not recognized
    """
    ext = Path(file_path).suffix.lower()
    
    if ext in PDF_EXTENSIONS:
        return "pdf"
    elif ext in DOCX_EXTENSIONS:
        return "docx"
    elif ext in TXT_EXTENSIONS:
        return "txt"
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext}'. Supported: {SUPPORTED_FILE_TYPES}"
        )


def _validate_file_exists(file_path: str) -> None:
    """
    Validate that file exists and is readable.
    
    Raises:
        FileNotFoundError_: File does not exist or not readable
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError_(f"File not found: {file_path}")
    if not os.path.isfile(file_path):
        raise FileNotFoundError_(f"Path is not a file: {file_path}")
    if not os.access(file_path, os.R_OK):
        raise FileNotFoundError_(f"File not readable: {file_path}")


def _validate_file_not_empty(file_path: str) -> None:
    """
    Validate that file is not empty.
    
    Raises:
        EmptyFileError: File is empty
    """
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise EmptyFileError(f"File is empty: {file_path}")
    except OSError as e:
        raise EmptyFileError(f"Cannot determine file size: {file_path}") from e


def load_txt(file_path: str) -> Document:
    """
    Load plain text file with encoding detection.
    
    Args:
        file_path: Absolute path to TXT file
    
    Returns:
        Document: Parsed document with auto-detected encoding
    
    Raises:
        FileNotFoundError_: File does not exist
        EmptyFileError: File is empty
        EncodingDetectionError: Cannot detect valid encoding
        TextExtractionError: Generic read failure
    """
    logger.info(f"Loading TXT file: {file_path}")
    
    _validate_file_exists(file_path)
    _validate_file_not_empty(file_path)
    
    try:
        # Read raw bytes for encoding detection
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        
        # Detect encoding
        detected = chardet.detect(raw_bytes)
        encoding = detected.get("encoding", "utf-8")
        confidence = detected.get("confidence", 0)
        
        if confidence < 0.7:
            logger.warning(
                f"Low encoding confidence ({confidence}) for {file_path}; "
                f"detected {encoding}, will try fallback chain"
            )
        
        # Try to decode with detected encoding
        try:
            text = raw_bytes.decode(encoding or "utf-8")
        except (UnicodeDecodeError, LookupError):
            # Fallback to chain
            text = None
            for fallback_enc in ENCODING_FALLBACK_CHAIN:
                try:
                    text = raw_bytes.decode(fallback_enc, errors="ignore")
                    encoding = fallback_enc
                    logger.warning(
                        f"Detected encoding failed; using fallback {fallback_enc} "
                        f"for {file_path}"
                    )
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            
            if text is None:
                raise EncodingDetectionError(
                    f"Cannot determine valid encoding for {file_path}"
                )
        
        # Validate not empty after decode
        if not text or not text.strip():
            raise EmptyFileError(f"File contains no readable text: {file_path}")
        
        doc = Document(
            doc_id=str(uuid.uuid4()),
            doc_name=Path(file_path).name,
            file_type="txt",
            raw_text=text,
            page_count=1,
            encoding=encoding,
            has_ocr=False,
            metadata={"source": "txt_file"}
        )
        
        logger.info(f"Successfully loaded TXT file: {file_path} ({len(text)} chars)")
        return doc
        
    except (EmptyFileError, EncodingDetectionError, FileNotFoundError_):
        raise
    except Exception as e:
        raise TextExtractionError(f"Failed to extract text from TXT file: {e}") from e


def load_docx(file_path: str) -> Document:
    """
    Load and parse DOCX file.
    
    Extracts text from paragraphs and tables, preserving section structure.
    
    Args:
        file_path: Absolute path to DOCX file
    
    Returns:
        Document: Parsed document with raw_text and page_count (estimated)
    
    Raises:
        FileNotFoundError_: File does not exist
        EmptyFileError: File is empty
        CorruptedDOCXError: DOCX structure is invalid
        TextExtractionError: Generic parsing failure
    """
    if not HAS_PYTHON_DOCX:
        raise TextExtractionError(
            "python-docx not installed. Install via: pip install python-docx"
        )
    
    logger.info(f"Loading DOCX file: {file_path}")
    
    _validate_file_exists(file_path)
    _validate_file_not_empty(file_path)
    
    try:
        doc = DoxDocument(file_path)
        
        # Extract text from paragraphs
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        
        # Extract text from tables (simple conversion)
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells
                )
                if row_text.strip():
                    paragraphs.append(row_text)
        
        if not paragraphs:
            raise EmptyFileError(f"DOCX file contains no readable text: {file_path}")
        
        raw_text = "\n\n".join(paragraphs)
        
        # Estimate page count (rough heuristic)
        para_count = len(doc.paragraphs)
        page_count = max(1, para_count // 30)  # ~30 paragraphs per page
        
        doc_obj = Document(
            doc_id=str(uuid.uuid4()),
            doc_name=Path(file_path).name,
            file_type="docx",
            raw_text=raw_text,
            page_count=page_count,
            encoding="utf-8",
            has_ocr=False,
            metadata={"source": "docx_file", "para_count": para_count}
        )
        
        logger.info(
            f"Successfully loaded DOCX file: {file_path} "
            f"({len(raw_text)} chars, ~{page_count} pages)"
        )
        return doc_obj
        
    except EmptyFileError:
        raise
    except Exception as e:
        if "not a valid zip file" in str(e).lower():
            raise CorruptedDOCXError(f"Invalid DOCX structure: {file_path}") from e
        raise TextExtractionError(f"Failed to extract text from DOCX: {e}") from e


def load_pdf(file_path: str, enable_ocr: bool = True) -> Document:
    """
    Load PDF file with optional OCR fallback for scanned pages.
    
    Attempts native text extraction first; falls back to OCR for image-based pages.
    
    Args:
        file_path: Absolute path to PDF file
        enable_ocr: If True, apply pytesseract OCR to scanned pages
    
    Returns:
        Document: Parsed document with raw_text, page_count, has_ocr flag
    
    Raises:
        FileNotFoundError_: File does not exist
        EmptyFileError: File is empty or yields no text
        CorruptedPDFError: PDF structure invalid
        PyTeseractNotInstalledError: OCR needed but pytesseract unavailable
        TextExtractionError: Generic extraction failure
    """
    if not HAS_PDFPLUMBER:
        raise TextExtractionError(
            "pdfplumber not installed. Install via: pip install pdfplumber"
        )
    
    logger.info(f"Loading PDF file: {file_path}")
    
    _validate_file_exists(file_path)
    _validate_file_not_empty(file_path)
    
    try:
        with pdfplumber.open(file_path) as pdf:
            pages_text = []
            pages_had_ocr = []
            
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    # Native text extraction
                    text = page.extract_text() or ""
                    
                    # Check if page is mostly empty (scanned, no text)
                    if text.strip() and len(text.strip()) > 50:
                        pages_text.append(text)
                        pages_had_ocr.append(False)
                    else:
                        # Try OCR if native extraction failed/sparse
                        if enable_ocr:
                            logger.debug(f"Page {page_num} sparse; attempting OCR")
                            ocr_text = _extract_ocr_from_page(page)
                            if ocr_text:
                                pages_text.append(ocr_text)
                                pages_had_ocr.append(True)
                            else:
                                pages_text.append(text or f"[Page {page_num} - no extractable text]")
                                pages_had_ocr.append(False)
                        else:
                            pages_text.append(text or f"[Page {page_num} - no extractable text]")
                            pages_had_ocr.append(False)
                    
                except Exception as e:
                    logger.warning(f"Error processing page {page_num}: {e}")
                    pages_text.append(f"[Page {page_num} - extraction error]")
                    pages_had_ocr.append(False)
            
            if not pages_text or all(not p.strip() for p in pages_text):
                raise EmptyFileError(f"PDF yields no readable text: {file_path}")

            # Build page_boundaries: char offset where each page starts in raw_text
            separator = "\n[PAGE BREAK]\n"
            page_boundaries: list = []
            offset = 0
            for i, pt in enumerate(pages_text):
                page_boundaries.append(offset)
                offset += len(pt) + (len(separator) if i < len(pages_text) - 1 else 0)

            # Join pages with page break markers
            raw_text = separator.join(pages_text)
            page_count = len(pdf.pages)
            has_ocr = any(pages_had_ocr)
            
            if has_ocr:
                logger.warning(
                    f"PDF {file_path} required OCR for {sum(pages_had_ocr)} pages"
                )
        
        doc = Document(
            doc_id=str(uuid.uuid4()),
            doc_name=Path(file_path).name,
            file_type="pdf",
            raw_text=raw_text,
            page_count=page_count,
            encoding="utf-8",
            has_ocr=has_ocr,
            page_boundaries=page_boundaries,
            metadata={
                "source": "pdf_file",
                "ocr_pages": sum(pages_had_ocr)
            }
        )
        
        logger.info(
            f"Successfully loaded PDF file: {file_path} "
            f"({len(raw_text)} chars, {page_count} pages, "
            f"OCR: {has_ocr})"
        )
        return doc
        
    except EmptyFileError:
        raise
    except Exception as e:
        if "cannot identify" in str(e).lower() or "not a valid pdf" in str(e).lower():
            raise CorruptedPDFError(f"Invalid PDF structure: {file_path}") from e
        raise TextExtractionError(f"Failed to extract text from PDF: {e}") from e


def _extract_ocr_from_page(page) -> str:
    """
    Extract text from PDF page using OCR.
    
    Args:
        page: pdfplumber page object
    
    Returns:
        str: Extracted text from OCR
    
    Raises:
        PyTeseractNotInstalledError: If pytesseract unavailable
    """
    if not HAS_PYTESSERACT:
        raise PyTeseractNotInstalledError(
            "pytesseract not installed. Install via: pip install pytesseract\n"
            "Also requires: apt-get install tesseract-ocr (Linux) or "
            "brew install tesseract (macOS)"
        )
    
    try:
        # Render page as image
        image = page.to_image()
        
        # Extract text via OCR
        text = pytesseract.image_to_string(image.original)
        return text
        
    except Exception as e:
        logger.warning(f"OCR extraction failed: {e}")
        return ""


def load_document(file_path: str, enable_ocr: bool = True) -> Document:
    """
    Load document with automatic format detection.
    
    Dispatches to appropriate loader (PDF, DOCX, TXT) based on file extension.
    
    Args:
        file_path: Absolute path to document file
        enable_ocr: Enable OCR for PDFs
    
    Returns:
        Document: Parsed document
    
    Raises:
        Various: Specific to file type (see individual loaders)
    """
    file_type = infer_file_type(file_path)
    
    if file_type == "pdf":
        return load_pdf(file_path, enable_ocr=enable_ocr)
    elif file_type == "docx":
        return load_docx(file_path)
    elif file_type == "txt":
        return load_txt(file_path)
    else:
        raise UnsupportedFileTypeError(f"Unsupported file type: {file_type}")
