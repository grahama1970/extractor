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

# ---------------- Palette & outline defaults ---------------- #
_PALETTES: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    "default": {
        "section": (0.95, 0.45, 0.10),
        "table": (0.10, 0.60, 0.95),
        "figure": (0.10, 0.80, 0.40),
        "equation": (0.60, 0.10, 0.95),
        "caption": (0.80, 0.50, 0.10),
        "list": (0.90, 0.10, 0.40),
        "footnote": (0.40, 0.40, 0.40),
        "_default": (0.95, 0.10, 0.10),
    },
    "colorblind-safe": {
        "section": (0.90, 0.60, 0.00),
        "table": (0.00, 0.45, 0.70),
        "figure": (0.00, 0.60, 0.50),
        "equation": (0.80, 0.40, 0.00),
        "caption": (0.35, 0.70, 0.90),
        "list": (0.80, 0.60, 0.70),
        "footnote": (0.60, 0.60, 0.60),
        "_default": (0.00, 0.00, 0.00),
    },
}

_OUTLINE_DEFAULTS: Dict[str, float] = {
    "section": 1.4,
    "table": 1.8,
    "figure": 1.4,
    "equation": 1.4,
    "caption": 1.2,
    "list": 1.2,
    "footnote": 1.0,
    "_default": 1.2,
}


# ---------------------------- helpers ---------------------------- #


def _color_rgb(name: str, palette: Dict[str, Tuple[float, float, float]]) -> Tuple[float, float, float]:
    """Lookup color from palette; fallback to '_default'."""
    n = (name or "").lower()
    if "section" in n or "header" in n:
        return palette.get("section", palette["_default"])
    if "table" in n:
        return palette.get("table", palette["_default"])
    if "figure" in n or "image" in n:
        return palette.get("figure", palette["_default"])
    if "equation" in n or "math" in n:
        return palette.get("equation", palette["_default"])
    if "caption" in n:
        return palette.get("caption", palette["_default"])
    if "list" in n:
        return palette.get("list", palette["_default"])
    if "footnote" in n:
        return palette.get("footnote", palette["_default"])
    return palette["_default"]


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


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3] + "..."


def _add_label(
    page: "fitz.Page",
    rect: "fitz.Rect",
    text: str,
    color: Tuple[float, float, float],
    *,
    min_font_size: float,
    max_width: float = 160.0,
):
    # place label slightly above-left of the box; clamp within page bounds
    padding = 2.0
    label_h = 12.0
    raw_rect = fitz.Rect(
        rect.x0,
        rect.y0 - (label_h + padding),
        rect.x0 + max(60.0, min(max_width, len(text) * 3.5)),
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
    label_text = _truncate(text, 48)
    try:
        fta = page.add_freetext_annot(label_rect, label_text)
    except AttributeError:
        fta = page.addFreetextAnnot(label_rect, label_text)
    try:
        fta.set_colors(stroke=color, fill=(1, 1, 1))
    except Exception:
        try:
            fta.setColors(stroke=color, fill=(1, 1, 1))
        except Exception:
            pass
    # Attempt adaptive font size to fit
    try:
        target_w = label_rect.width - 4
        size = 10.0
        est_w = len(label_text) * (size * 0.55)
        while est_w > target_w and size > min_font_size:
            size -= 0.5
            est_w = len(label_text) * (size * 0.55)
        if size < min_font_size:
            size = min_font_size
        try:
            fta.set_font("helv", size=size)
        except Exception:
            pass
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
    label_text = _truncate(text, 48)
    try:
        fta = page.add_freetext_annot(tab_rect, label_text)
    except AttributeError:
        fta = page.addFreetextAnnot(tab_rect, label_text)
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


def _add_link_annotation(page: "fitz.Page", rect: "fitz.Rect", target: Path) -> None:
    """Add a link annotation pointing to an external target (file:// URI).

    Uses insert_link when available; falls back silently if unsupported.
    """
    try:
        uri = target.resolve().as_uri()
        try:
            # Modern API
            page.insert_link({"from": rect, "uri": uri})
        except Exception:
            # Alternate API
            page.add_link(rect=rect, uri=uri)  # type: ignore[attr-defined]
    except Exception:
        return

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
    verify_dir: Optional[Path] = typer.Option(
        None,
        "--verify-dir",
        help="Optional Stage 05 verify dir; when set, add link annots for Table blocks to table_XXXX/view.html if exists.",
    ),
    palette: str = typer.Option("default", "--palette", help="Color palette: default|colorblind-safe"),
    legend: bool = typer.Option(False, "--legend/--no-legend", help="Render legend on page 1"),
    min_font_size: float = typer.Option(7.0, "--min-font-size", help="Minimum label font size"),
    outline_widths: Optional[str] = typer.Option(
        None,
        "--outline-widths",
        help="Comma list type:width (e.g. table:2.0,section:1.5); overrides defaults",
    ),
):
    """Render overlays from Stage 02 blocks JSON onto the PDF."""
    data = json.loads(blocks_json.read_text())
    blocks = data.get("blocks") if isinstance(data, dict) else None
    if not isinstance(blocks, list):
        raise SystemExit("Invalid blocks JSON: expected {\"blocks\": [...]} at top level")

    if palette not in _PALETTES:
        raise SystemExit(f"Unknown palette '{palette}'. Choices: {', '.join(_PALETTES.keys())}")
    pal = _PALETTES[palette]
    # parse overrides
    outline_overrides: Dict[str, float] = {}
    if outline_widths:
        for part in [p.strip() for p in outline_widths.split(",") if p.strip()]:
            if ":" in part:
                k, v = part.split(":", 1)
                try:
                    outline_overrides[k.strip().lower()] = float(v.strip())
                except Exception:
                    pass

    doc = fitz.open(str(pdf))
    with doc:
        if legend and len(doc) > 0:
            try:
                _render_legend(doc[0], pal)
            except Exception:
                pass
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
            color = _color_rgb(label, pal)
            logical_type = (b.get(block_type_key) or "").lower()
            ow = outline_overrides.get(logical_type, _OUTLINE_DEFAULTS.get(logical_type, _OUTLINE_DEFAULTS["_default"]))
            use_fill = color if style in {"fill", "both"} else None
            use_alpha = fill_alpha if style in {"fill", "both"} else 1.0
            _add_rect_annot(page, rect, color=color, width=ow, fill=use_fill, alpha=use_alpha)
            if not label_off:
                if label_style == "free":
                    _add_label(page, rect, text=label, color=color, min_font_size=min_font_size)
                else:
                    _add_label_tab(page, rect, text=label, color=color, alpha=0.25)
            # Optional: link table to verify view.html
            try:
                if verify_dir and isinstance(b.get("block_type"), str) and b.get("block_type").lower() == "table":
                    tid = b.get("raw_table_id") or b.get("table_id")
                    if isinstance(tid, str):
                        candidate = verify_dir / tid.replace("rawtbl_", "table_") / "view.html"
                        if candidate.exists():
                            _add_link_annotation(page, rect, candidate)
            except Exception:
                pass

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
            color = _color_rgb(t, _PALETTES["default"])
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
