#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
#   "camelot-py[cv]>=0.11",
#   "pymupdf>=1.22.0",
# ]
# ///
from pathlib import Path
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 05 minimal table ops")


def _load_stage05():
    """Load Stage 05 module."""
    p = Path("src/extractor/pipeline/steps/05_table_extractor.py").resolve()
    spec = importlib.util.spec_from_file_location("stage05", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 05 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@app.command()
def main(
    input_pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True)
):
    """Process a marked PDF file using configured pipeline stages."""
    try:
        load_dotenv(find_dotenv())
        mod = _load_stage05()
        # If Camelot is missing, just ensure import succeeded
        try:
            import camelot  # type: ignore  # noqa: F401

            have_camelot = True
        except Exception:
            have_camelot = False
        if not have_camelot:
            typer.echo("OK: Stage 05 module import (Camelot missing, skipping)")
            raise SystemExit(0)

        # Try a tiny image extraction on page 0, small bbox
        import fitz  # type: ignore

        pdf = fitz.open(str(input_pdf))
        bbox = (50.0, 150.0, 300.0, 260.0)
        out_dir = Path("data/results/pipeline/smokes/05_table_extractor/images")
        out_dir.mkdir(parents=True, exist_ok=True)
        img_path = mod.extract_table_image(pdf, 0, bbox, out_dir, table_idx=0)
        if not img_path or not Path(img_path).exists():
            raise RuntimeError("Failed to save table image")
        typer.echo("OK: Stage 05 saved a table image")
    except SystemExit:
        raise
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
