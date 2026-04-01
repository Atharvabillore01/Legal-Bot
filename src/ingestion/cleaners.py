"""
Text cleaning and preprocessing utilities.

Handles normalization, encoding fixes, header/footer removal, and
section detection.
"""

import logging
import re
from typing import Optional

from .exceptions import EncodingNormalizationError
from .constants import (
    MAX_CONSECUTIVE_NEWLINES,
    MAX_CONSECUTIVE_SPACES,
    FOOTER_MARKER_PATTERNS,
    EMPTY_THRESHOLD,
)

logger = logging.getLogger(__name__)


def clean_text(raw_text: str, file_type: str = "pdf") -> str:
    """
    Clean and normalize text content.
    
    Performs multiple cleaning passes to remove artifacts, normalize
    encoding, collapse whitespace, and remove headers/footers.
    
    Args:
        raw_text: Unprocessed text from loader
        file_type: 'pdf', 'docx', or 'txt' (affects heuristics)
    
    Returns:
        str: Cleaned, normalized text
    
    Raises:
        EncodingNormalizationError: If normalization fails critically
    
    Side effects:
        - Removes null bytes and control characters
        - Collapses excessive whitespace
        - Fixes encoding artifacts
        - Removes headers/footers (heuristic-based)
        - Normalizes line endings
    """
    if not raw_text or not raw_text.strip():
        return ""
    
    try:
        # Step 1: Normalize line endings
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Step 2: Remove null bytes and control characters
        text = _remove_control_characters(text)
        
        # Step 3: Normalize encoding artifacts (smart quotes, dashes, etc.)
        text = _normalize_encoding_artifacts(text)
        
        # Step 4: Remove headers and footers
        if file_type in ("pdf", "docx"):
            text = remove_headers_footers(text, file_type)
        
        # Step 5: Collapse excessive whitespace
        text = _collapse_whitespace(text)
        
        # Step 6: Strip overall and per-paragraph
        text = text.strip()
        
        return text
        
    except Exception as e:
        logger.error(f"Text cleaning failed: {e}")
        raise EncodingNormalizationError(f"Failed to clean text: {e}") from e


def _remove_control_characters(text: str) -> str:
    """Remove null bytes and other control characters."""
    # Remove NUL bytes
    text = text.replace("\x00", "")
    
    # Remove C0 control characters except \n, \t, \r
    allowed = {"\n", "\t", "\r"}
    text = "".join(
        char if char >= " " or char in allowed else ""
        for char in text
    )
    
    # Remove C1 control characters (0x80-0x9F)
    text = re.sub(r"[\x80-\x9f]", "", text)
    
    return text


def _normalize_encoding_artifacts(text: str) -> str:
    """Normalize common encoding artifacts to ASCII equivalents."""
    # Smart quotes → regular quotes
    replacements = {
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote / apostrophe
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2013": "-",   # en dash
        "\u2014": "-",   # em dash
        "\u2015": "-",   # horizontal bar
        "\u2026": "...", # horizontal ellipsis
        "\u2010": "-",   # hyphen
        "\u00a0": " ",   # non-breaking space
        "\u200b": "",    # zero-width space
        "\u200c": "",    # zero-width non-joiner
        "\u200d": "",    # zero-width joiner
        "\ufeff": "",    # zero-width no-break space (BOM)
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text


def _collapse_whitespace(text: str) -> str:
    """
    Collapse excessive whitespace while preserving paragraph structure.
    
    - Collapse 3+ consecutive newlines to 2 (paragraph break)
    - Collapse 3+ consecutive spaces to 1
    - Preserve single newlines (lines)
    """
    # Collapse multiple newlines
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    
    # Collapse multiple spaces (but not newlines)
    text = re.sub(r" {3,}", " ", text)
    
    return text


def remove_headers_footers(text: str, file_type: str = "pdf") -> str:
    """
    Heuristically remove document headers and footers.
    
    Uses pattern matching to identify and remove:
    - Page numbers (e.g., "Page 5", "5", "iii")
    - Copyright and document metadata lines
    - Repeated short lines at document boundaries
    
    Args:
        text: Text with potential headers/footers
        file_type: 'pdf' or 'docx' (affects heuristics)
    
    Returns:
        str: Text with inferred headers/footers removed
    """
    lines = text.split("\n")
    cleaned_lines = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Skip empty lines (for now)
        if not stripped:
            cleaned_lines.append(line)
            continue
        
        # Check against footer marker patterns
        is_footer = any(
            re.match(pattern, stripped, re.IGNORECASE)
            for pattern in FOOTER_MARKER_PATTERNS
        )
        
        if is_footer:
            logger.debug(f"Removed footer marker: '{stripped}'")
            continue
        
        # Heuristic: Remove very short lines at start/end (often headers)
        # But preserve them in the middle
        is_short = len(stripped) < 30
        is_boundary = (i < 3) or (i > len(lines) - 4)
        
        if is_short and is_boundary and not _is_content_line(stripped):
            logger.debug(f"Removed boundary line: '{stripped}'")
            continue
        
        cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines)


