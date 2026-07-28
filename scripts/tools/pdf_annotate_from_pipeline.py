#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv>=1.0.0,<2",
#   "pymupdf>=1.24.9",
# ]
# ///
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import List, Optional, Tuple, Set, Dict, Any

import fitz
import typer

app = typer.Typer(add_completion=False)


def _iou(a, b) -> float:
    """Compute intersection over union of two rectangles."""
    try:
        ra = fitz.Rect(*a)
        rb = fitz.Rect(*b)
    except Exception:
        return 0.0
    inter = ra & rb
    if inter.is_empty:
        return 0.0
    return inter.get_area() / (ra.get_area() + rb.get_area() - inter.get_area())


def _safe_load(p: Path) -> Optional[dict]:
    """Load JSON from path, returning None on failure or missing file."""
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def _camelot_to_fitz_bbox(bbox: List[float], page_rect: "fitz.Rect") -> Optional[List[float]]:
    """Convert Camelot bbox (origin bottom-left) to PyMuPDF coords (origin top-left)."""
    try:
        x0, y0, x1, y1 = [float(v) for v in bbox]
        page_h = float(page_rect.height)
        y0_f = page_h - y1
        y1_f = page_h - y0
        return [x0, y0_f, x1, y1_f]
    except Exception:
        return None


def _put_box(
    page: fitz.Page,
    bbox: List[float],
    color: Tuple[float, float, float],
    text: Optional[str] = None,
    lw: float = 1.2,
    fontsize: float = 6.5,
    tag_only: bool = False,
    use_annots: bool = True,
    do_fill: bool = True,
    fill_alpha: float = 0.05,
) -> None:
    """Render a box and optional label.

    When use_annots=True, create proper PDF annotation objects (Square + FreeText).
    Otherwise, draw vector graphics on the page (previous fallback behavior).
    """
    try:
        rect = fitz.Rect(*bbox)
    except Exception:
        return

    if use_annots:
        try:
            # Rectangle annotation (Square) with stroke color and border width
            a = page.add_rect_annot(rect)
            # PyMuPDF expects 0-1 floats for RGB
            if do_fill:
                a.set_colors(stroke=color, fill=color)
            else:
                a.set_colors(stroke=color)
            a.set_border(width=max(0.5, float(lw)))
            try:
                if 0.0 <= float(fill_alpha) <= 1.0:
                    a.set_opacity(float(fill_alpha) if do_fill else 1.0)
            except Exception:
                pass
            if text:
                # Set contents so viewers show text on click
                a.set_info(content=text)
            a.update()

            # Optional small free-text label to mimic previous overlay labeling
            if text and not tag_only:
                label_rect = fitz.Rect(rect.x0 + 1, rect.y0 - 10, rect.x0 + 260, rect.y0 + 2)
                label_rect = label_rect & page.rect
                if label_rect.is_empty:
                    label_rect = fitz.Rect(rect.x0 + 2, rect.y0 + 2, rect.x0 + 72, rect.y0 + 12)
                ft = page.add_freetext_annot(
                    label_rect,
                    text,
                    fontsize=max(5.0, float(fontsize)),
                    rotate=0,
                )
                ft.set_colors(stroke=color, fill=None, text=color)
                # Make the free text transparent background
                ft.set_border(width=0.0)
                try:
                    ft.set_opacity(0.25)
                except Exception:
                    pass
                ft.update()
                # Add a tiny sticky note so comment lists see an entry
                try:
                    na = page.add_text_annot(fitz.Point(rect.x1 - 8, max(rect.y0 + 8, 8)), text)
                    na.set_border(width=0.0)
                    na.update()
                except Exception:
                    pass
            elif text and tag_only:
                tag_rect = (
                    fitz.Rect(rect.x1 - 72, rect.y0 + 2, rect.x1 - 2, rect.y0 + 12) & page.rect
                )
                ft = page.add_freetext_annot(
                    tag_rect,
                    text,
                    fontsize=max(5.0, float(fontsize)),
                    rotate=0,
                )
                try:
                    ft.set_colors(stroke=color, fill=color, text=(1, 1, 1))
                except Exception:
                    try:
                        ft.setColors(stroke=color, fill=color)
                        ft.set_colors(text=(1, 1, 1))
                    except Exception:
                        pass
                try:
                    ft.set_border(width=0.0)
                except Exception:
                    pass
                try:
                    ft.set_opacity(0.25)
                except Exception:
                    pass
                ft.update()
            return
        except Exception:
            # Fall back to vector drawing if annotation APIs fail
            pass

    # Fallback: vector drawing (legacy behavior)
    page.draw_rect(rect, color=color, width=lw, fill=None)
    if text:
        if tag_only:
            label_rect = fitz.Rect(rect.x0 + 2, rect.y0 + 2, rect.x0 + 72, rect.y0 + 12)
        else:
            label_rect = fitz.Rect(rect.x0 + 1, rect.y0 - 10, rect.x0 + 260, rect.y0 + 2)
        page.insert_textbox(label_rect, text, fontsize=fontsize, color=color, overlay=True)


