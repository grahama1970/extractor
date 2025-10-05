#!/usr/bin/env python3
"""
Table Fusion Module
===================

Multi-strategy table candidate abstraction with optional learned calibration.

Purpose:
    - Fuse multiple Camelot extraction strategy results into single best table
    - Support header+body table merging across pages
    - Compute rich confidence features for downstream calibration
    - Optional: Load scikit-learn calibrator from TABLE_CALIBRATOR_PATH

Features:
    1. Single candidate: No-op pass-through
    2. Multi-candidate fusion: Select best based on scores/metrics
    3. Header/body merge: Detect and merge split tables
    4. Confidence diagnostics: structure_prob, fragmentation, header_jaccard, numeric_stability

Environment Variables:
    - TABLE_CALIBRATOR_PATH: Path to pickled scikit-learn model (optional)
      Model must have .predict_proba(X) method returning probabilities
    - TABLE_FUSION_DISABLE: Set to "1" to bypass fusion (future)

Usage:
    from extractor.pipeline.utils.table_fusion import fuse_table_candidates, TableCandidate
    
    candidates = [
        TableCandidate(
            pandas_df=[{"col1": "A", "col2": "B"}],
            bbox=[100, 200, 500, 300],
            page_index=0,
            strategy="lattice",
            score=85.0,
            fragmentation_score=0.12,
            camelot_metrics={"accuracy": 92.5, "whitespace": 8.3}
        ),
        # ... more candidates
    ]
    
    result = fuse_table_candidates(candidates)
    # result contains:
    # - pandas_df: Fused table data
    # - merge_type: "single", "header_body_merge", or "multi_best"
    # - confidence: {structure_prob, fragmentation, header_jaccard, numeric_stability, ...}
    # - source_strategies: List of strategies used
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import os
import pickle
import math


@dataclass
class TableCandidate:
    """
    Single table extraction candidate from one strategy.
    
    Attributes:
        pandas_df: Table data as list of row dicts
        bbox: Bounding box [x0, y0, x1, y1]
        page_index: Page number (0-indexed)
        strategy: Strategy name (e.g., "lattice", "stream")
        score: Quality score from extraction
        fragmentation_score: Fragmentation metric (lower is better)
        camelot_metrics: Dict with accuracy, whitespace, order
        pandas_metrics: Dict with shape, data_density, etc.
    """
    pandas_df: List[Dict[str, Any]]
    bbox: List[float]
    page_index: int
    strategy: str
    score: float
    fragmentation_score: float = 0.0
    camelot_metrics: Optional[Dict[str, Any]] = None
    pandas_metrics: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.camelot_metrics is None:
            self.camelot_metrics = {}
        if self.pandas_metrics is None:
            self.pandas_metrics = {}


def fuse_table_candidates(
    candidates: List[TableCandidate],
    calibrator_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fuse multiple table candidates into single best table with confidence.
    
    Strategy:
    1. Single candidate: Pass through with metadata
    2. Header+body detection: Merge if header/body pattern detected
    3. Multi-candidate: Select best by composite score
    
    Args:
        candidates: List of TableCandidate objects
        calibrator_path: Override path to calibrator model (default: env var)
        
    Returns:
        Dictionary containing:
        - pandas_df: Fused table data
        - bbox: Bounding box of fused table
        - page_index: Page number
        - merge_type: "single", "header_body_merge", or "multi_best"
        - confidence: Confidence components dict
        - source_strategies: List of strategy names used
        - camelot_metrics: Merged metrics
        - pandas_metrics: Merged metrics
    """
    if not candidates:
        return _empty_fusion_result()
    
    # Use env var if no explicit path provided
    if calibrator_path is None:
        calibrator_path = os.getenv("TABLE_CALIBRATOR_PATH")
    
    # Case 1: Single candidate (no-op)
    if len(candidates) == 1:
        return _fuse_single_candidate(candidates[0], calibrator_path)
    
    # Case 2: Detect header + body split pattern
    header_body_result = _detect_and_merge_header_body(candidates)
    if header_body_result:
        return _finalize_fusion(
            header_body_result["pandas_df"],
            header_body_result["bbox"],
            header_body_result["page_index"],
            "header_body_merge",
            candidates,
            calibrator_path,
        )
    
    # Case 3: Multi-candidate - select best
    best_candidate = _select_best_candidate(candidates)
    return _finalize_fusion(
        best_candidate.pandas_df,
        best_candidate.bbox,
        best_candidate.page_index,
        "multi_best",
        candidates,
        calibrator_path,
    )


