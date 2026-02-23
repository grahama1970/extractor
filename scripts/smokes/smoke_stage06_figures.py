#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
#   "pymupdf>=1.22.0",
# ]
# ///
import importlib.util
from pathlib import Path
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 06 figure extract (offline)")


def _load_stage06():
    p = Path("src/extractor/pipeline/steps/06_figure_extractor.py").resolve()
    spec = importlib.util.spec_from_file_location("stage06", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 06 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@app.command()
def main(
    input_pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True)
):
    try:
        load_dotenv(find_dotenv())
        import asyncio

        mod = _load_stage06()
        extract = getattr(mod, "extract_and_describe_figure")
        out_dir = Path("data/results/pipeline/smokes/06_figure_extractor")
        out_dir.mkdir(parents=True, exist_ok=True)
        result = asyncio.run(
            extract(
                input_pdf, {"page_idx": 0, "bbox": [50, 100, 200, 200]}, "fig-smoke", out_dir, True
            )
        )
        if not result:
            raise RuntimeError("No result from figure extraction")
        if not (out_dir / "fig-smoke.png").exists():
            raise RuntimeError("Figure image not saved")
        typer.echo("OK: Stage 06 figure image saved (descriptions skipped)")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
