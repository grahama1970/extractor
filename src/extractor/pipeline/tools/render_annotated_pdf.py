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

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import json
import typer

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    raise SystemExit(f"PyMuPDF (fitz) is required: {e}")


app = typer.Typer(help="Render overlays for pipeline PDF objects into a viewable PDF")


def _color_rgb(name: str) -> Tuple[float, float, float]:
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
    return (0.95, 0.10, 0.10)  # default red


def _add_rect_annot(
    page: "fitz.Page",
    rect: "fitz.Rect",
    color: Tuple[float, float, float],
    width: float = 1.2,
    *,
    fill: Optional[Tuple[float, float, float]] = None,
    alpha: float = 1.0,
):
    try:
        annot = page.add_rect_annot(rect)
    except AttributeError:  # older PyMuPDF
        annot = page.addRectAnnot(rect)
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
    # Improve viewer compatibility: ensure annotation is printable/visible
    try:
        flag_val = getattr(fitz, "ANNOT_FLAG_PRINT", None) or getattr(fitz, "PDF_ANNOT_PRINT", None)
        if flag_val is not None:
            annot.set_flags(flag_val)
    except Exception:
        pass
    try:
        annot.update()
    except Exception:
        pass
    return annot


def _draw_rect_overlay(
    page: "fitz.Page",
    rect: "fitz.Rect",
    color: Tuple[float, float, float],
    *,
    fill: bool = True,
    fill_alpha: float = 0.05,
    width: float = 1.0,
):
    try:
        sh = page.new_shape()
        sh.draw_rect(rect)
        # stroke_opacity defaults to 1.0; set fill_opacity for translucent fills
        if fill:
            sh.finish(
                color=color,
                fill=color,
                dashes=None,
                closePath=True,
                fill_opacity=max(0.0, min(1.0, float(fill_alpha))),
                stroke_opacity=1.0,
                width=max(0.5, float(width)),
            )
        else:
            sh.finish(
                color=color,
                fill=None,
                dashes=None,
                closePath=True,
                stroke_opacity=1.0,
                width=max(0.5, float(width)),
            )
        sh.commit()
    except Exception:
        # Fallback: basic draw without alpha support
        try:
            page.draw_rect(
                rect, color=color, width=max(0.5, float(width)), fill=(color if fill else None)
            )
        except Exception:
            pass


def _add_label_tab(
    page: "fitz.Page",
    rect: "fitz.Rect",
    text: str,
    color: Tuple[float, float, float],
    *,
    alpha: float = 0.25,
    fontsize: float = 6.5,
):
    tab_h = 12.0
    tab_w = max(56.0, min(120.0, len(text) * 4.2))
    raw = fitz.Rect(rect.x1 - tab_w, rect.y0 - (tab_h / 2.0), rect.x1, rect.y0 + tab_h / 2.0)
    tab_rect = _clamp_to_page(raw, page.rect)
    if tab_rect is None:
        return None
    try:
        try:
            fta = page.add_freetext_annot(tab_rect, text, fontsize=max(5.0, float(fontsize)))
        except TypeError:
            fta = page.add_freetext_annot(tab_rect, text)
    except AttributeError:
        try:
            fta = page.addFreetextAnnot(tab_rect, text, fontsize=max(5.0, float(fontsize)))
        except Exception:
            fta = page.addFreetextAnnot(tab_rect, text)
    try:
        fta.set_colors(stroke=color, fill=color, text=(1, 1, 1))
    except Exception:
        try:
            fta.setColors(stroke=color, fill=color)
        except Exception:
            pass
    try:
        fta.set_border(width=0.0)
    except Exception:
        pass
    try:
        fta.set_opacity(alpha)
    except Exception:
        pass
    # Improve viewer compatibility for FreeText tabs
    try:
        flag_val = getattr(fitz, "ANNOT_FLAG_PRINT", None) or getattr(fitz, "PDF_ANNOT_PRINT", None)
        if flag_val is not None:
            fta.set_flags(flag_val)
    except Exception:
        pass
    try:
        fta.update()
    except Exception:
        pass
    return fta


