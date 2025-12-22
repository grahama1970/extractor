from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from extractor.pipeline.utils.reliability import log_stage_error


def _iso_now() -> str:
    try:
        import datetime as _dt

        return _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    except Exception:
        return ""


def ensure_logs_dir(base_results_dir: Path, stage_name: str) -> Path:
    d = base_results_dir / stage_name / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_jsonl(logs_dir: Path, name: str, payload: Dict[str, Any]) -> None:
    path = logs_dir / name
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        log_stage_error("debug_utils.write_jsonl", exc, {"path": str(path)})
        raise


def log_timing(stage_key: str, record: Dict[str, Any], *, stage_dir: Optional[Path] = None) -> None:
    """Append a standardized timing/observability record.

    - Always attempts to write under RUN_RESULTS_DIR/{stage_key}/logs/timings.jsonl when RUN_RESULTS_DIR is set.
    - Optionally mirrors to `stage_dir/timings.jsonl` when provided (for stage-local artifacts).
    - Adds an ISO timestamp and the `stage` key automatically; keeps fields flat and JSONL-safe.
    """
    rec: Dict[str, Any] = {"ts": _iso_now(), "stage": stage_key}
    rec.update(record)
    rd = os.getenv("RUN_RESULTS_DIR")
    if rd:
        logs_dir = ensure_logs_dir(Path(rd), stage_key)
        write_jsonl(logs_dir, "timings.jsonl", rec)
    if stage_dir is not None:
        path = Path(stage_dir) / "timings.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


@dataclass
class TimerEvent:
    logs_dir: Path
    event: str
    meta: Dict[str, Any]
    start_ts: float = 0.0

    def __enter__(self) -> "TimerEvent":
        self.start_ts = time.perf_counter()
        write_jsonl(self.logs_dir, "timings.jsonl", {
            "ts": _iso_now(),
            "event": self.event + ":start",
            **self.meta,
        })
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed = time.perf_counter() - self.start_ts
        payload: Dict[str, Any] = {
            "ts": _iso_now(),
            "event": self.event + ":end",
            "elapsed_s": round(elapsed, 3),
            **self.meta,
        }
        if exc is not None:
            payload["error"] = {
                "type": getattr(exc, "__class__", type(exc)).__name__,
                "msg": str(exc)[:400],
            }
        write_jsonl(self.logs_dir, "timings.jsonl", payload)


@contextmanager
def time_block(logs_dir: Path, event: str, **meta: Any):
    te = TimerEvent(logs_dir=logs_dir, event=event, meta=meta)
    try:
        te.__enter__()
        yield te
    finally:
        te.__exit__(None, None, None)


def summarize_messages(messages: Any) -> Dict[str, Any]:
    try:
        # Rough, provider-agnostic shape
        count = 0
        chars = 0
        images = 0
        if isinstance(messages, list):
            for m in messages:
                cont = m.get("content") if isinstance(m, dict) else None
                if isinstance(cont, list):
                    for p in cont:
                        if isinstance(p, dict):
                            t = p.get("type")
                            if t == "text":
                                s = p.get("text")
                                if isinstance(s, str):
                                    chars += len(s)
                                    count += 1
                            elif t == "image_url":
                                images += 1
                                count += 1
                elif isinstance(cont, str):
                    chars += len(cont)
                    count += 1
        return {"parts": count, "chars": chars, "images": images}
    except Exception:
        return {}
