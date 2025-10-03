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
from typing import List, Optional, Tuple, Set, Dict, Any

import fitz
import typer

app = typer.Typer(add_completion=False)


def _iou(a, b) -> float:
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
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def _draw_box(
    page: fitz.Page,
    bbox: List[float],
    color: Tuple[float, float, float],
    text: Optional[str] = None,
    lw: float = 1.2,
    fontsize: float = 6.5,
    tag_only: bool = False,
) -> None:
    try:
        rect = fitz.Rect(*bbox)
    except Exception:
        return
    page.draw_rect(rect, color=color, width=lw, fill=None)
    if text:
        if tag_only:
            # Draw tiny tag box inside top-left to reduce collisions
            label_rect = fitz.Rect(rect.x0 + 2, rect.y0 + 2, rect.x0 + 72, rect.y0 + 12)
        else:
            label_rect = fitz.Rect(rect.x0 + 1, rect.y0 - 10, rect.x0 + 260, rect.y0 + 2)
        page.insert_textbox(label_rect, text, fontsize=fontsize, color=color, overlay=True)


def _parse_pages(pages: str, total_pages: int) -> Optional[Set[int]]:
    if not pages:
        return None
    allowed: Set[int] = set()
    for chunk in pages.split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        if '-' in chunk:
            start_str, end_str = chunk.split('-', 1)
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
    input_pdf: Path = typer.Option(..., exists=True, help='Clean PDF to annotate'),
    results: Path = typer.Option(..., exists=True, help='Pipeline results directory (Stage 02–07 outputs)'),
    output: Path = typer.Option(Path('scripts/artifacts/annotated.pdf')), 
    export_pages: bool = typer.Option(False, help='Also export annotated pages as PNGs'),
    pages: str = typer.Option('', help='Comma separated page numbers or ranges (1-indexed). Example: "1,5,10-12"'),
    fallback_only: bool = typer.Option(False, help='Only annotate pages where Stage 05 applied fallback strategies'),
    tables_as: str = typer.Option('box', help='How to annotate tables: box|json|markdown'),
    no_labels: bool = typer.Option(True, help='Do not draw verbose labels; reduce clutter (draw tags or none).'),
    lw: float = typer.Option(1.2, help='Stroke width for boxes'),
    label_fontsize: float = typer.Option(6.5, help='Font size for labels/tags'),
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    p02 = results / '02_marker_extractor/json_output/02_marker_blocks.json'
    p04 = results / '04_section_builder/json_output/04_sections.json'
    p05 = results / '05_table_extractor/json_output/05_tables.json'
    p06 = results / '06_figure_extractor/json_output/06_figures.json'
    p07 = results / '07_reflow_section/json_output/07_reflowed.json'

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

    if j05 and 'tables' in j05:
        for t in j05['tables']:
            bbox = t.get('bbox')
            if not bbox:
                continue
            table_boxes.append(bbox)
            try:
                pg = int(t.get('page_number', 1)) - 1
            except Exception:
                pg = 0
            table_boxes_by_page.setdefault(pg, []).append(bbox)
            if bool(t.get('quality_fallback')):
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

    if j02 and 'blocks' in j02:
        for i, b in enumerate(j02['blocks']):
            try:
                page_idx = int(b.get('page', b.get('page_idx', 0)))
                bbox = b.get('bbox') or b.get('rect')
                btype = (b.get('block_type') or b.get('type') or 'Block')
                if bbox is None or page_idx >= total_pages:
                    continue
                if not page_allowed(page_idx):
                    continue
                txt = str(b.get('text') or '').strip()
                label = f'02 {btype} #{i} (p{page_idx+1})'
                color = (0.5, 0.5, 0.0)
                bt = str(btype).lower()
                if 'section' in bt:
                    if txt.endswith(':'):
                        label = f'02 NotHeader (colon) #{i} (p{page_idx+1})'
                        color = (0.7, 0.3, 0.0)
                    elif txt.endswith('.') or txt.endswith(';'):
                        label = f'02 NotHeader (paragraph) #{i} (p{page_idx+1})'
                        color = (0.7, 0.3, 0.0)
                    else:
                        label = f'02 CandidateHeader #{i} (p{page_idx+1})'
                if 'table' in bt:
                    has_overlap = any(_iou(bbox, tb) > 0.2 for tb in table_boxes)
                    if not has_overlap:
                        above = table_boxes_by_page.get(page_idx, [])
                        try:
                            y0 = float(bbox[1])
                        except Exception:
                            y0 = 0.0
                        any_above = any((tb[3] <= y0 and (y0 - tb[3]) < 200.0) for tb in above)
                        if (txt.endswith('.') or txt.endswith(';') or len(txt.split()) >= 8) and not any_above:
                            label = f'02 Text (was Table?) #{i} (p{page_idx+1})'
                            color = (0.4, 0.4, 0.4)
                        else:
                            label = f'02 SuspectTable #{i} (p{page_idx+1})'
                            color = (0.7, 0.3, 0.0)
                legends.setdefault(page_idx, []).append(label)
                _draw_box(doc[page_idx], bbox, color, None if no_labels else label, lw=lw, fontsize=label_fontsize)
            except Exception:
                continue

    if j04 and 'sections' in j04:
        for s in j04['sections']:
            anchor = s.get('anchor') or {}
            bbox = anchor.get('bbox')
            page_idx = anchor.get('page_idx')
            title = s.get('title') or 'Section'
            if bbox and isinstance(page_idx, int) and 0 <= page_idx < total_pages:
                if not page_allowed(page_idx):
                    continue
                sec_label = f'04 Section: {title[:32]} (p{page_idx+1})'
                legends.setdefault(page_idx, []).append(sec_label)
                _draw_box(doc[page_idx], bbox, (1.0, 0.5, 0.0), None if no_labels else sec_label, lw=lw, fontsize=label_fontsize)

    # Sidecar outputs for tables (json/markdown)
    tables_sidecar: Dict[int, List[Dict[str, Any]]] = {}

    if j05 and 'tables' in j05:
        for k, t in enumerate(j05['tables']):
            try:
                page_num = int(t.get('page_number', 1))
            except Exception:
                page_num = 1
            page_idx = page_num - 1
            bbox = t.get('bbox')
            shape = t.get('pandas_metrics', {}).get('shape') or []
            frag = t.get('fragmentation_score')
            strategy = t.get('strategy') or ''
            fallback = bool(t.get('quality_fallback'))
            history = t.get('strategy_history') or []
            if not bbox or not (0 <= page_idx < total_pages):
                continue
            if not page_allowed(page_idx):
                continue
            tag_parts = [f'05 Table #{k}']
            if shape and isinstance(shape, list) and len(shape) == 2:
                try:
                    rows = int(shape[0])
                    cols = int(shape[1])
                except Exception:
                    rows, cols = shape
                if isinstance(rows, int) and rows == 1:
                    continue
                tag_parts.append(f'{rows}x{cols}')
            if frag is not None:
                tag_parts.append(f'frag={frag}')
            if strategy:
                tag_parts.append(f's={strategy}')
            if fallback:
                tag_parts.append('fallback')
            elif history:
                tag_parts.append(f'cand={len(history)}')
            color = (0.0, 0.4, 0.8)
            if fallback:
                color = (0.95, 0.3, 0.2)
            # Sidecar record
            tables_sidecar.setdefault(page_idx, []).append({
                'index': k,
                'page': page_num,
                'bbox': bbox,
                'shape': shape,
                'frag': frag,
                'strategy': strategy,
                'fallback': fallback,
            })
            label = ' '.join(tag_parts) + f' (p{page_num})'
            if tables_as == 'box':
                legends.setdefault(page_idx, []).append(label)
                _draw_box(doc[page_idx], bbox, color, None if no_labels else label, lw=lw, fontsize=label_fontsize)
            else:
                # Draw a small tag only to avoid clutter; details go to sidecar
                tag = f'T#{k}'
                legends.setdefault(page_idx, []).append(label)
                _draw_box(doc[page_idx], bbox, color, tag, lw=lw, fontsize=label_fontsize, tag_only=True)

    if j06 and 'figures' in j06:
        for k, f in enumerate(j06['figures']):
            try:
                page_num = int(f.get('page_number', 1))
            except Exception:
                page_num = 1
            page_idx = page_num - 1
            bbox = f.get('bbox')
            if bbox and 0 <= page_idx < total_pages:
                if page_allowed(page_idx):
                    flabel = f'06 Figure #{k} (p{page_num})'
                    legends.setdefault(page_idx, []).append(flabel)
                    _draw_box(doc[page_idx], bbox, (0.9, 0.0, 0.8), None if no_labels else flabel, lw=lw, fontsize=label_fontsize)

    if j07 and 'reflowed_sections' in j07:
        for s in j07['reflowed_sections']:
            for k, t in enumerate(s.get('tables') or []):
                try:
                    page_num = int(t.get('page_number', 1))
                except Exception:
                    page_num = 1
                page_idx = page_num - 1
                bbox = t.get('bbox')
                if bbox and 0 <= page_idx < total_pages:
                    if page_allowed(page_idx):
                        slabel = f'07 Table (S) #{k} (p{page_num})'
                        legends.setdefault(page_idx, []).append(slabel)
                        if tables_as == 'box':
                            _draw_box(doc[page_idx], bbox, (0.3, 0.7, 1.0), None if no_labels else slabel, lw=lw, fontsize=label_fontsize)
                        else:
                            _draw_box(doc[page_idx], bbox, (0.3, 0.7, 1.0), 'T(S)', lw=lw, fontsize=label_fontsize, tag_only=True)

    doc.save(str(output))

    # Sidecar outputs (tables + legends)
    side_root = output.parent / (output.stem + '_ann')
    side_root.mkdir(parents=True, exist_ok=True)
    # Legends per page
    for pg, items in legends.items():
        (side_root / f'page_{pg+1}_legend.md').write_text('\n'.join(f'- {it}' for it in items), encoding='utf-8')
    # Tables in JSON/MD
    if tables_sidecar:
        tables_dir = side_root / 'tables'
        tables_dir.mkdir(parents=True, exist_ok=True)
        if tables_as == 'json':
            # One JSON per page
            for pg, items in tables_sidecar.items():
                (tables_dir / f'page_{pg+1}.json').write_text(json.dumps(items, indent=2), encoding='utf-8')
        elif tables_as == 'markdown':
            # One Markdown per page (summary of tables)
            for pg, items in tables_sidecar.items():
                lines = [f'# Tables (Page {pg+1})']
                for it in items:
                    rows, cols = (it.get('shape') or [None, None])
                    lines.append(f"- Table #{it.get('index')} rows={rows} cols={cols} fallback={bool(it.get('fallback'))} strategy={it.get('strategy')}")
                (tables_dir / f'page_{pg+1}.md').write_text('\n'.join(lines), encoding='utf-8')

    if export_pages:
        outdir = output.parent / (output.stem + '_pages')
        outdir.mkdir(parents=True, exist_ok=True)
        page_indices = range(total_pages) if allowed_pages is None else sorted(allowed_pages)
        for idx in page_indices:
            if not (0 <= idx < total_pages):
                continue
            pm = doc[idx].get_pixmap(dpi=150)
            (outdir / f'page_{idx+1}.png').write_bytes(pm.tobytes('png'))
        print(str(outdir))

    print(str(output))


if __name__ == '__main__':
    app()
