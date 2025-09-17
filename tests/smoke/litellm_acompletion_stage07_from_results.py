#!/usr/bin/env python3
"""
Stage 07 – Router.acompletion smoke using real results.

Loads Stage 04/05/06 outputs, builds the exact Stage 07 context + messages
via the step's helpers, and calls Gemini Flash 2.5 through LiteLLM Router.

Usage:
  GEMINI_API_KEY=... python tests/smoke/litellm_acompletion_stage07_from_results.py \
    --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
    --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
    --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
    --model gemini/gemini-2.5-flash --timeout 120 --include-images

This smoke is intended to replicate the Stage 07 call as closely as possible
to debug provider behavior without running the whole pipeline.
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv, find_dotenv
from litellm import Router

from extractor.pipeline.steps import s07_reflow_section as s07


async def a_run(
    sections: Path,
    tables: Path,
    figures: Path,
    model: str,
    timeout: int,
    include_images: bool,
    trim_chars: Optional[int],
):
    load_dotenv(find_dotenv())
    os.environ.setdefault("LITELLM_LOG", "DEBUG")

    router = Router(
        model_list=[
            {
                "model_name": model.split("/")[-1],
                "litellm_params": {
                    "model": model,
                    "api_key": os.getenv("GEMINI_API_KEY"),
                },
            }
        ]
    )

    # Consolidate a single section for a quick test
    secs = s07.consolidate_data(sections, tables, figures, None)
    if not secs:
        raise SystemExit("No sections loaded")
    sec = secs[0]

    # Build Stage 07 context text and message payload (uses standard 'text'+'image_url')
    ctx = s07.build_section_context_text(sec)
    if trim_chars and trim_chars > 0:
        ctx = ctx[:trim_chars]
    msgs = s07.build_reflow_request_messages(
        sec,
        results_base_dir=Path("data/results/pipeline"),
        include_images=include_images,
        model=model,
        context_text=ctx,
    )

    try:
        resp = await router.acompletion(model=model.split("/")[-1], messages=msgs, timeout=timeout)
        usage = getattr(resp, "usage", None)
        ch = getattr(resp, "choices", None) or []
        content = getattr(ch[0].message, "content", None) if ch else None
        print("usage:", usage)
        print("content:", content)
        # Quick JSON check
        text = None
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            # concatenate any text parts (Gemini may return list)
            parts = []
            for p in content:
                if isinstance(p, dict) and isinstance(p.get("text"), str):
                    parts.append(p["text"]) 
            text = "\n".join(parts) if parts else None
        if text:
            try:
                data = json.loads(text.strip().strip("`"))
                print("VALID_JSON:", isinstance(data, (dict, list)))
            except Exception:
                print("VALID_JSON:", False)
    except Exception as e:
        print("exception:", repr(e))


app = typer.Typer(add_completion=False, help="Stage 07 Router smoke from real results")


@app.command()
def run(
    sections: Path = typer.Option(Path("data/results/pipeline/04_section_builder/json_output/04_sections.json"), exists=True),
    tables: Path = typer.Option(Path("data/results/pipeline/05_table_extractor/json_output/05_tables.json"), exists=True),
    figures: Path = typer.Option(Path("data/results/pipeline/06_figure_extractor/json_output/06_figures.json"), exists=True),
    model: str = typer.Option("gemini/gemini-2.5-flash"),
    timeout: int = typer.Option(120),
    include_images: bool = typer.Option(True, "--include-images/--no-include-images"),
    trim_chars: Optional[int] = typer.Option(1500, help="Optional context trim for faster smokes"),
):
    asyncio.run(a_run(sections, tables, figures, model, timeout, include_images, trim_chars))


if __name__ == "__main__":
    app()
