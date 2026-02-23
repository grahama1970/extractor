#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv>=1.0.0,<2",
# ]
# ///
"""
Smoke (acceptance): Verify high-level section/table/requirement layout for a curated PDF.
Default behavior is non-strict: writes a diff summary artifact and exits 0.
Set ACCEPT_STRICT=1 to make mismatches fail with exit code 1.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import typer

app = typer.Typer(add_completion=False)

PDF_DEFAULT = Path("data/input/pipeline/BHT_CV32A65X_with_requirements.pdf")
OUT_DEFAULT = Path("data/results/with_requirements_acceptance")


@dataclass
class ExpectedSpec:
    sections: int
    s1_tables: int
    s1_figures: int
    s1_sentence_reqs: int
    s1_conditional_reqs: int
    s2_tables_total: int
    s2_tables_merged: int
    s2_tables_titled: int


SPEC = ExpectedSpec(
    sections=2,
    s1_tables=1,
    s1_figures=1,
    s1_sentence_reqs=10,
    s1_conditional_reqs=2,
    s2_tables_total=3,
    s2_tables_merged=1,
    s2_tables_titled=3,
)


def run_extract(pdf: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p07 = out_dir / "07_reflow_section/json_output/07_reflowed.json"
    if p07.exists():
        return p07
    cmd = [
        "/home/graham/workspace/experiments/extractor/.venv/bin/python",
        "-m",
        "src.cli",
        "extract",
        str(pdf),
        str(out_dir),
        "--mode",
        "accurate",
    ]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        raise SystemExit("extract failed")
    return p07


def summarize(p07: Path) -> Dict[str, Any]:
    data = json.loads(p07.read_text())
    secs = data.get("reflowed_sections", [])
    # Define top-level sections as those with minimal level
    levels = [s.get("level") for s in secs if isinstance(s.get("level"), int)]
    minlvl = min(levels) if levels else None
    tops = [s for s in secs if s.get("level") == minlvl] if minlvl is not None else secs

    def section_metrics(s: Dict[str, Any]) -> Dict[str, Any]:
        text = str(s.get("reflowed_text") or "")
        tables = s.get("tables") or []
        figures = s.get("figures") or []
        # sentence-level requirements (modal verbs)
        modals = re.findall(r"\b(shall|must|will|should)\b", text, flags=re.I)
        # conditional requirements
        conditionals = re.findall(
            r"\b(if|when|where)\b.*?\b(shall|must|will|should)\b", text, flags=re.I | re.S
        )
        # table titles (very approximate: look for lines starting with 'Table' or 'Title:' in text nearby)
        titled = 0
        for t in tables:
            cap = str(t.get("caption") or t.get("title") or "")
            if cap.strip():
                titled += 1
        return {
            "tables": len(tables),
            "figures": len(figures),
            "sentence_reqs": len(modals),
            "conditional_reqs": len(conditionals),
            "tables_titled": titled,
        }

    tops_metrics = [section_metrics(s) for s in tops[:2]]
    # Heuristic: treat Stage 07 single-table-per-topic as the merged table result
    s1_merged_tables = 1 if tops_metrics and tops_metrics[0]["tables"] >= 1 else 0

    summary = {
        "top_sections": len(tops),
        "s1": tops_metrics[0] if len(tops_metrics) > 0 else {},
        "s2": tops_metrics[1] if len(tops_metrics) > 1 else {},
        "s1_merged_tables": s1_merged_tables,
    }
    return summary


def diff_against_spec(summary: Dict[str, Any], spec: ExpectedSpec) -> Dict[str, Any]:
    diffs = {}

    def want(actual, expected, key):
        diffs[key] = {"actual": actual, "+/-": actual - expected, "expected": expected}

    want(summary.get("top_sections", 0), spec.sections, "sections")
    s1 = summary.get("s1", {})
    s2 = summary.get("s2", {})
    want(s1.get("tables", 0), spec.s1_tables, "s1_tables")
    want(s1.get("figures", 0), spec.s1_figures, "s1_figures")
    want(s1.get("sentence_reqs", 0), spec.s1_sentence_reqs, "s1_sentence_reqs")
    want(s1.get("conditional_reqs", 0), spec.s1_conditional_reqs, "s1_conditional_reqs")
    want(summary.get("s1_merged_tables", 0), spec.s1_tables, "s1_merged_tables")
    want(s2.get("tables", 0), spec.s2_tables_total, "s2_tables_total")
    want(s2.get("tables_titled", 0), spec.s2_tables_titled, "s2_tables_titled")
    return diffs


@app.command()
def main(
    pdf: Path = typer.Option(PDF_DEFAULT, exists=True),
    out_dir: Path = typer.Option(OUT_DEFAULT),
):
    p07 = run_extract(pdf, out_dir)
    summary = summarize(p07)
    diffs = diff_against_spec(summary, SPEC)
    artifacts = Path("scripts/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "layout_acceptance_summary.json").write_text(
        json.dumps({"summary": summary, "diffs": diffs}, indent=2)
    )

    strict = os.getenv("ACCEPT_STRICT", "").lower() in {"1", "true", "yes", "y"}
    ok = all(v["+/-"] == 0 for v in diffs.values())
    if strict and not ok:
        typer.echo(
            "Layout acceptance failed (strict). See scripts/artifacts/layout_acceptance_summary.json",
            err=True,
        )
        raise typer.Exit(1)
    print(
        json.dumps(
            {"ok": ok, "artifact": "scripts/artifacts/layout_acceptance_summary.json"}, indent=2
        )
    )


if __name__ == "__main__":
    app()
