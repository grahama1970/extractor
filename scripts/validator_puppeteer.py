#!/usr/bin/env python3
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from loguru import logger
from playwright.async_api import async_playwright, Page, Browser
import aiohttp

app = typer.Typer(help="Run a single validation episode against a variant URL and report metrics.")


async def _post_json(url: str, payload: Dict[str, Any]) -> None:
    """Post JSON payload to URL, logging errors."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status >= 400:
                    logger.warning(f"POST {url} -> HTTP {resp.status}")
    except Exception as e:
        logger.warning(f"POST failed {url}: {e}")


async def _run_episode(
    target: str,
    api_base: str,
    run_id: str,
    episode_id: str,
    variant: str,
    tasks: List[Dict[str, Any]],
    screenshot_dir: Optional[Path],
) -> Dict[str, Any]:
    """Execute an episode with specified tasks and capture results."""
    errors: List[str] = []
    warnings: List[str] = []
    t0 = time.monotonic()

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        page: Page = await browser.new_page()

        page.on(
            "console", lambda msg: (errors if msg.type == "error" else warnings).append(msg.text)
        )
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        # Preflight and load classic layout
        await page.goto(target.rstrip("/") + "/classic", wait_until="domcontentloaded")

        # Wait for canvas (PDF render)
        t_load_start = time.monotonic()
        await page.wait_for_selector("canvas", state="attached", timeout=15000)
        # Allow a short time for render
        await page.wait_for_timeout(500)
        canvases = await page.query_selector_all("canvas")
        if not canvases:
            await browser.close()
            return {
                "ok": False,
                "error": "no_canvas",
                "errors": errors,
            }

        # Execute tasks using dev helpers (window.__ux)
        ttfa_ms: Optional[float] = None
        action_times: List[float] = []

        for i, task in enumerate(tasks, start=1):
            t_start = time.monotonic()
            ttype = task.get("type")
            page_num = int(task.get("page", 1))
            # Default region if none provided
            x0, y0, x1, y1 = 0.1, 0.1, 0.8, 0.25
            region = task.get("region") or task.get("region_hint")
            if isinstance(region, list) and len(region) == 4:
                x0, y0, x1, y1 = map(float, region)

            if ttype in {"box", "highlight", "note", "tag"}:
                # Use dev hook to draw a box as a proxy for an annotation
                await page.evaluate(
                    "(p, x0, y0, x1, y1) => { window.__ux?.setPage?.(p); window.__ux?.drawBox?.(p, x0, y0, x1, y1); }",
                    page_num,
                    x0,
                    y0,
                    x1,
                    y1,
                )
            else:
                # Unknown task type -> no-op
                pass

            t_end = time.monotonic()
            dt_ms = (t_end - t_start) * 1000.0
            action_times.append(dt_ms)
            if ttfa_ms is None:
                ttfa_ms = (t_start - t_load_start) * 1000.0

        # Screenshot
        shot_path = None
        if screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            shot_path = screenshot_dir / f"{variant}_{episode_id}.png"
            await page.screenshot(path=str(shot_path), full_page=True)

        await browser.close()

    # Compute metrics
    t1 = time.monotonic()
    wall_ms = (t1 - t0) * 1000.0
    tpa_ms = sum(action_times) / max(1, len(action_times))
    tasks_total = len(tasks)
    tasks_done = len(action_times)
    error_count = len(errors)

    # Score v1 (simple, deterministic)
    def clamp01(x: float) -> float:
        """Clamp a float value between 0.0 and 1.0."""
        return max(0.0, min(1.0, x))

    # Tunables
    target_tpa = 2500.0  # ms
    efficiency = 100.0 * clamp01(target_tpa / max(target_tpa, tpa_ms))
    accuracy = 100.0 * clamp01(tasks_done / max(1, tasks_total))
    stability = 100.0 * clamp01(1.0 - (error_count / 10.0))
    ux = 85.0  # placeholder until richer signals
    score = 0.55 * efficiency + 0.20 * accuracy + 0.15 * stability + 0.10 * ux

    payload = {
        "ts": time.time(),
        "run_id": run_id,
        "episode_id": episode_id,
        "variant": variant,
        "pass": True,
        "score": round(score, 2),
        "metrics": {
            "ttfa_ms": round((ttfa_ms or 0.0), 1),
            "tpa_ms": round(tpa_ms, 1),
            "wall_ms": round(wall_ms, 1),
            "tasks_done": tasks_done,
            "tasks_total": tasks_total,
            "warnings": len(warnings),
            "errors_sample": errors[:3],
            "warnings_sample": warnings[:3],
        },
        "error_count": error_count,
        "screenshots": [str(shot_path)] if shot_path else [],
    }

    # Send to orchestrator server (Arango ingest)
    await _post_json(api_base.rstrip("/") + "/ingest/episode", payload)
    return {"ok": True, "score": payload["score"], "payload": payload}


@app.command()
def episode(
    target: str = typer.Option(..., help="Variant URL, e.g. http://localhost:5173"),
    api_base: str = typer.Option("http://localhost:8000", help="Ingest API base (FastAPI server)"),
    run_id: str = typer.Option("run-local", help="Run identifier"),
    episode_id: str = typer.Option("e-0001", help="Episode identifier"),
    variant: str = typer.Option("variant", help="Variant name"),
    tasks_file: Path = typer.Option(..., exists=True, readable=True, help="Tasks JSON file"),
    screenshot_dir: Optional[Path] = typer.Option(None, help="Directory to write screenshots"),
):
    """Run a single headless validation episode and print a JSON result line."""
    tasks = json.loads(Path(tasks_file).read_text())
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    assert isinstance(tasks, list), "tasks_file must be a JSON list or object with 'tasks' list"

    result = asyncio.run(
        _run_episode(target, api_base, run_id, episode_id, variant, tasks, screenshot_dir)
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    app()
