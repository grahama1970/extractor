#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class Check:
    id: str
    path: str
    json_pointer: str  # e.g., "/sections"
    metric: str  # "len" or "value"
    op: str  # "==", ">=", "<="
    value: Any
    why: str


def _load_config() -> dict[str, Any]:
    cfg_env = os.getenv("SPARTA_INVARIANTS") or os.getenv("PIPELINE_INVARIANTS")
    cfg_path = Path(cfg_env) if cfg_env else Path("config/pipeline_invariants.json")
    try:
        return json.loads(cfg_path.read_text())
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"failed to read invariants: {e}"}))
        sys.exit(2)


def _get_pointer(obj: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return obj
    cur = obj
    for part in pointer.strip("/").split("/"):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                idx = int(part)
            except Exception:
                return None
            if 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            return None
    return cur


def _compare(lhs: Any, op: str, rhs: Any) -> bool:
    ops = {
        "==": lambda a, b: a == b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        "starts_with": lambda a, b: isinstance(a, str) and str(a).startswith(str(b)),
        "contains": lambda a, b: (isinstance(a, (list, tuple, set)) and b in a)
        or (isinstance(a, str) and str(b) in a),
    }
    return ops.get(op, lambda a, b: False)(lhs, rhs)


def _compute_metric(value: Any, metric: str) -> Optional[Any]:
    if metric == "len":
        try:
            return len(value)  # type: ignore[arg-type]
        except Exception:
            return None
    if metric == "len_or_zero":
        try:
            return len(value) if value is not None else 0
        except Exception:
            return 0
    if metric == "value":
        return value
    if metric == "text":
        return value if isinstance(value, str) else None
    return None


def main() -> int:
    cfg = _load_config()
    out_dir = Path(cfg.get("defaults", {}).get("out_dir", "data/results/pipeline"))
    failures: list[dict[str, Any]] = []
    passes: list[str] = []

    for raw in cfg.get("checks", []):
        c = Check(
            id=raw.get("id"),
            path=raw.get("path"),
            json_pointer=raw.get("json_pointer", "/"),
            metric=raw.get("metric", "len"),
            op=raw.get("op", "=="),
            value=raw.get("value"),
            why=raw.get("why", ""),
        )
        target = out_dir / c.path
        try:
            data = json.loads(target.read_text())
            node = _get_pointer(data, c.json_pointer)
            metric_val = _compute_metric(node, c.metric)
            expect = c.value
            ok = metric_val is not None and _compare(metric_val, c.op, expect)
            if ok:
                passes.append(c.id)
            else:
                failures.append(
                    {
                        "id": c.id,
                        "why": c.why,
                        "path": str(target),
                        "metric": c.metric,
                        "actual": metric_val,
                        "op": c.op,
                        "expected": expect,
                    }
                )
        except Exception as e:
            failures.append({"id": c.id, "why": c.why, "error": str(e), "path": str(target)})

    result = {"ok": not failures, "passes": passes, "failures": failures}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
