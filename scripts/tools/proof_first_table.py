#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyMuPDF>=1.24.9"]
# ///

"""
Create a proof PDF showing the first Stage 05 table with a blue box and a sticky note
"Table RxC". Saves to scripts/artifacts/proof_first_table.pdf and a PNG render.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional, Tuple


def _latest_run_dir(root: Path) -> Optional[Path]:
    """Return the most recent pipeline run directory from root."""
    runs = [p for p in (root / "data" / "results" / "pipeline_runs").glob("*") if p.is_dir()]
    if not runs:
        return None
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0]


def _rect_from_camelot(bb: Iterable[float], page_h: float) -> Tuple[float, float, float, float]:
    """Return rectangle coordinates adjusted for page height."""
    x0, y0, x1, y1 = [float(v) for v in bb]
    y0f = float(page_h) - y1
    y1f = float(page_h) - y0
    return (x0, y0f, x1, y1f)


def main() -> int:
    """Return the latest run directory and resolve input file paths."""
    import fitz

    root = Path.cwd()
    run = _latest_run_dir(root)
    if not run:
        raise SystemExit("No pipeline_runs directory found.")

    # Resolve inputs
    pdf = max((run / "01_annotation_processor").glob("*_clean.pdf"))
    j5_candidates = list((run / "05_table_extractor" / "json_output").glob("05_tables*.json"))
    if not j5_candidates:
        raise SystemExit("No 05_tables*.json found in latest run.")
    j5_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    j5 = json.loads(j5_candidates[0].read_text())
    tables = j5.get("tables") or []
    if not tables:
        raise SystemExit("Stage 05 has zero tables in latest run.")

    # Pick first table with a bbox
    t = next((t for t in tables if t.get("bbox")), tables[0])
    pno = int(t.get("page_number", 1)) - 1
    bb = t.get("bbox")
    rows, cols = None, None
    shp = (t.get("pandas_metrics") or {}).get("shape") or []
    if len(shp) >= 2:
        rows, cols = shp[0], shp[1]

    doc = fitz.open(str(pdf))
    page = doc[pno]
    # Convert Camelot→fitz coords
    x0, y0, x1, y1 = _rect_from_camelot(bb, page.rect.height)
    rect = fitz.Rect(x0, y0, x1, y1) & page.rect
    if rect.is_empty:
        raise SystemExit("Converted table rect is empty after clamping.")

    # Draw blue box (5% fill) and sticky note "Table RxC"
    color = (0.10, 0.60, 0.95)
    ann = page.add_rect_annot(rect)
    try:
        ann.set_colors(stroke=color, fill=color)
        ann.set_border(width=0.8)
        ann.set_opacity(0.05)
        ann.update()
    except Exception:
        pass
    # Sticky note near top-right
    try:
        note_text = f"Table {rows}x{cols}" if rows is not None and cols is not None else "Table"
        pt = fitz.Point(rect.x1 - 8, max(rect.y0 + 8, 8))
        na = page.add_text_annot(pt, note_text)
        try:
            na.set_colors(stroke=color, fill=None)
        except Exception:
            pass
        try:
            na.update()
        except Exception:
            pass
    except Exception:
        pass

    out = Path("scripts/artifacts/proof_first_table.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))

    # Export PNG
    try:
        pm = page.get_pixmap(dpi=180, annots=True)
    except TypeError:
        pm = page.get_pixmap(dpi=180)
    (out.parent / "proof_first_table_page.png").write_bytes(pm.tobytes("png"))

    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
