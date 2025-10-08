#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict
import os

PIPELINE_EVENTS_PATH = Path("data/results/pipeline/pipeline_events.log")


def log_stage_event(stage: str, phase: str, **fields: Any) -> None:
    """Append a single JSON line describing a stage event.

    phase: 'start' | 'end' | any lifecycle marker.
    Never raises; silently ignores errors.
    """
    try:
        PIPELINE_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        record: Dict[str, Any] = {
            "ts": time.time(),
            "stage": stage,
            "phase": phase,
        }
        record.update(fields)
        line = json.dumps(record, ensure_ascii=False)
        with PIPELINE_EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            if os.getenv("PIPELINE_EVENTS_FLUSH", "0").lower() in ("1","true","yes"):
                f.flush()
    except Exception:
        pass
