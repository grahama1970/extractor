#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Acceptance: requirement IDs stable across resume runs
Run accurate twice into the same OUT with --resume and compare IDs set.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import typer

app = typer.Typer(add_completion=False)

PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements.pdf")
OUT = Path("data/results/with_requirements_idstable")


def ids_from(out: Path) -> set[str]:
    """Extract IDs from requirements JSON file."""
    p = out / "07_requirements_miner/json_output/07_requirements.json"
    d = json.loads(p.read_text())
    return {str(r.get("id")) for r in d.get("requirements") or []}


@app.command()
def main():
    """Run extraction process using specified Python script and mode."""
    OUT.mkdir(parents=True, exist_ok=True)
    # First run
    rc = subprocess.run(
        [
            "/home/graham/workspace/experiments/extractor/.venv/bin/python",
            "-m",
            "src.cli",
            "extract",
            str(PDF),
            str(OUT),
            "--mode",
            "accurate",
        ]
    ).returncode
    if rc != 0:
        raise SystemExit(rc)
    ids1 = ids_from(OUT)
    # Resume run (should skip miner and preserve IDs)
    rc = subprocess.run(
        [
            "/home/graham/workspace/experiments/extractor/.venv/bin/python",
            "-m",
            "extractor.pipeline.run_all",
            "--pdf",
            str(PDF),
            "--results",
            str(OUT),
            "--resume",
        ]
    ).returncode
    if rc != 0:
        raise SystemExit(rc)
    ids2 = ids_from(OUT)
    ok = ids1 == ids2 and len(ids1) > 0
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "req_ids_stability.json").write_text(
        json.dumps({"ok": ok, "n": len(ids1)}, indent=2)
    )
    if not ok:
        raise SystemExit(1)
    print(json.dumps({"ok": ok}, indent=2))


if __name__ == "__main__":
    app()