def _draw_label_tab_overlay(
    page: "fitz.Page",
    rect: "fitz.Rect",
    text: str,
    color: Tuple[float, float, float],
    *,
    fontsize: float = 6.5,
):
    tab_h = 12.0
    tab_w = max(56.0, min(120.0, len(text) * 4.2))
    raw = fitz.Rect(rect.x1 - tab_w, rect.y0 - (tab_h / 2.0), rect.x1, rect.y0 + tab_h / 2.0)
    tab_rect = _clamp_to_page(raw, page.rect)
    if tab_rect is None:
        return
    # Draw filled tab
    _draw_rect_overlay(page, tab_rect, color, fill=True, fill_alpha=1.0, width=0.0)
    # White text inside tab
    try:
        page.insert_textbox(
            tab_rect, text, fontsize=max(5.0, float(fontsize)), color=(1, 1, 1), align=1
        )
    except Exception:
        pass


def _add_label_tab_inside_top_right(
    page: "fitz.Page",
    target_rect: "fitz.Rect",
    text: str,
    color: Tuple[float, float, float],
    *,
    fontsize: float = 8.0,
):
    """Place a filled tab inside the box at the top-right, flush to the right edge.

    Uses FreeText with white text on a colored rectangle for legibility.
    """
    label = text or ""
    tab_h = 14.0
    approx_char_w = 5.0
    tab_w = max(56.0, min(140.0, len(label) * approx_char_w + 10.0))
    inset = 1.0
    x1 = target_rect.x1
    x0 = max(target_rect.x0 + inset, x1 - tab_w)
    y0 = target_rect.y0 + inset
    y1 = min(target_rect.y1 - inset, y0 + tab_h)
    lab = fitz.Rect(x0, y0, x1, y1)
    lab = _clamp_to_page(lab, page.rect)
    if lab is None:
        return None
    try:
        fta = page.add_freetext_annot(lab, label, fontsize=max(6.0, float(fontsize)))
    except Exception:
        return None
    try:
        fta.set_colors(stroke=color, fill=color, text=(1, 1, 1))
    except Exception:
        try:
            fta.setColors(stroke=color, fill=color)
        except Exception:
            pass
    try:
        fta.set_border(width=0.0)
    except Exception:
        pass
    try:
        fta.set_info(content=label)
        fta.set_info(subject=label)
        fta.set_info(title=label)
    except Exception:
        pass
    try:
        flag_val = getattr(fitz, "ANNOT_FLAG_PRINT", None) or getattr(fitz, "PDF_ANNOT_PRINT", None)
        if flag_val is not None:
            fta.set_flags(flag_val)
    except Exception:
        pass
    try:
        fta.update()
    except Exception:
        pass
    return fta


def _add_note(page: "fitz.Page", rect: "fitz.Rect", text: str, color: Tuple[float, float, float]):
    """Add a small sticky note near the top-right of rect for compatibility with viewers' comment lists."""
    try:
        pt = fitz.Point(rect.x1 - 8, max(rect.y0 + 8, 8))
        na = page.add_text_annot(pt, text)
        try:
            na.set_colors(stroke=color, fill=None)
        except Exception:
            pass
        try:
            na.set_border(width=0)
        except Exception:
            pass
        try:
            flag_val = getattr(fitz, "ANNOT_FLAG_PRINT", None) or getattr(
                fitz, "PDF_ANNOT_PRINT", None
            )
            if flag_val is not None:
                na.set_flags(flag_val)
        except Exception:
            pass
        try:
            na.update()
        except Exception:
            pass
    except Exception:
        pass


