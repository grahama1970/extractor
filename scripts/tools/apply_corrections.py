#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path


def apply_step02(data: dict, corr: dict):
    """Apply corrections to specified block in the data dictionary."""
    blocks = data.get("blocks", [])
    idx = corr["idx"]
    if 0 <= idx < len(blocks):
        b = blocks[idx]
        if "label" in corr and corr["label"]:
            b["block_type"] = corr["label"]
        bb = b.get("bbox") or b.get("bbox0")
        if bb and isinstance(bb, list) and len(bb) == 4:
            # corrections are in pixels at 144dpi → convert to points (72dpi)
            scale = 72 / 144
            dx = corr.get("dx", 0) * scale
            dy = corr.get("dy", 0) * scale
            dw = corr.get("dw", 0) * scale
            dh = corr.get("dh", 0) * scale
            bb[0] += dx
            bb[2] += dx + dw
            bb[1] += dy
            bb[3] += dy + dh


def apply_step05(data: dict, corr: dict):
    """Update a table's title and bounding box offset from corrections."""
    tables = data.get("tables", [])
    idx = corr["idx"]
    if 0 <= idx < len(tables):
        t = tables[idx]
        if "label" in corr and corr["label"]:
            t["title"] = corr["label"]
        bb = t.get("bbox")
        if bb and isinstance(bb, list) and len(bb) == 4:
            scale = 72 / 144
            dx = corr.get("dx", 0) * scale
            dy = corr.get("dy", 0) * scale
            dw = corr.get("dw", 0) * scale
            dh = corr.get("dh", 0) * scale
            bb[0] += dx
            bb[2] += dx + dw
            bb[1] += dy
            bb[3] += dy + dh


def apply_step06(data: dict, corr: dict):
    """Apply title and bbox corrections to a specific figure."""
    figs = data.get("figures", [])
    idx = corr["idx"]
    if 0 <= idx < len(figs):
        f = figs[idx]
        if "label" in corr and corr["label"]:
            f["title"] = corr["label"]
        bb = f.get("bbox")
        if bb and isinstance(bb, list) and len(bb) == 4:
            scale = 72 / 144
            dx = corr.get("dx", 0) * scale
            dy = corr.get("dy", 0) * scale
            dw = corr.get("dw", 0) * scale
            dh = corr.get("dh", 0) * scale
            bb[0] += dx
            bb[2] += dx + dw
            bb[1] += dy
            bb[3] += dy + dh


APPLIERS = {
    "02": apply_step02,
    "05": apply_step05,
    "06": apply_step06,
}


def main() -> int:
    """Apply visual review corrections to pipeline JSON outputs."""
    ap = argparse.ArgumentParser(
        description="Apply visual review corrections to pipeline JSON outputs"
    )
    ap.add_argument("--corrections", required=True, type=Path)
    ap.add_argument("--out-root", required=True, type=Path, help="pipeline results root")
    args = ap.parse_args()

    data = json.loads(args.corrections.read_text())
    step = data["step"]
    Path(data["pdf"]).stem
    corrs = data.get("corrections", [])

    if step == "02":
        path = args.out_root / "02_marker_extractor/json_output/02_marker_blocks.json"
    elif step == "05":
        path = args.out_root / "05_table_extractor/json_output/05_tables.json"
    elif step == "06":
        path = args.out_root / "06_figure_extractor/json_output/06_figures.json"
    else:
        raise SystemExit(f"Unsupported step: {step}")

    payload = json.loads(path.read_text())
    apply = APPLIERS[step]
    for c in corrs:
        apply(payload, c)
    path.write_text(json.dumps(payload, indent=2))
    print(f"applied corrections → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
