#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
from __future__ import annotations

import json
from pathlib import Path
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(
    add_completion=False, help="Smoke: Stage 08 --skip-proving produces contract output"
)


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "-o")) -> None:
    """Reflow document sections and store results."""
    load_dotenv(find_dotenv() or None)
    # Minimal reflowed sections
    reflow = {
        "reflowed_sections": [
            {
                "id": "s1",
                "title": "Intro",
                "level": 1,
                "reflow_status": "success",
                "reflowed_text": "The system shall record the last 8 branch outcomes.",
            }
        ]
    }
    tmp = results / "_smokes_tmp08"
    tmp.mkdir(parents=True, exist_ok=True)
    s07 = tmp / "07_reflowed.json"
    s07.write_text(json.dumps(reflow))

    spec = importlib.util.spec_from_file_location(
        "stage08", "src/extractor/pipeline/steps/08_lean4_theorem_prover.py"
    )
    if not spec or not spec.loader:
        raise SystemExit("Failed to load Stage 08 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    mod.run(input_json=s07, output_dir=results, skip_proving=True)

    out = results / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
    if not out.exists():
        raise SystemExit("08_theorems.json not written")
    data = json.loads(out.read_text())
    if data.get("proving_skipped") is not True:
        raise SystemExit("Expected proving_skipped=true in output")
    typer.echo("OK: Stage 08 skip-proving produced output")


if __name__ == "__main__":
    app()