def _add_freetext_bold(
    page: "fitz.Page",
    target_rect: "fitz.Rect",
    text: str,
    *,
    color: Tuple[float, float, float] = (0, 0, 0),
    fontsize: float = 8.0,
):
    """Add a tiny bold FreeText label inside the top-right of target_rect.

    Attempts multiple font options for bold; falls back gracefully if unsupported.
    Background is transparent; border removed.
    """
    try:
        tab_h = 12.0
        tab_w = max(32.0, min(140.0, len(text) * 5.0))
        inset = 1.0
        x1 = target_rect.x1 - inset
        x0 = max(target_rect.x0 + inset, x1 - tab_w)
        y0 = target_rect.y0 + inset
        y1 = min(target_rect.y1 - inset, y0 + tab_h)
        r = _clamp_to_page(fitz.Rect(x0, y0, x1, y1), page.rect)
        if r is None:
            return None
        ft = page.add_freetext_annot(r, text, fontsize=max(6.0, float(fontsize)))
        for name in ("helvB", "Helvetica-Bold", "Times-Bold", "Courier-Bold", "helv"):
            try:
                # Newer PyMuPDF
                if hasattr(ft, "set_font"):
                    try:
                        ft.set_font(name, max(6.0, float(fontsize)))
                        break
                    except Exception:
                        pass
            except Exception:
                pass
        try:
            ft.set_colors(stroke=None, fill=None, text=color)
        except Exception:
            pass
        try:
            ft.set_border(width=0.0)
        except Exception:
            pass
        try:
            ft.update()
        except Exception:
            pass
        return ft
    except Exception:
        return None


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
    if obj.get("page") is not None:
        try:
            return int(obj["page"])  # 0-based
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
    return f"{t}:{i}".rstrip(":")


def _clamp_to_page(rect: "fitz.Rect", page_rect: "fitz.Rect") -> Optional["fitz.Rect"]:
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


def _rect_from_camelot(bb: Iterable[float], page_rect: "fitz.Rect") -> Optional["fitz.Rect"]:
    """Convert Camelot bbox (origin bottom-left; y up) → PyMuPDF rect (origin top-left; y down)."""
    try:
        x0, y0, x1, y1 = [float(v) for v in bb]
        page_h = float(page_rect.height)
        y0_fitz = page_h - y1
        y1_fitz = page_h - y0
        return _clamp_to_page(fitz.Rect(x0, y0_fitz, x1, y1_fitz), page_rect)
    except Exception:
        return None


def _parse_pages(pages: str, total_pages: int) -> Optional[set[int]]:
    if not pages:
        return None
    out: set[int] = set()
    for chunk in pages.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            try:
                start = int(a)
                end = int(b)
            except ValueError:
                continue
            if start > end:
                start, end = end, start
            for n in range(start, end + 1):
                if 1 <= n <= total_pages:
                    out.add(n - 1)
        else:
            try:
                n = int(chunk)
            except ValueError:
                continue
            if 1 <= n <= total_pages:
                out.add(n - 1)
    return out or None


