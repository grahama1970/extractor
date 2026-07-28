#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger
import aiohttp

app = typer.Typer(
    help="Validate an HTTP API against a tasks JSON; emit score and post /ingest/episode."
)


async def _post_json(url: str, payload: Dict[str, Any]) -> None:
    """Post JSON payload to URL, logging warnings on failure."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status >= 400:
                    logger.warning(f"POST {url} -> HTTP {resp.status}")
    except Exception as e:
        logger.warning(f"POST failed {url}: {e}")


def _clamp01(x: float) -> float:
    """Clamp a float value within the range [0, 1]."""
    return max(0.0, min(1.0, x))


async def _run_episode(
    target: str,
    api_base: str,
    run_id: str,
    episode_id: str,
    variant: str,
    tasks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run an episode's tasks and return aggregated results."""
    errors_sample: List[str] = []
    warnings_sample: List[str] = []
    timings: List[float] = []
    successes = 0

    base = target.rstrip("/")
    async with aiohttp.ClientSession() as session:
        for i, task in enumerate(tasks, start=1):
            req: Dict[str, Any] = task.get("request") or task
            method = str(req.get("method", "GET")).upper()
            url = str(req.get("url") or (base + "/" + str(req.get("path", "")).lstrip("/")))
            headers = req.get("headers") or {}
            body = req.get("body")
            data: Any = None
            json_body: Any = None
            if isinstance(body, (dict, list)):
                json_body = body
            elif body is not None:
                data = str(body)

            expect = task.get("expect") or {}
            expect_status = expect.get("status", 200)
            if isinstance(expect_status, int):
                status_ok = {expect_status}
            elif isinstance(expect_status, (list, tuple, set)):
                status_ok = set(int(x) for x in expect_status)
            else:
                status_ok = {200}
            expect_json_contains = expect.get("json_contains") or {}

            t0 = time.monotonic()
            ok = False
            try:
                async with session.request(
                    method, url, headers=headers, json=json_body, data=data, timeout=30
                ) as resp:
                    status = int(resp.status)
                    text = await resp.text()
                    dt_ms = (time.monotonic() - t0) * 1000.0
                    timings.append(dt_ms)

                    if status in status_ok:
                        ok = True
                        if expect_json_contains:
                            try:
                                js = json.loads(text)
                                for k, v in expect_json_contains.items():
                                    if js.get(k) != v:
                                        ok = False
                                        errors_sample.append(f"field {k} mismatch")
                                        break
                            except Exception as e:
                                ok = False
                                errors_sample.append(f"json parse error: {e}")
                    else:
                        errors_sample.append(f"{method} {url} -> {status}")
            except Exception as e:
                dt_ms = (time.monotonic() - t0) * 1000.0
                timings.append(dt_ms)
                errors_sample.append(str(e))
                ok = False

            if ok:
                successes += 1

    # Metrics
    tasks_total = len(tasks)
    tasks_done = successes
    error_count = max(0, tasks_total - tasks_done)
    tpa_ms = (sum(timings) / max(1, len(timings))) if timings else 0.0
    wall_ms = sum(timings)

    # Score v1 (same shape as UI validator)
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
            "warnings": len(warnings_sample),
            "errors_sample": errors_sample[:3],
        },
        "error_count": error_count,
        "screenshots": [],
    }

    await _post_json(api_base.rstrip("/") + "/ingest/episode", payload)
    return {"ok": True, "score": payload["score"], "payload": payload}


@app.command()
def run(
    target: str = typer.Option(..., help="Base API URL, e.g. http://localhost:8001"),
    api_base: str = typer.Option("http://localhost:8000", help="Ingest API base (FastAPI server)"),
    run_id: str = typer.Option("run-api", help="Run identifier"),
    episode_id: str = typer.Option("e-0001", help="Episode identifier"),
    variant: str = typer.Option("variant", help="Variant name"),
    tasks_file: Path = typer.Option(
        ..., exists=True, readable=True, help="Tasks JSON file (list or object with 'tasks')"
    ),
):
    """Run an API command with specified parameters."""
    tasks = json.loads(Path(tasks_file).read_text())
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    assert isinstance(tasks, list), "tasks_file must be a JSON list or object with 'tasks' list"
    res = asyncio.run(_run_episode(target, api_base, run_id, episode_id, variant, tasks))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    # Allow both styles: `python validate_api.py --opts` and `python validate_api.py run --opts`
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        sys.argv.pop(1)
    app()
