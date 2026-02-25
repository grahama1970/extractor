"""Extraction preview for calibration validation.

Shows what extraction would produce before committing to a preset.
Allows comparison between baseline detection and calibrated detection.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from extractor.pipeline.calibration.detector import (
    DetectedElement,
    DetectorConfig,
    ElementDetector,
)
from extractor.pipeline.calibration.pattern_learner import PatternLearner
from extractor.pipeline.calibration.schema import CalibrationSchema


@dataclass
class ElementSummary:
    """Summary of a detected element for preview."""

    element_type: str
    page_num: int
    bbox: list[float]
    text_preview: str  # First 50 chars
    confidence: float
    source: str  # "baseline" or "calibrated"
    matched_pattern: str | None = None


@dataclass
class PagePreview:
    """Preview of elements on a single page."""

    page_num: int
    baseline_elements: list[ElementSummary]
    calibrated_elements: list[ElementSummary]
    added: list[ElementSummary]  # In calibrated but not baseline
    removed: list[ElementSummary]  # In baseline but not calibrated
    improved: list[tuple[ElementSummary, ElementSummary]]  # Changed confidence


@dataclass
class PreviewResult:
    """Result of extraction preview."""

    pdf_path: str
    total_pages: int
    pages_previewed: list[int]
    page_previews: list[PagePreview]

    # Summary stats
    baseline_count: dict[str, int] = field(default_factory=dict)
    calibrated_count: dict[str, int] = field(default_factory=dict)

    # Patterns used (if from session)
    patterns_applied: list[str] = field(default_factory=list)
    session_key: str | None = None

    def total_baseline(self) -> int:
        return sum(self.baseline_count.values())

    def total_calibrated(self) -> int:
        return sum(self.calibrated_count.values())

    def improvement_delta(self) -> dict[str, int]:
        """Return count difference per type (positive = more detected)."""
        delta = {}
        all_types = set(self.baseline_count.keys()) | set(self.calibrated_count.keys())
        for t in all_types:
            delta[t] = self.calibrated_count.get(t, 0) - self.baseline_count.get(t, 0)
        return delta


class ExtractionPreview:
    """Preview extraction results before generating preset."""

    def __init__(self, schema: CalibrationSchema | None = None):
        """Initialize preview generator.

        Args:
            schema: CalibrationSchema instance. Creates new one if not provided.
        """
        self.schema = schema or CalibrationSchema()

    def preview_extraction(
        self,
        pdf_path: Path | str,
        session_key: str | None = None,
        pages: list[int] | None = None,
        max_pages: int = 5,
    ) -> PreviewResult:
        """Run extraction preview comparing baseline vs calibrated detection.

        Args:
            pdf_path: Path to PDF file.
            session_key: Optional calibration session to use patterns from.
            pages: Optional list of specific pages (1-indexed). If None, samples pages.
            max_pages: Maximum pages to preview if pages not specified.

        Returns:
            PreviewResult with detected elements and comparison.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        # Determine which pages to preview
        if pages:
            preview_pages = [p for p in pages if 1 <= p <= total_pages]
        else:
            # Sample pages: first, middle, last, and some random
            preview_pages = self._sample_pages(total_pages, max_pages)

        # Get baseline detector (no calibration)
        baseline_detector = ElementDetector(DetectorConfig())

        # Get calibrated detector (with learned patterns)
        calibrated_config = self._build_calibrated_config(session_key)
        calibrated_detector = ElementDetector(calibrated_config)

        # Get patterns applied
        patterns_applied = []
        if session_key:
            patterns_applied = self._get_pattern_names(session_key)

        # Run detection on each page
        page_previews = []
        baseline_count: dict[str, int] = {}
        calibrated_count: dict[str, int] = {}

        for page_num in preview_pages:
            page = doc[page_num - 1]  # 0-indexed

            # Baseline detection
            baseline_elements = baseline_detector.detect_page(page, page_num)
            baseline_summaries = [self._to_summary(e, "baseline") for e in baseline_elements]

            # Calibrated detection
            calibrated_elements = calibrated_detector.detect_page(page, page_num)
            calibrated_summaries = [
                self._to_summary(e, "calibrated", patterns_applied) for e in calibrated_elements
            ]

            # Compute diff
            added, removed, improved = self._compute_diff(baseline_summaries, calibrated_summaries)

            page_previews.append(
                PagePreview(
                    page_num=page_num,
                    baseline_elements=baseline_summaries,
                    calibrated_elements=calibrated_summaries,
                    added=added,
                    removed=removed,
                    improved=improved,
                )
            )

            # Count by type
            for e in baseline_summaries:
                baseline_count[e.element_type] = baseline_count.get(e.element_type, 0) + 1
            for e in calibrated_summaries:
                calibrated_count[e.element_type] = calibrated_count.get(e.element_type, 0) + 1

        doc.close()

        return PreviewResult(
            pdf_path=str(pdf_path),
            total_pages=total_pages,
            pages_previewed=preview_pages,
            page_previews=page_previews,
            baseline_count=baseline_count,
            calibrated_count=calibrated_count,
            patterns_applied=patterns_applied,
            session_key=session_key,
        )

    def _sample_pages(self, total: int, max_pages: int) -> list[int]:
        """Sample representative pages from document."""
        if total <= max_pages:
            return list(range(1, total + 1))

        # Always include first and last
        pages = {1, total}

        # Add middle page
        pages.add(total // 2)

        # Add some evenly distributed pages
        step = total // max_pages
        for i in range(1, max_pages - 2):
            pages.add(min(total, 1 + i * step))

        return sorted(pages)[:max_pages]

    def _build_calibrated_config(self, session_key: str | None) -> DetectorConfig:
        """Build detector config with learned patterns from session."""
        config = DetectorConfig()

        if not session_key:
            return config

        # Get learned patterns from session
        try:
            PatternLearner(self.schema)
            # Get patterns from the session
            patterns = self._get_session_patterns(session_key)

            # Apply header patterns
            header_regexes = []
            for p in patterns:
                if p.get("element_type") == "header" and p.get("stage1_regex"):
                    header_regexes.append(p["stage1_regex"])

            if header_regexes:
                config.header_patterns = header_regexes + config.header_patterns

        except Exception:
            # If we can't load patterns, use defaults
            pass

        return config

    def _get_session_patterns(self, session_key: str) -> list[dict[str, Any]]:
        """Get patterns from a calibration session."""
        try:
            patterns_coll = self.schema.db.collection("calibration_patterns")
            cursor = patterns_coll.find({"session_key": session_key})
            return list(cursor)
        except Exception:
            return []

    def _get_pattern_names(self, session_key: str) -> list[str]:
        """Get names of patterns from session."""
        patterns = self._get_session_patterns(session_key)
        return [p.get("pattern_name", "unknown") for p in patterns]

    def _to_summary(
        self,
        element: DetectedElement,
        source: str,
        patterns: list[str] | None = None,
    ) -> ElementSummary:
        """Convert DetectedElement to ElementSummary."""
        text_preview = element.text[:50] if element.text else ""
        if len(element.text) > 50:
            text_preview += "..."

        return ElementSummary(
            element_type=element.element_type,
            page_num=element.page_num,
            bbox=element.bbox,
            text_preview=text_preview,
            confidence=element.confidence,
            source=source,
            matched_pattern=patterns[0] if patterns else None,
        )

    def _compute_diff(
        self,
        baseline: list[ElementSummary],
        calibrated: list[ElementSummary],
    ) -> tuple[
        list[ElementSummary], list[ElementSummary], list[tuple[ElementSummary, ElementSummary]]
    ]:
        """Compute difference between baseline and calibrated detections.

        Returns:
            Tuple of (added, removed, improved) elements.
        """
        # Use bbox overlap to match elements
        added = []
        removed = []
        improved = []

        matched_calibrated = set()

        for base_elem in baseline:
            best_match = None
            best_overlap = 0.0

            for i, cal_elem in enumerate(calibrated):
                if i in matched_calibrated:
                    continue
                if base_elem.element_type != cal_elem.element_type:
                    continue

                overlap = self._bbox_overlap(base_elem.bbox, cal_elem.bbox)
                if overlap > 0.5 and overlap > best_overlap:
                    best_match = (i, cal_elem)
                    best_overlap = overlap

            if best_match:
                matched_calibrated.add(best_match[0])
                # Check if confidence improved
                if best_match[1].confidence > base_elem.confidence + 0.1:
                    improved.append((base_elem, best_match[1]))
            else:
                removed.append(base_elem)

        # Elements in calibrated but not matched to baseline
        for i, cal_elem in enumerate(calibrated):
            if i not in matched_calibrated:
                added.append(cal_elem)

        return added, removed, improved

    def _bbox_overlap(self, bbox1: list[float], bbox2: list[float]) -> float:
        """Calculate IoU overlap between two bboxes."""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])

        if x2 < x1 or y2 < y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        union = area1 + area2 - intersection

        if union == 0:
            return 0.0

        return intersection / union


