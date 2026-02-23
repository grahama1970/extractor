#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
# ]
# ///
import os
import json
import sys
import urllib.request
import typer

app = typer.Typer(help="CHUTES/OpenAI-compatible env check and /models probe")


def _norm_base(base: str) -> str:
    b = base.rstrip("/")
    if not b.endswith("/v1"):
        b = b + "/v1"
    return b


@app.command()
def run():
    ch_base = os.getenv("CHUTES_API_BASE", "").strip()
    ch_key = os.getenv("CHUTES_API_KEY", "").strip()
    if not ch_base or not ch_key:
        print(
            json.dumps({"ok": False, "error": "Missing CHUTES_API_BASE/CHUTES_API_KEY"}, indent=2)
        )
        sys.exit(1)
    base_norm = _norm_base(ch_base)
    os.environ.setdefault("OPENAI_BASE_URL", base_norm)
    os.environ.setdefault("OPENAI_API_BASE", base_norm)
    os.environ.setdefault("OPENAI_API_KEY", ch_key)
    out = {"ok": True, "OPENAI_BASE_URL": base_norm}
    # Try /models
    try:
        req = urllib.request.Request(
            f"{base_norm}/models",
            headers={"Authorization": f"Bearer {ch_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        ids = [x.get("id") for x in (data.get("data") or []) if x.get("id")]
        out["models_count"] = len(ids)
        out["models_sample"] = ids[:5]
    except Exception as e:
        out["ok"] = False
        out["error"] = f"/models probe failed: {e}"
    print(json.dumps(out, indent=2))
    sys.exit(0 if out.get("ok") else 2)


if __name__ == "__main__":
    app()
