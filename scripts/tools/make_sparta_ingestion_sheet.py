#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.16.0",
#   "pandas>=2.0.0",
#   "openpyxl>=3.1.0",
# ]
# ///

"""
Generate a Sparta-style ingestion Excel for visual collaboration.

Scans pipeline results directories and emits a single Excel workbook with one row
per run/document and key stage metrics (sections, tables, figures, etc.).

Usage:
  uv run scripts/tools/make_sparta_ingestion_sheet.py \
    --results-root data/results \
    --out scripts/artifacts/sparta_ingestion.xlsx
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import typer


app = typer.Typer(add_completion=False)


def _read_json(p: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_list(obj: Dict[str, Any] | None, key: str) -> int:
    try:
        v = obj.get(key)
        return len(v or [])
    except Exception:
        return 0


def _find_first(path: Path, rel: str) -> Optional[Path]:
    p = path / rel
    return p if p.exists() else None


def _stat_or_none(p: Path) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime)
    except Exception:
        return None


def _collect_row(run_dir: Path) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "run_dir": str(run_dir),
        "doc_id": None,
        "pdf_path": None,
        "stage01_clean_pdf": None,
        "stage02_blocks": None,
        "stage03_verified": None,
        "stage04_sections": None,
        "stage05_tables": None,
        "stage06_figures": None,
        "stage06b_sketch": None,
        "stage07_reflow": None,
        "stage07_requirements": None,
        "stage08_proved": None,
        "stage09_summaries": None,
        "last_updated": None,
        "notes": "",
    }

    # Stage 01
    s01 = run_dir / "01_annotation_processor"
    clean_pdf = None
    if s01.exists():
        for f in s01.glob("*_clean.pdf"):
            clean_pdf = f
            break
        row["stage01_clean_pdf"] = str(clean_pdf) if clean_pdf else None

    # Stage 02
    s02 = _find_first(run_dir, "02_marker_extractor/json_output/02_marker_blocks.json")
    if s02:
        j2 = _read_json(s02) or {}
        row["stage02_blocks"] = _count_list(j2, "blocks")
        # try to infer pdf from payload
        row["pdf_path"] = (j2.get("source_pdf") or clean_pdf or "") if j2 else (clean_pdf or "")

    # Stage 03
    s03 = _find_first(run_dir, "03_suspicious_headers/json_output/03_verified_blocks.json")
    if s03:
        j3 = _read_json(s03) or {}
        row["stage03_verified"] = _count_list(j3, "blocks")

    # Stage 04
    s04 = _find_first(run_dir, "04_section_builder/json_output/04_sections.json")
    if s04:
        j4 = _read_json(s04) or {}
        row["stage04_sections"] = _count_list(j4, "sections")
        # simple doc_id from first section title
        try:
            secs = (j4 or {}).get("sections") or []
            if secs:
                row["doc_id"] = (secs[0].get("title") or "").split(".")[0]
        except Exception:
            pass

    # Stage 05
    s05 = _find_first(run_dir, "05_table_extractor/json_output/05_tables.json")
    if s05:
        j5 = _read_json(s05) or {}
        row["stage05_tables"] = _count_list(j5, "tables")

    # Stage 06 figures
    s06 = _find_first(run_dir, "06_figure_extractor/json_output/06_figures.json")
    if s06:
        j6 = _read_json(s06) or {}
        row["stage06_figures"] = _count_list(j6, "figures")

    # Stage 06b
    s06b = _find_first(run_dir, "06b_layout_sketcher/json_output/06b_layout_sketch.json")
    if s06b:
        row["stage06b_sketch"] = True

    # Stage 07 reflow
    s07 = _find_first(run_dir, "07_reflow_section/json_output/07_reflowed.json")
    if s07:
        j7 = _read_json(s07) or {}
        row["stage07_reflow"] = True if j7 else False

    # Stage 07 requirements miner
    s07m = _find_first(run_dir, "07_requirements_miner/json_output/07_requirements.json")
    if s07m:
        j7m = _read_json(s07m) or {}
        row["stage07_requirements"] = _count_list(j7m, "requirements")

    # Stage 08
    s08 = _find_first(run_dir, "08_lean4_theorem_prover/json_output/08_theorems.json")
    if s08:
        j8 = _read_json(s08) or {}
        try:
            meta = (j8.get("summary") or {}) if isinstance(j8, dict) else {}
            proved = meta.get("proofs_proved") or meta.get("proved")
            row["stage08_proved"] = int(proved) if proved is not None else None
        except Exception:
            pass

    # Stage 09
    s09 = _find_first(run_dir, "09_section_summarizer/json_output/09_summaries.json")
    if s09:
        j9 = _read_json(s09) or {}
        row["stage09_summaries"] = _count_list(j9, "summaries")

    # last updated
    latest = None
    for p in run_dir.rglob("*.json"):
        ts = _stat_or_none(p)
        if ts and (latest is None or ts > latest):
            latest = ts
    row["last_updated"] = latest.isoformat() if latest else None

    return row


@app.command()
def main(
    results_root: Path = typer.Option("data/results", "--results-root", exists=True, help="Root folder to scan"),
    out: Path = typer.Option("scripts/artifacts/sparta_ingestion.xlsx", "--out", help="Output Excel path"),
) -> None:
    runs: List[Path] = []
    # Prefer pipeline_iter/* runs; fall back to pipeline/*
    for pattern in ("pipeline_iter/*", "pipeline/*"):
        for d in (results_root / pattern).parent.glob((results_root / pattern).name):
            if d.is_dir():
                runs.append(d)
    runs = sorted(runs)

    rows = [_collect_row(r) for r in runs]
    if not rows:
        typer.echo("No runs found under results root.")
        return

    df = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="ingestion")
    typer.echo(f"Wrote: {out}")


if __name__ == "__main__":
    app()