def _empty_fusion_result() -> Dict[str, Any]:
    """Return empty fusion result when no candidates."""
    return {
        "pandas_df": [],
        "bbox": [0, 0, 0, 0],
        "page_index": 0,
        "merge_type": "empty",
        "confidence": _compute_confidence_components([], None),
        "source_strategies": [],
        "camelot_metrics": {},
        "pandas_metrics": {"shape": [0, 0]},
    }


def _fuse_single_candidate(
    candidate: TableCandidate,
    calibrator_path: Optional[str],
) -> Dict[str, Any]:
    """Pass through single candidate with confidence metadata."""
    return _finalize_fusion(
        candidate.pandas_df,
        candidate.bbox,
        candidate.page_index,
        "single",
        [candidate],
        calibrator_path,
    )


def _detect_and_merge_header_body(
    candidates: List[TableCandidate]
) -> Optional[Dict[str, Any]]:
    """
    Detect header+body split pattern and merge if found.
    
    Pattern:
    - One candidate with single row (header)
    - Another candidate with multiple rows (body)
    - Similar horizontal alignment (bbox overlap)
    - Adjacent or near-adjacent pages
    
    Returns:
        Merged table dict if pattern detected, None otherwise
    """
    if len(candidates) < 2:
        return None
    
    # Find header candidate (1 row) and body candidate (2+ rows)
    header_cand = None
    body_cand = None
    
    for cand in candidates:
        rows = len(cand.pandas_df)
        if rows == 1 and header_cand is None:
            header_cand = cand
        elif rows >= 2 and body_cand is None:
            body_cand = cand
    
    if not (header_cand and body_cand):
        return None
    
    # Check horizontal alignment (bbox overlap)
    h_bbox = header_cand.bbox
    b_bbox = body_cand.bbox
    
    h_x_range = (h_bbox[0], h_bbox[2])
    b_x_range = (b_bbox[0], b_bbox[2])
    
    # Compute horizontal overlap
    overlap = min(h_x_range[1], b_x_range[1]) - max(h_x_range[0], b_x_range[0])
    h_width = h_x_range[1] - h_x_range[0]
    b_width = b_x_range[1] - b_x_range[0]
    
    # Require at least 50% overlap
    if overlap < 0.5 * min(h_width, b_width):
        return None
    
    # Check page adjacency (within 1 page)
    if abs(header_cand.page_index - body_cand.page_index) > 1:
        return None
    
    # Merge: header as first row, body rows follow
    merged_df = [header_cand.pandas_df[0]] + body_cand.pandas_df
    
    # Compute merged bbox (union)
    merged_bbox = [
        min(h_bbox[0], b_bbox[0]),
        min(h_bbox[1], b_bbox[1]),
        max(h_bbox[2], b_bbox[2]),
        max(h_bbox[3], b_bbox[3]),
    ]
    
    # Use body's page_index
    merged_page = body_cand.page_index
    
    return {
        "pandas_df": merged_df,
        "bbox": merged_bbox,
        "page_index": merged_page,
    }


