from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _classify_one(item: Any, *, strict_json: bool = True) -> Tuple[str, bool]:
    """Classify a single Router result dict or minimal shim.

    Returns (error_type, fallback_used)
      error_type ∈ {"ok","empty_content","invalid_json","provider_error"}
      fallback_used (bool) if detectable via meta; else False
    """
    # Prefer RouterResult-like shape
    meta = {}
    content = ""
    exception = None
    try:
        # Structured result
        meta = getattr(item, "meta", {}) or {}
        exception = getattr(item, "exception", None)
        content = getattr(item, "content", "") or ""
    except Exception:
        pass
    if not meta and isinstance(item, dict):
        meta = item.get("meta") or {}
        exception = item.get("exception")
        content = item.get("content") or ""

    # Provider error takes precedence
    if exception is not None:
        return ("provider_error", bool(meta.get("fallback_used")))

    # Empty content
    if not isinstance(content, str) or not content.strip():
        return ("empty_content", bool(meta.get("fallback_used")))

    # JSON validity for strict_json callers
    if strict_json:
        try:
            json.loads(content)
            return ("ok", bool(meta.get("fallback_used")))
        except Exception:
            return ("invalid_json", bool(meta.get("fallback_used")))

    # Non-strict path: treat non-empty content as ok
    return ("ok", bool(meta.get("fallback_used")))


def compute_llm_stats(results: List[Any], *, strict_json: bool = True) -> Dict[str, Any]:
    """Compute counts by error_type and fallback_used rate for a batch of results."""
    counts = {"ok": 0, "empty_content": 0, "invalid_json": 0, "provider_error": 0}
    total = len(results)
    fallback_used = 0
    for r in results:
        et, fb = _classify_one(r, strict_json=strict_json)
        counts[et] = counts.get(et, 0) + 1
        if fb:
            fallback_used += 1
    rate_fb = (fallback_used / total) if total else 0.0
    return {
        "total": total,
        "counts": counts,
        "fallback_used": fallback_used,
        "fallback_rate": rate_fb,
        "strict_json": strict_json,
    }


def write_llm_stats(stage: str, run_id: str, stats: Dict[str, Any], out_dir: Path) -> Path:
    """Write stats to out_dir/llm_stats.json and return the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"stage": stage, "run_id": run_id, **stats}
    path = out_dir / "llm_stats.json"
    path.write_text(json.dumps(payload, indent=2))
    return path

