#!/usr/bin/env python3
"""
Convert a Label Studio export (JSON) back into annotated PDFs by embedding
rectangle + FreeText annotations (machine_note mini-schema) via PyMuPDF.

Inputs:
- Label Studio export JSON (Project → Export → JSON). Each task should contain
  `data.source_pdf` and `data.page` as produced by our forward converter.

Outputs:
- Writes annotated copies of the source PDFs to an output directory, without
  modifying the originals. Each rectangle region is paired with a FreeText
  annotation containing a JSON mini-schema: {id, type, expected_json}.

Usage:
  python -m src.extractor.tools.labelstudio.ls_export_to_pdf \
    --export data/labelstudio/exports/my_project-annotations.json \
    --out-dir data/labelstudio/annotated_pdfs

Notes:
- We try to use the latest human annotation in `annotations`. If absent, we fall
  back to `predictions`.
- We link per-region fields (type/id/expected_json) to rectangles using
  `region_id` when present. If not available, we loosely match by `from_name` and
  presence of rectangle coords.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    raise SystemExit("PyMuPDF (fitz) is required. Install with `pip install pymupdf`.\n" + str(e))


def _pick_results(task: Dict) -> List[Dict]:
    """Pick the best set of results from a Label Studio task.

    Preference order: latest annotation → first annotation → first prediction → []
    """
    anns = task.get("annotations") or []
    if isinstance(anns, list) and anns:
        # Prefer the last one (often most recent / accepted)
        anns_sorted = sorted(anns, key=lambda a: a.get("updated_at") or a.get("id") or 0)
        return anns_sorted[-1].get("result", [])
    preds = task.get("predictions") or []
    if isinstance(preds, list) and preds:
        return preds[0].get("result", [])
    return []


def _group_regions(results: List[Dict]) -> Dict[str, Dict]:
    """Group LS results per rectangle region.

    Returns mapping region_key → {
      'rect': {x,y,width,height}, 'type': str|None, 'id': str|None, 'expected_json': str|None
    }

    We primarily link on 'region_id' → rectangle 'id'. If 'region_id' is missing,
    we attach non-rect entries to the last seen rectangle as a best-effort fallback.
    """
    regions: Dict[str, Dict] = {}
    last_rect_key: Optional[str] = None

    # First pass: capture rects
    for r in results:
        if r.get("type") == "rectanglelabels" and r.get("from_name") == "label":
            rid = r.get("id") or r.get("origin_id") or f"rect_{len(regions)}"
            val = r.get("value", {})
            if all(k in val for k in ("x", "y", "width", "height")):
                regions[rid] = {
                    "rect": {k: float(val[k]) for k in ("x", "y", "width", "height")},
                    "type": None,
                    "id": None,
                    "expected_json": None,
                }
                last_rect_key = rid

    # Second pass: attach per-region fields
    for r in results:
        if r.get("type") == "rectanglelabels":
            continue
        rgn = r.get("region_id") or last_rect_key
        if not rgn or rgn not in regions:
            continue
        fn = r.get("from_name")
        val = r.get("value", {})
        if fn == "type":
            choices = val.get("choices") or []
            if choices:
                regions[rgn]["type"] = str(choices[0]).strip()
        elif fn == "id":
            txt = val.get("text") or []
            if txt:
                regions[rgn]["id"] = str(txt[0]).strip()
        elif fn == "expected_json":
            txt = val.get("text") or []
            if txt:
                regions[rgn]["expected_json"] = str(txt[0]).strip()

    return regions


def _ls_to_pdf_rect(val: Dict[str, float], page_w: float, page_h: float) -> fitz.Rect:
    """Convert LS percent rect to PDF rect (bottom-left origin)."""
    x = float(val["x"]) / 100.0 * page_w
    top = float(val["y"]) / 100.0 * page_h
    w = float(val["width"]) / 100.0 * page_w
    h = float(val["height"]) / 100.0 * page_h
    x0 = x
    x1 = x + w
    y1 = page_h - top
    y0 = y1 - h
    return fitz.Rect(x0, y0, x1, y1)


def _embed_regions(doc: fitz.Document, page_index: int, regions: Dict[str, Dict]):
    page = doc[page_index]
    W, H = page.rect.width, page.rect.height
    for r in regions.values():
        rect = _ls_to_pdf_rect(r["rect"], W, H)
        # Rectangle annotation
        try:
            page.add_rect_annot(rect)
        except AttributeError:
            # Older PyMuPDF fallback
            page.addRectAnnot(rect)

        # FreeText machine_note as JSON
        meta = {k: v for k, v in {
            "id": r.get("id"),
            "type": r.get("type"),
            "expected_json": r.get("expected_json"),
        }.items() if v is not None}
        content = json.dumps(meta, ensure_ascii=False)
        try:
            page.add_freetext_annot(rect, content)
        except AttributeError:
            page.addFreetextAnnot(rect, content)


def main():
    ap = argparse.ArgumentParser(description="Convert Label Studio JSON export back into annotated PDFs.")
    ap.add_argument("--export", required=True, help="Path to Label Studio export JSON (list of tasks)")
    ap.add_argument("--out-dir", default="data/labelstudio/annotated_pdfs", help="Output directory for annotated PDFs")
    ap.add_argument("--suffix", default="_ls_marked", help="Suffix for output filenames before .pdf")
    args = ap.parse_args()

    export_path = Path(args.export)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(export_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)
    if not isinstance(tasks, list):
        raise SystemExit("Export JSON does not look like a list of tasks.")

    # Group tasks by source PDF
    by_pdf: Dict[str, List[Dict]] = defaultdict(list)
    for t in tasks:
        data = t.get("data") or {}
        pdf = data.get("source_pdf")
        if not pdf:
            # Try to infer from doc_id if provided
            doc_id = data.get("doc_id")
            if doc_id:
                # Heuristic: look under data/input/pipeline/<doc_id>.pdf
                candidate = Path("data/input/pipeline") / f"{doc_id}.pdf"
                if candidate.exists():
                    pdf = str(candidate)
        if not pdf:
            continue
        by_pdf[pdf].append(t)

    if not by_pdf:
        raise SystemExit("No tasks contained 'data.source_pdf' (or inferable doc). Nothing to do.")

    for pdf, items in by_pdf.items():
        src_pdf = Path(pdf)
        if not src_pdf.exists():
            print(f"[warn] Source PDF not found: {src_pdf} — skipping.")
            continue
        doc = fitz.open(src_pdf)
        # Output path
        out_pdf = out_dir / f"{src_pdf.stem}{args.suffix}.pdf"
        print(f"Annotating: {src_pdf} → {out_pdf}")

        for t in items:
            data = t.get("data") or {}
            page_num = int(data.get("page") or 1)
            page_index = max(0, page_num - 1)
            results = _pick_results(t)
            regions = _group_regions(results)
            if not regions:
                continue
            _embed_regions(doc, page_index, regions)

        doc.save(out_pdf)
        doc.close()
        print(f"Wrote: {out_pdf}")


if __name__ == "__main__":  # pragma: no cover
    main()