def _select_best_candidate(candidates: List[TableCandidate]) -> TableCandidate:
    """
    Select best candidate from multiple options using composite scoring.
    
    Scoring factors:
    - Primary: extraction score
    - Secondary: data density (non-empty cells)
    - Penalty: fragmentation score
    
    Returns:
        Best TableCandidate
    """
    best_candidate = None
    best_score = -1.0
    
    for cand in candidates:
        # Composite score
        density = cand.pandas_metrics.get("data_density", 0.5) if cand.pandas_metrics else 0.5
        frag_penalty = cand.fragmentation_score * 0.1
        
        composite = cand.score * (1 + density) - frag_penalty
        
        if composite > best_score:
            best_score = composite
            best_candidate = cand
    
    return best_candidate or candidates[0]


def _finalize_fusion(
    pandas_df: List[Dict[str, Any]],
    bbox: List[float],
    page_index: int,
    merge_type: str,
    candidates: List[TableCandidate],
    calibrator_path: Optional[str],
) -> Dict[str, Any]:
    """
    Finalize fusion result with confidence components and metadata.
    
    Args:
        pandas_df: Fused table data
        bbox: Bounding box
        page_index: Page number
        merge_type: Type of fusion performed
        candidates: All candidates involved
        calibrator_path: Path to calibrator model
        
    Returns:
        Complete fusion result dictionary
    """
    # Compute confidence components
    confidence = _compute_confidence_components(candidates, calibrator_path)
    
    # Aggregate metrics
    source_strategies = list(set(c.strategy for c in candidates))
    
    # Use best candidate's metrics as baseline
    best_cand = candidates[0] if candidates else None
    camelot_metrics = best_cand.camelot_metrics.copy() if best_cand and best_cand.camelot_metrics else {}
    pandas_metrics = best_cand.pandas_metrics.copy() if best_cand and best_cand.pandas_metrics else {}
    
    # Update shape to match fused result
    pandas_metrics["shape"] = [len(pandas_df), len(pandas_df[0]) if pandas_df else 0]
    
    return {
        "pandas_df": pandas_df,
        "bbox": bbox,
        "page_index": page_index,
        "merge_type": merge_type,
        "confidence": confidence,
        "source_strategies": source_strategies,
        "camelot_metrics": camelot_metrics,
        "pandas_metrics": pandas_metrics,
    }


def _compute_confidence_components(
    candidates: List[TableCandidate],
    calibrator_path: Optional[str],
) -> Dict[str, Any]:
    """
    Compute confidence components for fused table.
    
    Components:
    - structure_prob: Learned calibrator output (if available)
    - fragmentation: Avg fragmentation score (lower is better, inverted for confidence)
    - header_jaccard: Column name similarity across candidates
    - numeric_stability: Consistency of numeric cell counts
    - strategy_diversity: Number of unique strategies
    
    Args:
        candidates: All candidates
        calibrator_path: Path to calibrator model
        
    Returns:
        Confidence components dictionary
    """
    if not candidates:
        return {
            "structure_prob": None,
            "fragmentation": None,
            "header_jaccard": None,
            "numeric_stability": None,
            "strategy_diversity": 0,
        }
    
    # 1. Structure probability from calibrator (if available)
    structure_prob = None
    if calibrator_path and os.path.exists(calibrator_path):
        try:
            structure_prob = _predict_structure_prob(candidates, calibrator_path)
        except Exception:
            pass  # Gracefully handle calibrator loading failures
    
    # 2. Fragmentation (inverted: 1 - avg_frag)
    avg_frag = sum(c.fragmentation_score for c in candidates) / len(candidates)
    fragmentation_conf = max(0.0, 1.0 - avg_frag)
    
    # 3. Header Jaccard (column name consistency)
    header_jaccard = _compute_header_jaccard(candidates)
    
    # 4. Numeric stability (variance in numeric cell counts)
    numeric_stability = _compute_numeric_stability(candidates)
    
    # 5. Strategy diversity
    strategy_diversity = len(set(c.strategy for c in candidates))
    
    return {
        "structure_prob": round(structure_prob, 4) if structure_prob is not None else None,
        "fragmentation": round(fragmentation_conf, 4),
        "header_jaccard": round(header_jaccard, 4),
        "numeric_stability": round(numeric_stability, 4),
        "strategy_diversity": strategy_diversity,
    }


