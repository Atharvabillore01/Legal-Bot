"""
src/retrieval/contradiction_detector.py

Contradiction detection for legal document retrieval.

Functions:
    - detect_contradictions: Main detection orchestrator
    - extract_clause_names: Find legal clauses in text
    - extract_values: Get numeric/categorical values
    - score_contradiction: Severity and confidence scoring
"""

import logging
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from src.retrieval.models import (
    RetrievedChunk, ContradictionInfo, ExtractedValues, ContradictionScore
)
from src.retrieval.exceptions import ContradictionDetectionError, ValueExtractionError
from src.retrieval import constants

logger = logging.getLogger(__name__)


def detect_contradictions(
    chunks: List[RetrievedChunk],
) -> Dict[str, ContradictionInfo]:
    """
    Identify contradictions between chunks (same clause, different values).
    
    Three-stage detection:
    1. Clause matching: Group by clause name
    2. Value extraction: Pull numeric/categorical values
    3. Conflict scoring: Compare and score severity
    
    Args:
        chunks: List of RetrievedChunk to compare
    
    Returns:
        Dict mapping "chunk1_id|chunk2_id" → ContradictionInfo
    
    Latency: <60ms for 50 chunks
    """
    
    contradictions = {}
    
    if not chunks or len(chunks) < 2:
        return contradictions
    
    try:
        # Stage 1: Extract clauses from each chunk
        chunk_clauses = {}
        for chunk in chunks:
            clause_names = extract_clause_names(chunk.text)
            chunk_clauses[chunk.chunk_id] = clause_names
        
        # Stage 2: Find common clauses across chunks
        clause_to_chunks = {}
        for chunk_id, clauses in chunk_clauses.items():
            for clause_name in clauses:
                if clause_name not in clause_to_chunks:
                    clause_to_chunks[clause_name] = []
                clause_to_chunks[clause_name].append(chunk_id)
        
        # Stage 3: For each shared clause, extract and compare values
        chunk_map = {c.chunk_id: c for c in chunks}
        
        for clause_name, chunk_ids in clause_to_chunks.items():
            if len(chunk_ids) < 2:
                continue  # Need at least 2 chunks to have conflict
            
            # Only monitor specific high-impact clauses
            if clause_name not in constants.CONTRADICTION_CLAUSES:
                continue
            
            # Limit pairs to avoid O(n^2) explosion
            if len(contradictions) >= constants.MAX_CONTRADICTION_PAIRS:
                logger.warning(f"Contradiction detection hit max pairs limit")
                break
            
            # Compare all pairs (only across different documents)
            for i, chunk_id_1 in enumerate(chunk_ids):
                for chunk_id_2 in chunk_ids[i+1:]:
                    chunk_1 = chunk_map[chunk_id_1]
                    chunk_2 = chunk_map[chunk_id_2]

                    # Skip intra-document comparisons — not contradictions
                    if chunk_1.doc_id and chunk_2.doc_id and chunk_1.doc_id == chunk_2.doc_id:
                        continue
                    
                    # Extract values from both chunks
                    try:
                        values_1 = extract_values(chunk_1.text, clause_name)
                        values_2 = extract_values(chunk_2.text, clause_name)
                    except ValueExtractionError:
                        continue  # Skip if extraction fails
                    
                    # Score contradiction
                    contradiction_score = score_contradiction(
                        values_1, values_2, chunk_1, chunk_2
                    )
                    
                    # Only report if confidence threshold met
                    if contradiction_score.conflict_confidence >= constants.CONTRADICTION_MIN_CONFIDENCE:
                        pair_key = f"{chunk_id_1}|{chunk_id_2}"
                        
                        contradiction_info = ContradictionInfo(
                            conflicting_chunk_id=chunk_id_2,
                            conflicting_doc_name=chunk_2.doc_name,
                            conflict_type="value_mismatch",
                            clause_name=clause_name,
                            value_my=contradiction_score.explanation.split("vs")[0].strip()[:50],
                            value_other=contradiction_score.explanation.split("vs")[1].strip()[:50] if "vs" in contradiction_score.explanation else "unknown",
                            severity=contradiction_score.severity,
                            resolution=contradiction_score.resolution_preference,
                            detected_at=datetime.utcnow(),
                        )
                        
                        contradictions[pair_key] = contradiction_info
                        logger.debug(f"Detected {contradiction_score.severity} contradiction in {clause_name}: {chunk_id_1} vs {chunk_id_2}")
        
        logger.info(f"Detected {len(contradictions)} contradictions across {len(chunks)} chunks")
        
    except Exception as e:
        logger.error(f"Contradiction detection failed: {e}", exc_info=True)
        raise ContradictionDetectionError(f"Detection failed: {str(e)}")
    
    return contradictions