@app.command()
def from_run(
    pdf: Path = typer.Option(
        ..., "--pdf", help="Input Stage 01 clean PDF", exists=True, dir_okay=False
    ),
    run_dir: Path = typer.Option(
        ...,
        "--run-dir",
        help="Pipeline run directory (contains 02/04/05/06 JSON)",
        exists=True,
        file_okay=False,
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Output annotated PDF path"),
    include_sections: bool = typer.Option(True, help="Include Stage 04 sections"),
    include_tables: bool = typer.Option(True, help="Include Stage 05 tables"),
    include_figures: bool = typer.Option(True, help="Include Stage 06 figures"),
    include_text_groups: bool = typer.Option(True, help="Include Stage 02 text groups"),
    sections_style: str = typer.Option(
        "stroke", "--sections-style", help="Sections style: stroke|fill|both"
    ),
    fill_alpha: float = typer.Option(
        0.05,
        help="Fill opacity (0..1). Used for non-sections; sections use this when sections-style includes fill",
    ),
    tables_origin: str = typer.Option("camelot", help="Tables bbox origin: camelot|fitz"),
    export_pages: bool = typer.Option(
        False, help="Also export annotated pages as PNGs next to output"
    ),
    png_dpi: int = typer.Option(144, help="DPI for PNG export"),
    pages: str = typer.Option(
        "",
        help="Limit PNG export to these pages (1-indexed, e.g. '1,3,10-12'). PNG export only; PDF annotations are full-document.",
    ),
    legend: bool = typer.Option(
        False, help="Write per-page legend markdown files alongside the annotated PDF"
    ),
    figure_expand: float = typer.Option(
        0.20, help="Expand figure boxes by this fraction (e.g., 0.2 = +20%)"
    ),
):
    """Annotate sections, tables, figures, and text groups from a run directory."""
    # Resolve JSON paths
    p02 = run_dir / "02_marker_extractor/json_output/02_marker_blocks.json"
    p04 = run_dir / "04_section_builder/json_output/04_sections.json"
    p05 = run_dir / "05_table_extractor/json_output/05_tables.json"
    p06 = run_dir / "06_figure_extractor/json_output/06_figures.json"

    def _load(p: Path):
        try:
            return json.loads(p.read_text()) if p.exists() else None
        except Exception:
            return None

    j02, j04, j05, j06 = map(_load, (p02, p04, p05, p06))

    # Auto-name output when not provided
    if out is None:
        stem = pdf.stem
        if stem.endswith("_clean"):
            stem = stem[: -len("_clean")]
        out = Path("scripts/artifacts") / f"{stem}__run_annotated_prev.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf))
    with doc:
        legends: Dict[int, List[str]] = {}
        # Sections (Stage 04)
        if include_sections and j04 and isinstance(j04.get("sections"), list):
            for s in j04["sections"]:
                anchor = s.get("anchor") or {}
                bb = anchor.get("bbox")
                pno = anchor.get("page_idx")
                if not bb or pno is None or not (0 <= pno < len(doc)):
                    continue
                rect = _clamp_to_page(fitz.Rect(*bb), doc[pno].rect)
                if rect is None:
                    continue
                label = f"section:{(s.get('title') or 'Section')[:24]}"
                color = _color_rgb("section")
                use_fill = color if sections_style in {"fill", "both"} else None
                _add_rect_annot(
                    doc[pno],
                    rect,
                    color=color,
                    width=1.2,
                    fill=use_fill,
                    alpha=fill_alpha if use_fill else 1.0,
                )
                # Flattened overlay for guaranteed visibility
                _draw_rect_overlay(
                    doc[pno], rect, color, fill=bool(use_fill), fill_alpha=fill_alpha, width=1.2
                )
                _add_label_tab(doc[pno], rect, label, color, alpha=0.25, fontsize=6.5)
                _draw_label_tab_overlay(doc[pno], rect, label, color, fontsize=6.5)
                _add_note(doc[pno], rect, label, color)
                legends.setdefault(pno, []).append(label)

        # Tables (Stage 05)
        if include_tables and j05 and isinstance(j05.get("tables"), list):
            for t in j05["tables"]:
                bb = t.get("bbox")
                try:
                    pno = int(t.get("page_number", 1)) - 1
                except Exception:
                    pno = 0
                if not bb or not (0 <= pno < len(doc)):
                    continue
                if (tables_origin or "camelot").lower() == "camelot":
                    rect = _rect_from_camelot(bb, doc[pno].rect)
                else:
                    try:
                        rect = _clamp_to_page(fitz.Rect(*bb), doc[pno].rect)
                    except Exception:
                        rect = None
                if rect is None:
                    continue
                # Render-only: no page-area heuristics here; rely on Stage 05 filtering
                shp = t.get("pandas_metrics", {}).get("shape") or []
                int(shp[0]) if len(shp) > 0 and str(shp[0]).isdigit() else None
                int(shp[1]) if len(shp) > 1 and str(shp[1]).isdigit() else None
                # Allow 1-column tables; downstream can decide if they are paragraphs
                # Label: Table RxC for clarity
                label = f"Table {shp[0] if len(shp)>0 else '?'}x{shp[1] if len(shp)>1 else '?'}"
                color = _color_rgb("table")
                # Requirement: colored boxes with ~95% transparency (i.e., 5% opacity)
                ann = _add_rect_annot(
                    doc[pno],
                    rect,
                    color=color,
                    width=0.8,
                    fill=color,
                    alpha=max(0.0, min(1.0, fill_alpha)),
                )
                _draw_rect_overlay(
                    doc[pno], rect, color, fill=True, fill_alpha=fill_alpha, width=0.8
                )
                try:
                    if ann is not None:
                        ann.set_info(content=label)
                        ann.set_info(subject="Table")
                        ann.set_info(title=label)
                except Exception:
                    pass
                _add_note(doc[pno], rect, label, color)
                _add_freetext_bold(doc[pno], rect, label, color=(0, 0, 0), fontsize=8.0)
                legends.setdefault(pno, []).append(label)

        # Figures (Stage 06)
        if (
            include_figures
            and j06
            and isinstance(j06.get("figures"), list)
            and len(j06.get("figures") or []) > 0
        ):
            for f in j06["figures"]:
                bb = f.get("bbox")
                try:
                    pno = int(f.get("page_number", 1)) - 1
                except Exception:
                    pno = 0
                if not bb or not (0 <= pno < len(doc)):
                    continue
                rect0 = _clamp_to_page(fitz.Rect(*bb), doc[pno].rect)
                rect = rect0
                # Expand figure rectangle by figure_expand fraction around center
                if rect0 is not None and figure_expand and figure_expand != 0:
                    try:
                        cx = (rect0.x0 + rect0.x1) / 2.0
                        cy = (rect0.y0 + rect0.y1) / 2.0
                        w = rect0.width * (1.0 + figure_expand)
                        h = rect0.height * (1.0 + figure_expand)
                        rect = _clamp_to_page(
                            fitz.Rect(cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0),
                            doc[pno].rect,
                        )
                    except Exception:
                        rect = rect0
                if rect is None:
                    continue
                label = "Figure"
                color = _color_rgb("figure")
                ann = _add_rect_annot(
                    doc[pno],
                    rect,
                    color=color,
                    width=0.8,
                    fill=color,
                    alpha=max(0.0, min(1.0, fill_alpha)),
                )
                _draw_rect_overlay(
                    doc[pno], rect, color, fill=True, fill_alpha=fill_alpha, width=0.8
                )
                try:
                    if ann is not None:
                        try:
                            ann.set_info(content=label)
                            ann.set_info(subject=label)
                            ann.set_info(title=label)
                        except Exception:
                            pass
                except Exception:
                    pass
                _add_note(doc[pno], rect, label, color)
                _add_freetext_bold(doc[pno], rect, label, color=(0, 0, 0), fontsize=8.5)
                legends.setdefault(pno, []).append(label)
        # No fallback figures: render only Stage 06 output

        # Text groups (Stage 02 blocks)
        if include_text_groups and j02 and isinstance(j02.get("blocks"), list):
            for b in j02["blocks"]:
                btype = str(b.get("block_type") or "").lower()
                if "textgroup" not in btype:
                    continue
                rect0 = _rect_from(b)
                pno = _page_index(b)
                if rect0 is None or pno is None or not (0 <= pno < len(doc)):
                    continue
                rect = _clamp_to_page(rect0, doc[pno].rect)
                if rect is None:
                    continue
                label = "TextGroup"
                color = (0.45, 0.45, 0.45)
                ann = _add_rect_annot(
                    doc[pno],
                    rect,
                    color=color,
                    width=0.8,
                    fill=color,
                    alpha=max(0.0, min(1.0, fill_alpha)),
                )
                _draw_rect_overlay(
                    doc[pno], rect, color, fill=True, fill_alpha=fill_alpha, width=0.8
                )
                try:
                    if ann is not None:
                        ann.set_info(content=label)
                        ann.set_info(subject="TextGroup")
                        ann.set_info(title=label)
                except Exception:
                    pass
                _add_note(doc[pno], rect, label, color)
                _add_freetext_bold(doc[pno], rect, label, color=(0, 0, 0), fontsize=8.0)
                legends.setdefault(pno, []).append(label)

        out.parent.mkdir(parents=True, exist_ok=True)
        # Safe-save to repair any dangling references and compress
        doc.save(str(out), garbage=4, deflate=True)
    # Second-pass rewrite to avoid rare 'annotation not bound to any page' in some viewers
    try:
        tmp = out.with_suffix(".pdf.tmp")
        with fitz.open(str(out)) as d2:
            d2.save(str(tmp), garbage=4, deflate=True)
        tmp.replace(out)
    except Exception:
        pass

    # Optional per-page legend sidecar
    if legend:
        try:
            side_root = out.parent / (out.stem + "_ann")
            side_root.mkdir(parents=True, exist_ok=True)
            for pno, items in legends.items():
                (side_root / f"page_{pno+1}_legend.md").write_text(
                    "\n".join(f"- {it}" for it in items), encoding="utf-8"
                )
        except Exception:
            pass

    if export_pages:
        try:
            d = out.parent / (out.stem + "_pages")
            d.mkdir(parents=True, exist_ok=True)
            doc = fitz.open(str(out))
            allowed = _parse_pages(pages, len(doc))
            page_indices = range(len(doc)) if allowed is None else sorted(allowed)
            for i in page_indices:
                if not (0 <= i < len(doc)):
                    continue
                try:
                    pm = doc[i].get_pixmap(dpi=int(png_dpi), annots=True)
                except TypeError:
                    pm = doc[i].get_pixmap(dpi=int(png_dpi))
                (d / f"page_{i+1}.png").write_bytes(pm.tobytes("png"))
        except Exception:
            pass
    typer.secho(f"Wrote annotated PDF: {out}", fg=typer.colors.GREEN)


@app.command()
def from_blocks(
    pdf: Path = typer.Option(
        ..., "--pdf", help="Input PDF (prefer Stage 01 clean PDF)", exists=True, dir_okay=False
    ),
    blocks_json: Path = typer.Option(
        ...,
        "--blocks-json",
        help="Stage 02 blocks JSON (02_marker_blocks.json)",
        exists=True,
        dir_okay=False,
    ),
    out: Path = typer.Option(..., "--out", help="Output annotated PDF path"),
    block_type_key: str = typer.Option("block_type", help="Key for type label in blocks JSON"),
    min_width: float = typer.Option(6.0, help="Minimum box width to draw (pt)"),
    min_height: float = typer.Option(6.0, help="Minimum box height to draw (pt)"),
    style: str = typer.Option("both", help="Annotation style: stroke|fill|both"),
    fill_alpha: float = typer.Option(0.12, help="Fill opacity (0..1) when style includes fill"),
):
    data = json.loads(blocks_json.read_text())
    blocks = data.get("blocks") if isinstance(data, dict) else None
    if not isinstance(blocks, list):
        raise SystemExit('Invalid blocks JSON: expected {"blocks": [...]} at top level')

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
            _add_label_tab(page, rect, text=label, color=color, alpha=0.25)

        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))
    typer.secho(f"Wrote annotated PDF: {out}", fg=typer.colors.GREEN)


