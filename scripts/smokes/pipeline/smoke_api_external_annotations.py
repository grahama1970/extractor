#!/usr/bin/env python3
"""Smoke: POST UI annotations to pipeline server and expect run summary.

Run with the repo virtualenv to use the pinned dependencies:

    source .venv/bin/activate && PYTHONPATH=src \\
      python scripts/smokes/pipeline/smoke_api_external_annotations.py
"""
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


app = typer.Typer(
    add_completion=False,
    help="Smoke: POST UI annotations to pipeline server and expect run summary",
)


def _wait_http(url: str, timeout: float = 25.0) -> None:
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
    import sys

    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = src_path + (
        ":" + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else ""
    )
    runner = sys.executable
    # Launch the pipeline bridge server
    server = subprocess.Popen(
        [
            runner,
            "-m",
            "prototypes.tabbed.api.pipeline_server",
        ],
        env=env,
    )
    try:
        _wait_http(f"http://127.0.0.1:{port}/openapi.json")
        payload = {
            "pdf_path": str(pdf),
            "mode": "deterministic",  # keep smoke fast and offline
            "boxes_by_page": {
                1: [{"id": "t1", "type": "Table", "x": 0.15, "y": 0.40, "w": 0.70, "h": 0.40}]
            },
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
            raise SystemExit(f"pipeline server returned not ok: {j}")
        results_dir = Path(j.get("results_dir") or "")
        if not results_dir or not results_dir.exists():
            raise SystemExit("results_dir missing in response")
        # Assert key artifacts exist for usefulness
        sections = results_dir / "04_section_builder" / "json_output" / "04_sections.json"
        tables = results_dir / "05_table_extractor" / "json_output" / "05_tables.json"
        report = results_dir / "final_report.json"
        audit = results_dir / "09b_audit" / "json_output" / "09b_audit.json"
        if not sections.exists():
            raise SystemExit("sections json not found")
        if not tables.exists():
            raise SystemExit("tables json not found")
        if not report.exists():
            raise SystemExit("final report not found")
        if not audit.exists():
            raise SystemExit("audit report not found")
        typer.echo(f"OK: run completed in {results_dir}")
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
