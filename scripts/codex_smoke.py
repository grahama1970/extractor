#!/usr/bin/env python3
"""
Codex Exec Smoke Test

Launch a single codex exec instance in isolation, wait for completion, and
report a JSON result. This proves that we can:
 - spawn a codex child process
 - stream and capture stdout/stderr while it runs
 - wait until it completes (no IPC required)
 - surface return code and timing

Usage:
  python scripts/codex_smoke.py run --cmd "echo hello && sleep 0.2 && echo done" --shell --yolo

  # Python example
  python scripts/codex_smoke.py run --python -c "print('hello from codex')"

Exit codes:
  0 on success (child rc == 0), non‑zero otherwise. Always prints a JSON object.
"""
from __future__ import annotations

import asyncio
import json
from typing import List, Optional

import typer

from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec

app = typer.Typer(help="Codex exec smoke: launch one child and wait for completion.")


@app.command()
def run(
    cmd: Optional[str] = typer.Option(
        None, help="Shell command to run under codex (with --shell)."
    ),
    shell: bool = typer.Option(
        False, "--shell", help="Treat --cmd as a bash -lc payload (requires bash)."
    ),
    python_flag: bool = typer.Option(
        False, "--python", help="Run 'python' under codex instead of bash."
    ),
    args: List[str] = typer.Argument(
        None, help="Extra args (e.g., -c 'print(123)') when using --python."
    ),
    codex_bin: str = typer.Option("codex", help="codex CLI path"),
    yolo: bool = typer.Option(False, help="--dangerously-bypass-approvals-and-sandbox"),
) -> None:
    """Run a simple smoke under codex and print JSON with rc/stdout/stderr snippet."""
    # Determine launcher
    if shell:
        script = "bash"
        extra = ["-lc", cmd or "echo codex_smoke && sleep 0.1 && echo done"]
    elif python_flag:
        script = "python"
        extra = args or ["-c", "print('codex_smoke')"]
    else:
        # default to Python print
        script = "python"
        extra = ["-c", "print('codex_smoke')"]

    async def _go():
        res = await run_codex_exec(
            script_or_path=script,
            codex_bin=codex_bin,
            extra_args=extra,
            bypass_approvals_and_sandbox=yolo,
            overall_timeout_s=60.0,
            stdout_capture_limit=8 * 1024,
            stderr_capture_limit=8 * 1024,
        )
        out = {
            "ok": res.returncode == 0 and not res.timed_out and not res.idle_timed_out,
            "rc": res.returncode,
            "timed_out": res.timed_out,
            "idle_timed_out": res.idle_timed_out,
            "duration_s": round(res.duration_s, 3),
            "stdout": (res.stdout or "").strip()[:400],
            "stderr": (res.stderr or "").strip()[:400],
            "args": res.args,
        }
        print(json.dumps(out))
        raise SystemExit(0 if out["ok"] else 1)

    asyncio.run(_go())


if __name__ == "__main__":
    app()
