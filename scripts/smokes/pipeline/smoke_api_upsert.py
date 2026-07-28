#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
from __future__ import annotations

import json
import sys
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
    add_completion=False, help="Smoke: run external → upsert (Stage 10→11) via API server"
)


def _wait_http(url: str, timeout: float = 15.0) -> None:
    """Wait for a URL to become accessible within a timeout period."""
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
    """Start the Tabbed API server, run extract (external annotations), then upsert to Arango.

    Requires ArangoDB creds in the environment (.env is loaded automatically).
    """
    load_dotenv(find_dotenv() or None)
    env = os.environ.copy()

    # Launch FastAPI server (uvicorn)
    venv_py = sys.executable
    env["PYTHON"] = venv_py
    server = subprocess.Popen(
        [
            venv_py,
            "-m",
            "uvicorn",
            "prototypes.tabbed.api.server:app",
            f"--port={port}",
            "--host=127.0.0.1",
            "--log-level=error",
        ],
        env=env,
    )
    try:
        _wait_http(f"http://127.0.0.1:{port}/openapi.json")
        # 1) Extract via run-external (minimal single box)
        payload = {
            "pdf_path": str(pdf),
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
        with urllib.request.urlopen(req, timeout=900) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        if not j.get("ok"):
            raise SystemExit("run-external returned not ok")
        results_dir = Path(j.get("results_dir") or "")
        if not results_dir.exists():
            raise SystemExit("results_dir missing after run-external")

        # 2) Upsert to Arango (Stage 10→11)
        up = json.dumps({"results_dir": str(results_dir), "fast_embeddings": True}).encode("utf-8")
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/pipeline/upsert",
            data=up,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=600) as resp2:
            j2 = json.loads(resp2.read().decode("utf-8"))
        if not j2.get("ok"):
            raise SystemExit("upsert endpoint returned not ok")

        # Confirm files exist and carry sane counts
        conf10 = Path(j2.get("export_confirmation") or "")
        conf11 = Path(j2.get("graph_confirmation") or "")
        if not (conf10.exists() and conf11.exists()):
            raise SystemExit("confirmation files missing after upsert")
        c10 = json.loads(conf10.read_text())
        created = int(c10.get("documents_created", 0))
        updated = int(c10.get("documents_updated", 0))
        if (created + updated) <= 0:
            raise SystemExit("no documents created or updated in Stage 10 export")
        c11 = json.loads(conf11.read_text())
        if c11.get("edges_created") is None:
            raise SystemExit("Stage 11 confirmation missing edges_created")

        # Save a tiny artifact log for CI
        artifacts = Path("scripts/artifacts")
        artifacts.mkdir(parents=True, exist_ok=True)
        log = artifacts / f"smoke_api_upsert_{int(time.time())}.log"
        log.write_text(
            json.dumps(
                {
                    "ok": True,
                    "results_dir": str(results_dir),
                    "export_confirmation": str(conf10),
                    "graph_confirmation": str(conf11),
                    "created": created,
                    "updated": updated,
                    "edges": c11.get("edges_created"),
                },
                indent=2,
            )
        )
        typer.echo(f"OK: upsert smoke passed → {log}")
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
