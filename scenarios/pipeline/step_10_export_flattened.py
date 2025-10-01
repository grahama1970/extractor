#!/usr/bin/env python3
"""Scenario: Validate presence of Step 10 flattened JSON artifact.

Non-deterministic: we do not assert exact content, only that a recent
10_flattened_data.json exists and is readable JSON.

Search order (most recent wins):
- data/results/pipeline/**/10_arangodb_exporter/json_output/10_flattened_data.json
- out_fast/**/10_arangodb_exporter/json_output/10_flattened_data.json
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def find_latest() -> Path | None:
    candidates = list(ROOT.glob("data/results/pipeline/**/10_arangodb_exporter/json_output/10_flattened_data.json"))
    candidates += list(ROOT.glob("out_fast/**/10_arangodb_exporter/json_output/10_flattened_data.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> None:
    latest = find_latest()
    if latest is None:
        print("SKIP: no 10_flattened_data.json found under data/results/pipeline or out_fast")
        sys.exit(0)
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Scenario pipeline/step_10_export_flattened: FAIL (invalid JSON) path={latest} err={e}")
        sys.exit(1)
    # Heuristic presence checks
    ok = isinstance(data, dict) and any(k in data for k in ("sections", "pages", "nodes"))
    print(f"Scenario pipeline/step_10_export_flattened: path={latest} keys={list(data)[:10]}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

