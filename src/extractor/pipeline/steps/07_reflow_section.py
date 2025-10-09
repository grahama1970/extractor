#!/usr/bin/env python3
"""
Stage 07 — Reflow Section (Summary‑Only Baseline)

Deterministic, offline writer that normalizes Stage‑04/05/06 outputs into
{ reflowed_sections: [...] } for downstream Stage‑07r mining. No LLM/VLM here.
"""

from __future__ import annotations
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger
from rich.console import Console

console = Console()
app = typer.Typer(add_completion=False)

STAGE07_DEBUG = os.getenv("STAGE07_DEBUG", "").lower() in {"1","true","yes","y"}
SUMMARY_ONLY_ENV = os.getenv("SUMMARY_ONLY07", "").lower() in {"1","true","yes","y"}


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _normalize_sections(s04: Dict[str, Any]) -> List[Dict[str, Any]]:
    sections = s04.get("sections") or []
    if not isinstance(sections, list):
        return []
    out: List[Dict[str, Any]] = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        sid = s.get("id") or s.get("section_id") or None
        if not sid:
            continue
        title = s.get("title") or s.get("display_title") or "Untitled"
        blocks = []
        for b in s.get("blocks") or []:
            if not isinstance(b, dict):
                continue
            txt = (b.get("text") or b.get("content") or "").strip()
            if not txt:
                continue
            blocks.append({
                "type": "paragraph",
                "text": txt,
                "page": b.get("page", b.get("page_idx")),
                "bbox": b.get("bbox"),
                "id": b.get("id") or b.get("block_id"),
            })
        out.append({
            "id": sid,
            "title": title,
            "blocks": blocks,
            "tables": s.get("tables", []),
            "figures": s.get("figures", []),
            "reflowed_text": (s.get("merged_text") or s.get("raw_text") or ""),
            "reflowed_json": {
                "section_id": sid,
                "title": title,
                "blocks": ([{"type": "paragraph", "text": (s.get("merged_text") or s.get("raw_text") or "")[:4000]}]
                           if (s.get("merged_text") or s.get("raw_text")) else [])
            },
            "ocr_corrections": {},
            "improvements_made": "summary-only (no LLM)",
            "reflow_status": "summary_only",
        })
    return out


@app.command()
def run(
    sections: Path = typer.Option(..., "--sections", exists=True, help="Path to 04_sections.json"),
    tables: Path = typer.Option(..., "--tables", exists=True, help="Path to 05_tables.json"),
    figures: Path = typer.Option(..., "--figures", exists=True, help="Path to 06_figures.json"),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o", help="Results root directory"),
    timeout: int = typer.Option(120, "--timeout"),
    summary_only: bool = typer.Option(False, "--summary-only", help="Force summary-only output"),
):
    if os.getenv("STAGE07_SHIM_WARN", "1").lower() in {"1","true","yes","y"}:
        console.print("[yellow][deprecated] 07_reflow_section shim – prefer 07_orchestrator.py.[/yellow]")
    console.print("[bold green]Starting Section Reflow (Stage 07)[/bold green]")
    if SUMMARY_ONLY_ENV:
        summary_only = True

    stage_dir = output_dir / "07_reflow_section"
    out_dir = stage_dir / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        logger.remove()
        logger.add(str(stage_dir / "stage_07_reflow.log"), level="INFO")
    except Exception:
        pass

    s04 = _read_json(sections)
    s05 = _read_json(tables)
    s06 = _read_json(figures)

    # Minimal normalization (pass-through tables/figures later if available per section)
    processed = _normalize_sections(s04)

    # Opportunistic: if Stage 05 provided tables with section_id, attach to matching section
    try:
        tlist = s05.get("tables") or []
        if isinstance(tlist, list) and tlist:
            by_sid: Dict[str, List[Dict[str, Any]]] = {}
            for t in tlist:
                sid = t.get("section_id")
                if not sid:
                    continue
                by_sid.setdefault(str(sid), []).append(t)
            if by_sid:
                for sec in processed:
                    sec["tables"] = sec.get("tables", []) + by_sid.get(str(sec.get("id")), [])
    except Exception:
        pass

    # Figures are not used by 07r, but include pass-through if present later
    # (No extra merging here)

    # Deterministic hash for quick diffs
    det_hash = None
    try:
        h = hashlib.sha256()
        for ps in processed:
            h.update(f"{ps.get('id','')}:{(ps.get('reflowed_text') or '')[:64]}".encode("utf-8","ignore"))
        det_hash = h.hexdigest()
    except Exception:
        det_hash = None

    payload = {
        "timestamp": datetime.now().isoformat(),
        "status": "Completed",
        "section_count": len(processed),
        "reflowed_sections": processed,
    }
    if det_hash:
        payload["deterministic_hash"] = det_hash

    out_path = out_dir / "07_reflowed.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    console.print(f"✅ Wrote reflow output → {out_path}")


if __name__ == "__main__":
    app()
