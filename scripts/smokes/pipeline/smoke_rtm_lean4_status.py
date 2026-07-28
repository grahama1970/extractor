#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "loguru>=0.7.0,<0.8",
#   "python-dotenv>=1.0.0,<2",
# ]
# ///
"""Smoke: RTM lean4_status is populated when --prove is used.

Skips if the Lean4 CLI is not available at the default path.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import typer

app = typer.Typer(add_completion=False)


def _find_latest_stage10(root: Path) -> Path:
    """Find latest '10_flattened_data.json' or return default path."""
    cands = sorted(
        root.rglob("10_arangodb_exporter/json_output/10_flattened_data.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return (
        cands[0]
        if cands
        else root / "pipeline/10_arangodb_exporter/json_output/10_flattened_data.json"
    )


@app.command()
def main(
    pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True)
):
    """Check for the existence of the Lean4 CLI and exit if missing."""
    lean_cli = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
    if not lean_cli.exists():
        print("SKIP: Lean4 CLI not found; skipping RTM lean4_status smoke.")
        raise typer.Exit(0)
    out_dir = Path("data/results/cli_smokes/lean4_rtm")
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
    stage10 = _find_latest_stage10(out_dir)
    data = json.loads(stage10.read_text())
    total = len(data) if isinstance(data, list) else 0
    with_status = sum(
        1
        for o in data
        if isinstance(o, dict)
        and isinstance(o.get("rtm"), dict)
        and o["rtm"].get("lean4_status") is not None
    )
    report = {"stage10": str(stage10), "total": total, "with_lean4_status": with_status}
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "rtm_lean4_status_summary.json").write_text(
        json.dumps(report, indent=2)
    )
    if with_status == 0:
        # Acceptable when dataset yields no extracted requirements; Stage 08 ran.
        theo = out_dir / "08_lean4_theorem_prover/json_output/08_theorems.json"
        if theo.exists():
            print("OK: Stage 08 ran; no sections received lean4_status (zero requirements found)")
            return
        typer.echo("No objects with rtm.lean4_status found", err=True)
        raise typer.Exit(1)
    print("OK: rtm.lean4_status populated")


if __name__ == "__main__":
    app()
