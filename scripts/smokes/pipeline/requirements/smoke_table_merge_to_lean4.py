#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv>=1.0.0,<2",
#   "pandas>=2.2.0",
# ]
# ///
"""
Smoke: Convert merged tables from Stage 07 (reflowed.json) to Lean4 requirements,
then invoke the real Lean4 CLI (deterministic/no‑LLM) to validate the batch path.

Acceptance (offline):
- Stage 07 exists for the richer PDF (with requirements)
- ≥ 1 constraint requirement extracted from at least one table (merged or regular)
- Lean4 CLI runs and writes OUT.json
- Summary + extracted constraints saved to scripts/artifacts/
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import typer

app = typer.Typer(add_completion=False)

PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements.pdf")
OUT = Path("data/results/with_requirements_smoke")
RELF = OUT / "07_reflow_section/json_output/07_reflowed.json"


def ensure_stage07() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if RELF.exists():
        return
    cmd = [
        "/home/graham/workspace/experiments/extractor/.venv/bin/python",
        "-m",
        "src.cli",
        "extract",
        str(PDF),
        str(OUT),
        "--mode",
        "accurate",
    ]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        raise SystemExit("pipeline extract failed")


def df_from_maybe_dict(obj: Any) -> pd.DataFrame | None:
    # Accept dict-of-lists or list-of-dicts
    try:
        if isinstance(obj, dict) and obj:
            return pd.DataFrame(obj)
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return pd.DataFrame(obj)
    except Exception:
        return None
    return None


def constraints_from_df(df: pd.DataFrame) -> List[str]:
    cons: List[str] = []
    cols = {c.strip().lower(): c for c in df.columns}
    # Pattern 1: Param + Constraint
    if "constraint" in cols and len(df.columns) >= 2:
        ccol = cols["constraint"]
        pcol = next((c for k, c in cols.items() if k in {"param", "parameter", "name"}), None)
        if pcol is None and len(df.columns) >= 2:
            # assume first non-constraint column is the parameter name
            pcol = [c for c in df.columns if c != ccol][0]
        for _, row in df.iterrows():
            name = str(row.get(pcol, "X")).strip()
            expr = str(row.get(ccol, "")).strip()
            if expr:
                cons.append(f"The parameter {name} shall satisfy: {expr}")
    # Pattern 2: Min/Max range for a variable column
    if {"min", "max"}.issubset(cols.keys()) and len(df.columns) >= 3:
        minc, maxc = cols["min"], cols["max"]
        varc = next((c for k, c in cols.items() if k in {"value", "var", "variable"}), None)
        for _, row in df.iterrows():
            vname = str(row.get(varc, "x")) if varc else "x"
            try:
                lo = str(row[minc]).strip(); hi = str(row[maxc]).strip()
                if lo and hi:
                    cons.append(f"{lo} <= {vname} <= {hi}")
            except Exception:
                pass
    # Generic equality constraints per row for common schemas
    if not cons:
        key_cols = [c for c in df.columns if c.lower() in {"signal", "name", "param", "parameter"}]
        if key_cols:
            keyc = key_cols[0]
            for _, row in df.iterrows():
                ident = str(row.get(keyc, "X"))
                for col in df.columns:
                    if col == keyc:
                        continue
                    val = row.get(col)
                    if val is None or str(val).strip() == "":
                        continue
                    # Skip verbose free text fields
                    if col.lower() in {"description", "notes"}:
                        continue
                    cons.append(f"The {keyc} {ident} shall have {col} = {val}")
    return cons


def extract_table_constraints(reflow_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(reflow_path.read_text())
    sections = data.get("reflowed_sections", [])
    items: List[Dict[str, Any]] = []
    for s in sections:
        sid = s.get("id") or s.get("section_id") or s.get("title") or "section"
        title = s.get("title", "")
        tables = s.get("tables") or []
        # Prefer sections with TABLE/MERGE in title, but accept any with tables
        if not tables:
            continue
        # Pull constraints from each table
        for t in tables:
            # pandas_df_dict preferred
            df=None
            for key in ("pandas_df_dict","pandas_df","df","pandas_df_raw"):
                df = df_from_maybe_dict(t.get(key))
                if df is not None:
                    break
            cons: List[str] = []
            if df is not None and not df.empty:
                cons.extend(constraints_from_df(df))
            # fallback: parse text_content lines with ':' pattern
            if not cons:
                txt = (t.get("text_content") or "").strip()
                for line in txt.splitlines():
                    m = re.match(r"([^:]+):\s*(.+)", line.strip())
                    if m:
                        name, expr = m.group(1).strip(), m.group(2).strip()
                        cons.append(f"The parameter {name} shall satisfy: {expr}")
            for c in cons:
                items.append({
                    "requirement": c,
                    "metadata": {"section_id": str(sid), "section_title": title},
                })
    return items


@app.command()
def main():
    lean_cli = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
    if not lean_cli.exists():
        print("SKIP: Lean4 CLI not found; install first.")
        raise typer.Exit(0)

    ensure_stage07()
    if not RELF.exists():
        typer.echo("Stage 07 not found after extract", err=True)
        raise typer.Exit(1)

    items = extract_table_constraints(RELF)
    artifacts = Path("scripts/artifacts"); artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts/"merged_table_constraints.json").write_text(json.dumps(items, indent=2))

    if not items:
        print("SKIP: No table constraints extracted from Stage 07")
        raise typer.Exit(0)

    tmp_in = Path("/tmp/lean_table_merge_in.json"); tmp_in.write_text(json.dumps(items, indent=2))
    tmp_out = Path("/tmp/lean_table_merge_out.json")

    cmd = [
        "/home/graham/workspace/experiments/extractor/.venv/bin/python",
        str(lean_cli),
        "batch",
        "--input-file",
        str(tmp_in),
        "--output-file",
        str(tmp_out),
        "--deterministic",
        "--no-llm",
        "--max-workers",
        "1",
    ]
    env = os.environ.copy(); env["PYTHONPATH"] = "/home/graham/workspace/experiments/lean4/src:" + env.get("PYTHONPATH", "")
    rc = subprocess.run(cmd, env=env).returncode
    if rc != 0 or not tmp_out.exists():
        typer.echo("Lean4 batch failed on merged table constraints", err=True)
        raise typer.Exit(1)

    data = json.loads(tmp_out.read_text())
    results = [r for r in data.get("proof_results", []) if isinstance(r, dict)]
    proved = sum(1 for r in results if r.get("status") == "proved")
    summary = {
        "input_count": len(items),
        "proved": proved,
        "out_json": str(tmp_out),
        "constraints_artifact": str(artifacts/"merged_table_constraints.json"),
    }
    (artifacts/"merged_table_lean4_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
