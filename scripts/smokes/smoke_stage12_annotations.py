#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 12 insert annotations (import/CLI)")


@app.command()
def main():
    """Load and execute a Python module from a specified file path."""
    load_dotenv(find_dotenv())
    p = "src/extractor/pipeline/steps/12_insert_annotations.py"
    spec = importlib.util.spec_from_file_location("stage12", p)
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 12 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    if not hasattr(mod, "run"):
        raise SystemExit(1)
    typer.echo("OK: Stage 12 module imports; CLI present (DB ops skipped)")


if __name__ == "__main__":
    app()
