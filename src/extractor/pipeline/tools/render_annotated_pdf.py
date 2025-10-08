#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.16.0",
#   "pymupdf>=1.26.1",
# ]
# ///

"""
Render an annotated, viewable PDF that overlays rectangles and labels for
pipeline-detected PDF objects (Stage 02 blocks or Stage 01 annotations).

Usage (Stage 02 blocks):
  uv run python -m extractor.pipeline.tools.render_annotated_pdf \
    --pdf "data/results/pipeline/01_annotation_processor/<stem>_clean.pdf" \
    --blocks-json "data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json" \
    --out "data/results/pipeline/annotated/<stem>__blocks_annotated.pdf"

Usage (Stage 01 annotations):
  uv run python -m extractor.pipeline.tools.render_annotated_pdf \
    --pdf "data/results/pipeline/01_annotation_processor/<stem>_clean.pdf" \
    --stage01-json "data/results/pipeline/01_annotation_processor/json_output/01_annotations.json" \
    --out "data/results/pipeline/annotated/<stem>__stage01_annotated.pdf"

Notes
- Coordinates are assumed to be in PDF points (72 DPI) and page-indexed from 0.
- This writes actual PDF annotations (Square + FreeText) so any viewer can toggle
  or inspect them. No rasterization required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import json
import math
import typer

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    raise SystemExit(f"PyMuPDF (fitz) is required: {e}")


app = typer.Typer(help="Render overlays for pipeline PDF objects into a viewable PDF")


# ---------------------------- helpers ---------------------------- #


def _color_rgb(name: str) -> Tuple[float, float, float]:
    """Simple color palette by logical block type names (case-insensitive)."""
    n = (name or "").lower()
    if any(k in n for k in ("section", "header")):
        return (0.95, 0.45, 0.10)  # orange
    if "table" in n:
        return (0.10, 0.60, 0.95)  # blue
    if "figure" in n or "image" in n:
        return (0.10, 0.80, 0.40)  # green
    if "equation" in n or "math" in n:
        return (0.60, 0.10, 0.95)  # purple
    if "caption" in n:
        return (0.80, 0.50, 0.10)  # brown-ish
    if "list" in n:
        return (0.90, 0.10, 0.40)  # pink/red
    if "footnote" in n:
        return (0.40, 0.40, 0.40)  # gray
    # default
    return (0.95, 0.10, 0.10)  # red


def _add_rect_annot(
    page: "fitz.Page",
    rect: "fitz.Rect",
    color: Tuple[float, float, float],
    width: float = 1.0,
    *,
    fill: Optional[Tuple[float, float, float]] = None,
    alpha: float = 1.0,
):
    try:
        annot = page.add_rect_annot(rect)
    except AttributeError:  # older PyMuPDF
        annot = page.addRectAnnot(rect)
    # style
    try:
        annot.set_border(width=width)
    except Exception:
        pass
    try:
        annot.set_colors(stroke=color, fill=fill)
    except Exception:
        try:
            annot.setColors(stroke=color, fill=fill)
        except Exception:
            pass
    try:
        if 0.0 <= alpha <= 1.0:
            annot.set_opacity(alpha)
    except Exception:
        pass
    try:
        annot.update()
    except Exception:
        pass
    return annot


def _add_label(page: "fitz.Page", rect: "fitz.Rect", text: str, color: Tuple[float, float, float]):
    # place label slightly above-left of the box; clamp within page bounds
    padding = 2.0
    label_h = 12.0
    raw_rect = fitz.Rect(
        rect.x0,
        rect.y0 - (label_h + padding),
        rect.x0 + max(60.0, len(text) * 3.5),
        rect.y0 - padding,
    )
    label_rect = _clamp_to_page(raw_rect, page.rect)
    if label_rect is None or label_rect.height <= 1.0:
        # fallback: draw inside the box at top-left
        y0 = min(rect.y1 - padding, max(rect.y0 + padding, 0.0))
        label_rect = _clamp_to_page(
            fitz.Rect(rect.x0 + padding, y0, rect.x0 + max(60.0, len(text) * 3.5), y0 + label_h),
            page.rect,
        )
        if label_rect is None:
            return None
    try:
        fta = page.add_freetext_annot(label_rect, text)
    except AttributeError:
        fta = page.addFreetextAnnot(label_rect, text)
    try:
        fta.set_colors(stroke=color, fill=(1, 1, 1))
    except Exception:
        try:
            fta.setColors(stroke=color, fill=(1, 1, 1))
        except Exception:
            pass
    try:
        fta.update()
    except Exception:
        pass
    return fta


def _add_label_tab(
    page: "fitz.Page",
    rect: "fitz.Rect",
    text: str,
    color: Tuple[float, float, float],
    *,
    alpha: float = 0.2,
):
    """Draw a small tab overlapping the upper-right corner of the box.

    Uses a FreeText annotation with background fill and optional opacity.
    """
    tab_h = 12.0
    tab_w = max(56.0, min(120.0, len(text) * 4.2))
    # Anchor to upper-right, overlapping box slightly
    raw = fitz.Rect(rect.x1 - tab_w, rect.y0 - (tab_h / 2.0), rect.x1, rect.y0 + tab_h / 2.0)
    tab_rect = _clamp_to_page(raw, page.rect)
    if tab_rect is None:
        return None
    try:
        fta = page.add_freetext_annot(tab_rect, text)
    except AttributeError:
        fta = page.addFreetextAnnot(tab_rect, text)
    # Style: filled with type color; white text
    try:
        fta.set_colors(stroke=color, fill=color, text=(1, 1, 1))
    except Exception:
        try:
            fta.setColors(stroke=color, fill=color)
        except Exception:
            pass
    try:
        if 0.0 <= alpha <= 1.0:
            fta.set_opacity(alpha)
    except Exception:
        pass
    try:
        fta.update()
    except Exception:
        pass
    return fta

def _rect_from(obj: Dict[str, Any]) -> Optional["fitz.Rect"]:
    bb = obj.get("bbox") or obj.get("original_rect") or obj.get("expanded_rect")
    if not isinstance(bb, (list, tuple)) or len(bb) != 4:
        return None
    try:
        x0, y0, x1, y1 = [float(v) for v in bb]
        return fitz.Rect(x0, y0, x1, y1)
    except Exception:
        return None


def _page_index(obj: Dict[str, Any]) -> Optional[int]:
    # prefer 0-based 'page' or 'page_idx'; tolerate 1-based 'page_num'
    if obj.get("page") is not None:
        try:
            return int(obj["page"])  # assumed 0-based in our pipeline
        except Exception:
            pass
    if obj.get("page_idx") is not None:
        try:
            return int(obj["page_idx"])  # 0-based
        except Exception:
            pass
    if obj.get("page_num") is not None:
        try:
            return max(0, int(obj["page_num"]) - 1)  # 1-based → 0-based
        except Exception:
            pass
    return None


def _label_for(obj: Dict[str, Any], default_type_key: str = "block_type") -> str:
    t = str(obj.get(default_type_key) or obj.get("type") or "obj").strip()
    i = str(obj.get("block_id") or obj.get("id") or "").strip()
    if i:
        return f"{t}:{i}"
    return t


def _clamp_to_page(rect: "fitz.Rect", page_rect: "fitz.Rect") -> Optional["fitz.Rect"]:
    """Clamp a rect to page bounds and ensure positive area, else return None."""
    try:
        r = fitz.Rect(
            max(page_rect.x0, rect.x0),
            max(page_rect.y0, rect.y0),
            min(page_rect.x1, rect.x1),
            min(page_rect.y1, rect.y1),
        )
        if r.width <= 0 or r.height <= 0:
            return None
        return r
    except Exception:
        return None


# ------------------------------ CLI ------------------------------ #


@app.command()
def from_blocks(
    pdf: Path = typer.Option(..., "--pdf", help="Input PDF (prefer Stage 01 clean PDF)", exists=True, dir_okay=False),
    blocks_json: Path = typer.Option(..., "--blocks-json", help="Stage 02 blocks JSON (02_marker_blocks.json)", exists=True, dir_okay=False),
    out: Path = typer.Option(..., "--out", help="Output annotated PDF path"),
    block_type_key: str = typer.Option("block_type", help="Key for type label in blocks JSON"),
    min_width: float = typer.Option(6.0, help="Minimum box width to draw (pt)"),
    min_height: float = typer.Option(6.0, help="Minimum box height to draw (pt)"),
    style: str = typer.Option("both", help="Annotation style: stroke|fill|both"),
    fill_alpha: float = typer.Option(0.12, help="Fill opacity (0..1) when style includes fill"),
    label_style: str = typer.Option(
        "tab", help="Label style: tab|free"
    ),
    label_off: bool = typer.Option(
        False, "--label-off/--label-on", help="Disable labels entirely"
    ),
):
    """Render overlays from Stage 02 blocks JSON onto the PDF."""
    data = json.loads(blocks_json.read_text())
    blocks = data.get("blocks") if isinstance(data, dict) else None
    if not isinstance(blocks, list):
        raise SystemExit("Invalid blocks JSON: expected {\"blocks\": [...]} at top level")

    doc = fitz.open(str(pdf))
    with doc:
        for b in blocks:
            rect0 = _rect_from(b)
            pno = _page_index(b)
            if rect0 is None or pno is None or not (0 <= pno < len(doc)):
                continue
            page = doc[pno]
            rect = _clamp_to_page(rect0, page.rect)
            if rect is None or rect.width < min_width or rect.height < min_height:
                continue
            label = _label_for(b, default_type_key=block_type_key)
            color = _color_rgb(label)
            use_fill = color if style in {"fill", "both"} else None
            use_alpha = fill_alpha if style in {"fill", "both"} else 1.0
            _add_rect_annot(page, rect, color=color, width=1.2, fill=use_fill, alpha=use_alpha)
            if not label_off:
                if label_style == "free":
                    _add_label(page, rect, text=label, color=color)
                else:
                    _add_label_tab(page, rect, text=label, color=color, alpha=0.25)

        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))
    typer.secho(f"Wrote annotated PDF: {out}", fg=typer.colors.GREEN)


@app.command()
def from_stage01(
    pdf: Path = typer.Option(..., "--pdf", help="Input PDF (Stage 01 clean PDF)", exists=True, dir_okay=False),
    stage01_json: Path = typer.Option(..., "--stage01-json", help="01_annotations.json path", exists=True, dir_okay=False),
    out: Path = typer.Option(..., "--out", help="Output annotated PDF path"),
    style: str = typer.Option("both", help="Annotation style: stroke|fill|both"),
    fill_alpha: float = typer.Option(0.12, help="Fill opacity (0..1) when style includes fill"),
    label_style: str = typer.Option(
        "tab", help="Label style: tab|free"
    ),
    label_off: bool = typer.Option(
        False, "--label-off/--label-on", help="Disable labels entirely"
    ),
):
    """Render overlays from Stage 01 annotations JSON (original/expanded rects)."""
    data = json.loads(stage01_json.read_text())
    annots = data.get("annotations") if isinstance(data, dict) else None
    if not isinstance(annots, list):
        raise SystemExit("Invalid Stage 01 JSON: expected {\"annotations\": [...]} at top level")

    doc = fitz.open(str(pdf))
    with doc:
        for a in annots:
            rect0 = _rect_from(a)
            pno = _page_index(a)
            if rect0 is None or pno is None or not (0 <= pno < len(doc)):
                continue
            page = doc[pno]
            rect = _clamp_to_page(rect0, page.rect)
            if rect is None:
                continue
            t = str(((a.get("interpretation") or {}).get("inferred_object") or {}).get("type") or a.get("type") or "region")
            label = f"{t}:{a.get('id','')}".rstrip(":")
            color = _color_rgb(t)
            use_fill = color if style in {"fill", "both"} else None
            use_alpha = fill_alpha if style in {"fill", "both"} else 1.0
            _add_rect_annot(page, rect, color=color, width=1.2, fill=use_fill, alpha=use_alpha)
            if not label_off:
                if label_style == "free":
                    _add_label(page, rect, text=label, color=color)
                else:
                    _add_label_tab(page, rect, text=label, color=color, alpha=0.25)

        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))
    typer.secho(f"Wrote annotated PDF: {out}", fg=typer.colors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    app()
