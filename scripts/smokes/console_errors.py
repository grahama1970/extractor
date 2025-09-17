from __future__ import annotations
import os, sys, pathlib, requests
from typing import List
import typer
from playwright.sync_api import sync_playwright, Page

app = typer.Typer(add_completion=False)

def discover_ws(cdp_origin: str, token: str | None) -> str:
    url = f"{cdp_origin.rstrip('/')}/json/version"
    if token:
        url += f"?token={token}"
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.json()["webSocketDebuggerUrl"]

@app.command()
def run(
    url: str = typer.Option("http://127.0.0.1:8080/classic", help="Page to test"),
    cdp_origin: str = typer.Option("http://127.0.0.1:9222", help="CDP http origin"),
    token: str = typer.Option("", help="Browserless token (optional)"),
    timeout_s: float = typer.Option(20, help="Total time to wait for network idle"),
    screenshot: str = typer.Option("scripts/artifacts/ui_screenshot.png", help="Path for screenshot"),
):
    artifacts_dir = pathlib.Path(screenshot).parent
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    ws = discover_ws(cdp_origin, token or None)

    errs: List[str] = []
    logs: List[str] = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(ws)
        page: Page = browser.new_page()

        page.on("console", lambda m: (logs.append(f"[{m.type}] {m.text}"), errs.append(m.text) if m.type == "error" else None))
        page.on("pageerror", lambda e: errs.append(f"PAGEERROR: {e}"))

        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=int(timeout_s * 1000))
        page.screenshot(path=screenshot, full_page=True)
        browser.close()

    if errs:
        print("❌ UI runtime errors detected:")
        for e in errs:
            print("   -", e)
        (artifacts_dir / "ui_console.log").write_text("\n".join(logs), encoding="utf-8")
        print(f"Screenshot saved: {screenshot}")
        sys.exit(1)

    print("✅ No runtime errors found.")
    print(f"Screenshot saved: {screenshot}")

if __name__ == "__main__":
    app()

