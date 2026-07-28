#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "httpx>=0.27",
# ]
# ///
"""
Smoke: OSLC stubs (offline)

Checks:
- GET /api/oslc/service returns ok
- POST /api/oslc/link appends a link
- GET /api/oslc/links includes the posted link

Artifacts:
- scripts/artifacts/oslc_stub_smoke.json
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
    """Return the status of a service link creation operation."""
    svc = httpx.get(f"{BASE}/api/oslc/service", timeout=5)
    ok_service = svc.status_code == 200 and (svc.json() or {}).get("ok") is True

    link_payload = {
        "source": "urn:pdf-object:obj-1",
        "target": "urn:test:case-1",
        "type": "oslc_rm:satisfies",
    }
    post = httpx.post(f"{BASE}/api/oslc/link", json=link_payload, timeout=5)
    ok_post = post.status_code == 200 and (post.json() or {}).get("ok") is True

    listing = httpx.get(f"{BASE}/api/oslc/links", timeout=5)
    body = listing.json() if listing.status_code == 200 else {}
    links = body.get("links") or []
    found = any(
        l.get("source") == link_payload["source"] and l.get("target") == link_payload["target"]
        for l in links
        if isinstance(l, dict)
    )

    summary = {
        "base": BASE,
        "ok_service": ok_service,
        "ok_post": ok_post,
        "found_link": bool(found),
        "total_links": len(links),
    }
    (ART / "oslc_stub_smoke.json").write_text(json.dumps(summary, indent=2))
    if ok_service and ok_post and found:
        print(json.dumps(summary))
        return 0
    print(json.dumps(summary))
    return 2


if __name__ == "__main__":
    sys.exit(main())
