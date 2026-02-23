#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
import os
import sys
from pathlib import Path
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 07 text-only via adapter")


@app.command()
def main(
    model: str = typer.Option(
        os.getenv(
            "LITELLM_DEFAULT_MODEL",
            os.getenv("DEFAULT_LITELLM_MODEL", "gemini/gemini-2.5-flash"),
        ),
        help="Model name",
    ),
    prompt_version: str = typer.Option("reflow@0.1.0"),
    doc_id: str = typer.Option("bht"),
    section_id: str = typer.Option("s0"),
    timeout: int = typer.Option(40),
):
    try:
        # Load API keys from .env if present
        load_dotenv(find_dotenv())
        # Ensure adapter import path
        sys.path.insert(0, os.path.abspath("src"))
        from llm_adapter.adapter import LLMAdapter  # type: ignore

        guard = (
            "You are a strict JSON reflow engine. Return ONLY a JSON object with keys: "
            "reflowed_json, ocr_corrections, improvements_made, summary. No code fences. "
            "Requirements: reflowed_json.blocks must preserve reading order and include: "
            "(a) a single merged table block when tables are fragmented/continued. The table title MUST start with 'INFERRED:'; "
            "(b) a figure block with a non-empty title, short caption, and image_ref when applicable. "
            "Always provide ocr_corrections and improvements_made; include summary."
        )
        context = "Section: 4.1.5.4. BHT (Branch History Table) submodule. Includes a branch history table and explanatory text."
        messages = [
            {"role": "user", "content": [{"type": "text", "text": f"{guard}\n\n{context}"}]}
        ]

        import asyncio

        adapter = LLMAdapter(logs_root=Path("logs"))
        res = asyncio.run(
            adapter.reflow_section(
                model=model,
                messages=messages,
                prompt_version=prompt_version,
                doc_id=doc_id,
                section_id=section_id,
                request_id="smoke07-text",
                timeout=timeout,
            )
        )
        if not isinstance(res.reflowed_json, dict) or "blocks" not in res.reflowed_json:
            raise RuntimeError("Missing reflowed_json.blocks")
        typer.echo("OK: Stage 07 text-only JSON returned")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
