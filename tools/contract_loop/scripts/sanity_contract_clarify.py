#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "flask>=2.2",
# ]
# ///
from __future__ import annotations

import json
import urllib.request
from dataclasses import asdict
from typing import Any

from tools.contract_loop.clarify.server import ClarifyServer, DIST_DIR
from tools.contract_loop.clarify.types import ClarifyQuestion


def _fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    if not DIST_DIR.exists():
        raise SystemExit(f"Clarify UI dist missing at {DIST_DIR}. Run the build step first.")

    q = ClarifyQuestion(
        id="sanity-question",
        prompt="Is the clarifying UI responding?",
        options=["yes", "no"],
        docs_link=None,
        artifact_paths=[],
        visual_assets=[],
    )
    server = ClarifyServer("sanity_step", 1, [q])
    port = server.start()
    try:
        payload = _fetch_json(f"http://127.0.0.1:{port}/api/questions")
        if payload.get("step") != "sanity_step":
            raise SystemExit(f"Unexpected clarify payload: {payload}")
        if payload.get("questions") != [asdict(q)]:
            raise SystemExit(f"Clarify questions mismatch: {payload}")
        print("OK: clarify server responded with expected payload.")
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