@app.command()
def from_stage01(
    pdf: Path = typer.Option(
        ..., "--pdf", help="Input PDF (Stage 01 clean PDF)", exists=True, dir_okay=False
    ),
    stage01_json: Path = typer.Option(
        ..., "--stage01-json", help="01_annotations.json path", exists=True, dir_okay=False
    ),
    out: Path = typer.Option(..., "--out", help="Output annotated PDF path"),
    style: str = typer.Option("both", help="Annotation style: stroke|fill|both"),
    fill_alpha: float = typer.Option(0.12, help="Fill opacity (0..1) when style includes fill"),
):
    data = json.loads(stage01_json.read_text())
    annots = data.get("annotations") if isinstance(data, dict) else None
    if not isinstance(annots, list):
        raise SystemExit('Invalid Stage 01 JSON: expected {"annotations": [...]} at top level')

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
            t = str(
                ((a.get("interpretation") or {}).get("inferred_object") or {}).get("type")
                or a.get("type")
                or "region"
            )
            label = f"{t}:{a.get('id','')}".rstrip(":")
            color = _color_rgb(t)
            use_fill = color if style in {"fill", "both"} else None
            use_alpha = fill_alpha if style in {"fill", "both"} else 1.0
            _add_rect_annot(page, rect, color=color, width=1.2, fill=use_fill, alpha=use_alpha)
            _add_label_tab(page, rect, text=label, color=color, alpha=0.25)

        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))
    typer.secho(f"Wrote annotated PDF: {out}", fg=typer.colors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    app()