def _is_content_line(line: str) -> bool:
    """
    Determine if a line is likely document content (not header/footer).
    
    Heuristics:
    - Contains capitalized words or punctuation content
    - Not just metadata patterns
    """
    line = line.strip()
    
    # Has meaningful content indicators
    has_letters = any(c.isalpha() for c in line)
    has_caps = any(c.isupper() for c in line)
    has_digits = any(c.isdigit() for c in line)
    
    # Metadata patterns to exclude
    metadata_patterns = {
        r"^©",
        r"^®",
        r"^™",
        r"^www\.",
        r"^http",
        r"@.*\.",
    }
    
    is_metadata = any(
        re.match(pattern, line, re.IGNORECASE)
        for pattern in metadata_patterns
    )
    
    return has_letters and has_caps and not is_metadata


def detect_section(text: str) -> Optional[str]:
    """
    Extract section or heading context from a text snippet.
    
    Heuristics for legal documents:
    - ALL CAPS followed by content (legal section style)
    - Numbered sections (1. Title, 1.1 Subsection)
    - Markdown headers (# Heading, ## Subheading)
    
    Args:
        text: Text snippet to analyze
    
    Returns:
        Optional[str]: Extracted section name, or None if undetectable
    
    Example:
        >>> text = "Article 1. Definitions\\nFor purposes of this Agreement..."
        >>> detect_section(text)
        "Article 1. Definitions"
    """
    lines = text.split("\n")
    
    for i, line in enumerate(lines[:5]):  # Check first few lines
        stripped = line.strip()
        
        if not stripped:
            continue
        
        # Pattern 1: ALL CAPS section header (legal style)
        if stripped.isupper() and len(stripped) < 100:
            # Make sure it's not just whitespace or numbers
            if any(c.isalpha() for c in stripped):
                return stripped[:80]  # Cap at 80 chars
        
        # Pattern 2: Markdown header
        if stripped.startswith("#"):
            header = re.sub(r"^#+\s*", "", stripped)
            if header:
                return header[:80]
        
        # Pattern 3: Numbered section (e.g., "1. Introduction", "1.1 Subsection")
        match = re.match(r"^([\d\.]+)\s+([A-Z][^\.]*\.?)", stripped)
        if match:
            full = f"{match.group(1)} {match.group(2)}"
            return full[:80]
    
    return None


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace: strip leading/trailing, collapse internal.
    
    Args:
        text: Text to normalize
    
    Returns:
        str: Normalized text
    """
    # Per-line strip
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    text = "\n".join(lines)
    
    # Overall strip
    text = text.strip()
    
    return text


def validate_clean_text(text: str) -> bool:
    """
    Validate cleaned text meets minimum quality threshold.
    
    Args:
        text: Cleaned text
    
    Returns:
        bool: True if text is valid (non-empty, sufficient length)
    """
    if not text or not text.strip():
        return False
    
    if len(text) < EMPTY_THRESHOLD:
        return False
    
    return True
