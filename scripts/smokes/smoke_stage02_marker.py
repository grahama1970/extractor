#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
from pathlib import Path
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 02 minimal block extraction")


def _load_stage02():
    p = Path("src/extractor/pipeline/steps/02_marker_extractor.py").resolve()
    spec = importlib.util.spec_from_file_location("stage02", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 02 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@app.command()
def main(
    input_pdf: Path = typer.Option(
        Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"),
        exists=True,
        help="Fixture PDF",
    )
):
    try:
        load_dotenv(find_dotenv())
        mod = _load_stage02()
        extract_blocks = getattr(mod, "extract_blocks")
        blocks = extract_blocks(input_pdf)
        if not isinstance(blocks, list) or len(blocks) == 0:
            raise RuntimeError("No blocks returned by Stage 02 extractor")
        typer.echo(f"OK: Stage 02 returned {len(blocks)} blocks")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
