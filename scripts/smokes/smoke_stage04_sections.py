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


app = typer.Typer(add_completion=False, help="Smoke: Stage 04 build sections from minimal blocks")


def _load_stage04():
    p = "src/extractor/pipeline/steps/04_section_builder.py"
    spec = importlib.util.spec_from_file_location("stage04", p)
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 04 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@app.command()
def main():
    load_dotenv(find_dotenv())
    mod = _load_stage04()
    build = getattr(mod, "build_sections_from_blocks")
    blocks = [
        {"block_type": "SectionHeader", "text": "1. Intro", "page_idx": 0, "bbox": [0, 0, 100, 20]},
        {
            "block_type": "Text",
            "text": "This is the intro.",
            "page_idx": 0,
            "bbox": [0, 30, 200, 60],
        },
        {"block_type": "Text", "text": "More text.", "page_idx": 0, "bbox": [0, 65, 200, 90]},
    ]
    sections = build(blocks, fallback_heuristics=True)
    if not isinstance(sections, list) or not sections:
        raise SystemExit(1)
    s0 = sections[0]
    if not s0.get("title") or "blocks" not in s0:
        raise SystemExit(1)
    typer.echo("OK: Stage 04 sections built from minimal blocks")


if __name__ == "__main__":
    app()
