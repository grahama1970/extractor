#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.0",
# ]
# ///

from __future__ import annotations

import json
import os
import time
from typing import Any

import typer

app = typer.Typer(add_completion=False, help="Health smoke for LEAN4_PROVER_MODEL via scillm")


@app.command()
def main(
    model: str = typer.Option(
        os.getenv("LEAN4_PROVER_MODEL", os.getenv("LEAN4_MODEL", "certainly/lean4")), "--model"
    ),
    timeout: int = typer.Option(60, "--timeout"),
) -> None:
    base = (os.getenv("CHUTES_API_BASE") or "").strip()
    key = (os.getenv("CHUTES_API_KEY") or "").strip()
    if not (base and key):
        raise typer.Exit(code=2)
    try:
        from scillm import completion
    except Exception as e:
        typer.echo(json.dumps({"ok": False, "error": f"scillm import failed: {e}"}, indent=2))
        raise typer.Exit(code=2)

    prompt = (
        "Return STRICT JSON only with keys: success(bool), lean_code(string), stdout(string), stderr(string), proof_output(string|null).\n"
        "Use an extremely simple requirement like '1+1=2' in Lean 4."
    )
    messages = [
        {
            "role": "system",
            "content": "You are a Lean 4 prover service returning STRICT JSON only.",
        },
        {"role": "user", "content": prompt},
    ]
    t0 = time.time()
    resp = completion(
        model=model,
        api_base=base,
        api_key=None,
        messages=messages,
        response_format={"type": "json_object"},
        api_key=key,
        timeout=timeout,
        temperature=0,
    )
    dt = time.time() - t0
    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
    try:
        obj: dict[str, Any] = json.loads(content) if isinstance(content, str) else {}
    except Exception:
        obj = {}
    ok = bool(
        isinstance(obj, dict)
        and set(["success", "lean_code", "stdout", "stderr"]).issubset(obj.keys())
    )
    out = {
        "ok": ok,
        "elapsed_sec": round(dt, 3),
        "model": model,
        "schema_ok": ok,
        "raw": obj if ok else (content[:200] if isinstance(content, str) else str(type(content))),
    }
    typer.echo(json.dumps(out, indent=2))
    raise typer.Exit(code=0 if ok else 1)


if __name__ == "__main__":
    app()
