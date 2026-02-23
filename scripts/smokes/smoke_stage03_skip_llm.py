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

import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 03 offline pass-through (--skip-llm)")


@app.command()
def main(
    results: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    """Verify Stage 03 writes 03_verified_blocks.json in --skip-llm mode."""
    load_dotenv(find_dotenv() or None)
    stage_out = results / "03_suspicious_headers" / "json_output"
    stage_out.parent.mkdir(parents=True, exist_ok=True)
    stage_out.mkdir(exist_ok=True)

    # Create a minimal Stage 02-like JSON
    tmp_dir = results / "_smokes_tmp03"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    blocks = {
        "blocks": [
            {"block_type": "SectionHeader", "text": "1. Intro", "suspicious_header": True},
            {"block_type": "Paragraph", "text": "Hello world."},
        ]
    }
    s02 = tmp_dir / "02_blocks.json"
    s02.write_text(json.dumps(blocks))

    # Provide a fake clean PDF path (Stage 03 only checks existence in skip-llm path)
    pdf_dir = tmp_dir / "pdf01"
    pdf_dir.mkdir(exist_ok=True)
    fake_pdf = pdf_dir / "fixture_clean.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")

    import importlib.util

    p = Path("src/extractor/pipeline/steps/03_suspicious_headers.py").resolve()
    spec = importlib.util.spec_from_file_location("stage03", str(p))
    if not spec or not spec.loader:
        raise SystemExit("Failed to load Stage 03 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    try:
        mod.run(
            input_json=s02,
            pdf_dir=pdf_dir,
            output_dir=results,
            model=None,
            concurrency=1,
            dpi=72,
            debug=False,
            limit=0,
            timeout=0,
            annotations_json=None,
            use_knowledge=False,
            use_prior=False,
            auto_reject=False,
            persist_headers=False,
            verify_all_headers=False,
            skip_llm=True,
        )
        out = stage_out / "03_verified_blocks.json"
        if not out.exists():
            raise SystemExit("Expected 03_verified_blocks.json not written")
        typer.echo("OK: Stage 03 skip-llm wrote verified blocks")
    except SystemExit:
        raise
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
