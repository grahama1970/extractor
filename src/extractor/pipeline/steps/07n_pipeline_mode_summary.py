#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import typer
from loguru import logger

app = typer.Typer(help="Aggregate deterministic/hash_component flags.")


@app.command()
def run(inputs: List[Path] = typer.Argument(..., exists=True), output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o")):
    summary = []
    for p in inputs:
        try:
            data = json.loads(p.read_text())
            summary.append({"file": str(p), "hash_component": data.get("hash_component"), "deterministic": data.get("deterministic")})
        except Exception:
            pass
    out_dir = output_dir / "07n_pipeline_mode_summary" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / "07n_pipeline_mode.json"
    outp.write_text(json.dumps({"stages": summary}, indent=2))
    logger.success(f"07n: wrote {outp}")


if __name__ == "__main__":
    app()

