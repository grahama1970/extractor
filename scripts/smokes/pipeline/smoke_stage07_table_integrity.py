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


app = typer.Typer(add_completion=False, help="Stage 07 table integrity (no cell edits)")


def _ensure_stage07(results: Path) -> None:
    """Ensure Stage 07 processing."""
    sec = results / "04_section_builder/json_output/04_sections.json"
    tab = results / "05_table_extractor/json_output/05_tables.json"
    fig = results / "06_figure_extractor/json_output/06_figures.json"
    # always rerun Stage 07 to use latest prompt/schema
    # Ensure upstream via quick_smoke run
    env = os.environ.copy()
    env.setdefault("LITELLM_HTTPX", "1")
    env.setdefault("LITELLM_DEBUG", "1")
    prep = [
        sys.executable,
        str(Path("src/extractor/pipeline/tools/quick_smoke.py")),
        "--pdf",
        str(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf")),
    ]
    if subprocess.run(prep, env=env).returncode != 0:
        raise SystemExit("quick_smoke failed")
    # Run Stage 07 strict
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
        raise SystemExit("Stage 07 run failed")


def run_smoke(results: Path) -> None:
    """Run smoke tests on processed data to validate pipeline stages."""
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")

    _ensure_stage07(results)

    tabs = json.loads((results / "05_table_extractor/json_output/05_tables.json").read_text())
    re07 = json.loads((results / "07_reflow_section/json_output/07_reflowed.json").read_text())
    sections = re07.get("reflowed_sections") or []

    # Find any structured table blocks; if none, skip as pass (not applicable)
    found_structured = False
    for sec in sections:
        blocks = (sec.get("reflowed_json") or {}).get("blocks")
        if isinstance(blocks, list):
            for b in blocks:
                if (
                    isinstance(b, dict)
                    and b.get("type") == "table"
                    and isinstance(b.get("rows"), list)
                ):
                    found_structured = True
                    sid = sec.get("id") or sec.get("section_id")
                    canonical = None
                    for candidate in sec.get("tables") or []:
                        canonical = step07._build_table_block_from_stage05(candidate)
                        if canonical:
                            break
                    if not canonical:
                        # fallback to Stage 05 raw tables when Stage 07 metadata missing
                        for t in tabs.get("tables", []):
                            if sid and t.get("section_id") and t.get("section_id") != sid:
                                continue
                            canonical = step07._build_table_block_from_stage05(t)
                            if canonical:
                                break
                    if not canonical:
                        raise SystemExit("Table integrity failed: unable to derive canonical table")
                    if canonical.get("columns") != (b.get("columns") or []):
                        raise SystemExit("Table integrity failed: sanitized columns mismatch")
                    canon_rows = canonical.get("rows") or []
                    re_rows = b.get("rows") or []
                    if not canon_rows or not re_rows:
                        raise SystemExit("Table integrity failed: missing rows")
                    if len(re_rows) < len(canon_rows):
                        raise SystemExit("Table integrity failed: missing canonical rows")
                    for expected, actual in zip(canon_rows, re_rows):
                        canon_norm = [step07._normalize_table_text(x) for x in expected]
                        actual_norm = [step07._normalize_table_text(x) for x in actual]
                        if actual_norm != canon_norm:
                            raise SystemExit("Table integrity failed: row content mismatch")

    if not found_structured:
        typer.echo("SKIP: No structured table blocks found in Stage 07 (not applicable)")
    else:
        typer.echo("OK: Stage 07 table integrity (subset) passed")


@app.command()
def main(
    results: Path = typer.Option(Path("data/results/pipeline"), "--results"),
):
    """Run smoke tests on the specified results directory."""
    run_smoke(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(Path("data/results/pipeline"))
