#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path
import urllib.request
import urllib.error
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: POST UI annotations to pipeline server and expect run summary")


def _wait_http(url: str, timeout: float = 12.0) -> None:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            with urllib.request.urlopen(url) as _:
                return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for {url}")


@app.command()
def main(
    pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True),
    port: int = typer.Option(8002),
):
    load_dotenv(find_dotenv() or None)
    env = os.environ.copy()
    # Launch the pipeline bridge server
    server = subprocess.Popen([
        env.get("PYTHON", "python"),
        "-m",
        "prototypes.tabbed.api.pipeline_server",
    ], env=env)
    try:
        _wait_http(f"http://127.0.0.1:{port}/openapi.json")
        payload = {
            "pdf_path": str(pdf),
            "boxes_by_page": {
                1: [ {"id": "t1", "type": "Table", "x": 0.15, "y": 0.40, "w": 0.70, "h": 0.40} ]
            }
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/pipeline/run-external",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        if not j.get("ok"):
            raise SystemExit("pipeline server returned not ok")
        summary = Path("scripts/artifacts/run_summary_happy.json")
        if not summary.exists():
            raise SystemExit("run summary not found")
        sj = json.loads(summary.read_text())
        if sj.get("score") is None:
            raise SystemExit("run summary missing score")
        typer.echo("OK: pipeline server accepted external annotations and produced a run summary")
    finally:
        try:
            server.send_signal(signal.SIGTERM)
            server.wait(timeout=5)
        except Exception:
            try:
                server.kill()
            except Exception:
                pass


if __name__ == "__main__":
    app()

