"""
src/llm/confidence_scorer.py

Confidence scoring for LLM responses based on retrieval quality.

Converts raw retrieval metrics (L2 distances, similarity scores) into
human-readable confidence levels (LOW/MEDIUM/HIGH) with interpretable scores [0, 1].

Confidence Scoring Formula:
    score = 1 / (1 + l2_distance)  # Normalize L2 distance to [0, 1]
    confidence = avg(top_k_scores)  # Weighted average of chunk scores
    
    Adjustments:
    - Contradiction penalty: ×0.95 per detected contradiction
    - Source authority penalty: ×0.85 for low-authority sources
    - Source age penalty: ×0.90 for sources >5 years old

Key Functions:
    - normalize_l2_distance: Convert L2 distance to [0, 1] score
    - calculate_query_confidence: Compute confidence from chunks
    - classify_confidence_level: Assign LOW/MEDIUM/HIGH label
    - adjust_confidence_for_factors: Apply adjustment penalties
"""

import logging
from typing import List, Dict, Optional, Literal
from datetime import datetime, timedelta
from statistics import mean, stdev

from .models import Citation, ConfidenceLevel
from .exceptions import (
    PromptError
)
from .constants import (
    CONFIDENCE_THRESHOLD_LOW,
    CONFIDENCE_THRESHOLD_MEDIUM,
    CONFIDENCE_LEVELS,
    CONFIDENCE_CONTRADICTION_PENALTY,
    CONFIDENCE_LOW_AUTHORITY_PENALTY,
    CONFIDENCE_OLD_SOURCE_PENALTY,
    DEBUG_PROMPT_BUILDING
)

logger = logging.getLogger(__name__)


def normalize_l2_distance(distance: float) -> float:
    """
    Normalize L2 distance to confidence score [0, 1].
    
    Uses formula: score = 1 / (1 + distance)
    
    This maps:
    - distance=0 → score=1.0 (perfect match)
    - distance=1 → score=0.5 (moderate match)
    - distance=∞ → score=0.0 (no match)
    
    Args:
        distance (float): L2 distance from FAISS retrieval (≥0)
    
    Returns:
        float: Confidence score [0.0, 1.0]
    
    Example:
        >>> score = normalize_l2_distance(0.5)
        >>> assert 0.6 < score < 0.7
        >>> assert normalize_l2_distance(0) == 1.0
    """
    if distance < 0:
        raise ValueError(f"L2 distance cannot be negative: {distance}")
    
    score = 1.0 / (1.0 + distance)
    return min(max(score, 0.0), 1.0)  # Clamp to [0, 1]


def calculate_base_confidence(
    chunk_scores: List[float],
    use_weighted_average: bool = True
) -> float:
    """
    Calculate base confidence from chunk similarity scores.
    
    Args:
        chunk_scores (List[float]): Similarity scores [0, 1] for each chunk
        use_weighted_average (bool): If True, weight by rank (higher scores more weight)
    
    Returns:
        float: Confidence score [0.0, 1.0]
    
    Example:
        >>> scores = [0.9, 0.85, 0.7]
        >>> conf = calculate_base_confidence(scores)
        >>> assert 0.7 <= conf <= 0.9
    """
    if not chunk_scores:
        return 0.0
    
    if use_weighted_average:
        # Weight by descending rank: 1st chunk = 3x weight, 2nd = 2x, etc.
        weights = list(range(len(chunk_scores), 0, -1))
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(chunk_scores, weights)) / total_weight
        return weighted_score
    else:
        # Simple average
        return mean(chunk_scores) if chunk_scores else 0.0


def adjust_confidence_for_contradictions(
    confidence: float,
    contradiction_count: int
) -> float:
    """
    Adjust confidence score downward for detected contradictions.
    
    Each contradiction reduces confidence by 5% (multiply by 0.95).
    
    Formula: adjusted = confidence × (0.95 ^ contradiction_count)
    
    Args:
        confidence (float): Base confidence [0, 1]
        contradiction_count (int): Number of contradictions detected
    
    Returns:
        float: Adjusted confidence [0, 1]
    
    Example:
        >>> conf = adjust_confidence_for_contradictions(0.9, 2)
        >>> assert conf < 0.9  # Reduced due to contradictions
        >>> assert conf > 0.8  # But not too much
    """
    if contradiction_count < 0:
        raise ValueError(f"Contradiction count cannot be negative: {contradiction_count}")
    
    penalty = CONFIDENCE_CONTRADICTION_PENALTY ** contradiction_count
    adjusted = confidence * penalty
    
    return min(max(adjusted, 0.0), 1.0)


