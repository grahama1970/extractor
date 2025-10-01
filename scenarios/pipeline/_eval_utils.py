#!/usr/bin/env python3
from __future__ import annotations
import json
from typing import Any, Dict
from pathlib import Path

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))

def summarize(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return {"type": "dict", "size": len(obj), "keys": list(obj.keys())[:50]}
    if isinstance(obj, list):
        return {"type": "list", "size": len(obj)}
    return {"type": type(obj).__name__}

def structure_diff(candidate: Any, gold: Any) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    if type(candidate) is not type(gold):
        diff["type_mismatch"] = {"candidate": type(candidate).__name__, "gold": type(gold).__name__}
        return diff
    if isinstance(candidate, dict) and isinstance(gold, dict):
        ck = set(candidate.keys()); gk = set(gold.keys())
        missing = sorted(list(gk - ck))[:20]
        extra = sorted(list(ck - gk))[:20]
        diff.update({
            "dict_sizes": {"candidate": len(candidate), "gold": len(gold)},
            "missing_keys_top": missing,
            "extra_keys_top": extra,
        })
    elif isinstance(candidate, list) and isinstance(gold, list):
        diff.update({
            "list_lengths": {"candidate": len(candidate), "gold": len(gold)},
        })
    return diff

def shorten(s: str, max_len: int = 2000) -> str:
    return s if len(s) <= max_len else s[: max_len - 3] + "..."

