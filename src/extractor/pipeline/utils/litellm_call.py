"""
Thin, test-oriented CLI and helpers compatible with prior `litellm_call` usage.

Notes
- Real model routing lives in `scillm_router.py` (SciLLM first). This module
  only provides a stable interface for tests and simple local usage.
- Tests monkeypatch `litellm_call`, so the default implementation here is best
  effort and conservative.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import typer

from extractor.pipeline.utils.reliability import log_stage_error

# Default model pin (purely a placeholder for tests)
MODEL = "chutes:text:default"


def _to_messages_and_model(
    item: Dict[str, Any], default_model: str
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """Extract `(model, messages, extras)` from a single work item.

    - Preserves extra kwargs (e.g., temperature) exactly as provided.
    - Falls back to `default_model` when `item.get("model")` is missing.
    """
    model = item.get("model") or default_model
    messages = item.get("messages") or []
    extras = {k: v for k, v in item.items() if k not in {"model", "messages"}}
    return model, messages, extras


async def litellm_call(prompts: List[Any], **kwargs) -> List[str]:
    """Best-effort default implementation (tests monkeypatch this).

    Attempts to route via SciLLM Router if available, otherwise echoes.
    The surface matches tests that pass `wrap_json` and `response_format`.
    """
    # Lazy import to avoid hard dependency in test collection
    try:
        from .scillm_router import get_text_router
    except Exception as exc:
        log_stage_error("litellm_call.py", exc, {"context": "litellm_call.py"})
        raise
        get_text_router = None  # type: ignore

    if not get_text_router:
        # Fallback: echo content for sanity
        outs: List[str] = []
        for i, p in enumerate(prompts):
            text = (
                json.dumps(p)
                if not isinstance(p, (str, bytes))
                else (p.decode() if isinstance(p, bytes) else p)
            )
            outs.append(str(text))
        return outs

    # SciLLM path (one-by-one to keep it simple)
    router = get_text_router()
    out: List[str] = []
    wrap_json = bool(kwargs.get("wrap_json"))
    response_format = kwargs.get("response_format")
    for p in prompts:
        # Normalize prompt to messages list
        if isinstance(p, dict) and "messages" in p:
            _, messages, _ = _to_messages_and_model(p, MODEL)
        elif isinstance(p, str):
            messages = [{"role": "user", "content": p}]
        else:
            messages = [{"role": "user", "content": json.dumps(p)}]

        params: Dict[str, Any] = {"messages": messages}
        if response_format:
            params["response_format"] = {"type": str(response_format)}
        try:
            resp = await router.acompletion(**params)
            # Minimal text extraction; avoid importing the full utils here
            text = (
                resp.get("choices", [{}])[0].get("message", {}).get("content", "")
                if isinstance(resp, dict)
                else getattr(getattr(resp, "choices", [None])[0], "text", "")
            )
            if not isinstance(text, str):
                text = json.dumps(text)
            if wrap_json and (not _looks_like_json(text)):
                out.append(json.dumps({"content": text}))
            else:
                out.append(text)
        except Exception as exc:
            log_stage_error("litellm_call.py", exc, {"context": "litellm_call.py"})
            raise
    return out


def _looks_like_json(s: str) -> bool:
    """Check if a string is a valid JSON format."""
    s2 = s.strip()
    if not s2:
        return False
    if s2[0] in "[{" and s2[-1] in "]}":
        try:
            json.loads(s2)
            return True
        except Exception as exc:
            log_stage_error("litellm_call.py", exc, {"context": "litellm_call.py"})
            raise
            return False
    return False


def _read_stdin_lines() -> List[str]:
    """Read non-empty lines from standard input."""
    data = sys.stdin.read()
    return [line for line in data.splitlines() if line.strip()]


def build_cli() -> typer.Typer:
    """Build a LiteLLM-compatible CLI wrapper with optional JSON wrapping."""
    app = typer.Typer(add_completion=False, help="LiteLLM-compatible CLI wrapper (SciLLM-backed)")

    @app.command()
    def sanity(
        wrap_json: bool = typer.Option(
            False, "--wrap-json", help="Wrap non-JSON output as {content}"
        )
    ) -> None:
        """Minimal sanity call (tests monkeypatch `litellm_call`)."""
        prompt = {
            "model": MODEL,
            "messages": [{"role": "user", "content": 'Return only {"ok":true} as JSON.'}],
        }

        async def _run():
            return await litellm_call([prompt], wrap_json=wrap_json, response_format="json_object")

        outs = asyncio.run(_run())
        print((outs[0] if outs else "").strip())

    @app.command()
    def main(
        sources: List[str] = typer.Argument(None),
        stdin: bool = typer.Option(False, "--stdin", help="Read prompts (one per line) from stdin"),
        json_shorthand: bool = typer.Option(
            False, "--json", help="Shorthand for --wrap-json + --response-format json_object"
        ),
        wrap_json: bool = typer.Option(
            False, "--wrap-json", help="Wrap non-JSON output as {content}"
        ),
        response_format: str | None = typer.Option(
            None, "--response-format", help="Response format type, e.g., json_object"
        ),
        quiet: bool = typer.Option(False, "--quiet", help="Suppress stdout (use with --output)"),
        output: Path | None = typer.Option(
            None, "--output", help="Write outputs (one per line) to file"
        ),
    ) -> None:
        # Apply shorthand
        if json_shorthand:
            wrap_json = True
            response_format = "json_object"

        prompts: List[str]
        if stdin:
            prompts = _read_stdin_lines()
        else:
            prompts = [s for s in (sources or []) if s is not None]

        async def _run():
            return await litellm_call(
                prompts,
                wrap_json=wrap_json,
                response_format=response_format,
            )

        outs = asyncio.run(_run())
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("\n".join(outs) + ("\n" if outs else ""))
        if not quiet:
            for line in outs:
                print(line)

    return app


def cli_main() -> None:
    """Execute the command-line interface."""
    build_cli()()


__all__ = ["MODEL", "_to_messages_and_model", "litellm_call", "build_cli", "cli_main"]
