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
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 09 summary (adapter strict JSON)")


@app.command()
def main(
    model: str = typer.Option(
        os.getenv(
            "LITELLM_DEFAULT_MODEL",
            os.getenv("DEFAULT_LITELLM_MODEL", "gemini/gemini-2.5-flash"),
        ),
        help="Model",
    ),
    prompt_version: str = typer.Option("summary@0.1.0"),
    timeout: int = typer.Option(30),
):
    try:
        # Load API keys from .env if present
        load_dotenv(find_dotenv())
        sys.path.insert(0, os.path.abspath("src"))
        from llm_adapter.adapter import LLMAdapter  # type: ignore

        text = "This section explains the Branch History Table (BHT) component and its behavior."
        messages = [{"role": "user", "content": [{"type": "text", "text": text}]}]
        import asyncio
        adapter = LLMAdapter()
        res = asyncio.run(
            adapter.summarize_section(
                model=model,
                messages=messages,
                prompt_version=prompt_version,
                doc_id="doc", section_id="s0", request_id="smoke09", timeout=timeout,
            )
        )
        sj = res.summary_json
        ok = isinstance(sj, dict) and "bullets" in sj
        if not ok:
            raise RuntimeError("Invalid summary_json")
        typer.echo("OK: Stage 09 strict JSON summary returned")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