def adjust_confidence_for_authority(
    confidence: float,
    authority_levels: List[str]
) -> float:
    """
    Adjust confidence for source authority levels.
    
    Authority importance:
    - 'binding' sources: boost confidence slightly
    - 'precedent' sources: boost confidence moderately
    - 'informational' sources: slightly reduce confidence
    
    Args:
        confidence (float): Base confidence [0, 1]
        authority_levels (List[str]): Authority level for each chunk
    
    Returns:
        float: Adjusted confidence
    
    Example:
        >>> conf = adjust_confidence_for_authority(0.7, ["binding", "precedent"])
        >>> assert conf >= 0.7
    """
    if not authority_levels:
        return confidence
    
    low_authority_count = sum(1 for auth in authority_levels if auth.lower() == "informational")
    
    if low_authority_count > 0:
        penalty = CONFIDENCE_LOW_AUTHORITY_PENALTY ** low_authority_count
        adjusted = confidence * penalty
        return min(max(adjusted, 0.0), 1.0)
    
    return confidence


def adjust_confidence_for_recency(
    confidence: float,
    published_dates: List[Optional[datetime]]
) -> float:
    """
    Adjust confidence for source recency.
    
    Sources older than 5 years are penalized: ×0.90 per old source
    Recent sources (<1 year) have neutral effect.
    
    Args:
        confidence (float): Base confidence [0, 1]
        published_dates (List[datetime]): Publication date for each chunk
    
    Returns:
        float: Adjusted confidence
    
    Example:
        >>> old_date = datetime.now() - timedelta(days=2000)  # >5 years
        >>> conf = adjust_confidence_for_recency(0.85, [old_date])
        >>> assert conf < 0.85  # Reduced for old source
    """
    if not published_dates:
        return confidence
    
    now = datetime.now()
    old_source_count = 0
    
    for date in published_dates:
        if date is None:
            continue
        age_days = (now - date).days
        if age_days > 365 * 5:  # More than 5 years old
            old_source_count += 1
    
    if old_source_count > 0:
        penalty = CONFIDENCE_OLD_SOURCE_PENALTY ** old_source_count
        adjusted = confidence * penalty
        return min(max(adjusted, 0.0), 1.0)
    
    return confidence


def calculate_query_confidence(
    chunk_scores: List[float],
    contradiction_count: int = 0,
    authority_levels: Optional[List[str]] = None,
    published_dates: Optional[List[datetime]] = None
) -> float:
    """
    Calculate comprehensive confidence score with all adjustments.
    
    Pipeline:
    1. Calculate base confidence from chunk scores
    2. Apply contradiction penalty
    3. Apply authority adjustment
    4. Apply recency adjustment
    5. Clamp to [0, 1]
    
    Args:
        chunk_scores (List[float]): Normalized similarity scores for chunks
        contradiction_count (int): Number of contradictions detected (default: 0)
        authority_levels (List[str], optional): Authority for each chunk
        published_dates (List[datetime], optional): Publication date for each chunk
    
    Returns:
        float: Final confidence score [0.0, 1.0]
    
    Example:
        >>> scores = [0.92, 0.87, 0.73]
        >>> conf = calculate_query_confidence(scores, contradiction_count=1)
        >>> assert 0.7 < conf < 0.95
    """
    if not chunk_scores:
        return 0.0
    
    # Base confidence from chunk scores
    confidence = calculate_base_confidence(chunk_scores)
    
    # Apply adjustments
    confidence = adjust_confidence_for_contradictions(confidence, contradiction_count)
    
    if authority_levels:
        confidence = adjust_confidence_for_authority(confidence, authority_levels)
    
    if published_dates:
        confidence = adjust_confidence_for_recency(confidence, published_dates)
    
    return min(max(confidence, 0.0), 1.0)


