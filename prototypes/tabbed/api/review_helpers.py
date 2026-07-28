"""Helper models, box converters, and agent-note collector for review_server.

Split out to keep review_server.py under 800 lines.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# --- Models ---


class Box(BaseModel):
    """Define a rectangular box with properties for position and metadata."""
    id: str
    type: str
    instanceId: str = ""
    x: float  # 0..1 normalized
    y: float
    w: float
    h: float
    source: str = "pipeline"
    confidence: Optional[float] = None
    reviewed: bool = False
    edited: bool = False
    stage: Optional[str] = None
    title: Optional[str] = None
    text_preview: Optional[str] = None


class RunSummary(BaseModel):
    """Represent summary data for a document processing run."""
    stem: str
    run_dir: str
    pdf_path: Optional[str] = None
    page_count: Optional[int] = None
    has_blocks: bool = False
    has_tables: bool = False
    has_figures: bool = False
    is_blacklisted: bool = False
    profile_domain: Optional[str] = None
    profile_route: Optional[str] = None
    block_count: int = 0
    table_count: int = 0
    figure_count: int = 0
    verdict: Optional[str] = None  # PASS / WARN / FAIL
    overall_score: Optional[float] = None
    grade: Optional[str] = None


class AgentNote(BaseModel):
    """A diagnostic note from the pipeline agent about extraction issues."""
    model_config = {"arbitrary_types_allowed": True}

    severity: str  # "error" | "warning" | "info"
    source: str  # stage or subsystem that produced the note
    message: str
    details: Optional[Dict[str, Any]] = None
    page: Optional[int] = None  # page number if note is page-specific


# Rebuild models to resolve forward references from `from __future__ import annotations`
AgentNote.model_rebuild()


class CorrectionChange(BaseModel):
    """Tracks a single bbox change: added, modified, or deleted."""
    box_id: str
    action: str  # "added", "modified", "deleted"
    before: Optional[Box] = None
    after: Optional[Box] = None


class CorrectionEntry(BaseModel):
    """Model a single document correction, including text and location."""
    stem: str
    page: int
    boxes: List[Box]
    notes: str = ""
    reviewer: str = ""
    changes: Optional[List[CorrectionChange]] = None


class BulkActionRequest(BaseModel):
    """Create a bulk action request with specified PDF stems and action."""
    stems: List[str]
    action: str  # "blacklist", "dismiss", "reextract"
    reason: str = ""


# --- Box converters ---


def blocks_to_boxes(
    blocks: List[Dict],
    page_dims: List[tuple[float, float]],
) -> Dict[int, List[Box]]:
    """Convert S02 marker blocks to normalized Box objects grouped by page."""
    boxes_by_page: Dict[int, List[Box]] = {}
    for b in blocks:
        bbox = b.get("bbox")
        page_idx = b.get("page_idx", b.get("page"))
        if bbox is None or page_idx is None:
            continue
        page_idx = int(page_idx)
        if page_idx < 0 or page_idx >= len(page_dims):
            continue

        pw, ph = page_dims[page_idx]
        if pw <= 0 or ph <= 0:
            continue

        x0, y0, x1, y1 = [float(v) for v in bbox]
        box = Box(
            id=b.get("id", f"block_{page_idx}_{len(boxes_by_page.get(page_idx, []))}"),
            type=b.get("block_type", "Text"),
            instanceId=b.get("id", ""),
            x=max(0.0, min(1.0, x0 / pw)),
            y=max(0.0, min(1.0, y0 / ph)),
            w=max(0.0, min(1.0, (x1 - x0) / pw)),
            h=max(0.0, min(1.0, (y1 - y0) / ph)),
            source="pipeline",
            confidence=b.get("header_confidence"),
            stage="02",
            text_preview=(b.get("text", "") or "")[:120],
        )
        boxes_by_page.setdefault(page_idx + 1, []).append(box)  # 1-indexed for UI
    return boxes_by_page


def tables_to_boxes(
    tables: List[Dict],
    page_dims: List[tuple[float, float]],
) -> Dict[int, List[Box]]:
    """Convert S05 tables to normalized Box objects. Handles Camelot origin (bottom-left)."""
    boxes_by_page: Dict[int, List[Box]] = {}
    for i, t in enumerate(tables):
        bbox = t.get("bbox")
        try:
            page_num = int(t.get("page_number", 1))
        except Exception:
            page_num = 1
        page_idx = page_num - 1
        if bbox is None or page_idx < 0 or page_idx >= len(page_dims):
            continue

        pw, ph = page_dims[page_idx]
        if pw <= 0 or ph <= 0:
            continue

        x0, y0_cam, x1, y1_cam = [float(v) for v in bbox]
        # Camelot: origin bottom-left, y increases upward -> flip
        y0 = ph - y1_cam
        y1 = ph - y0_cam

        shape = t.get("pandas_metrics", {}).get("shape", [])
        label = f"Table {shape[0] if len(shape) > 0 else '?'}x{shape[1] if len(shape) > 1 else '?'}"

        box = Box(
            id=f"table_{page_num}_{i}",
            type="Table",
            instanceId=f"table_{i}",
            x=max(0.0, min(1.0, x0 / pw)),
            y=max(0.0, min(1.0, y0 / ph)),
            w=max(0.0, min(1.0, (x1 - x0) / pw)),
            h=max(0.0, min(1.0, (y1 - y0) / ph)),
            source="pipeline",
            stage="05",
            title=label,
        )
        boxes_by_page.setdefault(page_num, []).append(box)
    return boxes_by_page


def figures_to_boxes(
    figures: List[Dict],
    page_dims: List[tuple[float, float]],
) -> Dict[int, List[Box]]:
    """Convert S06 figures to normalized Box objects."""
    boxes_by_page: Dict[int, List[Box]] = {}
    for i, f in enumerate(figures):
        bbox = f.get("bbox")
        try:
            page_num = int(f.get("page_number", 1))
        except Exception:
            page_num = 1
        page_idx = page_num - 1
        if bbox is None or page_idx < 0 or page_idx >= len(page_dims):
            continue

        pw, ph = page_dims[page_idx]
        if pw <= 0 or ph <= 0:
            continue

        x0, y0, x1, y1 = [float(v) for v in bbox]
        box = Box(
            id=f"figure_{page_num}_{i}",
            type="Figure",
            instanceId=f"figure_{i}",
            x=max(0.0, min(1.0, x0 / pw)),
            y=max(0.0, min(1.0, y0 / ph)),
            w=max(0.0, min(1.0, (x1 - x0) / pw)),
            h=max(0.0, min(1.0, (y1 - y0) / ph)),
            source="pipeline",
            stage="06",
            title=f.get("title") or f.get("inferred_title") or "Figure",
        )
        boxes_by_page.setdefault(page_num, []).append(box)
    return boxes_by_page


def merge_boxes(
    *box_dicts: Dict[int, List[Box]],
) -> Dict[int, List[Box]]:
    """Merge multiple box dicts into one (union by page)."""
    merged: Dict[int, List[Box]] = {}
    for bd in box_dicts:
        for page, boxes in bd.items():
            merged.setdefault(page, []).extend(boxes)
    return merged


# --- Agent notes collector ---


def collect_agent_notes(
    run_dir: Path,
    pdf_stem: str,
    *,
    load_json_fn,
    load_blacklist_fn,
    blacklist_path: Path,
) -> List[AgentNote]:
    """Collect extraction diagnostic notes from pipeline run data.

    Reads profile errors, layout audit failures, suspicious headers,
    timing anomalies, and blacklist reasons to produce human-readable
    agent notes about extraction issues.
    """
    notes: List[AgentNote] = []

    # 1. Profile preset_match errors (S00)
    profile = load_json_fn(run_dir / "00_profile_detector" / "profile.json")
    if profile:
        pm = profile.get("preset_match", {})
        errors = pm.get("errors", [])
        if errors:
            notes.append(AgentNote(
                severity="warning",
                source="S00 Profile Detector",
                message=f"Document has {len(errors)} extraction risk(s): {', '.join(errors)}",
                details={"errors": errors, "preset": pm.get("matched"), "confidence": pm.get("confidence")},
            ))
        # Low confidence preset match
        conf = pm.get("confidence", 100)
        if isinstance(conf, (int, float)) and conf < 10:
            notes.append(AgentNote(
                severity="warning",
                source="S00 Profile Detector",
                message=f"Low preset confidence ({conf}) — extraction parameters may be suboptimal",
                details={"matched_preset": pm.get("matched"), "all_scores": pm.get("all_scores")},
            ))

    # 2. Suspicious headers (S03)
    s03 = load_json_fn(run_dir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json")
    if s03:
        susp_count = s03.get("suspicious_block_count", 0)
        if susp_count > 0:
            notes.append(AgentNote(
                severity="warning",
                source="S03 Suspicious Headers",
                message=f"{susp_count} suspicious header block(s) detected — may be false section breaks",
                details={"suspicious_block_count": susp_count, "total_blocks": s03.get("block_count", len(s03.get("blocks", [])))},
            ))
        warn_count = s03.get("warnings_count", 0)
        if warn_count > 0:
            notes.append(AgentNote(
                severity="info",
                source="S03 Suspicious Headers",
                message=f"{warn_count} warning(s) during header verification",
            ))

    # 3. Layout audit (S04a)
    audit = load_json_fn(run_dir / "04a_layout_audit" / "json_output" / "04a_layout_audit.json")
    if audit:
        error_count = audit.get("errors", 0)
        total_checks = audit.get("sections_checked", 0)
        if error_count > 0:
            checks = audit.get("checks", [])
            reason_counts: Dict[str, int] = {}
            for c in checks:
                if not c.get("ok", True):
                    reason = c.get("reason", "unknown")
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
            reason_summary = ", ".join(f"{r} ({n})" for r, n in sorted(reason_counts.items(), key=lambda x: -x[1])[:5])
            sev = "error" if error_count > total_checks * 0.3 else "warning"
            notes.append(AgentNote(
                severity=sev,
                source="S04a Layout Audit",
                message=f"{error_count}/{total_checks} layout checks failed: {reason_summary}",
                details={"error_count": error_count, "total_checks": total_checks, "reason_counts": reason_counts},
            ))

    # 4. Timing anomalies
    timings_path = run_dir / "timings.jsonl"
    if timings_path.exists():
        try:
            total_ms = 0
            slow_stages: List[str] = []
            for line in timings_path.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                rec = json.loads(line)
                lat = rec.get("latency_ms", 0)
                total_ms += lat
                if lat > 120_000:  # > 2 min is notable
                    slow_stages.append(f"{rec.get('stage', '?')} ({lat / 1000:.0f}s)")
            if slow_stages:
                notes.append(AgentNote(
                    severity="info",
                    source="Pipeline Timing",
                    message=f"Slow stages: {'; '.join(slow_stages)} (total {total_ms / 1000:.0f}s)",
                    details={"total_ms": total_ms, "slow_stages": slow_stages},
                ))
        except Exception:
            pass

    # 5. Scanned PDF detection
    scanned = load_json_fn(run_dir / "scanned_pdf.json")
    if scanned and scanned.get("is_scanned"):
        text_ratio = scanned.get("text_ratio", 0)
        notes.append(AgentNote(
            severity="warning" if text_ratio < 0.1 else "info",
            source="PDF Classification",
            message=f"Scanned PDF detected (text ratio: {text_ratio:.1%}) — OCR quality may vary",
            details=scanned,
        ))

    # 6. Blacklist status
    blacklist = load_blacklist_fn()
    if pdf_stem in blacklist:
        reason = "unknown"
        if blacklist_path.exists():
            for line in blacklist_path.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("stem") == pdf_stem:
                        reason = entry.get("reason", "unknown")
                        break
                except Exception:
                    pass
        notes.append(AgentNote(
            severity="error",
            source="Blacklist",
            message=f"PDF is blacklisted — reason: {reason}",
            details={"reason": reason},
        ))

    # 7. Missing expected stages
    expected_stages = [
        ("02_marker_extractor", "json_output/02_marker_blocks.json", "S02 text blocks"),
        ("05_table_extractor", "json_output/05_tables.json", "S05 tables"),
        ("06_figure_extractor", "json_output/06_figures.json", "S06 figures"),
    ]
    for stage_dir, output_file, label in expected_stages:
        stage_path = run_dir / stage_dir
        if stage_path.is_dir() and not (stage_path / output_file).exists():
            notes.append(AgentNote(
                severity="error",
                source=label,
                message=f"{label} stage ran but produced no output — extraction likely failed",
            ))
        elif not stage_path.is_dir():
            notes.append(AgentNote(
                severity="info",
                source=label,
                message=f"{label} stage was not executed",
            ))

    # Sort: errors first, then warnings, then info
    severity_order = {"error": 0, "warning": 1, "info": 2}
    notes.sort(key=lambda n: severity_order.get(n.severity, 3))

    return notes
