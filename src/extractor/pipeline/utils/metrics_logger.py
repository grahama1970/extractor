from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

try:  # optional dependency
    from arango import ArangoClient  # type: ignore
    from arango.database import StandardDatabase  # type: ignore
except Exception:  # pragma: no cover - arango may not be installed
    ArangoClient = None  # type: ignore
    StandardDatabase = object  # type: ignore


_ARANGO_DB: Optional[StandardDatabase] = None
_COLLECTION_NAME = os.getenv("PIPELINE_METRICS_COLLECTION", "pipeline_metrics")


def _get_arango_db() -> Optional[StandardDatabase]:
    global _ARANGO_DB
    if _ARANGO_DB is not None:
        return _ARANGO_DB
    if ArangoClient is None:
        return None

    host = os.getenv("ARANGO_HOST")
    port = os.getenv("ARANGO_PORT")
    user = os.getenv("ARANGO_USERNAME") or os.getenv("ARANGO_USER")
    password = os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")
    database = os.getenv("ARANGO_DB") or os.getenv("ARANGO_DATABASE")
    if not all([host, port, user, password, database]):
        return None
    try:
        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(database, username=user, password=password)
        if not db.has_collection(_COLLECTION_NAME):
            db.create_collection(_COLLECTION_NAME)
        _ARANGO_DB = db
        return db
    except Exception as e:  # pragma: no cover - connection errors
        logger.warning(f"Metrics logger could not connect to ArangoDB: {e}")
        return None


def _write_local_log(entry: Dict[str, Any]) -> None:
    try:
        log_path = Path("logs/metrics_log.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{entry}\n")
    except Exception:
        logger.debug("Failed to write metrics log locally")


def log_metric(stage: str, data: Dict[str, Any]) -> None:
    entry: Dict[str, Any] = {
        "stage": stage,
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": os.getenv("LITELLM_SESSION_ID"),
    }
    entry.update(data)

    db = _get_arango_db()
    if db is not None:
        try:
            db.collection(_COLLECTION_NAME).insert(entry)
            return
        except Exception as e:  # pragma: no cover - prefer local log fallback
            logger.debug(f"Failed to log metric to ArangoDB: {e}")
    _write_local_log(entry)
