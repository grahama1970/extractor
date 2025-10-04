#!/usr/bin/env python3
"""
Overlay Stage-02 blocks onto a copy of a PDF for visual review.

Usage:
  python debug/write_blocks_to_pdf.py \
    --pdf data/results/pipeline/with_requirements/01_annotation_processor/BHT_CV32A65X_with_requirements_clean.pdf \
    --json data/results/pipeline/with_requirements/02_marker_extractor/json_output/02_marker_blocks.json \
    --out scripts/artifacts/BHT_CV32A65X_with_requirements_overlay.pdf

It draws rectangle annotations and small FreeText labels for:
  - SectionHeader (green)
  - suspicious_header=True (red outline + "SUSPICIOUS")
  - Table (blue)
  - Figure (purple)
  - Requirement/Requirements (orange) when identifiable by block_type or title text

This is a lightweight helper to visually collaborate on filtering heuristics.
It does not modify pipeline logic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any

import fitz  # PyMuPDF


COLORS = {
    "SectionHeader": (0, 0.8, 0),     # green
    "Text": (0.3, 0.3, 0.3),          # gray
    "Table": (0.1, 0.4, 1.0),         # blue
    "Figure": (0.6, 0.1, 0.8),        # purple
    "Requirement": (1.0, 0.5, 0.0),   # orange
    "Suspicious": (1.0, 0.0, 0.0),    # red
}


def norm_text(s: str) -> str:
    s = (s or "").strip().replace("\n", " ")
    if len(s) > 80:
        s = s[:77] + "…"
    return s


def pick_color(block: Dict[str, Any]) -> tuple[float, float, float]:
    bt = block.get("block_type") or block.get("type") or "Text"
    if block.get("suspicious_header"):
        return COLORS["Suspicious"]
    if "requirement" in (bt or "").lower():
        return COLORS["Requirement"]
    return COLORS.get(bt, COLORS["Text"])


def add_rect_with_label(page: fitz.Page, rect: fitz.Rect, label: str, color=(0, 0, 0)) -> None:
    try:
        annot = page.add_rect_annot(rect)
    except AttributeError:
        annot = page.addRectAnnot(rect)
    annot.set_colors(stroke=color)
    annot.set_border(width=0.8)
    try:
        annot.update()
    except Exception:
        pass
    # FreeText slightly below the box
    lbl_rect = fitz.Rect(rect.x0, max(0, rect.y1 + 2), min(page.rect.x1, rect.x0 + 380), min(page.rect.y1, rect.y1 + 28))
    try:
        ft = page.add_freetext_annot(lbl_rect, label, fontsize=9, fill_color=(1, 1, 1))
        ft.set_colors(stroke=color, fill=(1, 1, 1))
        ft.update()
    except Exception:
        try:
            page.addFreetextAnnot(lbl_rect, label)
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Overlay Stage-02 blocks onto a PDF copy")
    ap.add_argument("--pdf", required=True, help="Input PDF (typically *_clean.pdf)")
    ap.add_argument("--json", required=True, help="Stage 02 blocks JSON (02_marker_blocks.json)")
    ap.add_argument("--out", required=True, help="Output annotated PDF path")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    jpath = Path(args.json)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with jpath.open("r", encoding="utf-8") as f:
        data = json.load(f)
        blocks = data.get("blocks") or []

    doc = fitz.open(str(pdf))
    for b in blocks:
        bbox = b.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        page_idx = int(b.get("page_idx") if b.get("page_idx") is not None else b.get("page", 0))
        if page_idx < 0 or page_idx >= len(doc):
            continue
        page = doc[page_idx]
        rect = fitz.Rect(*[float(x) for x in bbox])
        color = pick_color(b)
        bt = b.get("block_type") or b.get("type") or "Text"
        suspicious = bool(b.get("suspicious_header"))
        raw_text = (b.get("text") or b.get("content") or "").strip()
        code = {"SectionHeader": "[H]", "Table": "[T]", "Figure": "[F]", "ListItem": "[L]"}.get(bt, "[P]")
        if bt == "SectionHeader":
            import re as _re
            head = (raw_text.split(".")[0] if "." in raw_text else raw_text).strip()
            if len(head) > 60: head = head[:57] + "…"
            why = []
            if _re.match(r"^\d+(?:[.\-](?:\d+|[A-Za-z]+))*[.)]?\s+\S", raw_text): why.append("outline")
            elif _re.match(r"^[IVXLCDM]+[.)]?\s+\S", raw_text): why.append("roman")
            if raw_text.isupper(): why.append("caps")
            if raw_text.endswith(":"): why.append("colon")
            letters=[ch for ch in raw_text if ch.isalpha()]; lower_ratio=(sum(ch.islower() for ch in letters)/len(letters)) if letters else 0.0
            if lower_ratio>=0.5 or len(raw_text.split())>=10: why.append("sentence?")
            label = f"{code} {head}" + (f"  ({','.join(why)})" if why else "")
        else:
            hint = norm_text(raw_text)[:40]
            label = f"{code} {hint}" if hint else code
        if suspicious: label += "  [SUSP]"
        add_rect_with_label(page, rect, label, color=color)

    doc.save(str(out))
    doc.close()
    print(f"Wrote annotated PDF: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
