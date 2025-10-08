#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.16.0",
#   "pymupdf>=1.26.1",
# ]
# ///

from __future__ import annotations

"""
Import existing PDF annotations (Rect/FreeText/etc.) as a normalized JSON layer
for the UI. This does NOT affect extraction; it only provides a gold/reference
overlay to compare against in the web interface.

Output: <results_dir>/ui/gold_from_pdf.json
Schema (partial):
{
  "source_pdf": "...",
  "count": N,
  "items": [
     {"page": 0, "bbox": [x0,y0,x1,y1], "type": "FreeText", "text": "...", "source": "pdf-annot"}
  ]
}
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer


app = typer.Typer(help="Import PDF annotations to a UI gold layer JSON")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _norm_type(subtype: str | None, info: Dict[str, Any]) -> str:
    t = (subtype or "").strip() or (info.get("subject") or info.get("title") or "")
    t = str(t or "Annotation")
    # Simple mapping to our logical types when obvious
    low = t.lower()
    if "table" in low:
        return "Table"
    if "header" in low or "section" in low:
        return "SectionHeader"
    if "figure" in low or "image" in low:
        return "Figure"
    if "list" in low:
        return "ListItem"
    return t


@app.command()
def import_pdf(
    results_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    pdf_path: Optional[Path] = typer.Option(None, "--pdf", help="Explicit source PDF; otherwise inferred from 01_annotations.json"),
):
    try:
        import fitz  # type: ignore
    except Exception as e:  # pragma: no cover
        raise SystemExit(f"PyMuPDF (fitz) is required: {e}")

    rd = Path(results_dir)
    if pdf_path is None:
        s01 = rd / "01_annotation_processor" / "json_output" / "01_annotations.json"
        if s01.exists():
            try:
                data = json.loads(s01.read_text())
                src = data.get("source_pdf")
                if src:
                    pdf_path = Path(src)
            except Exception:
                pdf_path = None
    if not pdf_path or not pdf_path.exists():
        raise SystemExit("Unable to determine source PDF (pass --pdf or ensure 01_annotations.json contains source_pdf)")

    items: List[Dict[str, Any]] = []
    doc = fitz.open(str(pdf_path))
    with doc:
        for pno in range(len(doc)):
            page = doc[pno]
            try:
                annots = page.annots() or []
            except Exception:
                annots = []
            for a in annots:
                try:
                    rect = a.rect
                    bbox = [
                        _safe_float(rect.x0),
                        _safe_float(rect.y0),
                        _safe_float(rect.x1),
                        _safe_float(rect.y1),
                    ]
                    info = a.info or {}
                    subtype = getattr(a, "type", ("", ""))[0] if hasattr(a, "type") else info.get("type")
                    itype = _norm_type(subtype, info)
                    text = info.get("content") or info.get("subject") or info.get("title") or ""
                    items.append({
                        "page": pno,
                        "bbox": bbox,
                        "type": itype,
                        "text": text,
                        "source": "pdf-annot",
                    })
                except Exception:
                    continue

    out_dir = rd / "ui"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"source_pdf": str(pdf_path), "count": len(items), "items": items}
    out_path = out_dir / "gold_from_pdf.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    typer.secho(f"Wrote gold annotations: {out_path}", fg=typer.colors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    app()

