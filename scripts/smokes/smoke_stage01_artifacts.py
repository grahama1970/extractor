#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "loguru>=0.7.0",
#   "typer>=0.12",
#   "pymupdf>=1.23.0",
# ]
# ///
from pathlib import Path
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 01 artifacts exist (images + clean PDF)")


def _load_stage01():
    """Load and execute a Python module from a specified file path."""
    p = Path("src/extractor/pipeline/steps/s01_annotation_processor.py").resolve()
    spec = importlib.util.spec_from_file_location("stage01", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 01 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@app.command()
def main(
    input_pdf: Path = typer.Option(
        Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"),
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Fixture PDF",
    ),
    output_dir: Path = typer.Option(
        Path("data/results/pipeline/smokes"), help="Base output directory"
    ),
):
    """Execute the main command for processing a PDF file."""
    try:
        load_dotenv(find_dotenv())
        mod = _load_stage01()
        Config = getattr(mod, "Config")
        stage_dir = output_dir / "01_annotation_processor"
        stage_dir.mkdir(parents=True, exist_ok=True)
        cfg = Config(
            input_pdf=input_pdf,
            output_dir=stage_dir,
            include_freetext=True,
            use_images=False,
            render_dpi=120,
            llm_model="ignore",
            llm_concurrency=1,
            limit_annotations=0,
            max_runtime_seconds=0,
            debug=False,
            cache=False,
        )
        extract_annotations_data = getattr(mod, "extract_annotations_data")
        annots = extract_annotations_data(input_pdf, cfg)
        if not annots:
            typer.echo("No annotations found", err=True)
            raise SystemExit(2)
        image_dir = stage_dir / "visual_output"
        if not image_dir.exists() or not any(image_dir.iterdir()):
            typer.echo("No images saved", err=True)
            raise SystemExit(3)
        create_clean_pdf = getattr(mod, "create_clean_pdf")
        out_pdf = Path(create_clean_pdf(input_pdf, stage_dir))
        if not out_pdf.exists():
            typer.echo("Clean PDF not created", err=True)
            raise SystemExit(4)
        typer.echo("OK: Stage 01 artifacts present")
    except SystemExit:
        raise
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
