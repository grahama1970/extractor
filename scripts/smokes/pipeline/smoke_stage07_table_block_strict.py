#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import typer
from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.steps import s07_reflow_section as step07


app = typer.Typer(add_completion=False, help="Stage 07 strict table block smoke")


def _ensure_stage07(results: Path) -> None:
    """Validate inputs and configure environment for stage 07."""
    sec = results / "04_section_builder/json_output/04_sections.json"
    tab = results / "05_table_extractor/json_output/05_tables.json"
    fig = results / "06_figure_extractor/json_output/06_figures.json"
    env = os.environ.copy()
    env.setdefault("LITELLM_HTTPX", "1")
    env.setdefault("LITELLM_DEBUG", "1")
    # Quick upstream
    if not (sec.exists() and tab.exists() and fig.exists()):
        prep = [
            sys.executable,
            str(Path("src/extractor/pipeline/tools/quick_smoke.py")),
            "--pdf",
            str(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf")),
        ]
        if subprocess.run(prep, env=env).returncode != 0:
            raise SystemExit("quick_smoke failed")
    # Run strict
    cmd = [
        sys.executable,
        "src/extractor/pipeline/steps/07_reflow_section.py",
        "run",
        "--sections",
        str(sec),
        "--tables",
        str(tab),
        "--figures",
        str(fig),
        "--mode",
        "strict",
        "-o",
        str(results),
    ]
    if subprocess.run(cmd, env=env).returncode != 0:
        raise SystemExit("Stage 07 strict run failed")


def run_smoke(results: Path) -> None:
    """Load environment variables and process JSON results for smoke testing."""
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")

    _ensure_stage07(results)
    tabs = json.loads((results / "05_table_extractor/json_output/05_tables.json").read_text())
    re07 = json.loads((results / "07_reflow_section/json_output/07_reflowed.json").read_text())

    sections = re07.get("reflowed_sections") or []
    if not sections:
        raise SystemExit("No reflowed_sections present")
    sec = sections[0]
    rj = sec.get("reflowed_json") or {}
    blocks = rj.get("blocks") or []
    tbl = next((b for b in blocks if isinstance(b, dict) and b.get("type") == "table"), None)
    if not tbl:
        raise SystemExit("No table block generated in strict reflow")

    # Verify first row matches Stage 05 pandas_df for same section (if mapping exists)
    sid = sec.get("id") or sec.get("section_id")
    canon_source = None
    for t in sec.get("tables") or []:
        canon_source = t
        break
    if not canon_source:
        typer.echo("SKIP: No Stage 07 merged tables available for this section")
        raise SystemExit(0)
    # Fallback: locate corresponding Stage 05 table when metadata missing
    t0 = canon_source
    if not canon_source.get("pandas_df"):
        for t in tabs.get("tables", []):
            if sid and t.get("section_id") and t.get("section_id") != sid:
                continue
            t0 = t
            break
    if not t0:
        typer.echo("SKIP: No Stage 05 tables associated to this section")
        raise SystemExit(0)
    canonical = step07._build_table_block_from_stage05(t0)
    if not canonical:
        typer.echo("SKIP: Unable to derive canonical table from source data")
        raise SystemExit(0)
    cols = canonical.get("columns") or []
    df = canonical.get("rows") or []
    if not (cols and df):
        typer.echo("SKIP: Stage 05 table missing columns/rows")
        raise SystemExit(0)
    table_cols = tbl.get("columns") or []
    table_rows = tbl.get("rows") or []
    if table_cols != canonical.get("columns"):
        raise SystemExit("Table block columns do not match canonical sanitized Stage 05 columns")
    if not isinstance(table_rows, list) or not table_rows:
        raise SystemExit("Table block has no rows")
    for idx, row in enumerate(canonical.get("rows", [])):
        try:
            candidate = table_rows[idx]
        except Exception:
            raise SystemExit("Table block row count mismatch compared to canonical Stage 05")
        canon_norm = [step07._normalize_table_text(x) for x in row]
        cand_norm = [step07._normalize_table_text(x) for x in candidate]
        if cand_norm != canon_norm:
            raise SystemExit("Table block row content mismatch compared to canonical Stage 05")
    typer.echo("OK: Stage 07 strict table block matches canonical Stage 05 data")


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "--results")):
    """Run a smoke test to the results path."""
    run_smoke(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(Path("data/results/pipeline"))
