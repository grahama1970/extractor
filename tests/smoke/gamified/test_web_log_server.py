from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient
import sys, types

# Stub heavy/optional modules to allow importing the FastAPI app without full ML stack
if 'torch' not in sys.modules:
    sys.modules['torch'] = types.ModuleType('torch')
if 'numpy' not in sys.modules:
    sys.modules['numpy'] = types.ModuleType('numpy')
if 'requests' not in sys.modules:
    sys.modules['requests'] = types.ModuleType('requests')
if 'dotenv' not in sys.modules:
    dotenv = types.ModuleType('dotenv')
    def _find_dotenv(*a, **k):
        return ''
    dotenv.find_dotenv = _find_dotenv
    sys.modules['dotenv'] = dotenv
if 'pydantic_settings' not in sys.modules:
    ps = types.ModuleType('pydantic_settings')
    class BaseSettings: ...
    ps.BaseSettings = BaseSettings
    sys.modules['pydantic_settings'] = ps

from extractor.core.scripts.server import app


def test_proto_dashboard_and_ingest_endpoints():
    client = TestClient(app)

    # Proto dashboard should be reachable and return HTML
    r = client.get("/proto/dashboard")
    assert r.status_code == 200
    assert "Prototype Orchestrator Dashboard" in r.text

    # Ingest a log event (no DB required)
    payload_log = {
        "ts": time.time(),
        "run_id": "smoke",
        "variant": "mul_shift_add",
        "episode_id": None,
        "stream": "app",
        "level": "INFO",
        "source": "smoke_test",
        "message": "hello from smoke",
        "meta": {"k": "v"},
    }
    rl = client.post("/ingest/log", json=payload_log)
    assert rl.status_code == 200
    assert rl.json().get("ok") is True

    # Ingest an episode event (no DB required)
    payload_ep = {
        "ts": time.time(),
        "run_id": "smoke",
        "episode_id": "smoke-ep-1",
        "variant": "mul_shift_add",
        "pass": True,
        "score": 42.0,
        "metrics": {},
        "error_count": 0,
        "screenshots": [],
    }
    re = client.post("/ingest/episode", json=payload_ep)
    assert re.status_code == 200
    assert re.json().get("ok") is True

    # Scoreboard and logs may return 503 without DB; assert no 5xx on proto dashboard
    sc = client.get("/scoreboard")
    assert sc.status_code in (200, 503)
