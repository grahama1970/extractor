#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
#   "rich>=13.7.1",
# ]
# ///
from __future__ import annotations

import os
import json
import asyncio
import typer
from rich.console import Console


app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def run(model: str = typer.Option(None, "--model", help="Model alias (default: LITELLM_LARGE_TEXT_MODEL)")):
    """Probe SciLLM Router text JSON on a single model."""
    import scillm  # type: ignore

    alias = model or os.getenv("LITELLM_LARGE_TEXT_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL")
    if not alias:
        console.print("[yellow]No model provided and no default found.[/yellow]")
        raise typer.Exit(1)

    req = {
        "model": alias,
        "messages": [{"role": "user", "content": "Return only {\"ok\":true} as JSON."}],
        "response_format": {"type": "json_object"},
        "timeout": 30,
        "api_key": os.getenv("CHUTES_API_KEY"),
        "api_base": os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1"),
        "custom_llm_provider": os.getenv("CHUTES_PROVIDER", "openai"),
    }

    async def _go():
        router = scillm.Router(deterministic=True)  # type: ignore
        res = await router.parallel_acompletions([req], max_concurrency=1)  # type: ignore
        content = res[0]["choices"][0]["message"]["content"] if res else ""
        ok = False
        if content:
            try:
                ok = json.loads(content).get("ok") is True
            except Exception:
                ok = False
        console.print(f"model={alias} ok={ok} snip={(content or '')[:100]}")
        raise typer.Exit(0 if ok else 1)

    asyncio.run(_go())


if __name__ == "__main__":
    app()