def _parse_pages(pages: str, total_pages: int) -> Optional[Set[int]]:
    """Parse page numbers from a string into a set of integers."""
    if not pages:
        return None
    allowed: Set[int] = set()
    for chunk in pages.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_str, end_str = chunk.split("-", 1)
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError:
                continue
            if start > end:
                start, end = end, start
            for num in range(start, end + 1):
                if 1 <= num <= total_pages:
                    allowed.add(num - 1)
        else:
            try:
                num = int(chunk)
            except ValueError:
                continue
            if 1 <= num <= total_pages:
                allowed.add(num - 1)
    return allowed if allowed else None


@app.command()
def main(
    input_pdf: Path = typer.Option(..., exists=True, help="Clean PDF to annotate"),
    results: Path = typer.Option(
        ..., exists=True, help="Pipeline results directory (Stage 02–07 outputs)"
    ),
    output: Optional[Path] = typer.Option(
        None, help="Output annotated PDF; defaults to scripts/artifacts/<input>_annotated.pdf"
    ),
    export_pages: bool = typer.Option(False, help="Also export annotated pages as PNGs"),
    pages: str = typer.Option(
        "", help='Comma separated page numbers or ranges (1-indexed). Example: "1,5,10-12"'
    ),
    fallback_only: bool = typer.Option(
        False, help="Only annotate pages where Stage 05 applied fallback strategies"
    ),
    tables_as: str = typer.Option("box", help="How to annotate tables: box|json|markdown"),
    no_labels: bool = typer.Option(
        True, help="Do not draw verbose labels; reduce clutter (draw tags or none)."
    ),
    lw: float = typer.Option(1.2, help="Stroke width for boxes"),
    label_fontsize: float = typer.Option(6.5, help="Font size for labels/tags"),
    use_annot_objs: bool = typer.Option(
        True, help="Use PDF annotation objects instead of drawing vectors"
    ),
    include_sections: bool = typer.Option(True, help="Draw Stage 04 sections"),
    include_stage02: bool = typer.Option(False, help="Draw Stage 02 blocks (debug)"),
    include_tables: bool = typer.Option(False, help="Draw Stage 05 tables"),
    include_figures: bool = typer.Option(False, help="Draw Stage 06 figures"),
    include_reflow: bool = typer.Option(False, help="Draw Stage 07 reflow tables"),
    tags_only: bool = typer.Option(False, help="Draw tag labels only, not full rectangles"),
) -> None:
    # Derive friendly output name when not provided
    if output is None:
        stem = input_pdf.stem
        # drop a trailing _clean if present, then append _annotated
        stem = re.sub(r"_clean$", "", stem)
        out_name = f"{stem}_annotated.pdf"
        output = Path("scripts/artifacts") / out_name
    output.parent.mkdir(parents=True, exist_ok=True)

    p02 = results / "02_marker_extractor/json_output/02_marker_blocks.json"
    p04 = results / "04_section_builder/json_output/04_sections.json"
    p05 = results / "05_table_extractor/json_output/05_tables.json"
    p06 = results / "06_figure_extractor/json_output/06_figures.json"
    p07 = results / "07_reflow_section/json_output/07_reflowed.json"

    j02 = _safe_load(p02)
    j04 = _safe_load(p04)
    j05 = _safe_load(p05)
    j06 = _safe_load(p06)
    j07 = _safe_load(p07)

    doc = fitz.open(str(input_pdf))
    total_pages = len(doc)

    table_boxes: List[List[float]] = []
    table_boxes_by_page: dict[int, List[List[float]]] = {}
    fallback_pages: Set[int] = set()

    if j05 and "tables" in j05:
        for t in j05["tables"]:
            bbox = t.get("bbox")
            if not bbox:
                continue
            table_boxes.append(bbox)
            try:
                pg = int(t.get("page_number", 1)) - 1
            except Exception:
                pg = 0
            table_boxes_by_page.setdefault(pg, []).append(bbox)
            if bool(t.get("quality_fallback")):
                fallback_pages.add(pg)

    allowed_pages = _parse_pages(pages, total_pages)
    if fallback_only:
        allowed_pages = fallback_pages if fallback_pages else set()

    def page_allowed(idx: int) -> bool:
        if allowed_pages is None:
            return True
        return idx in allowed_pages

    # Per-page legend summary (sidecar)
    legends: Dict[int, List[str]] = {}

    if include_stage02 and j02 and "blocks" in j02:
        for i, b in enumerate(j02["blocks"]):
            try:
                page_idx = int(b.get("page", b.get("page_idx", 0)))
                bbox = b.get("bbox") or b.get("rect")
                btype = b.get("block_type") or b.get("type") or "Block"
                if bbox is None or page_idx >= total_pages:
                    continue
                if not page_allowed(page_idx):
                    continue
                txt = str(b.get("text") or "").strip()
                label = f"02 {btype} #{i} (p{page_idx+1})"
                color = (0.5, 0.5, 0.0)
                bt = str(btype).lower()
                if "section" in bt:
                    if txt.endswith(":"):
                        label = f"02 NotHeader (colon) #{i} (p{page_idx+1})"
                        color = (0.7, 0.3, 0.0)
                    elif txt.endswith(".") or txt.endswith(";"):
                        label = f"02 NotHeader (paragraph) #{i} (p{page_idx+1})"
                        color = (0.7, 0.3, 0.0)
                    else:
                        label = f"02 CandidateHeader #{i} (p{page_idx+1})"
                if "table" in bt:
                    has_overlap = any(_iou(bbox, tb) > 0.2 for tb in table_boxes)
                    if not has_overlap:
                        above = table_boxes_by_page.get(page_idx, [])
                        try:
                            y0 = float(bbox[1])
                        except Exception:
                            y0 = 0.0
                        any_above = any((tb[3] <= y0 and (y0 - tb[3]) < 200.0) for tb in above)
                        if (
                            txt.endswith(".") or txt.endswith(";") or len(txt.split()) >= 8
                        ) and not any_above:
                            label = f"02 Text (was Table?) #{i} (p{page_idx+1})"
                            color = (0.4, 0.4, 0.4)
                        else:
                            label = f"02 SuspectTable #{i} (p{page_idx+1})"
                            color = (0.7, 0.3, 0.0)
                legends.setdefault(page_idx, []).append(label)
                _put_box(
                    doc[page_idx],
                    bbox,
                    color,
                    None if no_labels else label,
                    lw=lw,
                    fontsize=label_fontsize,
                    tag_only=tags_only,
                    use_annots=use_annot_objs,
                )
            except Exception:
                continue

    if include_sections and j04 and "sections" in j04:
        for s in j04["sections"]:
            anchor = s.get("anchor") or {}
            bbox = anchor.get("bbox")
            page_idx = anchor.get("page_idx")
            title = s.get("title") or "Section"
            if bbox and isinstance(page_idx, int) and 0 <= page_idx < total_pages:
                if not page_allowed(page_idx):
                    continue
                sec_label = f"04 Section: {title[:32]} (p{page_idx+1})"
                legends.setdefault(page_idx, []).append(sec_label)
                _put_box(
                    doc[page_idx],
                    bbox,
                    (1.0, 0.5, 0.0),
                    None if no_labels else sec_label,
                    lw=lw,
                    fontsize=label_fontsize,
                    tag_only=tags_only,
                    use_annots=use_annot_objs,
                )

    # Sidecar outputs for tables (json/markdown)
    tables_sidecar: Dict[int, List[Dict[str, Any]]] = {}

    if include_tables and j05 and "tables" in j05:
        for k, t in enumerate(j05["tables"]):
            try:
                page_num = int(t.get("page_number", 1))
            except Exception:
                page_num = 1
            page_idx = page_num - 1
            bbox = t.get("bbox")
            shape = t.get("pandas_metrics", {}).get("shape") or []
            frag = t.get("fragmentation_score")
            strategy = t.get("strategy") or ""
            fallback = bool(t.get("quality_fallback"))
            history = t.get("strategy_history") or []
            if not bbox or not (0 <= page_idx < total_pages):
                continue
            if not page_allowed(page_idx):
                continue
            tag_parts = [f"05 Table #{k}"]
            if shape and isinstance(shape, list) and len(shape) == 2:
                try:
                    rows = int(shape[0])
                    cols = int(shape[1])
                except Exception:
                    rows, cols = shape
                if isinstance(rows, int) and rows == 1:
                    continue
                tag_parts.append(f"{rows}x{cols}")
            if frag is not None:
                tag_parts.append(f"frag={frag}")
            if strategy:
                tag_parts.append(f"s={strategy}")
            if fallback:
                tag_parts.append("fallback")
            elif history:
                tag_parts.append(f"cand={len(history)}")
            color = (0.0, 0.4, 0.8)
            if fallback:
                color = (0.95, 0.3, 0.2)
            # Sidecar record
            tables_sidecar.setdefault(page_idx, []).append(
                {
                    "index": k,
                    "page": page_num,
                    "bbox": bbox,
                    "shape": shape,
                    "frag": frag,
                    "strategy": strategy,
                    "fallback": fallback,
                }
            )
            label = " ".join(tag_parts) + f" (p{page_num})"
            if tables_as == "box":
                legends.setdefault(page_idx, []).append(label)
                _bbox_conv = _camelot_to_fitz_bbox(bbox, doc[page_idx].rect) if bbox else None
                if not _bbox_conv:
                    continue
                _put_box(
                    doc[page_idx],
                    _bbox_conv,
                    color,
                    None if no_labels else label,
                    lw=lw,
                    fontsize=label_fontsize,
                    tag_only=tags_only,
                    use_annots=use_annot_objs,
                )
            else:
                # Draw a small tag only to avoid clutter; details go to sidecar
                tag = f"T#{k}"
                legends.setdefault(page_idx, []).append(label)
                _bbox_conv = _camelot_to_fitz_bbox(bbox, doc[page_idx].rect) if bbox else None
                if not _bbox_conv:
                    continue
                _put_box(
                    doc[page_idx],
                    _bbox_conv,
                    color,
                    tag,
                    lw=lw,
                    fontsize=label_fontsize,
                    tag_only=True,
                    use_annots=use_annot_objs,
                )

    if include_figures and j06 and "figures" in j06:
        for k, f in enumerate(j06["figures"]):
            try:
                page_num = int(f.get("page_number", 1))
            except Exception:
                page_num = 1
            page_idx = page_num - 1
            bbox = f.get("bbox")
            if bbox and 0 <= page_idx < total_pages:
                if page_allowed(page_idx):
                    flabel = f"06 Figure #{k} (p{page_num})"
                    legends.setdefault(page_idx, []).append(flabel)
                    _put_box(
                        doc[page_idx],
                        bbox,
                        (0.9, 0.0, 0.8),
                        None if no_labels else flabel,
                        lw=lw,
                        fontsize=label_fontsize,
                        tag_only=tags_only,
                        use_annots=use_annot_objs,
                    )

    if include_reflow and j07 and "reflowed_sections" in j07:
        for s in j07["reflowed_sections"]:
            for k, t in enumerate(s.get("tables") or []):
                try:
                    page_num = int(t.get("page_number", 1))
                except Exception:
                    page_num = 1
                page_idx = page_num - 1
                bbox = t.get("bbox")
                if bbox and 0 <= page_idx < total_pages:
                    if page_allowed(page_idx):
                        slabel = f"07 Table (S) #{k} (p{page_num})"
                        legends.setdefault(page_idx, []).append(slabel)
                        if tables_as == "box":
                            _put_box(
                                doc[page_idx],
                                bbox,
                                (0.3, 0.7, 1.0),
                                None if no_labels else slabel,
                                lw=lw,
                                fontsize=label_fontsize,
                                tag_only=tags_only,
                                use_annots=use_annot_objs,
                            )
                        else:
                            _put_box(
                                doc[page_idx],
                                bbox,
                                (0.3, 0.7, 1.0),
                                "T(S)",
                                lw=lw,
                                fontsize=label_fontsize,
                                tag_only=True,
                                use_annots=use_annot_objs,
                            )

    # Safe-save to reduce chances of corrupt annotation refs
    doc.save(str(output), garbage=4, deflate=True)
    # Second-pass rewrite to avoid rare 'annotation not bound to any page'
    try:
        tmp = output.with_suffix(".pdf.tmp")
        with fitz.open(str(output)) as d2:
            d2.save(str(tmp), garbage=4, deflate=True)
        tmp.replace(output)
    except Exception:
        pass

    # Sidecar outputs (tables + legends)
    side_root = output.parent / (output.stem + "_ann")
    side_root.mkdir(parents=True, exist_ok=True)
    # Legends per page
    for pg, items in legends.items():
        (side_root / f"page_{pg+1}_legend.md").write_text(
            "\n".join(f"- {it}" for it in items), encoding="utf-8"
        )
    # Tables in JSON/MD
    if tables_sidecar:
        tables_dir = side_root / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        if tables_as == "json":
            # One JSON per page
            for pg, items in tables_sidecar.items():
                (tables_dir / f"page_{pg+1}.json").write_text(
                    json.dumps(items, indent=2), encoding="utf-8"
                )
        elif tables_as == "markdown":
            # One Markdown per page (summary of tables)
            for pg, items in tables_sidecar.items():
                lines = [f"# Tables (Page {pg+1})"]
                for it in items:
                    rows, cols = it.get("shape") or [None, None]
                    lines.append(
                        f"- Table #{it.get('index')} rows={rows} cols={cols} fallback={bool(it.get('fallback'))} strategy={it.get('strategy')}"
                    )
                (tables_dir / f"page_{pg+1}.md").write_text("\n".join(lines), encoding="utf-8")

    if export_pages:
        outdir = output.parent / (output.stem + "_pages")
        outdir.mkdir(parents=True, exist_ok=True)
        page_indices = range(total_pages) if allowed_pages is None else sorted(allowed_pages)
        for idx in page_indices:
            if not (0 <= idx < total_pages):
                continue
            # annots=True ensures PDF annotation objects are rendered in the PNG exports
            try:
                pm = doc[idx].get_pixmap(dpi=150, annots=True)
            except TypeError:
                # Older PyMuPDF: annots flag may not exist; render without it
                pm = doc[idx].get_pixmap(dpi=150)
            (outdir / f"page_{idx+1}.png").write_bytes(pm.tobytes("png"))
        print(str(outdir))

    print(str(output))


if __name__ == "__main__":
    app()
