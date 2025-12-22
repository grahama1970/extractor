from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


def log_stage_error(stage: str, exc: BaseException, context: Optional[Dict[str, Any]] = None) -> None:
    """Consistent structured error logging for pipeline stages."""
    payload: Dict[str, Any] = {
        "stage": stage,
        "error": exc.__class__.__name__,
        "message": str(exc),
    }
    if context:
        payload["context"] = context
    logger.error(json.dumps(payload, ensure_ascii=False))


def write_json_strict(path: Path, obj: Any, stage: str = "", ensure_ascii: bool = False) -> None:
    """Write JSON and surface failures instead of swallowing them."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=ensure_ascii), encoding="utf-8")
    except Exception as exc:
        log_stage_error(stage or "write_json_strict", exc, {"path": str(path)})
        raise
