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


app = typer.Typer(add_completion=False, help="Smoke: Stage 10 skip-embeddings + skip-export")


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "-o")) -> None:
    load_dotenv(find_dotenv() or None)

    # Minimal Stage 07 reflowed payload
    reflow = {
        "reflowed_sections": [
            {
                "id": "s1",
                "title": "Intro",
                "level": 1,
                "reflow_status": "success",
                "reflowed_text": "Hello world.",
                "page_start": 0,
                "page_end": 0,
                "bbox": [0, 0, 100, 100],
                "tables": [],
                "figures": [],
            }
        ],
        "source_files": {"sections": "fixture.pdf"},
    }
    # Minimal Stage 09 summaries payload
    summaries = {"summaries": []}

    tmp = results / "_smokes_tmp10"
    tmp.mkdir(parents=True, exist_ok=True)
    s07 = tmp / "07_reflowed.json"
    s09 = tmp / "09_summaries.json"
    s07.write_text(json.dumps(reflow))
    s09.write_text(json.dumps(summaries))

    spec = importlib.util.spec_from_file_location(
        "stage10", "src/extractor/pipeline/steps/10_arangodb_exporter.py"
    )
    if not spec or not spec.loader:
        raise SystemExit("Failed to load Stage 10 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    mod.run(
        reflowed_json=s07,
        summaries_json=s09,
        output_dir=results,
        collection_name="pdf_objects",
        skip_export=True,
        skip_embeddings=True,
    )

    flat = results / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if not flat.exists():
        raise SystemExit("Flattened JSON not written")
    data = json.loads(flat.read_text())
    if not isinstance(data, list) or not data:
        raise SystemExit("Flattened JSON empty")
    if any(obj.get("embedding") is not None for obj in data):
        raise SystemExit("Embeddings were unexpectedly computed in skip mode")
    typer.echo("OK: Stage 10 skip-embeddings produced flattened JSON without embeddings")


if __name__ == "__main__":
    app()

