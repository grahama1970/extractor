#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi>=0.115.0",
#   "uvicorn>=0.32.0",
#   "pydantic>=2.4.0",
#   "pdf_oxide>=0.3.14",
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
from pydantic import BaseModel

from pdf_oxide import PdfDocument

from review_helpers import (
    AgentNote,
    Box,
    BulkActionRequest,
    CorrectionEntry,
    RunSummary,
    blocks_to_boxes,
    collect_agent_notes,
    figures_to_boxes,
    merge_boxes,
    tables_to_boxes,
)

app = FastAPI(title="PDF Review Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PI_SKILLS_ROOT = Path(
    os.environ.get("PI_SKILLS_ROOT", Path.home() / "workspace/experiments/pi-mono/.pi/skills")
)

# Mount agent endpoint router for 5ft voice canvas
try:
    from agent_endpoint import router as agent_router, flush_all_sessions_sync
    app.include_router(agent_router)

    @app.on_event("shutdown")
    async def _flush_canvas_sessions():
        """Flush all active canvas sessions to disk on server shutdown."""
        flushed = flush_all_sessions_sync()
        if flushed:
            print(f"[shutdown] Flushed {flushed} canvas sessions to disk")
except ImportError:
    pass  # agent_endpoint.py not available

# Run directory locations
EXTRACTED_RUNS_NVME = Path(
    os.environ.get(
        "EXTRACTED_RUNS_NVME",
        PI_SKILLS_ROOT / "review-pdf/extracted_runs_staging",
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
        PI_SKILLS_ROOT / "learn-datalake/state/corrections",
    )
)
CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)

SHADOW_DIR = Path(
    os.environ.get(
        "SHADOW_DIR",
        PI_SKILLS_ROOT / "learn-datalake/state/shadow",
    )
)

BLACKLIST_PATH = Path(
    os.environ.get(
        "BLACKLIST_PATH",
        PI_SKILLS_ROOT / "learn-datalake/state/failed_pdf_blacklist.jsonl",
    )
)
STATE_DIR = Path(
    os.environ.get(
        "STATE_DIR",
        PI_SKILLS_ROOT / "learn-datalake/state",
    )
)
REPORTS_DIR = Path(
    os.environ.get(
        "REPORTS_DIR",
        PI_SKILLS_ROOT / "review-pdf/reports",
    )
)


# --- Helpers ---


