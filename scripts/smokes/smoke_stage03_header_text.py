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


app = typer.Typer(add_completion=False, help="Smoke: Stage 03 header verify (text-only via adapter)")


@app.command()
def main(
    model: str = typer.Option(
        os.getenv(
            "LITELLM_DEFAULT_MODEL",
            os.getenv("DEFAULT_LITELLM_MODEL", "gemini/gemini-2.5-flash"),
        ),
        help="Model",
    ),
    prompt_version: str = typer.Option("header@0.1.0"),
    timeout: int = typer.Option(30),
):
    try:
        # Load API keys from .env if present
        load_dotenv(find_dotenv())
        sys.path.insert(0, os.path.abspath("src"))
        from llm_adapter.adapter import LLMAdapter  # type: ignore

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a header verification engine. Return ONLY JSON with keys {verdict, reasons}.\n"
                            "- verdict: one of ['accept','reject']\n"
                            "- reasons: array of short strings explaining the decision\n\n"
                            "Candidate: '4.1.5.4. BHT (Branch History Table) submodule'\n"
                            "Context: numbered, bold, spacing above."
                        ),
                    }
                ],
            }
        ]

        import asyncio
        adapter = LLMAdapter(logs_root=Path("logs"))
        res = asyncio.run(
            adapter.verify_header(
                model=model,
                messages=messages,
                prompt_version=prompt_version,
                doc_id="bht",
                section_id="hdr-1",
                request_id="smoke03-text",
                timeout=timeout,
            )
        )
        ok = (res.verdict in ("accept", "reject")) and isinstance(res.reasons, list)
        if not ok:
            raise RuntimeError("Invalid header verdict shape")
        typer.echo("OK: Stage 03 text-only header verdict returned")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
