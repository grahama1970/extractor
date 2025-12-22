from __future__ import annotations

from extractor.pipeline.utils.reliability import log_stage_error
"""Shared helpers for extractor pipeline sanity checks (Sparta-style)."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class SanityIssue:
    """Represents a single sanity failure with optional metadata."""

    message: str
    details: dict[str, Any]


def read_json(path: Path) -> dict[str, Any]:
    """Return JSON contents or {} when parsing fails."""

    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception as exc:
        log_stage_error('sanity_utils.py', exc, {'context': 'sanity_utils.py'})
        raise
        return {}


def count_jsonl(path: Path, limit: int | None = None) -> int:
    """Count non-empty JSONL rows (best-effort)."""

    if not path.exists():
        return 0
    total = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.strip():
                    total += 1
                if limit and total >= limit:
                    break
    except Exception as exc:
        log_stage_error('sanity_utils.py', exc, {'context': 'sanity_utils.py'})
        raise
        return 0
    return total


def file_exists(path: Path, *, min_bytes: int = 1) -> bool:
    try:
        return path.exists() and path.stat().st_size >= min_bytes
    except Exception as exc:
        log_stage_error('sanity_utils.py', exc, {'context': 'sanity_utils.py'})
        raise
        return False


def emit_sanity(step: str, *, ok: bool, issues: Iterable[SanityIssue] | None = None, **payload: Any) -> int:
    """Print a JSON sanity summary and return 0/1."""

    summary: dict[str, Any] = {"step": step, "ok": ok}
    if issues:
        summary["issues"] = [
            {"message": issue.message, **issue.details}
            for issue in issues
        ]
    summary.update(payload)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if ok else 1


def env_path(name: str, default: Path) -> Path:
    override = os.getenv(name)
    return Path(override) if override else default


def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in {"1", "true", "yes", "y", "on"}


__all__ = [
    "SanityIssue",
    "count_jsonl",
    "emit_sanity",
    "env_bool",
    "env_path",
    "file_exists",
    "read_json",
]
