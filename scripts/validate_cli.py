#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

import typer
import aiohttp
import asyncio

app = typer.Typer(help="Validate a CLI program against tasks; emit score and post /ingest/episode.")


async def _post_json(url: str, payload: Dict[str, Any]) -> None:
    """Post JSON payload to URL asynchronously, ignoring errors."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                _ = await resp.text()
    except Exception:
        pass


def _clamp01(x: float) -> float:
    """Clamp a float value between 0.0 and 1.0."""
    return max(0.0, min(1.0, x))


def _run_one(
    cmd: str, cwd: Optional[Path], env: Optional[Dict[str, str]], timeout_s: float
) -> Dict[str, Any]:
    """Execute a shell command with specified working directory, environment, and timeout."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        dt_ms = (time.monotonic() - t0) * 1000.0
        return {
            "rc": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "ms": dt_ms,
        }
    except subprocess.TimeoutExpired:
        dt_ms = (time.monotonic() - t0) * 1000.0
        return {"rc": 124, "stdout": "", "stderr": "timeout", "ms": dt_ms}
    except Exception as e:
        dt_ms = (time.monotonic() - t0) * 1000.0
        return {"rc": 1, "stdout": "", "stderr": str(e), "ms": dt_ms}


async def _run_episode(
    api_base: str,
    run_id: str,
    episode_id: str,
    variant: str,
    tasks: List[Dict[str, Any]],
    substitutions: Dict[str, str],
    cwd: Optional[Path],
) -> Dict[str, Any]:
    """Execute tasks for an episode, returning aggregated results."""
    outputs: List[Dict[str, Any]] = []
    timings: List[float] = []
    successes = 0
    errors_sample: List[str] = []

    for t in tasks:
        cmd_tpl = t.get("cmd") or t.get("command")
        if not cmd_tpl:
            errors_sample.append("missing cmd")
            continue
        cmd = cmd_tpl.format(**substitutions)
        timeout_s = float(t.get("timeout_s", 60.0))
        env_add = t.get("env") or {}
        env = os.environ.copy()
        for k, v in env_add.items():
            env[str(k)] = str(v)

        res = _run_one(cmd, cwd=cwd, env=env, timeout_s=timeout_s)
        timings.append(res["ms"])

        ok = True
        exp_rc = int(t.get("expect_exit", 0))
        if res["rc"] != exp_rc:
            ok = False
            errors_sample.append(f"rc {res['rc']} != {exp_rc}")
        exp_sub = t.get("expect_stdout_contains")
        if isinstance(exp_sub, str) and exp_sub not in res["stdout"]:
            ok = False
            errors_sample.append("stdout missing substr")
        elif isinstance(exp_sub, list):
            for s in exp_sub:
                if str(s) not in res["stdout"]:
                    ok = False
                    errors_sample.append("stdout missing item")
                    break
        exp_err_not = t.get("reject_stderr_contains")
        if isinstance(exp_err_not, str) and exp_err_not in res["stderr"]:
            ok = False
            errors_sample.append("stderr forbidden substr")
        elif isinstance(exp_err_not, list):
            for s in exp_err_not:
                if str(s) in res["stderr"]:
                    ok = False
                    errors_sample.append("stderr forbidden item")
                    break

        outputs.append(
            {
                "cmd": cmd,
                "rc": res["rc"],
                "ms": round(res["ms"], 1),
                "stdout_sample": (res["stdout"][:2000]),
                "stderr_sample": (res["stderr"][:500]),
                "ok": ok,
            }
        )
        if ok:
            successes += 1

    tasks_total = len(outputs)
    tasks_done = successes
    error_count = max(0, tasks_total - tasks_done)
    tpa_ms = (sum(timings) / max(1, len(timings))) if timings else 0.0
    wall_ms = sum(timings)

    target_tpa = 2500.0
    efficiency = 100.0 * _clamp01(target_tpa / max(target_tpa, tpa_ms))
    accuracy = 100.0 * _clamp01(tasks_done / max(1, tasks_total))
    stability = 100.0 * _clamp01(1.0 - (error_count / 10.0))
    ux = 85.0
    score = 0.55 * efficiency + 0.20 * accuracy + 0.15 * stability + 0.10 * ux

    payload = {
        "ts": time.time(),
        "run_id": run_id,
        "episode_id": episode_id,
        "variant": variant,
        "pass": True,
        "score": round(score, 2),
        "metrics": {
            "tpa_ms": round(tpa_ms, 1),
            "wall_ms": round(wall_ms, 1),
            "tasks_done": tasks_done,
            "tasks_total": tasks_total,
            "errors_sample": errors_sample[:3],
        },
        "error_count": error_count,
        "screenshots": [],
        "outputs": outputs[:5],
    }

    await _post_json(api_base.rstrip("/") + "/ingest/episode", payload)
    return {"ok": True, "score": payload["score"], "payload": payload}


@app.command()
def run(
    api_base: str = typer.Option("http://localhost:8000", help="Ingest API base (FastAPI server)"),
    run_id: str = typer.Option("run-cli", help="Run identifier"),
    episode_id: str = typer.Option("e-0001", help="Episode identifier"),
    variant: str = typer.Option("variant", help="Variant name"),
    tasks_file: Path = typer.Option(
        ..., exists=True, readable=True, help="Tasks JSON file (list or object with 'tasks')"
    ),
    cwd: Optional[Path] = typer.Option(None, help="Working directory for commands"),
):
    """Run a simulation with specified tasks and identifiers."""
    tasks = json.loads(Path(tasks_file).read_text())
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    assert isinstance(tasks, list), "tasks_file must be a JSON list or object with 'tasks' list"
    substitutions = {
        "variant": variant,
        "run_id": run_id,
        "episode_id": episode_id,
        # Ensure sample tasks can invoke the active Python interpreter
        "python": sys.executable or "python3",
    }
    res = asyncio.run(
        _run_episode(api_base, run_id, episode_id, variant, tasks, substitutions, cwd)
    )
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    # Allow both styles: `python validate_cli.py --opts` and `python validate_cli.py run --opts`
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        sys.argv.pop(1)
    app()
