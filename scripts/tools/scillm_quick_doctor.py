#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
#   "rich>=13.7.1",
#   "scillm>=0.1.0",
# ]
# ///

"""
SciLLM Quick Doctor: verifies a minimal Chutes chat JSON round-trip.

Behavior
- Reads CHUTES_API_BASE, CHUTES_API_KEY, CHUTES_TEXT_MODEL from env by default.
- Optionally accepts --base/--key/--model overrides.
- Unsets conflicting OPENAI_* envs to avoid Bearer paths.
    - Uses scillm.completion directly on an OpenAI-compatible Chutes path (x-api-key).
- Prints a single JSON object to stdout and exits 0 on success; non-zero on failure.
"""

from __future__ import annotations

import json
import os
import warnings
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

import typer


app = typer.Typer(add_completion=False)


@dataclass
class DoctorResult:
    ok: bool
    method: str
    base: str
    model: str
    had_openai_env: bool
    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _unset_openai_envs() -> bool:
    keys = [
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "OPENAI_ORG_ID",
    ]
    had_any = any(os.environ.get(k) for k in keys)
    for k in keys:
        if k in os.environ:
            os.environ.pop(k, None)
    return had_any


def _call_direct(base: str, key: str, model: str) -> Dict[str, Any]:
    from scillm import completion  # type: ignore

    # Single paved call: let SciLLM canonicalize headers
    return completion(
        model=model,
        api_base=base.rstrip("/"),
        api_key=key,
        custom_llm_provider="openai_like",
        messages=[
            {
                "role": "user",
                "content": 'Return only {"ok":true} as JSON.',
            }
        ],
        response_format={"type": "json_object"},
        timeout=60,
    )


@app.command()
def main(
    base: Optional[str] = typer.Option(None, "--base", help="Override CHUTES_API_BASE"),
    key: Optional[str] = typer.Option(None, "--key", help="Override CHUTES_API_KEY"),
    model: Optional[str] = typer.Option(None, "--model", help="Override CHUTES_TEXT_MODEL"),
):
    env_base = base or os.environ.get("CHUTES_API_BASE", "").strip()
    env_key = key or os.environ.get("CHUTES_API_KEY", "").strip()
    env_model = model or os.environ.get("CHUTES_TEXT_MODEL", "").strip()

    if not env_base or not env_key or not env_model:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Missing CHUTES_API_BASE, CHUTES_API_KEY, or CHUTES_TEXT_MODEL",
                }
            )
        )
        raise typer.Exit(code=2)

    had_openai_env = _unset_openai_envs()

    warnings.filterwarnings("ignore", message="Pydantic serializer warnings:")

    # Direct path only
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Task was destroyed but it is pending")
            warnings.filterwarnings("ignore", "Pydantic serializer warnings")
            raw = _call_direct(env_base, env_key, env_model)
        content = raw["choices"][0]["message"]["content"]
        ok = False
        if isinstance(content, dict):
            ok = content == {"ok": True}
        elif isinstance(content, str):
            try:
                ok = json.loads(content) == {"ok": True}
            except Exception:
                ok = False
        print(
            DoctorResult(
                ok=ok,
                method="direct",
                base=env_base,
                model=env_model,
                had_openai_env=had_openai_env,
                error=None if ok else "unexpected_content",
                raw=None if ok else {"snippet": str(content)[:80]},
            ).to_json()
        )
    except Exception as e:
        err = f"{type(e).__name__}: {e!r}"
        print(
            DoctorResult(
                ok=False,
                method="direct",
                base=env_base,
                model=env_model,
                had_openai_env=had_openai_env,
                error=err,
                raw=None,
            ).to_json()
        )
        raise typer.Exit(code=2)
    else:
        raise typer.Exit(code=0 if ok else 3)


if __name__ == "__main__":  # pragma: no cover
    app()
