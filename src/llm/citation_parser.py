"""
src/llm/citation_parser.py

Citation extraction and parsing from LLM responses.

Handles:
  - Extracting [[CITE:{chunk_id}]] markers from LLM output
  - Mapping chunk_id to source document metadata
  - Calculating character offsets for cited text
  - Building structured Citation objects for QueryResponse

Key Functions:
    - parse_citations: Extract all citation markers from response
    - map_citations_to_sources: Resolve chunk_id to metadata
    - extract_character_offsets: Find positions of cited text
    - build_citation_json: Assemble Citation objects
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Set

from .models import Citation
from .exceptions import (
    CitationError,
    CitationParseError,
    CitationValidationError,
    OffsetCalculationError
)
from .constants import CITATION_MARKER_PATTERN, DEBUG_CITATION_PARSING

logger = logging.getLogger(__name__)


def parse_citations(response_text: str) -> List[str]:
    """
    Extract all [[CITE:{chunk_id}]] markers from LLM response.
    
    Uses regex pattern to find all citation markers in the text.
    Returns unique chunk IDs in order of first appearance.
    
    Args:
        response_text (str): LLM response text
    
    Returns:
        List[str]: List of chunk_id strings (e.g., ["chunk_15", "chunk_23"])
    
    Raises:
        CitationParseError: If regex parsing fails
    
    Example:
        >>> text = "The cap is $5M [[CITE:chunk_15]]. Confirmed [[CITE:chunk_23]]."
        >>> citations = parse_citations(text)
        >>> assert citations == ["chunk_15", "chunk_23"]
    """
    if not response_text:
        return []
    
    try:
        # Find all citation markers
        matches = re.findall(CITATION_MARKER_PATTERN, response_text)
        
        # Return unique citations preserving order
        seen = set()
        unique_citations = []
        for chunk_id in matches:
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique_citations.append(chunk_id)
        
        if DEBUG_CITATION_PARSING:
            logger.debug(f"Found {len(unique_citations)} unique citations: {unique_citations}")
        
        return unique_citations
    
    except Exception as e:
        raise CitationParseError(
            f"Failed to parse citations from response: {str(e)}",
            unparseable_text=response_text[:200]
        )


def find_citation_offsets(response_text: str, chunk_id: str) -> List[Tuple[int, int]]:
    """
    Find all character offsets for a specific citation in response text.
    
    Locates all occurrences of [[CITE:{chunk_id}]] and returns their
    start and end positions in the response text.
    
    Args:
        response_text (str): LLM response text
        chunk_id (str): Chunk ID to find (e.g., "chunk_15")
    
    Returns:
        List[Tuple[int, int]]: List of (start, end) offsets for each occurrence
    
    Raises:
        OffsetCalculationError: If offset calculation fails
    
    Example:
        >>> text = "Clause [[CITE:chunk_15]] states X. Also [[CITE:chunk_15]] says Y."
        >>> offsets = find_citation_offsets(text, "chunk_15")
        >>> assert len(offsets) == 2
    """
    try:
        pattern = rf"\[\[CITE:{re.escape(chunk_id)}\]\]"
        offsets = []
        
        for match in re.finditer(pattern, response_text):
            offsets.append((match.start(), match.end()))
        
        if DEBUG_CITATION_PARSING:
            logger.debug(f"Found {len(offsets)} offsets for {chunk_id}: {offsets}")
        
        return offsets
    
    except Exception as e:
        raise OffsetCalculationError(
            f"Failed to calculate offsets for {chunk_id}: {str(e)}",
            text_length=len(response_text)
        )


def extract_cited_text(response_text: str, chunk_id: str, context_window: int = 50) -> Optional[str]:
    """
    Extract the text around a citation marker (context window).
    
    Finds the text surrounding the citation marker to provide context
    for what was cited. Useful for human validation.
    
    Args:
        response_text (str): LLM response text
        chunk_id (str): Chunk ID to extract context for
        context_window (int): Characters before/after marker to include (default: 50)
    
    Returns:
        Optional[str]: Context text around citation, or None if not found
    
    Example:
        >>> text = "The liability cap is USD 5,000,000 [[CITE:chunk_15]]."
        >>> cited = extract_cited_text(text, "chunk_15", context_window=10)
        >>> assert "5,000,000" in cited
    """
    offsets = find_citation_offsets(response_text, chunk_id)
    
    if not offsets:
        return None
    
    # Get text around first citation
    start, end = offsets[0]
    context_start = max(0, start - context_window)
    context_end = min(len(response_text), end + context_window)
    
    return response_text[context_start:context_end].strip()


def validate_chunk_id(chunk_id: str) -> bool:
    """
    Validate chunk_id is non-empty and contains only safe characters.

    Accepts UUID-based IDs (e.g. 550e8400_0), prefixed IDs (chunk_15),
    and any alphanumeric/dash/underscore string.
    """
    if not chunk_id or not chunk_id.strip():
        return False
    return bool(re.match(r"^[a-zA-Z0-9_\-]+$", chunk_id.strip()))


def map_citations_to_sources(
    citation_ids: List[str],
    metadata_lookup: Dict[str, Dict]
) -> Dict[str, Dict]:
    """
    Map chunk_id citations to source document metadata.
    
    Looks up each chunk_id in the metadata dictionary (provided by Module 2 or 3)
    and resolves to document information.
    
    Args:
        citation_ids (List[str]): Citation chunk IDs (e.g., ["chunk_15"])
        metadata_lookup (Dict[str, Dict]): Metadata mapping from retrieval module
            Format: {chunk_id: {doc_name, page_number, jurisdiction, section, ...}}
    
    Returns:
        Dict[str, Dict]: Resolved citations with metadata
            Format: {chunk_id: {doc_name, page_number, ...}}
    
    Raises:
        CitationMappingError: If chunk_id not found in metadata
    
    Example:
        >>> citations = ["chunk_15"]
        >>> metadata = {"chunk_15": {"doc_name": "contract.pdf", "page_number": 7}}
        >>> resolved = map_citations_to_sources(citations, metadata)
        >>> assert resolved["chunk_15"]["doc_name"] == "contract.pdf"
    """
    resolved = {}
    
    for chunk_id in citation_ids:
        if not validate_chunk_id(chunk_id):
            raise CitationValidationError(
                f"Invalid chunk_id format: {chunk_id}",
                citation_data={"chunk_id": chunk_id}
            )
        
        if chunk_id not in metadata_lookup:
            logger.warning(f"Citation chunk_id not found in metadata: {chunk_id!r} — skipping")
            continue

        resolved[chunk_id] = metadata_lookup[chunk_id]
    
    return resolved


def build_citation_objects(
    response_text: str,
    metadata_lookup: Dict[str, Dict]
) -> List[Citation]:
    """
    Build structured Citation objects from LLM response.
    
    Orchestrates the full citation extraction pipeline:
    1. Parse citation markers from response
    2. Map chunk_ids to metadata
    3. Calculate character offsets
    4. Create Citation Pydantic models
    
    Args:
        response_text (str): LLM response text containing [[CITE:...]] markers
        metadata_lookup (Dict[str, Dict]): Metadata mapping from retrieval module
    
    Returns:
        List[Citation]: Structured citations with all metadata
    
    Raises:
        CitationError: If citation building fails
    
    Example:
        >>> response = "The value is $5M [[CITE:chunk_15]]."
        >>> metadata = {
        ...     "chunk_15": {
        ...         "doc_name": "contract.pdf",
        ...         "page_number": 7,
        ...         "jurisdiction": "NY",
        ...         "section": "Price"
        ...     }
        ... }
        >>> citations = build_citation_objects(response, metadata)
        >>> assert len(citations) == 1
        >>> assert citations[0].source_doc == "contract.pdf"
    """
    try:
        # Extract citation markers
        citation_ids = parse_citations(response_text)
        
        if not citation_ids:
            return []
        
        # Map to metadata — missing chunk_ids are logged and skipped
        try:
            resolved_citations = map_citations_to_sources(citation_ids, metadata_lookup)
        except CitationError:
            resolved_citations = {}
        
        # Build Citation objects
        citations = []
        for chunk_id in citation_ids:
            metadata = resolved_citations[chunk_id]
            
            # Extract context around citation
            cited_text = extract_cited_text(response_text, chunk_id, context_window=75)
            
            # Find first offset
            offsets = find_citation_offsets(response_text, chunk_id)
            if not offsets:
                continue
            
            start_pos, end_pos = offsets[0]
            
            # Create Citation object
            citation = Citation(
                chunk_id=chunk_id,
                source_doc=metadata.get('doc_name', ''),
                page_number=metadata.get('page_number', 1),
                text_excerpt=cited_text or metadata.get('text', '')[:500],
                character_offset_start=start_pos,
                character_offset_end=end_pos,
                jurisdiction=metadata.get('jurisdiction'),
                section=metadata.get('section')
            )
            
            citations.append(citation)
        
        if DEBUG_CITATION_PARSING:
            logger.debug(f"Built {len(citations)} citation objects")
        
        return citations
    
    except CitationError:
        raise
    except Exception as e:
        raise CitationValidationError(
            f"Failed to build citation objects: {str(e)}",
            citation_data={"response_length": len(response_text)}
        )


def clean_response_citations(response_text: str) -> Tuple[str, List[str]]:
    """
    Extract and remove [[CITE:...]] markers from response text.
    
    Returns the response with markers removed (for display) and list of
    citation IDs that were removed.
    
    Args:
        response_text (str): Response text with [[CITE:...]] markers
    
    Returns:
        Tuple[str, List[str]]: (cleaned_text, cited_chunk_ids)
    
    Example:
        >>> text = "Value is $5M [[CITE:chunk_15]]. Terms [[CITE:chunk_23]]."
        >>> clean, citations = clean_response_citations(text)
        >>> assert "[[CITE" not in clean
        >>> assert citations == ["chunk_15", "chunk_23"]
    """
    citations = parse_citations(response_text)
    cleaned = re.sub(CITATION_MARKER_PATTERN, "", response_text)
    return cleaned.strip(), citations


def validate_citations_in_chunks(
    citations: List[Citation],
    chunk_texts: Dict[str, str]
) -> Dict[str, bool]:
    """
    Validate that citations actually appear in source chunks.
    
    Checks if the cited text excerpt actually appears in the
    original chunk for hallucination detection.
    
    Args:
        citations (List[Citation]): Extracted citations
        chunk_texts (Dict[str, str]): Original chunk texts {chunk_id: text}
    
    Returns:
        Dict[str, bool]: Validation results {chunk_id: is_valid}
    
    Example:
        >>> citations = [Citation(chunk_id="chunk_15", text_excerpt="$5M", ...)]
        >>> chunks = {"chunk_15": "The cap is exactly $5M as specified"}
        >>> valid = validate_citations_in_chunks(citations, chunks)
        >>> assert valid["chunk_15"] == True
    """
    validation = {}
    
    for citation in citations:
        chunk_id = citation.chunk_id
        source_text = chunk_texts.get(chunk_id, "")
        
        # Check if excerpt appears in source
        is_valid = citation.text_excerpt.lower() in source_text.lower()
        validation[chunk_id] = is_valid
        
        if DEBUG_CITATION_PARSING:
            status = "valid" if is_valid else "INVALID"
            logger.debug(f"Citation {chunk_id}: {status}")
    
    return validation
