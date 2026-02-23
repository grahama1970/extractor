#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymupdf>=1.24.2",
#   "Pillow>=10.3.0",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

# Avoid importing extractor.pipeline package __init__ (which re-exports APIs with extra deps).
# Load the overlay module directly by path.
import importlib.util as _ilu

_overlay_path = Path("src/extractor/pipeline/visual/overlay.py")
import sys as _sys

spec = _ilu.spec_from_file_location("overlay", _overlay_path)
if spec and spec.loader:
    _mod = _ilu.module_from_spec(spec)
    _sys.modules["overlay"] = _mod
    spec.loader.exec_module(_mod)
    Box = _mod.Box
    draw_overlays = _mod.draw_overlays
else:
    raise RuntimeError(f"Failed to load overlay module from {_overlay_path}")


def _load_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def boxes_from_stage02(path: Path) -> Iterable[Box]:
    data = _load_json(path)
    for i, b in enumerate(data.get("blocks", [])):
        bbox = b.get("bbox") or b.get("bbox0")
        page = b.get("page_idx") or b.get("page_num") or 0
        if not bbox or len(bbox) != 4:
            continue
        t = b.get("block_type") or b.get("type") or "block"
        yield Box(
            page=int(page),
            x0=bbox[0],
            y0=bbox[1],
            x1=bbox[2],
            y1=bbox[3],
            label=f"{t}:{i}",
            color=(0, 170, 255),
        )


def boxes_from_stage05(path: Path) -> Iterable[Box]:
    data = _load_json(path)
    for i, t in enumerate(data.get("tables", [])):
        bbox = t.get("bbox")
        page = t.get("page_idx", 0)
        title = t.get("title") or "table"
        if not bbox:
            continue
        yield Box(
            page=int(page),
            x0=bbox[0],
            y0=bbox[1],
            x1=bbox[2],
            y1=bbox[3],
            label=f"T{i}:{title}",
            color=(0, 200, 0),
        )


def boxes_from_stage06(path: Path) -> Iterable[Box]:
    data = _load_json(path)
    for i, f in enumerate(data.get("figures", [])):
        bbox = f.get("bbox")
        page = f.get("page_idx", 0)
        title = f.get("title") or f.get("inferred_title") or "figure"
        if not bbox:
            continue
        yield Box(
            page=int(page),
            x0=bbox[0],
            y0=bbox[1],
            x1=bbox[2],
            y1=bbox[3],
            label=f"F{i}:{title}",
            color=(255, 128, 0),
        )


def boxes_from_stage03(path: Path) -> Iterable[Box]:
    data = _load_json(path)
    for i, b in enumerate(data.get("suspicious_headers", [])):
        bbox = b.get("bbox")
        page = b.get("page_idx", 0)
        reason = b.get("reason") or "suspicious"
        if not bbox:
            continue
        yield Box(
            page=int(page),
            x0=bbox[0],
            y0=bbox[1],
            x1=bbox[2],
            y1=bbox[3],
            label=f"H{i}:{reason}",
            color=(255, 0, 0),
        )


STEP_MAP = {
    "02": ("02_marker_extractor/json_output/02_marker_blocks.json", boxes_from_stage02),
    "03": ("03_suspicious_headers/json_output/03_verified_blocks.json", boxes_from_stage03),
    "05": ("05_table_extractor/json_output/05_tables.json", boxes_from_stage05),
    "06": ("06_figure_extractor/json_output/06_figures.json", boxes_from_stage06),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Render visual overlays for selected steps")
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument(
        "--out", required=True, type=Path, help="pipeline results root (data/results/pipeline)"
    )
    ap.add_argument("--viz-out", required=True, type=Path, help="directory for rendered PNGs")
    ap.add_argument("--steps", default="02,05,06", help="comma list among 02,03,05,06")
    ap.add_argument("--dpi", type=int, default=144)
    ap.add_argument(
        "--y-flip", action="store_true", help="flip Y if coordinates use bottom-left origin"
    )
    args = ap.parse_args()

    pdf = args.pdf
    steps: List[str] = [s.strip() for s in args.steps.split(",") if s.strip()]
    for s in steps:
        rel, fn = STEP_MAP.get(s, (None, None))
        if not rel:
            print(f"WARN: unknown step {s}")
            continue
        src = args.out / rel
        if not src.exists():
            print(f"WARN: missing output for step {s}: {src}")
            continue
        boxes = list(fn(src))
        out_dir = args.viz_out / s
        draw_overlays(pdf, boxes, out_dir, dpi=args.dpi, y_flip=args.y_flip)
        print(f"rendered step {s} → {out_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