def _append_shadow(filename: str, record: dict) -> None:
    """Append a JSON line to SHADOW_DIR / filename for training signal collection.

    Never raises — shadow logging must not crash the endpoint.
    """
    try:
        SHADOW_DIR.mkdir(parents=True, exist_ok=True)
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(SHADOW_DIR / filename, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def _find_run_dir(pdf_stem: str) -> Optional[Path]:
    """Find run directory by PDF filename stem (checks NVMe then HDD)."""
    for runs_dir in (EXTRACTED_RUNS_NVME, EXTRACTED_RUNS_HDD):
        if not runs_dir.is_dir():
            continue
        for entry in runs_dir.iterdir():
            if entry.name.startswith(pdf_stem):
                target = entry.resolve() if entry.is_symlink() else entry
                if target.is_dir():
                    return target
    return None


def _find_pdf_by_filename(pdf_stem: str) -> Optional[Path]:
    """Find the original PDF in the corpus by filename stem."""
    for pdf in CORPUS_ROOT.rglob(f"{pdf_stem}.pdf"):
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
    """Load blacklisted PDF filename stems."""
    if not BLACKLIST_PATH.exists():
        return set()
    entries: set[str] = set()
    for line in BLACKLIST_PATH.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            entries.add(entry.get("stem", ""))
        except Exception:
            pass
    return entries


def _get_page_dims(pdf_path: Path) -> List[tuple[float, float]]:
    """Get (width, height) for each page."""
    doc = PdfDocument(str(pdf_path))
    return [doc.page_dimensions(i) for i in range(doc.page_count())]


def _build_report_index() -> Dict[str, Dict[str, Any]]:
    """Build an index of filename stem to latest report from all report directories.

    Scans REPORTS_DIR for per_doc JSON files. For each entry, keeps the
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
            name = report_file.stem
            data = _load_json(report_file)
            if data and "overall" in data:
                index[name] = data
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


def _get_report(pdf_stem: str) -> Optional[Dict[str, Any]]:
    """Get the latest review report for a PDF filename stem."""
    return _get_report_index().get(pdf_stem)


def _collect_notes(run_dir: Path, pdf_stem: str) -> List[AgentNote]:
    """Delegate to review_helpers.collect_agent_notes with server-level config."""
    return collect_agent_notes(
        run_dir,
        pdf_stem,
        load_json_fn=_load_json,
        load_blacklist_fn=_load_blacklist,
        blacklist_path=BLACKLIST_PATH,
    )


# --- Cached Runs Index (avoids re-scanning 12K+ dirs on every request) ---

import threading

_runs_cache: Optional[List[RunSummary]] = None
_runs_cache_ts: float = 0.0
_runs_cache_lock = threading.Lock()
_RUNS_CACHE_TTL = 300  # 5 minutes


def _build_one_run(entry_path: str, entry_name: str, blacklist: set, report_index: dict) -> Optional[RunSummary]:
    """Build a RunSummary for one directory. Designed for thread pool use."""
    try:
        target = os.path.realpath(entry_path) if os.path.islink(entry_path) else entry_path
        if not os.path.isdir(target):
            return None
        parts = entry_name.rsplit("_", 1)
        pdf_stem = parts[0] if len(parts) > 1 else entry_name

        has_blocks = os.path.exists(os.path.join(target, "02_marker_extractor", "json_output", "02_marker_blocks.json"))
        has_tables = os.path.exists(os.path.join(target, "05_table_extractor", "json_output", "05_tables.json"))
        has_figures = os.path.exists(os.path.join(target, "06_figure_extractor", "json_output", "06_figures.json"))

        profile = _load_json(Path(target) / "00_profile_detector" / "profile.json")
        page_count = profile.get("page_count") if profile else None
        domain = profile.get("domain") if profile else None
        route = profile.get("route") if profile else None
        pdf_file = profile.get("file") if profile else None

        report = report_index.get(pdf_stem)
        run_verdict = run_score = run_grade = None
        if report:
            overall = report.get("overall", {})
            run_verdict = overall.get("verdict")
            run_score = overall.get("score")
            run_grade = overall.get("grade")

        return RunSummary(
            stem=pdf_stem,
            run_dir=target,
            pdf_path=pdf_file,
            page_count=page_count,
            has_blocks=has_blocks,
            has_tables=has_tables,
            has_figures=has_figures,
            is_blacklisted=pdf_stem in blacklist,
            profile_domain=domain,
            profile_route=route,
            verdict=run_verdict,
            overall_score=run_score,
            grade=run_grade,
        )
    except Exception:
        return None


def _build_runs_cache() -> List[RunSummary]:
    """Scan all run directories and build the full runs list. Uses thread pool for HDD I/O."""
    import time as _t
    from concurrent.futures import ThreadPoolExecutor
    t0 = _t.time()
    blacklist = _load_blacklist()
    report_index = _get_report_index()
    runs: List[RunSummary] = []

    for runs_dir in (EXTRACTED_RUNS_NVME, EXTRACTED_RUNS_HDD):
        if not runs_dir.is_dir():
            continue
        # Collect entries first (fast — just readdir, no stat)
        entries = []
        try:
            for de in os.scandir(str(runs_dir)):
                entries.append((de.path, de.name))
        except OSError:
            continue
        entries.sort(key=lambda x: x[1])

        dir_t0 = _t.time()
        print(f"[runs-cache] Scanning {len(entries)} entries in {runs_dir.name}...", flush=True)

        # Use thread pool for parallel I/O (HDD benefits from 8-16 threads for stat/read)
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(_build_one_run, path, name, blacklist, report_index) for path, name in entries]
            for i, f in enumerate(futures):
                result = f.result()
                if result is not None:
                    runs.append(result)
                if (i + 1) % 2000 == 0:
                    print(f"[runs-cache]   ...processed {i+1}/{len(entries)} ({_t.time() - dir_t0:.1f}s)", flush=True)

        print(f"[runs-cache] {runs_dir.name}: {len(runs)} runs in {_t.time() - dir_t0:.1f}s", flush=True)

    # Deduplicate by filename stem (NVMe takes priority)
    seen: set[str] = set()
    deduped: List[RunSummary] = []
    for r in runs:
        if r.stem not in seen:
            seen.add(r.stem)
            deduped.append(r)

    elapsed = _t.time() - t0
    print(f"[runs-cache] Built index of {len(deduped)} runs in {elapsed:.1f}s", flush=True)
    return deduped


def _get_runs_cache() -> List[RunSummary]:
    """Get cached runs list, rebuilding in background if stale."""
    global _runs_cache, _runs_cache_ts
    import time as _t

    now = _t.time()
    with _runs_cache_lock:
        if _runs_cache is not None and (now - _runs_cache_ts) < _RUNS_CACHE_TTL:
            return _runs_cache

    # Build synchronously on first call, then cache
    if _runs_cache is None:
        runs = _build_runs_cache()
        with _runs_cache_lock:
            _runs_cache = runs
            _runs_cache_ts = _t.time()
        return runs

    # Stale cache: return stale data, refresh in background
    def _refresh():
        global _runs_cache, _runs_cache_ts
        runs = _build_runs_cache()
        with _runs_cache_lock:
            _runs_cache = runs
            _runs_cache_ts = _t.time()

    threading.Thread(target=_refresh, daemon=True).start()
    return _runs_cache


# Start building the cache in a background thread on startup
def _warmup_cache():
    """Pre-build runs cache so first request is fast."""
    global _runs_cache, _runs_cache_ts
    import time as _t
    print("[runs-cache] Starting background cache warmup...")
    runs = _build_runs_cache()
    with _runs_cache_lock:
        _runs_cache = runs
        _runs_cache_ts = _t.time()
    print(f"[runs-cache] Warmup complete: {len(runs)} runs indexed", flush=True)

threading.Thread(target=_warmup_cache, daemon=True).start()


# --- Endpoints ---


@app.get("/api/runs")
def list_runs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    blacklisted_only: bool = Query(False),
    verdict: Optional[List[str]] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=1),
    max_score: Optional[float] = Query(None, ge=0, le=1),
    sort_by: str = Query("stem", pattern="^(stem|score|verdict|domain)$"),
    sort_desc: bool = Query(False),
) -> Dict[str, Any]:
    """List available extraction runs with summary metadata.

    Uses a pre-built cache (warmed up on startup) to avoid scanning 12K+ dirs per request.
    Supports filtering by verdict (PASS/WARN/FAIL) and score range.
    """
    all_runs = _get_runs_cache()

    # Apply filters
    filtered: List[RunSummary] = []
    for r in all_runs:
        if blacklisted_only and not r.is_blacklisted:
            continue
        if verdict:
            upper_verdicts = [v.upper() for v in verdict]
            if r.verdict not in upper_verdicts:
                continue
        if min_score is not None and (r.overall_score is None or r.overall_score < min_score):
            continue
        if max_score is not None and (r.overall_score is None or r.overall_score > max_score):
            continue
        filtered.append(r)

    # Sort
    sort_keys = {
        "stem": lambda r: r.stem,
        "score": lambda r: r.overall_score if r.overall_score is not None else -1,
        "verdict": lambda r: {"FAIL": 0, "WARN": 1, "PASS": 2}.get(r.verdict or "", 3),
        "domain": lambda r: r.profile_domain or "",
    }
    filtered.sort(key=sort_keys.get(sort_by, sort_keys["stem"]), reverse=sort_desc)

    total = len(filtered)
    page = filtered[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "runs": [r.model_dump() for r in page]}


@app.get("/api/runs/{pdf_stem}/scores")
def get_run_scores(pdf_stem: str) -> Dict[str, Any]:
    """Get review-pdf quality scores and verdict for a run."""
    report = _get_report(pdf_stem)
    if report is None:
        raise HTTPException(404, f"No review report found for: {pdf_stem}")
    return {
        "stem": pdf_stem,
        "overall": report.get("overall", {}),
        "dimensions": report.get("dimensions", {}),
        "issues": report.get("issues", []),
        "domain": report.get("domain"),
        "timestamp": report.get("timestamp"),
    }


@app.get("/api/runs/{pdf_stem}/annotations")
def get_run_annotations(
    pdf_stem: str,
    include_blocks: bool = Query(True),
    include_tables: bool = Query(True),
    include_figures: bool = Query(True),
    headers_only: bool = Query(False),
) -> Dict[str, Any]:
    """Load annotations from a run directory as tabbed-compatible boxes."""
    run_dir = _find_run_dir(pdf_stem)
    if run_dir is None:
        raise HTTPException(404, f"No run directory found for: {pdf_stem}")

    # Find original PDF for page dimensions
    profile = _load_json(run_dir / "00_profile_detector" / "profile.json")
    pdf_path_str = profile.get("file") if profile else None
    pdf_path = Path(pdf_path_str) if pdf_path_str else _find_pdf_by_filename(pdf_stem)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(404, f"Original PDF not found for: {pdf_stem}")

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
            all_boxes.append(blocks_to_boxes(blocks, page_dims))

    # S05 tables
    if include_tables:
        tables_json = _load_json(
            run_dir / "05_table_extractor" / "json_output" / "05_tables.json"
        )
        if tables_json and isinstance(tables_json.get("tables"), list):
            all_boxes.append(tables_to_boxes(tables_json["tables"], page_dims))

    # S06 figures
    if include_figures:
        figures_json = _load_json(
            run_dir / "06_figure_extractor" / "json_output" / "06_figures.json"
        )
        if figures_json and isinstance(figures_json.get("figures"), list):
            all_boxes.append(figures_to_boxes(figures_json["figures"], page_dims))

    merged = merge_boxes(*all_boxes)

    # Count by type
    type_counts: Dict[str, int] = {}
    for page_boxes in merged.values():
        for box in page_boxes:
            type_counts[box.type] = type_counts.get(box.type, 0) + 1

    # Collect agent notes about extraction issues
    agent_notes = _collect_notes(run_dir, pdf_stem)

    return {
        "stem": pdf_stem,
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


@app.get("/api/runs/{pdf_stem}/notes")
def get_agent_notes(pdf_stem: str) -> Dict[str, Any]:
    """Get agent diagnostic notes for a run."""
    run_dir = _find_run_dir(pdf_stem)
    if run_dir is None:
        raise HTTPException(404, f"No run directory found for: {pdf_stem}")
    notes = _collect_notes(run_dir, pdf_stem)
    return {
        "stem": pdf_stem,
        "notes": [n.model_dump() for n in notes],
        "error_count": sum(1 for n in notes if n.severity == "error"),
        "warning_count": sum(1 for n in notes if n.severity == "warning"),
    }


@app.get("/api/runs/{pdf_stem}/pdf")
def get_run_pdf(pdf_stem: str):
    """Serve the original PDF for rendering in the UI."""
    run_dir = _find_run_dir(pdf_stem)
    if run_dir is None:
        raise HTTPException(404, f"No run directory found for: {pdf_stem}")

    profile = _load_json(run_dir / "00_profile_detector" / "profile.json")
    pdf_path_str = profile.get("file") if profile else None
    pdf_path = Path(pdf_path_str) if pdf_path_str else _find_pdf_by_filename(pdf_stem)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(404, f"PDF not found for: {pdf_stem}")

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        headers={"Access-Control-Expose-Headers": "Content-Length"},
    )


@app.get("/api/runs/{pdf_stem}/page/{page_num}/png")
def get_page_png(pdf_stem: str, page_num: int, dpi: int = Query(144, ge=72, le=300)):
    """Render a single page as PNG for thumbnail/preview."""
    run_dir = _find_run_dir(pdf_stem)
    if run_dir is None:
        raise HTTPException(404, f"No run found for: {pdf_stem}")

    profile = _load_json(run_dir / "00_profile_detector" / "profile.json")
    pdf_path_str = profile.get("file") if profile else None
    pdf_path = Path(pdf_path_str) if pdf_path_str else _find_pdf_by_filename(pdf_stem)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(404, "PDF not found")

    doc = PdfDocument(str(pdf_path))
    idx = page_num - 1
    if idx < 0 or idx >= doc.page_count():
        raise HTTPException(404, f"Page {page_num} out of range")

    png_bytes = doc.render_page(idx, dpi=dpi)

    return StreamingResponse(
        iter([png_bytes]),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.post("/api/runs/{pdf_stem}/corrections")
def save_corrections(pdf_stem: str, entry: CorrectionEntry) -> Dict[str, str]:
    """Save human corrections for a run. Appends to per-document JSONL.

    When changes are provided, also writes a reextract request so the
    re-extraction agent picks up the human-edited bboxes.
    """
    corrections_file = CORRECTIONS_DIR / f"{pdf_stem}_corrections.jsonl"
    record = {
        **entry.model_dump(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "boxes": [b.model_dump() for b in entry.boxes],
    }
    if entry.changes:
        record["changes"] = [c.model_dump() for c in entry.changes]
    with open(corrections_file, "a") as f:
        f.write(json.dumps(record) + "\n")

    _append_shadow("corrections.jsonl", {
        "stem": pdf_stem,
        "page": entry.page,
        "changes": [c.model_dump() for c in entry.changes] if entry.changes else [],
        "human_id": entry.reviewer or "reviewer",
        "action": "correction",
    })

    # Auto-trigger re-extraction when human edits are present
    if entry.changes:
        reextract_dir = STATE_DIR / "reextract_requests"
        reextract_dir.mkdir(parents=True, exist_ok=True)
        request_file = reextract_dir / f"{pdf_stem}.json"
        request_file.write_text(json.dumps({
            "stem": pdf_stem,
            "reason": "Human bbox corrections applied",
            "change_count": len(entry.changes),
            "change_summary": {
                "added": sum(1 for c in entry.changes if c.action == "added"),
                "modified": sum(1 for c in entry.changes if c.action == "modified"),
                "deleted": sum(1 for c in entry.changes if c.action == "deleted"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    return {"status": "saved", "file": str(corrections_file)}


@app.get("/api/runs/{pdf_stem}/corrections")
def get_corrections(pdf_stem: str) -> Dict[str, Any]:
    """Load all saved corrections for a run."""
    corrections_file = CORRECTIONS_DIR / f"{pdf_stem}_corrections.jsonl"
    if not corrections_file.exists():
        return {"stem": pdf_stem, "corrections": []}
    corrections = []
    for line in corrections_file.read_text().strip().split("\n"):
        if line.strip():
            try:
                corrections.append(json.loads(line))
            except Exception:
                pass
    return {"stem": pdf_stem, "corrections": corrections}


@app.post("/api/runs/bulk-action")
def bulk_action(req: BulkActionRequest) -> Dict[str, Any]:
    """Apply a bulk action to multiple PDF filename stems."""
    results: Dict[str, str] = {}

    if req.action == "blacklist":
        BLACKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BLACKLIST_PATH, "a") as f:
            for name in req.stems:
                entry = {
                    "stem": name,
                    "reason": req.reason or "Manual blacklist from quarantine UI",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                f.write(json.dumps(entry) + "\n")
                results[name] = "blacklisted"

    elif req.action == "dismiss":
        CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
        for name in req.stems:
            corrections_file = CORRECTIONS_DIR / f"{name}_corrections.jsonl"
            record = {
                "stem": name,
                "action": "dismiss",
                "reason": req.reason or "Dismissed from quarantine UI",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(corrections_file, "a") as f:
                f.write(json.dumps(record) + "\n")
            results[name] = "dismissed"

    elif req.action == "reextract":
        reextract_dir = STATE_DIR / "reextract_requests"
        reextract_dir.mkdir(parents=True, exist_ok=True)
        for name in req.stems:
            request_file = reextract_dir / f"{name}.json"
            request_file.write_text(json.dumps({
                "stem": name,
                "reason": req.reason or "Re-extraction requested from quarantine UI",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
            results[name] = "reextract_requested"

    else:
        raise HTTPException(400, f"Unknown action: {req.action}")

    return {"action": req.action, "count": len(req.stems), "results": results}


class ReviewVerdict(BaseModel):
    """A human review verdict (approve or flag) for a PDF."""
    verdict: str  # "approve" or "flag"
    notes: str = ""
    reviewer: str = ""


@app.post("/api/runs/{pdf_stem}/review")
def submit_review(pdf_stem: str, req: ReviewVerdict) -> Dict[str, str]:
    """Record a human approve/flag verdict for a run."""
    _append_shadow("reviews.jsonl", {
        "stem": pdf_stem,
        "verdict": req.verdict,
        "notes": req.notes,
        "reviewer": req.reviewer or "reviewer",
        "action": "review",
    })
    return {"status": "recorded", "stem": pdf_stem, "verdict": req.verdict}


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
