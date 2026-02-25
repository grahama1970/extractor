#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi>=0.115.0",
#   "uvicorn>=0.32.0",
#   "pydantic>=2.4.0",
#   "pymupdf>=1.25.0",
# ]
# ///
"""Review server — serves extraction run data as tabbed-compatible annotations.

Reads S02/S05/S06 bbox data from run directories and converts to normalized
(0-1) Box coordinates for the tabbed UI. Supports browsing runs, loading
annotations, and saving human corrections.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

try:
    import fitz
except Exception as e:
    raise RuntimeError("PyMuPDF (fitz) is required") from e

app = FastAPI(title="PDF Review Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount agent endpoint router for 5ft voice canvas
try:
    from agent_endpoint import router as agent_router
    app.include_router(agent_router)
except ImportError:
    pass  # agent_endpoint.py not available

# Run directory locations
EXTRACTED_RUNS_NVME = Path(
    os.environ.get(
        "EXTRACTED_RUNS_NVME",
        "/home/graham/workspace/experiments/pi-mono/.pi/skills/review-pdf/extracted_runs_staging",
    )
)
EXTRACTED_RUNS_HDD = Path(
    os.environ.get(
        "EXTRACTED_RUNS_HDD",
        "/mnt/storage12tb/skills/review-pdf/extracted_runs",
    )
)
CORPUS_ROOT = Path(
    os.environ.get("CORPUS_ROOT", "/mnt/storage12tb/extractor_corpus")
)
CORRECTIONS_DIR = Path(
    os.environ.get(
        "CORRECTIONS_DIR",
        "/home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake/state/corrections",
    )
)
CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)

BLACKLIST_PATH = Path(
    os.environ.get(
        "BLACKLIST_PATH",
        "/home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake/state/failed_pdf_blacklist.jsonl",
    )
)
STATE_DIR = Path(
    os.environ.get(
        "STATE_DIR",
        "/home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake/state",
    )
)
REPORTS_DIR = Path(
    os.environ.get(
        "REPORTS_DIR",
        "/home/graham/workspace/experiments/pi-mono/.pi/skills/review-pdf/reports",
    )
)


# --- Models ---


class Box(BaseModel):
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


class CorrectionEntry(BaseModel):
    stem: str
    page: int
    boxes: List[Box]
    notes: str = ""
    reviewer: str = ""


# --- Helpers ---


def _find_run_dir(stem: str) -> Optional[Path]:
    """Find run directory by PDF stem (checks NVMe then HDD)."""
    for runs_dir in (EXTRACTED_RUNS_NVME, EXTRACTED_RUNS_HDD):
        if not runs_dir.is_dir():
            continue
        for entry in runs_dir.iterdir():
            if entry.name.startswith(stem):
                target = entry.resolve() if entry.is_symlink() else entry
                if target.is_dir():
                    return target
    return None


def _find_pdf_for_stem(stem: str) -> Optional[Path]:
    """Find the original PDF in the corpus by stem."""
    for pdf in CORPUS_ROOT.rglob(f"{stem}.pdf"):
        if pdf.is_file():
            return pdf
    return None


def _load_json(path: Path) -> Optional[Any]:
    """Safely load JSON from path."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _load_blacklist() -> set[str]:
    """Load blacklisted PDF stems."""
    if not BLACKLIST_PATH.exists():
        return set()
    stems: set[str] = set()
    for line in BLACKLIST_PATH.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            stems.add(entry.get("stem", ""))
        except Exception:
            pass
    return stems


def _get_page_dims(pdf_path: Path) -> List[tuple[float, float]]:
    """Get (width, height) for each page."""
    doc = fitz.open(str(pdf_path))
    dims = [(float(p.rect.width), float(p.rect.height)) for p in doc]
    doc.close()
    return dims


