#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "httpx>=0.27",
# ]
# ///
"""
Smoke: Conflicts save endpoint

POST /api/conflicts/save with a small payload and assert artifact file exists.

Artifacts:
- scripts/artifacts/conflicts_save_smoke.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import httpx

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ART = Path("scripts/artifacts")
ART.mkdir(parents=True, exist_ok=True)


def main() -> int:
    doc_id = "docdemo"
    payload = {
        "doc_id": doc_id,
        "items": [
            {
                "id": "c1",
                "type": "duplicate",
                "groupId": "tbl-001",
                "resolved": False,
                "notes": "demo",
            }
        ],
    }
    r = httpx.post(f"{BASE}/api/conflicts/save", json=payload, timeout=5)
    ok = r.status_code == 200 and (r.json() or {}).get("ok") is True
    path = (r.json() or {}).get("path") if ok else None
    exists = bool(path) and Path(path).exists()
    summary = {"base": BASE, "ok": ok, "path": path, "exists": bool(exists)}
    (ART / "conflicts_save_smoke.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return 0 if (ok and exists) else 2


if __name__ == "__main__":
    sys.exit(main())
