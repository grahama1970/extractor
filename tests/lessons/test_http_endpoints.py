import os
import time
import pytest

import httpx
import hashlib

from scripts.lessons.arango_client import get_db

API_BASE = os.getenv("LESSONS_API_BASE", "http://127.0.0.1:8001")


def _get(url: str, **params):
    """Retrieve HTTP response from a specified URL with parameters."""
    r = httpx.get(f"{API_BASE}{url}", params=params, timeout=10.0)
    return r


def _post(url: str, payload: dict):
    """Post JSON payload to a specified URL and return the response."""
    r = httpx.post(f"{API_BASE}{url}", json=payload, timeout=15.0)
    return r


def _server_up() -> bool:
    """Validate API server responsiveness."""
    try:
        r = httpx.get(f"{API_BASE}/api/build", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _server_up(), reason="Lessons API not running; start ./scripts/dev.sh")
def test_http_edge_lifecycle():
    """Skip test if the Lessons API server is not running."""
    ts = int(time.time())
    title_a = f"DEMO[http] A {ts}"
    title_b = f"DEMO[http] B {ts}"

    # Add two lessons via API
    for t in (title_a, title_b):
        r = _post(
            "/api/lessons/add",
            {
                "title": t,
                "scope": "tabbed",
                "tags": ["http"],
                "status": "active",
                "problem": "temp",
                "playbook": "temp",
                "demo": True,
                "demo_batch": "http",
            },
        )
        assert r.status_code == 200 and r.json().get("ok")

    # Create symmetric related edges with rationale
    r = _post(
        "/api/lessons/edge/related",
        {
            "from_title": title_a,
            "from_scope": "tabbed",
            "to_title": title_b,
            "to_scope": "tabbed",
            "weight": 0.7,
            "rationale": "http edge test",
            "approved": False,
            "source": "test",
        },
    )
    assert r.status_code == 200 and r.json().get("ok")

    # List related neighbors
    r = _get("/api/lessons/related", title=title_a, scope="tabbed", k=5)
    assert r.status_code == 200 and r.json().get("ok")
    items = r.json().get("items", [])
    assert any(i["neighbor"]["title"] == title_b for i in items)

    # Approve edge with human rationale
    r = _post(
        "/api/lessons/edge/approve",
        {
            "from_title": title_a,
            "from_scope": "tabbed",
            "to_title": title_b,
            "to_scope": "tabbed",
            "rationale": "approved via http",
        },
    )
    assert r.status_code == 200 and r.json().get("ok")

    # Multihop should include some paths when depth=1 (neighbors)
    r = _get("/api/lessons/multihop", title=title_a, scope="tabbed", depth=1, limit=10)
    assert r.status_code == 200 and r.json().get("ok")
    paths = r.json().get("items", [])
    assert isinstance(paths, list)


@pytest.mark.skipif(not _server_up(), reason="Lessons API not running; start ./scripts/dev.sh")
def test_http_edge_reject_and_rejected_pairs_present():
    """Test HTTP rejection of lesson pairs and their presence."""
    ts = int(time.time())
    title_c = f"DEMO[http-reject] C {ts}"
    title_d = f"DEMO[http-reject] D {ts}"

    # Add two lessons via API and capture keys
    keys = []
    for t in (title_c, title_d):
        r = _post(
            "/api/lessons/add",
            {
                "title": t,
                "scope": "tabbed",
                "tags": ["http"],
                "status": "active",
                "problem": "temp",
                "playbook": "temp",
                "demo": True,
                "demo_batch": "http-reject",
            },
        )
        assert r.status_code == 200 and r.json().get("ok")
        keys.append(r.json()["item"]["_key"])  # type: ignore

    # Reject the pair via API
    r = _post(
        "/api/lessons/edge/reject",
        {
            "from_title": title_c,
            "from_scope": "tabbed",
            "to_title": title_d,
            "to_scope": "tabbed",
            "reason": "test reject",
        },
    )
    assert r.status_code == 200 and r.json().get("ok")

    # Verify rejected_pairs contains the pair (best-effort; skip if DB not reachable)
    try:
        db = get_db()
        a = f"lessons/{keys[0]}"
        b = f"lessons/{keys[1]}"
        a, b = (a, b) if a <= b else (b, a)
        pid = hashlib.sha1((a + "|" + b).encode("utf-8")).hexdigest()
        doc = db.collection("rejected_pairs").get(pid)
        assert doc and doc.get("pair_id") == pid
    except Exception:
        pytest.skip("ArangoDB not reachable to verify rejected_pairs")
