#!/usr/bin/env python3
"""
Codex Prompt Smoke Test

Goal: Launch one codex exec process with a simple Python snippet that reads a
prompt file and prints a compact JSON acknowledgement. We wait for completion
and print a top-level JSON with ok/rc/timing and the child JSON echo.

Usage:
  python scripts/codex_prompt_smoke.py run --prompt-file prototypes/gamified/docs/prompt_multiplication_poc.md --yolo

Notes:
  - This does NOT interpret the prompt; it proves 'codex exec' runs, can read the prompt file,
    and that we can wait for completion and parse its output deterministically.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer

from extractor.pipeline.utils.codex_call import run_codex_exec

app = typer.Typer(help="Smoke: launch one codex instance with a prompt file and wait.")


@app.command()
def run(
    prompt_file: Path = typer.Option(..., exists=True, help="Path to a prompt Markdown file"),
    codex_bin: str = typer.Option("codex", help="Path to codex CLI"),
    yolo: bool = typer.Option(False, "--yolo", help="--dangerously-bypass-approvals-and-sandbox"),
) -> None:
    """Run codex exec to read the prompt file and print a small JSON report."""

    # Child code: read a file and return JSON { ok, bytes, head }
    child = (
        "import sys, json, pathlib; "
        "p=pathlib.Path(sys.argv[1]); "
        "txt=p.read_text(encoding='utf-8'); "
        "head=txt[:200]; "
        "print(json.dumps({'ok': True, 'bytes': len(txt), 'head': head}))"
    )

    async def _go():
        res = await run_codex_exec(
            script_or_path="python",
            codex_bin=codex_bin,
            extra_args=["-c", child, str(prompt_file)],
            bypass_approvals_and_sandbox=yolo,
            overall_timeout_s=60.0,
            stdout_capture_limit=16 * 1024,
            stderr_capture_limit=16 * 1024,
        )
        child_json: Optional[dict] = None
        try:
            # Parse last non-empty line of stdout as JSON
            out = (res.stdout or "").strip().splitlines()
            if out:
                child_json = json.loads(out[-1])
        except Exception:
            child_json = None
        top = {
            "ok": (res.returncode == 0 and child_json is not None and child_json.get("ok") is True),
            "rc": res.returncode,
            "duration_s": round(res.duration_s, 3),
            "child": child_json,
            "stderr_tail": (res.stderr or "").strip()[-200:],
        }
        print(json.dumps(top))
        raise SystemExit(0 if top["ok"] else 1)

    asyncio.run(_go())


if __name__ == "__main__":
    app()