def _predict_structure_prob(
    candidates: List[TableCandidate],
    calibrator_path: str,
) -> Optional[float]:
    """
    Predict structure probability using loaded calibrator model.
    
    Features: fragmentation, header_jaccard_max, numeric_stability,
              row_count, col_count, strategy_diversity
    
    Args:
        candidates: Table candidates
        calibrator_path: Path to pickled model
        
    Returns:
        Probability between 0-1, or None if prediction fails
    """
    try:
        with open(calibrator_path, "rb") as f:
            model = pickle.load(f)
        
        # Extract features (simplified - real calibration would be more sophisticated)
        avg_frag = sum(c.fragmentation_score for c in candidates) / len(candidates)
        header_jac = _compute_header_jaccard(candidates)
        num_stab = _compute_numeric_stability(candidates)
        
        # Use first candidate for shape
        first = candidates[0]
        shape = first.pandas_metrics.get("shape", [0, 0]) if first.pandas_metrics else [0, 0]
        row_count = shape[0]
        col_count = shape[1]
        strategy_div = len(set(c.strategy for c in candidates))
        
        # Feature vector
        X = [[avg_frag, header_jac, num_stab, row_count, col_count, strategy_div]]
        
        # Predict probability
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)
            # Assume binary classification: class 1 is "good table"
            return float(proba[0][1])
        else:
            # Fallback: use decision function or predict
            score = model.predict(X)[0] if hasattr(model, "predict") else 0.5
            return float(score)
    
    except Exception:
        return None


def _compute_header_jaccard(candidates: List[TableCandidate]) -> float:
    """
    Compute Jaccard similarity of column headers across candidates.
    
    Higher is better (more consistent headers).
    
    Returns:
        Jaccard index (0-1)
    """
    if len(candidates) < 2:
        return 1.0
    
    # Extract column names from first row of each candidate
    header_sets = []
    for cand in candidates:
        if cand.pandas_df:
            # Use keys from first row as headers
            headers = set(cand.pandas_df[0].keys())
            header_sets.append(headers)
    
    if not header_sets:
        return 1.0
    
    # Compute pairwise Jaccard and average
    jaccard_scores = []
    for i in range(len(header_sets)):
        for j in range(i + 1, len(header_sets)):
            intersection = len(header_sets[i] & header_sets[j])
            union = len(header_sets[i] | header_sets[j])
            jaccard = intersection / union if union > 0 else 0.0
            jaccard_scores.append(jaccard)
    
    return sum(jaccard_scores) / len(jaccard_scores) if jaccard_scores else 1.0


def _compute_numeric_stability(candidates: List[TableCandidate]) -> float:
    """
    Compute consistency of numeric cell content across candidates.
    
    Measures coefficient of variation (CV) of numeric cell counts.
    Lower CV = higher stability.
    
    Returns:
        Stability score (0-1), where 1 is perfectly stable
    """
    if len(candidates) < 2:
        return 1.0
    
    # Count numeric cells in each candidate
    numeric_counts = []
    for cand in candidates:
        count = 0
        for row in cand.pandas_df:
            for value in row.values():
                # Check if value looks numeric
                try:
                    float(str(value))
                    count += 1
                except (ValueError, TypeError):
                    pass
        numeric_counts.append(count)
    
    if not numeric_counts:
        return 1.0
    
    # Compute coefficient of variation
    mean = sum(numeric_counts) / len(numeric_counts)
    if mean == 0:
        return 1.0
    
    variance = sum((x - mean) ** 2 for x in numeric_counts) / len(numeric_counts)
    std_dev = math.sqrt(variance)
    cv = std_dev / mean
    
    # Convert CV to stability score (invert and cap at 1)
    # CV of 0 = stability 1.0, CV of 1 = stability 0.5, etc.
    stability = 1.0 / (1.0 + cv)
    
    return stability
