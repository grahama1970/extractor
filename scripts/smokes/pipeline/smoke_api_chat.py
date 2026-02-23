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
    add_completion=False, help="Smoke: chat/query returns an answer for current PDF after upsert"
)


def _wait_http(url: str, timeout: float = 18.0) -> None:
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
    port: int = typer.Option(8003),
):
    load_dotenv(find_dotenv() or None)
    env = os.environ.copy()

    server = subprocess.Popen(
        [
            os.environ.get("PYTHON", os.sys.executable),
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
        # Extract first
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

        # Upsert
        up = json.dumps({"results_dir": j.get("results_dir"), "fast_embeddings": True}).encode(
            "utf-8"
        )
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

        # Chat
        cq = json.dumps({"q": "What is BHT?", "pdf": pdf.name}).encode("utf-8")
        req3 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/chat/query",
            data=cq,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req3, timeout=60) as resp3:
            j3 = json.loads(resp3.read().decode("utf-8"))
        if not (j3.get("ok") and (j3.get("answer") or "")):
            raise SystemExit("chat query returned empty answer")

        artifacts = Path("scripts/artifacts")
        artifacts.mkdir(parents=True, exist_ok=True)
        out = artifacts / f"smoke_api_chat_{int(time.time())}.log"
        out.write_text(
            json.dumps(
                {"ok": True, "answer": j3.get("answer"), "citations": j3.get("citations")}, indent=2
            )
        )
        typer.echo(f"OK: chat smoke passed → {out}")
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