def extract_clause_names(text: str) -> List[str]:
    """
    Extract legal clause names from chunk text.
    
    Patterns:
    1. "Article N:" → "Article N"
    2. "Section N.M:" → "Section N.M"
    3. Known clause keywords (e.g., "Liability", "Confidentiality")
    4. Numbered sections with headers
    
    Args:
        text: Chunk text
    
    Returns:
        List[str] of extracted clause names
    """
    
    clause_names = set()
    
    if not text:
        return []
    
    # Pattern 1: "Article 5:" or "Article 5 :"
    article_pattern = r'(?:^|\n)\s*Article\s+(\d+(?:\.\d+)?)\s*:'
    for match in re.finditer(article_pattern, text, re.MULTILINE):
        clause_names.add(f"Article {match.group(1)}")
    
    # Pattern 2: "Section 5.2:" or "§5.2:"
    section_pattern = r'(?:^|\n)\s*(?:Section|§)\s+(\d+(?:\.\d+)*)\s*:'
    for match in re.finditer(section_pattern, text, re.MULTILINE):
        clause_names.add(f"Section {match.group(1)}")
    
    # Pattern 3: Known clause keywords
    for clause_keyword in constants.CONTRADICTION_CLAUSES:
        if clause_keyword.lower() in text.lower():
            clause_names.add(clause_keyword)
    
    return list(clause_names)


def extract_values(text: str, clause_name: str) -> ExtractedValues:
    """
    Extract numeric/categorical values from clause text.
    
    Supports:
    - Monetary amounts: "USD 5,000,000" → 5000000
    - Percentages: "50%" → 0.50
    - Temporal: "3 years" → PT3Y
    - Categorical: "California law" → "California"
    
    Args:
        text: Clause text
        clause_name: Type of clause
    
    Returns:
        ExtractedValues with confidence score
    
    Raises:
        ValueExtractionError: Cannot extract values
    """
    
    values = []
    value_types = []
    normalized = None
    confidence = 0.0
    extraction_method = "regex"
    
    try:
        # Monetary extraction
        monetary_pattern = r'(USD|EUR|GBP|\$|€)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d+)?)\s*(?:million|thousand|billion|M|K|B)?'
        for match in re.finditer(monetary_pattern, text, re.IGNORECASE):
            currency = match.group(1) or "USD"
            amount_str = match.group(2).replace(',', '')
            try:
                amount = float(amount_str)
                # Scale if abbreviated
                if 'M' in match.group(0) or 'million' in match.group(0).lower():
                    amount *= 1_000_000
                elif 'K' in match.group(0) or 'thousand' in match.group(0).lower():
                    amount *= 1_000
                elif 'B' in match.group(0) or 'billion' in match.group(0).lower():
                    amount *= 1_000_000_000
                
                values.append(f"{currency} {amount:,.0f}")
                value_types.append("monetary")
                normalized = amount
                confidence = max(confidence, 0.95)
            except ValueError:
                pass
        
        # Percentage extraction
        pct_pattern = r'(\d+(?:\.\d+)?)\s*%'
        for match in re.finditer(pct_pattern, text):
            pct = float(match.group(1)) / 100.0
            values.append(f"{match.group(1)}%")
            value_types.append("percentage")
            normalized = pct
            confidence = max(confidence, 0.90)
        
        # Temporal extraction
        temporal_pattern = r'(\d+)\s*(year|month|day|week)s?'
        for match in re.finditer(temporal_pattern, text, re.IGNORECASE):
            value = match.group(0)
            values.append(value)
            value_types.append("temporal")
            confidence = max(confidence, 0.85)
        
        # Categorical/jurisdictional extraction
        for jurisdiction in constants.KNOWN_JURISDICTIONS:
            if jurisdiction.lower() in text.lower():
                values.append(jurisdiction)
                value_types.append("jurisdictional")
                confidence = max(confidence, 0.80)
    
    except Exception as e:
        logger.warning(f"Value extraction error for '{clause_name}': {e}")
        confidence = 0.3
    
    if not values:
        confidence = 0.0
    
    return ExtractedValues(
        clause_name=clause_name,
        values=values,
        value_types=value_types,
        normalized=normalized,
        confidence=confidence,
        ambiguous=len(values) > 1,
        extraction_method=extraction_method,
    )


