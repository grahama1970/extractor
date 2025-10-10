#!/usr/bin/env python3
"""
Stage 06c: PDF Annotator (deterministic, no LLM)

Overlays rectangles for sections, tables, and figures on the clean PDF to aid
visual review and collaboration. Writes an annotated PDF and a JSON index of
all overlays for downstream tooling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyMuPDF (fitz) is required for 06c_pdf_annotator") from e


app = typer.Typer(help="Overlay section/table/figure boxes on a PDF (deterministic)")


def _safe_get_bbox(obj: Dict[str, Any]) -> Optional[List[float]]:
    bb = obj.get("bbox") or obj.get("box")
    if not isinstance(bb, (list, tuple)) or len(bb) != 4:
        return None
    try:
        return [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
    except Exception:
        return None


@app.command()
def run(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    sections_json: Path = typer.Option(..., "--sections", exists=True, help="Stage 04 sections JSON"),
    tables_json: Path = typer.Option(..., "--tables", exists=True, help="Stage 05 tables JSON"),
    figures_json: Path = typer.Option(..., "--figures", exists=True, help="Stage 06 figures JSON"),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Results root"),
):
    stage_dir = output_dir / "06c_pdf_annotator"
    stage_dir.mkdir(parents=True, exist_ok=True)
    json_dir = stage_dir / "json_output"
    json_dir.mkdir(exist_ok=True)

    # Load inputs
    sections = (json.loads(sections_json.read_text(encoding="utf-8")).get("sections") or [])
    tables = (json.loads(tables_json.read_text(encoding="utf-8")).get("tables") or [])
    figures = (json.loads(figures_json.read_text(encoding="utf-8")).get("figures") or [])

    # Annotate
    doc = fitz.open(str(pdf_path))
    overlays: List[Dict[str, Any]] = []

    def _add(page_idx: int, bbox: List[float], kind: str, payload: Dict[str, Any]) -> None:
        if page_idx < 0 or page_idx >= len(doc):
            return
        page = doc[page_idx]
        rect = fitz.Rect(*bbox)
        color = (0, 1, 0) if kind == "section" else (1, 0, 0) if kind == "table" else (0, 0, 1)
        page.draw_rect(rect, color=color, width=0.8, fill=None, overlay=True)
        overlays.append({"page": page_idx, "bbox": list(bbox), "kind": kind, **payload})

    for s in sections:
        pg0 = int(s.get("page_start") or s.get("page_idx") or -1)
        bb = _safe_get_bbox(s)
        if bb is not None and pg0 >= 0:
            _add(pg0, bb, "section", {"id": s.get("id"), "title": s.get("title")})

    for t in tables:
        pg = int(t.get("page_index") or t.get("page_idx") or -1)
        bb = _safe_get_bbox(t)
        if bb is not None and pg >= 0:
            _add(pg, bb, "table", {"table_index": t.get("table_index")})

    for f in figures:
        pg = int(f.get("page") or f.get("page_idx") or -1)
        bb = _safe_get_bbox(f)
        if bb is not None and pg >= 0:
            _add(pg, bb, "figure", {"figure_id": f.get("figure_id")})

    # Save outputs
    annotated_pdf = stage_dir / "annotated.pdf"
    doc.save(str(annotated_pdf))
    doc.close()

    (json_dir / "06c_annotations.json").write_text(
        json.dumps({"overlays": overlays}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    typer.echo(f"Annotated PDF saved: {annotated_pdf}")


if __name__ == "__main__":
    app()

