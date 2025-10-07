#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12.3","httpx>=0.28.0","uvicorn>=0.30.6","fastapi>=0.115.0","rich>=13.7.1"]
# ///
from __future__ import annotations
import os, sys, threading, time
import typer, httpx
from fastapi import FastAPI
from pydantic import BaseModel
from rich.console import Console

app_cli = typer.Typer(add_completion=False)
console = Console()


class RunReq(BaseModel):
    tool_backend: str = "local"


def _start_local_mini_agent(host: str = "127.0.0.1", port: int = 18077) -> tuple[threading.Thread, str]:
    api = FastAPI()

    @api.get("/ready")
    def ready():
        return {"ok": True, "service": "mini-agent", "ts": time.time()}

    @api.post("/agent/run")
    def run(req: RunReq):
        return {"ok": True, "tool_backend": req.tool_backend, "ts": time.time()}

    import uvicorn

    def _serve():
        uvicorn.run(api, host=host, port=port, log_level="error")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    base = f"http://{host}:{port}"
    # wait a moment
    for _ in range(50):
        try:
            r = httpx.get(base + "/ready", timeout=0.2)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.05)
    return t, base


@app_cli.command()
def main(base: str = typer.Option(os.getenv("MINI_AGENT_BASE", ""), help="Mini-agent base URL")):
    started = None
    if not base:
        t, base = _start_local_mini_agent()
        started = t
        console.print(f"[dim]Started local mini-agent at {base}[/dim]")

    ok = True
    try:
        r1 = httpx.get(base + "/ready", timeout=5)
        console.print(f"GET /ready -> {r1.status_code} {r1.text[:120]}")
        ok = ok and r1.status_code == 200 and r1.json().get("ok") is True
        r2 = httpx.post(base + "/agent/run", json={"tool_backend":"local"}, timeout=5)
        console.print(f"POST /agent/run -> {r2.status_code} {r2.text[:120]}")
        ok = ok and r2.status_code == 200 and r2.json().get("ok") is True
    except Exception as e:
        console.print(f"[red]Mini-agent check failed:[/red] {e}")
        ok = False

    if started:
        console.print("[dim]Local mini-agent test complete.[/dim]")

    raise typer.Exit(0 if ok else 1)


if __name__ == "__main__":
    app_cli()

