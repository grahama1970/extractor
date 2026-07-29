#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: Stage 11 emits 'proves' edges when Stage 08 proofs exist.

Skips gracefully if the Lean4 CLI is not available at the default path
and therefore Stage 08 cannot run.
"""
from __future__ import annotations
import os

import json
from pathlib import Path
import subprocess
import sys
import typer

app = typer.Typer(add_completion=False)


def _find_latest_edges(root: Path) -> Path | None:
    """Find the latest edges JSON file in the specified directory."""
    cands = sorted(
        root.rglob("11_arango_create_graph/json_output/11_graph_edges.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return cands[0] if cands else None


@app.command()
def main(
    pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True)
):
    """Run Lean4 CLI proves edges smoke test with a PDF."""
    lean_cli = Path(os.environ.get("LEAN4_CLI", Path.home() / "workspace/experiments/lean4/src/lean4_prover/cli_mini.py"))
    if not lean_cli.exists():
        print("SKIP: Lean4 CLI not found; skipping Stage 11 'proves' edges smoke.")
        raise typer.Exit(0)

    out_dir = Path("data/results/cli_smokes/lean4_proves")
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "src.cli",
        "extract",
        str(pdf),
        str(out_dir),
        "--mode",
        "accurate",
        "--prove",
    ]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        typer.echo("CLI accurate --prove failed", err=True)
        raise typer.Exit(1)

    edges_path = _find_latest_edges(out_dir)
    if not edges_path or not edges_path.exists():
        typer.echo("Stage 11 edges JSON not found", err=True)
        raise typer.Exit(1)

    edges = json.loads(edges_path.read_text())
    total = len(edges) if isinstance(edges, list) else 0
    proves_count = sum(
        1 for e in edges if isinstance(e, dict) and e.get("relationship_type") == "proves"
    )

    # Inspect Stage 08 theorems to set expectation
    theorems = sorted(
        out_dir.rglob("08_lean4_theorem_prover/json_output/08_theorems.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    proved_expected = 0
    if theorems:
        tdata = json.loads(theorems[0].read_text())
        if isinstance(tdata, dict):
            prs = tdata.get("proof_results")
            if isinstance(prs, list):
                for pr in prs:
                    try:
                        status = (pr or {}).get("status")
                        item = (pr or {}).get("item") or {}
                        src = item.get("source_details") or {}
                        if src.get("section_id") and (
                            status is None
                            or str(status).lower() in {"ok", "proved", "success", "true"}
                        ):
                            proved_expected += 1
                    except Exception:
                        pass
    report = {
        "edges_path": str(edges_path),
        "total_edges": total,
        "proves_edges": proves_count,
        "proved_expected": proved_expected,
    }
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "stage11_offline_edges_summary.json").write_text(
        json.dumps(report, indent=2)
    )

    if proved_expected > 0 and proves_count == 0:
        typer.echo("No 'proves' edges found but proofs were reported", err=True)
        raise typer.Exit(1)

    print("OK: Stage 11 'proves' edges check passed")


if __name__ == "__main__":
    app()
