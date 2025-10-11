#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "PyMuPDF>=1.24.9",
# ]
# ///

"""
Create a proof PDF with a box over the first detected figure, expanded by a factor (default 20%).

Outputs to scripts/artifacts/proof_expand_p1_figure.pdf unless --out is provided.

Examples:
  uv run scripts/tools/proof_expand_figure.py --run-dir data/results/pipeline_runs/RERUN_20251011_153316
  uv run scripts/tools/proof_expand_figure.py --fig-json path/to/06_figures.json --pdf path/to/*_clean.pdf
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class Inputs:
    pdf: Path
    fig_json: Path
    out: Path
    expand: float


def _latest_run_dir(root: Path) -> Optional[Path]:
    cand = [p for p in (root / "data" / "results" / "pipeline_runs").glob("*") if p.is_dir()]
    if not cand:
        return None
    cand.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cand[0]


def _resolve_inputs(run_dir: Optional[Path], pdf: Optional[Path], fig_json: Optional[Path], out: Optional[Path], expand: float) -> Inputs:
    if run_dir is None:
        lr = _latest_run_dir(Path.cwd())
        if lr is None:
            raise SystemExit("Could not find a pipeline run directory; provide --run-dir and/or --fig-json/--pdf")
        run_dir = lr

    if fig_json is None:
        cand = list((run_dir / "06_figure_extractor" / "json_output").glob("06_figures*.json"))
        if not cand:
            raise SystemExit(f"No 06_figures*.json under {run_dir}")
        cand.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        fig_json = cand[0]

    if pdf is None:
        # Look for Stage 01 clean PDF
        cands = list((run_dir / "01_annotation_processor").glob("*_clean.pdf"))
        if not cands:
            raise SystemExit(f"No *_clean.pdf under {run_dir}/01_annotation_processor")
        cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        pdf = cands[0]

    if out is None:
        out = Path("scripts/artifacts/proof_expand_p1_figure.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    return Inputs(pdf=pdf, fig_json=fig_json, out=out, expand=expand)


def _expand_and_clamp(rect: Tuple[float, float, float, float], page_w: float, page_h: float, ratio: float) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = rect
    w = max(0.0, x1 - x0)
    h = max(0.0, y1 - y0)
    dx = w * ratio
    dy = h * ratio
    nx0 = max(0.0, x0 - dx)
    ny0 = max(0.0, y0 - dy)
    nx1 = min(page_w, x1 + dx)
    ny1 = min(page_h, y1 + dy)
    return (nx0, ny0, nx1, ny1)


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Write a proof PDF with an expanded box over p1's first figure.")
    ap.add_argument("--run-dir", type=Path)
    ap.add_argument("--pdf", type=Path)
    ap.add_argument("--fig-json", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--expand", type=float, default=0.20, help="Expansion ratio (e.g., 0.20 for +20%)")
    args = ap.parse_args(argv)

    ins = _resolve_inputs(args.run_dir, args.pdf, args.fig_json, args.out, args.expand)

    data = json.loads(ins.fig_json.read_text())
    figures = data.get("figures") or data
    if not isinstance(figures, list) or not figures:
        raise SystemExit(f"No figures in {ins.fig_json}")
    f0 = figures[0]

    # Accept various schemas
    bbox = f0.get("bbox") or f0.get("rect") or f0.get("bounds")
    if not bbox or len(bbox) != 4:
        raise SystemExit("First figure has no bbox")

    page_idx = None
    if f0.get("page_idx") is not None:
        page_idx = int(f0["page_idx"])  # 0-based
    elif f0.get("page_number") is not None:
        page_idx = int(f0["page_number"]) - 1
    else:
        page_idx = 0

    import fitz  # PyMuPDF

    doc = fitz.open(str(ins.pdf))
    if not (0 <= page_idx < len(doc)):
        page_idx = 0
    page = doc[page_idx]
    pr = page.rect
    x0, y0, x1, y1 = [float(v) for v in bbox]
    rx0, ry0, rx1, ry1 = _expand_and_clamp((x0, y0, x1, y1), pr.width, pr.height, ins.expand)

    # Clamp explicitly to page rect to ensure deterministic right-edge alignment
    rx0c = max(pr.x0, rx0)
    ry0c = max(pr.y0, ry0)
    rx1c = min(pr.x1, rx1)
    ry1c = min(pr.y1, ry1)
    rect = fitz.Rect(rx0c, ry0c, rx1c, ry1c)
    if rect.is_empty:
        raise SystemExit("Expanded rect is empty after clamping")

    # Use a consistent figure color; label will match this
    figure_color = (0.10, 0.80, 0.40)  # green

    # Draw a visible box (annotation object)
    ann = page.add_rect_annot(rect)
    try:
        ann.set_colors(stroke=figure_color)
        ann.set_border(width=2.0)
        # Set common fields so viewers display an obvious label in comments list
        try:
            ann.set_info(content="figure")
            ann.set_info(subject="figure")
            ann.set_info(title="figure")
        except Exception:
            pass
        ann.update()
    except Exception:
        pass

    # Also add a visible label as a Square+FreeText combo placed just OUTSIDE the box at top-right,
    # with its LEFT edge aligned to the figure box's RIGHT edge for a "tab" look.
    try:
        # Use the actual annotation rect to compensate for border-expansion semantics
        try:
            abox = ann.rect
        except Exception:
            abox = rect
        label_text = "figure"
        tab_h = 14.0
        # Estimate width from characters and clamp
        approx_char_w = 5.0
        tab_w = max(56.0, min(140.0, len(label_text) * approx_char_w + 10.0))
        # Place outside to the right: left edge at the box's right edge
        gap = 0.0  # no gap; visually attached
        pr = page.rect
        # Prefer outside placement; if it would overflow, fall back to inside flush-right
        outside_x0 = abox.x1 + gap
        outside_x1 = outside_x0 + tab_w
        y0 = abox.y0
        y1 = y0 + tab_h
        if outside_x1 <= pr.x1 + 1e-6:  # enough room to the right
            x0, x1 = outside_x0, outside_x1
        else:
            # place inside, flush-right
            x1 = abox.x1
            x0 = max(abox.x0, x1 - tab_w)
        lab = fitz.Rect(x0, y0, x1, y1)
        # 1) Background tab as a filled Square (robust across viewers)
        tab_bg = page.add_rect_annot(lab)
        try:
            tab_bg.set_colors(stroke=figure_color, fill=figure_color)
            tab_bg.set_border(width=0.0)
            tab_bg.update()
        except Exception:
            pass
        # 2) Text as a FreeText with transparent background, white lettering
        fta = page.add_freetext_annot(lab, label_text, fontsize=8.0)
        try:
            fta.set_colors(stroke=None, fill=None, text=(1, 1, 1))
        except Exception:
            pass
        try:
            fta.set_border(width=0.0)
        except Exception:
            pass
        try:
            fta.set_info(content="figure"); fta.set_info(subject="figure"); fta.set_info(title="figure")
        except Exception:
            pass
        try:
            fta.update()
        except Exception:
            pass
    except Exception:
        pass

    ins.out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ins.out))
    print(json.dumps({
        "pdf": str(ins.pdf),
        "fig_json": str(ins.fig_json),
        "page_idx": page_idx,
        "orig_bbox": bbox,
        "expanded_rect": [rect.x0, rect.y0, rect.x1, rect.y1],
        "out": str(ins.out),
    }, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