def format_preview_text(result: PreviewResult) -> str:
    """Format preview result for TUI display.

    Args:
        result: PreviewResult from preview_extraction.

    Returns:
        Formatted text suitable for terminal display.
    """
    lines = []
    lines.append(f"# Extraction Preview: {Path(result.pdf_path).name}")
    lines.append("")
    lines.append(f"**Pages:** {result.total_pages} total, {len(result.pages_previewed)} previewed")
    lines.append(f"**Session:** {result.session_key or 'None (baseline only)'}")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Type | Baseline | Calibrated | Delta |")
    lines.append("|------|----------|------------|-------|")

    all_types = sorted(set(result.baseline_count.keys()) | set(result.calibrated_count.keys()))
    delta = result.improvement_delta()

    for t in all_types:
        base = result.baseline_count.get(t, 0)
        cal = result.calibrated_count.get(t, 0)
        d = delta.get(t, 0)
        delta_str = f"+{d}" if d > 0 else str(d)
        lines.append(f"| {t} | {base} | {cal} | {delta_str} |")

    lines.append(
        f"| **Total** | {result.total_baseline()} | {result.total_calibrated()} | {result.total_calibrated() - result.total_baseline():+d} |"
    )
    lines.append("")

    # Patterns applied
    if result.patterns_applied:
        lines.append("## Patterns Applied")
        lines.append("")
        for p in result.patterns_applied:
            lines.append(f"- {p}")
        lines.append("")

    # Per-page details
    lines.append("## Page Details")
    lines.append("")

    for page in result.page_previews:
        lines.append(f"### Page {page.page_num}")
        lines.append("")

        if page.added:
            lines.append(f"**Added ({len(page.added)}):**")
            for e in page.added[:3]:  # Limit to 3
                lines.append(f'  - {e.element_type}: "{e.text_preview}" ({e.confidence:.0%})')
            if len(page.added) > 3:
                lines.append(f"  - ... and {len(page.added) - 3} more")
            lines.append("")

        if page.removed:
            lines.append(f"**Removed ({len(page.removed)}):**")
            for e in page.removed[:3]:
                lines.append(f'  - {e.element_type}: "{e.text_preview}"')
            if len(page.removed) > 3:
                lines.append(f"  - ... and {len(page.removed) - 3} more")
            lines.append("")

        if page.improved:
            lines.append(f"**Improved Confidence ({len(page.improved)}):**")
            for before, after in page.improved[:3]:
                lines.append(
                    f"  - {before.element_type}: {before.confidence:.0%} → {after.confidence:.0%}"
                )
            lines.append("")

        if not page.added and not page.removed and not page.improved:
            lines.append("No changes from baseline.")
            lines.append("")

    return "\n".join(lines)