def _blocks_to_boxes(
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


def _tables_to_boxes(
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
        # Camelot: origin bottom-left, y increases upward → flip
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


def _figures_to_boxes(
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


def _merge_boxes(
    *box_dicts: Dict[int, List[Box]],
) -> Dict[int, List[Box]]:
    """Merge multiple box dicts into one (union by page)."""
    merged: Dict[int, List[Box]] = {}
    for bd in box_dicts:
        for page, boxes in bd.items():
            merged.setdefault(page, []).extend(boxes)
    return merged


def _collect_agent_notes(run_dir: Path, stem: str) -> List[AgentNote]:
    """Collect extraction diagnostic notes from pipeline run data.

    Reads profile errors, layout audit failures, suspicious headers,
    timing anomalies, and blacklist reasons to produce human-readable
    agent notes about extraction issues.
    """
    notes: List[AgentNote] = []

    # 1. Profile preset_match errors (S00)
    profile = _load_json(run_dir / "00_profile_detector" / "profile.json")
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
    s03 = _load_json(run_dir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json")
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
    audit = _load_json(run_dir / "04a_layout_audit" / "json_output" / "04a_layout_audit.json")
    if audit:
        error_count = audit.get("errors", 0)
        total_checks = audit.get("sections_checked", 0)
        if error_count > 0:
            # Summarize failure reasons
            checks = audit.get("checks", [])
            reason_counts: Dict[str, int] = {}
            pages_affected: set[int] = set()
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
    scanned = _load_json(run_dir / "scanned_pdf.json")
    if scanned and scanned.get("is_scanned"):
        text_ratio = scanned.get("text_ratio", 0)
        notes.append(AgentNote(
            severity="warning" if text_ratio < 0.1 else "info",
            source="PDF Classification",
            message=f"Scanned PDF detected (text ratio: {text_ratio:.1%}) — OCR quality may vary",
            details=scanned,
        ))

    # 6. Blacklist status
    blacklist = _load_blacklist()
    if stem in blacklist:
        # Find reason from blacklist
        reason = "unknown"
        if BLACKLIST_PATH.exists():
            for line in BLACKLIST_PATH.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("stem") == stem:
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


def _build_report_index() -> Dict[str, Dict[str, Any]]:
    """Build an index of stem → latest report from all report directories.

    Scans REPORTS_DIR for per_doc JSON files. For each stem, keeps the
    most recent report (highest timestamp in directory name).
    """
    index: Dict[str, Dict[str, Any]] = {}
    if not REPORTS_DIR.is_dir():
        return index
    for run_dir in sorted(REPORTS_DIR.iterdir()):
        per_doc = run_dir / "per_doc"
        if not per_doc.is_dir():
            continue
        for report_file in per_doc.glob("*.json"):
            stem = report_file.stem
            data = _load_json(report_file)
            if data and "overall" in data:
                index[stem] = data
    return index


# Cached report index (rebuilt on first access per process)
_report_index_cache: Optional[Dict[str, Dict[str, Any]]] = None
_report_index_ts: float = 0.0


def _get_report_index() -> Dict[str, Dict[str, Any]]:
    """Get the cached report index, rebuilding if stale (>60s)."""
    global _report_index_cache, _report_index_ts
    import time

    now = time.time()
    if _report_index_cache is None or (now - _report_index_ts) > 60:
        _report_index_cache = _build_report_index()
        _report_index_ts = now
    return _report_index_cache


def _get_report_for_stem(stem: str) -> Optional[Dict[str, Any]]:
    """Get the latest review report for a stem."""
    return _get_report_index().get(stem)


# --- Endpoints ---


@app.get("/api/runs")
def list_runs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    blacklisted_only: bool = Query(False),
    verdict: Optional[List[str]] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=1),
    max_score: Optional[float] = Query(None, ge=0, le=1),
    sort_by: str = Query("stem", regex="^(stem|score|verdict|domain)$"),
    sort_desc: bool = Query(False),
) -> Dict[str, Any]:
    """List available extraction runs with summary metadata.

    Supports filtering by verdict (PASS/WARN/FAIL) and score range.
    """
    blacklist = _load_blacklist()
    report_index = _get_report_index()
    runs: List[RunSummary] = []

    for runs_dir in (EXTRACTED_RUNS_NVME, EXTRACTED_RUNS_HDD):
        if not runs_dir.is_dir():
            continue
        for entry in sorted(runs_dir.iterdir(), key=lambda p: p.name):
            target = entry.resolve() if entry.is_symlink() else entry
            if not target.is_dir():
                continue
            # Extract stem (everything before the last _hash)
            parts = entry.name.rsplit("_", 1)
            stem = parts[0] if len(parts) > 1 else entry.name

            is_bl = stem in blacklist
            if blacklisted_only and not is_bl:
                continue

            # Quick check for stage outputs
            has_blocks = (target / "02_marker_extractor" / "json_output" / "02_marker_blocks.json").exists()
            has_tables = (target / "05_table_extractor" / "json_output" / "05_tables.json").exists()
            has_figures = (target / "06_figure_extractor" / "json_output" / "06_figures.json").exists()

            # Profile info
            profile = _load_json(target / "00_profile_detector" / "profile.json")
            page_count = profile.get("page_count") if profile else None
            domain = profile.get("domain") if profile else None
            route = profile.get("route") if profile else None

            # Find original PDF
            pdf_file = profile.get("file") if profile else None

            # Attach review scores if available
            report = report_index.get(stem)
            run_verdict = None
            run_score = None
            run_grade = None
            if report:
                overall = report.get("overall", {})
                run_verdict = overall.get("verdict")
                run_score = overall.get("score")
                run_grade = overall.get("grade")

            # Apply verdict filter
            if verdict:
                upper_verdicts = [v.upper() for v in verdict]
                if run_verdict not in upper_verdicts:
                    continue

            # Apply score range filter
            if min_score is not None and (run_score is None or run_score < min_score):
                continue
            if max_score is not None and (run_score is None or run_score > max_score):
                continue

            runs.append(RunSummary(
                stem=stem,
                run_dir=str(target),
                pdf_path=pdf_file,
                page_count=page_count,
                has_blocks=has_blocks,
                has_tables=has_tables,
                has_figures=has_figures,
                is_blacklisted=is_bl,
                profile_domain=domain,
                profile_route=route,
                verdict=run_verdict,
                overall_score=run_score,
                grade=run_grade,
            ))

    # Deduplicate by stem (NVMe takes priority)
    seen: set[str] = set()
    deduped: List[RunSummary] = []
    for r in runs:
        if r.stem not in seen:
            seen.add(r.stem)
            deduped.append(r)

    # Sort
    sort_keys = {
        "stem": lambda r: r.stem,
        "score": lambda r: r.overall_score if r.overall_score is not None else -1,
        "verdict": lambda r: {"FAIL": 0, "WARN": 1, "PASS": 2}.get(r.verdict or "", 3),
        "domain": lambda r: r.profile_domain or "",
    }
    deduped.sort(key=sort_keys.get(sort_by, sort_keys["stem"]), reverse=sort_desc)

    total = len(deduped)
    page = deduped[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "runs": [r.model_dump() for r in page]}


@app.get("/api/runs/{stem}/scores")
def get_run_scores(stem: str) -> Dict[str, Any]:
    """Get review-pdf quality scores and verdict for a run."""
    report = _get_report_for_stem(stem)
    if report is None:
        raise HTTPException(404, f"No review report found for stem: {stem}")
    return {
        "stem": stem,
        "overall": report.get("overall", {}),
        "dimensions": report.get("dimensions", {}),
        "issues": report.get("issues", []),
        "domain": report.get("domain"),
        "timestamp": report.get("timestamp"),
    }


@app.get("/api/runs/{stem}/annotations")
def get_run_annotations(
    stem: str,
    include_blocks: bool = Query(True),
    include_tables: bool = Query(True),
    include_figures: bool = Query(True),
    headers_only: bool = Query(False),
) -> Dict[str, Any]:
    """Load annotations from a run directory as tabbed-compatible boxes."""
    run_dir = _find_run_dir(stem)
    if run_dir is None:
        raise HTTPException(404, f"No run directory found for stem: {stem}")

    # Find original PDF for page dimensions
    profile = _load_json(run_dir / "00_profile_detector" / "profile.json")
    pdf_path_str = profile.get("file") if profile else None
    pdf_path = Path(pdf_path_str) if pdf_path_str else _find_pdf_for_stem(stem)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(404, f"Original PDF not found for stem: {stem}")

    page_dims = _get_page_dims(pdf_path)

    all_boxes: List[Dict[int, List[Box]]] = []

    # S02 blocks
    if include_blocks:
        blocks_json = _load_json(
            run_dir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
        )
        if blocks_json and isinstance(blocks_json.get("blocks"), list):
            blocks = blocks_json["blocks"]
            if headers_only:
                blocks = [b for b in blocks if b.get("is_header") or "header" in (b.get("block_type") or "").lower()]
            all_boxes.append(_blocks_to_boxes(blocks, page_dims))

    # S05 tables
    if include_tables:
        tables_json = _load_json(
            run_dir / "05_table_extractor" / "json_output" / "05_tables.json"
        )
        if tables_json and isinstance(tables_json.get("tables"), list):
            all_boxes.append(_tables_to_boxes(tables_json["tables"], page_dims))

    # S06 figures
    if include_figures:
        figures_json = _load_json(
            run_dir / "06_figure_extractor" / "json_output" / "06_figures.json"
        )
        if figures_json and isinstance(figures_json.get("figures"), list):
            all_boxes.append(_figures_to_boxes(figures_json["figures"], page_dims))

    merged = _merge_boxes(*all_boxes)

    # Count by type
    type_counts: Dict[str, int] = {}
    for page_boxes in merged.values():
        for box in page_boxes:
            type_counts[box.type] = type_counts.get(box.type, 0) + 1

    # Collect agent notes about extraction issues
    agent_notes = _collect_agent_notes(run_dir, stem)

    return {
        "stem": stem,
        "pdf_path": str(pdf_path),
        "page_count": len(page_dims),
        "page_dims": [{"width": w, "height": h} for w, h in page_dims],
        "type_counts": type_counts,
        "boxes_by_page": {
            str(page): [b.model_dump() for b in boxes]
            for page, boxes in sorted(merged.items())
        },
        "agent_notes": [n.model_dump() for n in agent_notes],
    }


@app.get("/api/runs/{stem}/notes")
def get_agent_notes(stem: str) -> Dict[str, Any]:
    """Get agent diagnostic notes for a run."""
    run_dir = _find_run_dir(stem)
    if run_dir is None:
        raise HTTPException(404, f"No run directory found for stem: {stem}")
    notes = _collect_agent_notes(run_dir, stem)
    return {
        "stem": stem,
        "notes": [n.model_dump() for n in notes],
        "error_count": sum(1 for n in notes if n.severity == "error"),
        "warning_count": sum(1 for n in notes if n.severity == "warning"),
    }


@app.get("/api/runs/{stem}/pdf")
def get_run_pdf(stem: str):
    """Serve the original PDF for rendering in the UI."""
    run_dir = _find_run_dir(stem)
    if run_dir is None:
        raise HTTPException(404, f"No run directory found for stem: {stem}")

    profile = _load_json(run_dir / "00_profile_detector" / "profile.json")
    pdf_path_str = profile.get("file") if profile else None
    pdf_path = Path(pdf_path_str) if pdf_path_str else _find_pdf_for_stem(stem)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(404, f"PDF not found for stem: {stem}")

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        headers={"Access-Control-Expose-Headers": "Content-Length"},
    )


@app.get("/api/runs/{stem}/page/{page_num}/png")
def get_page_png(stem: str, page_num: int, dpi: int = Query(144, ge=72, le=300)):
    """Render a single page as PNG for thumbnail/preview."""
    run_dir = _find_run_dir(stem)
    if run_dir is None:
        raise HTTPException(404, f"No run found for: {stem}")

    profile = _load_json(run_dir / "00_profile_detector" / "profile.json")
    pdf_path_str = profile.get("file") if profile else None
    pdf_path = Path(pdf_path_str) if pdf_path_str else _find_pdf_for_stem(stem)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(404, "PDF not found")

    doc = fitz.open(str(pdf_path))
    idx = page_num - 1
    if idx < 0 or idx >= len(doc):
        doc.close()
        raise HTTPException(404, f"Page {page_num} out of range")

    pix = doc[idx].get_pixmap(dpi=dpi)
    png_bytes = pix.tobytes("png")
    doc.close()

    return StreamingResponse(
        iter([png_bytes]),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.post("/api/runs/{stem}/corrections")
def save_corrections(stem: str, entry: CorrectionEntry) -> Dict[str, str]:
    """Save human corrections for a run. Appends to per-stem JSONL."""
    corrections_file = CORRECTIONS_DIR / f"{stem}_corrections.jsonl"
    record = {
        **entry.model_dump(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "boxes": [b.model_dump() for b in entry.boxes],
    }
    with open(corrections_file, "a") as f:
        f.write(json.dumps(record) + "\n")
    return {"status": "saved", "file": str(corrections_file)}


@app.get("/api/runs/{stem}/corrections")
def get_corrections(stem: str) -> Dict[str, Any]:
    """Load all saved corrections for a run."""
    corrections_file = CORRECTIONS_DIR / f"{stem}_corrections.jsonl"
    if not corrections_file.exists():
        return {"stem": stem, "corrections": []}
    corrections = []
    for line in corrections_file.read_text().strip().split("\n"):
        if line.strip():
            try:
                corrections.append(json.loads(line))
            except Exception:
                pass
    return {"stem": stem, "corrections": corrections}


class BulkActionRequest(BaseModel):
    stems: List[str]
    action: str  # "blacklist", "dismiss", "reextract"
    reason: str = ""


@app.post("/api/runs/bulk-action")
def bulk_action(req: BulkActionRequest) -> Dict[str, Any]:
    """Apply a bulk action to multiple stems."""
    results: Dict[str, str] = {}

    if req.action == "blacklist":
        # Append each stem to blacklist JSONL
        BLACKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BLACKLIST_PATH, "a") as f:
            for stem in req.stems:
                entry = {
                    "stem": stem,
                    "reason": req.reason or "Manual blacklist from quarantine UI",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                f.write(json.dumps(entry) + "\n")
                results[stem] = "blacklisted"

    elif req.action == "dismiss":
        # Write a correction entry marking the stem as dismissed/acknowledged
        CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
        for stem in req.stems:
            corrections_file = CORRECTIONS_DIR / f"{stem}_corrections.jsonl"
            record = {
                "stem": stem,
                "action": "dismiss",
                "reason": req.reason or "Dismissed from quarantine UI",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(corrections_file, "a") as f:
                f.write(json.dumps(record) + "\n")
            results[stem] = "dismissed"

    elif req.action == "reextract":
        # Write a re-extraction request that the supervisor can pick up
        reextract_dir = STATE_DIR / "reextract_requests"
        reextract_dir.mkdir(parents=True, exist_ok=True)
        for stem in req.stems:
            request_file = reextract_dir / f"{stem}.json"
            request_file.write_text(json.dumps({
                "stem": stem,
                "reason": req.reason or "Re-extraction requested from quarantine UI",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
            results[stem] = "reextract_requested"

    else:
        raise HTTPException(400, f"Unknown action: {req.action}")

    return {"action": req.action, "count": len(req.stems), "results": results}


@app.get("/api/health")
def health():
    """Health check."""
    nvme_ok = EXTRACTED_RUNS_NVME.is_dir()
    hdd_ok = EXTRACTED_RUNS_HDD.is_dir()
    return {
        "status": "ok" if (nvme_ok or hdd_ok) else "degraded",
        "nvme_available": nvme_ok,
        "hdd_available": hdd_ok,
        "corrections_dir": str(CORRECTIONS_DIR),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003, log_level="info")
