#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
#   "pymupdf>=1.22.0",
# ]
# ///
from __future__ import annotations

import json
import shutil
from pathlib import Path
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(
    add_completion=False, help="Smoke: Stage 06 --skip-descriptions using fixture PDF"
)


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "-o")) -> None:
    load_dotenv(find_dotenv() or None)
    fixture = Path("data/input/pipeline/BHT_CV32A65X_marked.pdf")
    if not fixture.exists():
        raise SystemExit("Fixture PDF missing: data/input/pipeline/BHT_CV32A65X_marked.pdf")

    tmp = results / "_smokes_tmp06"
    pdf_dir = tmp / "pdf01"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    clean_pdf = pdf_dir / f"{fixture.stem}_clean.pdf"
    shutil.copyfile(fixture, clean_pdf)

    # Minimal Stage 02 blocks with one image
    s02 = tmp / "02_blocks.json"
    s02.write_text(
        json.dumps(
            {
                "blocks": [
                    {
                        "block_type": "Image",
                        "page_idx": 0,
                        "bbox": [50, 50, 200, 200],
                    }
                ]
            }
        )
    )

    # Minimal Stage 04 sections
    s04 = tmp / "04_sections.json"
    s04.write_text(
        json.dumps(
            {
                "sections": [
                    {
                        "id": "s1",
                        "title": "Intro",
                        "level": 1,
                        "page_start": 0,
                        "page_end": 0,
                        "bbox": [0, 0, 600, 800],
                    }
                ]
            }
        )
    )

    spec = importlib.util.spec_from_file_location(
        "stage06", "src/extractor/pipeline/steps/06_figure_extractor.py"
    )
    if not spec or not spec.loader:
        raise SystemExit("Failed to load Stage 06 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    mod.run(
        stage_02_json=s02,
        stage_04_json=s04,
        pdf_dir=pdf_dir,
        output_dir=results,
        skip_descriptions=True,
    )

    out = results / "06_figure_extractor" / "json_output" / "06_figures.json"
    if not out.exists():
        raise SystemExit("06_figures.json not written")
    data = json.loads(out.read_text())
    if data.get("status") != "Completed":
        raise SystemExit("Stage 06 status not Completed")
    typer.echo("OK: Stage 06 skip-descriptions produced figures JSON")


if __name__ == "__main__":
    app()