def score_contradiction(
    values_1: ExtractedValues,
    values_2: ExtractedValues,
    chunk_1: RetrievedChunk,
    chunk_2: RetrievedChunk,
) -> ContradictionScore:
    """
    Score severity and confidence of a contradiction.
    
    Factors:
    1. Value difference score
    2. Extraction confidence
    3. Authority level
    4. Document recency
    
    Args:
        values_1, values_2: Extracted values from chunks
        chunk_1, chunk_2: The chunks being compared (for metadata)
    
    Returns:
        ContradictionScore with severity and resolution preference
    """
    
    # If either has no values, no conflict
    if not values_1.values or not values_2.values:
        return ContradictionScore(
            diff_score=0.0,
            conflict_confidence=0.0,
            severity="low",
            resolution_preference="prefer_newer",
            explanation="No values extracted from one or both chunks",
        )
    
    # Compute value difference
    diff_score = 0.0
    
    if values_1.normalized is not None and values_2.normalized is not None:
        # Numeric comparison
        v1, v2 = values_1.normalized, values_2.normalized
        if v1 == 0 and v2 == 0:
            diff_score = 0.0
        elif v1 == 0 or v2 == 0:
            diff_score = 1.0
        else:
            diff_score = abs(v1 - v2) / max(abs(v1), abs(v2))
    elif values_1.values[0] != values_2.values[0]:
        # String comparison (different = conflict)
        diff_score = 1.0
    else:
        # Same value
        diff_score = 0.0
    
    # Clamp to [0, 1]
    diff_score = min(1.0, diff_score)
    
    # Detect negligible difference (rounding variation)
    if diff_score < constants.CONTRADICTION_VALUE_DIFF_THRESHOLD:
        return ContradictionScore(
            diff_score=diff_score,
            conflict_confidence=0.0,
            severity="low",
            resolution_preference="prefer_newer",
            explanation=f"Negligible difference: {diff_score:.1%}",
        )
    
    # Combine with extraction confidence
    conflict_confidence = min(values_1.confidence, values_2.confidence) * diff_score
    
    # Determine authority-based resolution
    auth_1 = constants.AUTHORITY_RANKING.get(chunk_1.doc_authority_level, 1)
    auth_2 = constants.AUTHORITY_RANKING.get(chunk_2.doc_authority_level, 1)
    
    if auth_1 > auth_2:
        resolution_preference = "prefer_binding"
    elif auth_2 > auth_1:
        resolution_preference = "prefer_binding"
    else:
        # Same authority level, prefer newer
        if chunk_1.doc_uploaded_at > chunk_2.doc_uploaded_at:
            resolution_preference = "prefer_newer"
        elif chunk_2.doc_uploaded_at > chunk_1.doc_uploaded_at:
            resolution_preference = "prefer_newer"
        else:
            resolution_preference = "manual_review"
    
    # Determine severity
    if diff_score < constants.CONTRADICTION_SEVERITY_LOW_THRESHOLD:
        severity = "low"
    elif diff_score < constants.CONTRADICTION_SEVERITY_MEDIUM_THRESHOLD:
        severity = "medium"
    else:
        severity = "high"
    
    explanation = f"{values_1.values[0]} vs {values_2.values[0]} (diff: {diff_score:.1%})"
    
    return ContradictionScore(
        diff_score=diff_score,
        conflict_confidence=conflict_confidence,
        severity=severity,
        resolution_preference=resolution_preference,
        explanation=explanation,
    )