def format_preview_json(result: PreviewResult) -> dict[str, Any]:
    """Format preview result as JSON-serializable dict.

    Args:
        result: PreviewResult from preview_extraction.

    Returns:
        Dictionary suitable for JSON serialization.
    """
    return {
        "pdf_path": result.pdf_path,
        "total_pages": result.total_pages,
        "pages_previewed": result.pages_previewed,
        "session_key": result.session_key,
        "patterns_applied": result.patterns_applied,
        "summary": {
            "baseline_count": result.baseline_count,
            "calibrated_count": result.calibrated_count,
            "delta": result.improvement_delta(),
            "total_baseline": result.total_baseline(),
            "total_calibrated": result.total_calibrated(),
        },
        "pages": [
            {
                "page_num": p.page_num,
                "baseline_count": len(p.baseline_elements),
                "calibrated_count": len(p.calibrated_elements),
                "added_count": len(p.added),
                "removed_count": len(p.removed),
                "improved_count": len(p.improved),
                "added": [
                    {
                        "type": e.element_type,
                        "text": e.text_preview,
                        "confidence": e.confidence,
                        "bbox": e.bbox,
                    }
                    for e in p.added
                ],
                "removed": [
                    {
                        "type": e.element_type,
                        "text": e.text_preview,
                        "bbox": e.bbox,
                    }
                    for e in p.removed
                ],
            }
            for p in result.page_previews
        ],
    }
