#!/usr/bin/env python3
"""
Smoke: Stage 09a left gutter contains text plaques

- Runs Stage 09a on a known PDF fixture
- Verifies at least one FreeText annotation lies entirely within the left gutter band
  OR a pixel-density guard passes on a rasterized gutter slice
- Writes deterministic artifacts under scripts/artifacts/
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Tuple

import fitz  # PyMuPDF


ARTIFACTS_DIR = Path("scripts/artifacts")
ART_PREVIEW_COPY = ARTIFACTS_DIR / "annot_preview_request-1-1.png"
ART_LOG_JSON = ARTIFACTS_DIR / "gutter_sanity_log.json"


def _ensure_artifacts_dir() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _lane_rect(page: fitz.Page, gutter_w: float) -> fitz.Rect:
    r = page.rect
    # 6pt padding to match 09a _draw_page_gutter_side
    return fitz.Rect(r.x0 + 6, r.y0 + 6, r.x0 + 6 + gutter_w, r.y1 - 6)


def _annot_in_rect(rect: fitz.Rect, lane: fitz.Rect) -> bool:
    # Strictly contains (allow tiny epsilon)
    eps = 0.5
    return (rect.x0 >= lane.x0 - eps) and (rect.x1 <= lane.x1 + eps) and (rect.y0 >= lane.y0 - eps) and (rect.y1 <= lane.y1 + eps)


def _count_dark_pixels_in_region(pix: fitz.Pixmap, x0: int, y0: int, x1: int, y1: int, dark_thresh: int = 64) -> Tuple[int, int]:
    """Count pixels whose average RGB < dark_thresh in the rectangular region."""
    x0 = max(0, min(x0, pix.width))
    y0 = max(0, min(y0, pix.height))
    x1 = max(0, min(x1, pix.width))
    y1 = max(0, min(y1, pix.height))
    if x1 <= x0 or y1 <= y0:
        return 0, 0
    p = pix
    if pix.n >= 4:  # strip alpha
        p = fitz.Pixmap(fitz.csRGB, pix)
    data = p.samples
    stride = p.width * p.n
    dark = 0
    total = 0
    for yy in range(y0, y1):
        row = data[yy * stride : (yy + 1) * stride]
        for xx in range(x0, x1):
            i = xx * p.n
            r = row[i + 0]
            g = row[i + 1]
            b = row[i + 2]
            avg = (r + g + b) // 3
            if avg < dark_thresh:
                dark += 1
            total += 1
    return dark, total


def main() -> int:
    from extractor.pipeline.steps import s09a_pdf_annotator as s09a

    _ensure_artifacts_dir()

    input_pdf = Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf")
    sections_json = Path("data/results/pipeline/04_section_builder/json_output/04_sections.json")
    tables_json = Path("data/results/pipeline/05_table_extractor/json_output/05_tables.json")
    figures_json = Path("data/results/pipeline/06_figure_extractor/json_output/06_figures.json")
    reflowed_json = Path("data/results/pipeline/07_reflow_section/json_output/07_reflowed.json")
    out_dir = Path("data/results/pipeline")

    if not input_pdf.exists():
        print(f"ERROR: fixture not found: {input_pdf}", file=sys.stderr)
        return 2

    annotated = s09a.run(
        input_pdf,
        sections_json,
        tables_json,
        figures_json,
        reflowed_json=reflowed_json,
        output_dir=out_dir,
        render_previews=True,
    )

    preview_src = annotated.parent / "visual_output" / "page_0001.png"
    if preview_src.exists():
        try:
            shutil.copyfile(preview_src, ART_PREVIEW_COPY)
        except Exception:
            pass

    doc = fitz.open(str(annotated))
    try:
        page = doc[0]
        lane = _lane_rect(page, gutter_w=float(getattr(s09a, "GUTTER_WIDTH", 84.0)))
        found_freetext = False
        freetext_annots = []
        try:
            for a in page.annots() or []:
                t_code, t_name = a.type
                if "FreeText" in str(t_name):
                    rect = a.rect
                    inside = _annot_in_rect(rect, lane)
                    freetext_annots.append(
                        {"type": str(t_name), "rect": [rect.x0, rect.y0, rect.x1, rect.y1], "inside_gutter": bool(inside)}
                    )
                    if inside:
                        found_freetext = True
        except Exception:
            pass

        result = {"pass": False, "mode": "", "details": {}}

        if found_freetext:
            result["pass"] = True
            result["mode"] = "freetext"
            result["details"]["message"] = "Found FreeText annotation fully inside left gutter."
        else:
            dpi = int(getattr(s09a, "PREVIEW_DPI", 144))
            scale = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            gx0 = max(0, int(lane.x0 * scale))
            gy0 = max(0, int(lane.y0 * scale))
            gx1 = min(pix.width, int(lane.x1 * scale))
            gy1 = min(pix.height, int(lane.y1 * scale))
            dark, total = _count_dark_pixels_in_region(pix, gx0, gy0, gx1, gy1, dark_thresh=64)
            pct = (dark / total * 100.0) if total > 0 else 0.0
            threshold_pct = 0.5
            if pct >= threshold_pct:
                result["pass"] = True
                result["mode"] = "pixels"
                result["details"].update(
                    {
                        "dark_pixels": dark,
                        "total_pixels": total,
                        "percent": pct,
                        "threshold_percent": threshold_pct,
                    }
                )
            else:
                result["pass"] = False
                result["mode"] = "none"
                result["details"].update(
                    {
                        "dark_pixels": dark,
                        "total_pixels": total,
                        "percent": pct,
                        "threshold_percent": threshold_pct,
                    }
                )

        payload = {
            "annotated_pdf": str(annotated),
            "preview_png": str(ART_PREVIEW_COPY) if ART_PREVIEW_COPY.exists() else None,
            "lane_rect_pts": [lane.x0, lane.y0, lane.x1, lane.y1],
            "freetext_annots": freetext_annots,
            "result": result,
        }
        try:
            ART_LOG_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

        if not result["pass"]:
            print(
                "ERROR: Stage 09a gutter sanity failed: no FreeText plaque in gutter and pixel threshold not met "
                f"(mode={result['mode']}, details={result['details']})",
                file=sys.stderr,
            )
            return 1

        print(f"OK: Stage 09a gutter sanity passed via {result['mode']}. Artifacts: {ART_PREVIEW_COPY} ; {ART_LOG_JSON}")
        return 0
    finally:
        try:
            doc.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
