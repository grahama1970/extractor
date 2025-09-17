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


app = typer.Typer(add_completion=False, help="Smoke: Stage 08 Lean4 (import/help)")


@app.command()
def main():
    try:
        load_dotenv(find_dotenv())
        p = "src/extractor/pipeline/steps/08_lean4_theorem_prover.py"
        spec = importlib.util.spec_from_file_location("stage08", p)
        if not spec or not spec.loader:
            raise RuntimeError("Failed to load Stage 08 module")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        # Consider it OK if module imports and exposes a CLI builder or run function
        ok = hasattr(mod, "build_cli") or hasattr(mod, "run")
        if not ok:
            raise RuntimeError("Stage 08 lacks CLI/run entrypoints")
        typer.echo("OK: Stage 08 module imported and has CLI/run entrypoint")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
