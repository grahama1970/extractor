#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Fail if Stage 02 has zero figure-like blocks.

Usage examples:

  uv run scripts/smokes/smoke_stage02_has_figures.py \
    --json data/results/pipeline_runs/RERUN_20251011_153316/02_marker_extractor/json_output/02_marker_blocks_corefix3.json

  uv run scripts/smokes/smoke_stage02_has_figures.py \
    --run-dir data/results/pipeline_runs/RERUN_20251011_153316

Exits non-zero when count < --min.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional


def _latest_stage02_json(run_dir: Path) -> Optional[Path]:
    candidates = list(
        (run_dir / "02_marker_extractor" / "json_output").glob("02_marker_blocks*.json")
    )
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _iter_blocks(obj) -> Iterable[dict]:
    if isinstance(obj, dict):
        # Common patterns
        if isinstance(obj.get("blocks"), list):
            yield from obj["blocks"]
            return
        # Some tools dump the list at top-level but wrapped under a different key
        for k in ("items", "data", "payload"):
            v = obj.get(k)
            if isinstance(v, list):
                yield from v
                return
    elif isinstance(obj, list):
        yield from obj


def _block_type(b: dict) -> str:
    t = b.get("type") or b.get("block_type") or b.get("kind") or ""
    return str(t)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Fail if Stage 02 has zero figure-like blocks.")
    ap.add_argument("--json", dest="json_path", type=Path, help="Path to 02_marker_blocks*.json")
    ap.add_argument(
        "--run-dir",
        dest="run_dir",
        type=Path,
        help="Pipeline run directory (contains 02_marker_extractor/...)",
    )
    ap.add_argument(
        "--types",
        default="Figure,Image,Picture",
        help="Comma-separated set of figure-like types to count",
    )
    ap.add_argument(
        "--min", dest="min_count", type=int, default=1, help="Minimum required count to pass"
    )
    args = ap.parse_args(argv)

    json_path: Optional[Path] = args.json_path
    if json_path is None and args.run_dir is not None:
        json_path = _latest_stage02_json(args.run_dir)
    if not json_path:
        print(
            "ERROR: Could not resolve Stage 02 JSON. Provide --json or --run-dir.", file=sys.stderr
        )
        return 2
    if not json_path.exists():
        print(f"ERROR: JSON not found: {json_path}", file=sys.stderr)
        return 2

    wanted = {s.strip().lower() for s in (args.types.split(",") if args.types else []) if s.strip()}
    data = json.loads(json_path.read_text())
    blocks = list(_iter_blocks(data))
    total = len(blocks)
    hits = [b for b in blocks if _block_type(b).strip().lower() in wanted]
    count = len(hits)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "total_blocks": total,
                "types": sorted(list(wanted)),
                "figure_like_count": count,
                "min_required": args.min_count,
                "ok": count >= args.min_count,
            },
            indent=2,
        )
    )

    return 0 if count >= args.min_count else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