def classify_confidence_level(confidence_score: float) -> Literal["LOW", "MEDIUM", "HIGH"]:
    """
    Classify confidence score into LOW/MEDIUM/HIGH.
    
    Thresholds:
    - LOW: < 0.3
    - MEDIUM: 0.3 to 0.7
    - HIGH: >= 0.7
    
    Args:
        confidence_score (float): Confidence [0, 1]
    
    Returns:
        Literal: "LOW", "MEDIUM", or "HIGH"
    
    Example:
        >>> assert classify_confidence_level(0.2) == "LOW"
        >>> assert classify_confidence_level(0.5) == "MEDIUM"
        >>> assert classify_confidence_level(0.8) == "HIGH"
    """
    if confidence_score < CONFIDENCE_THRESHOLD_LOW:
        return "LOW"
    elif confidence_score < CONFIDENCE_THRESHOLD_MEDIUM:
        return "MEDIUM"
    else:
        return "HIGH"


def create_confidence_level_object(confidence_score: float) -> ConfidenceLevel:
    """
    Create a ConfidenceLevel Pydantic model with interpretation.
    
    Args:
        confidence_score (float): Confidence [0, 1]
    
    Returns:
        ConfidenceLevel: Model with level, interpretation, and UI guidance
    
    Example:
        >>> level = create_confidence_level_object(0.85)
        >>> assert level.level == "HIGH"
        >>> assert "high" in level.interpretation.lower()
    """
    level_str = classify_confidence_level(confidence_score)
    level_config = CONFIDENCE_LEVELS[level_str]
    
    return ConfidenceLevel(
        level=level_str,
        score=confidence_score,
        interpretation=level_config["interpretation"],
        ui_color=level_config["ui_color"]
    )


def is_sufficient_confidence(confidence_score: float, min_threshold: float = CONFIDENCE_THRESHOLD_LOW) -> bool:
    """
    Check if confidence meets minimum threshold.
    
    Args:
        confidence_score (float): Confidence [0, 1]
        min_threshold (float): Minimum acceptable confidence (default: 0.3)
    
    Returns:
        bool: True if confidence >= threshold
    
    Example:
        >>> assert is_sufficient_confidence(0.5) == True
        >>> assert is_sufficient_confidence(0.2) == False
    """
    return confidence_score >= min_threshold


def score_variance(chunk_scores: List[float]) -> Optional[float]:
    """
    Calculate variance in chunk scores.
    
    High variance suggests disagreement between sources.
    Low variance suggests consistent sources.
    
    Args:
        chunk_scores (List[float]): Chunk similarity scores
    
    Returns:
        Optional[float]: Standard deviation, or None if <2 chunks
    
    Example:
        >>> scores = [0.9, 0.1]  # High disagreement
        >>> var = score_variance(scores)
        >>> assert var > 0.3
    """
    if len(chunk_scores) < 2:
        return None
    
    return stdev(chunk_scores)


def confidence_summary(
    chunk_scores: List[float],
    contradiction_count: int = 0,
    authority_levels: Optional[List[str]] = None,
    published_dates: Optional[List[datetime]] = None
) -> Dict:
    """
    Generate comprehensive confidence summary with breakdown.
    
    Args:
        chunk_scores (List[float]): Chunk scores
        contradiction_count (int): Contradiction count
        authority_levels (List[str], optional): Authority levels
        published_dates (List[datetime], optional): Publication dates
    
    Returns:
        Dict: Summary with score, level, factors, and recommendations
    
    Example:
        >>> summary = confidence_summary([0.9, 0.85])
        >>> assert "score" in summary
        >>> assert "level" in summary
        >>> assert "factors" in summary
    """
    base_confidence = calculate_base_confidence(chunk_scores)
    final_confidence = calculate_query_confidence(
        chunk_scores,
        contradiction_count,
        authority_levels,
        published_dates
    )
    level = classify_confidence_level(final_confidence)
    variance = score_variance(chunk_scores)
    
    return {
        "base_score": round(base_confidence, 3),
        "final_score": round(final_confidence, 3),
        "level": level,
        "adjustments": {
            "contradictions": contradiction_count,
            "authority_penalized": bool(authority_levels and any(a.lower() == "informational" for a in authority_levels)),
            "recency_penalized": bool(published_dates and any((datetime.now() - d).days > 365*5 for d in published_dates if d))
        },
        "variance": round(variance, 3) if variance else None,
        "chunk_count": len(chunk_scores),
        "recommendation": f"{'Review sources carefully' if level == 'LOW' else 'Monitor for updates' if level == 'MEDIUM' else 'Highly reliable answer'}"
    }
