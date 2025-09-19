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
from typing import List, Optional, Tuple
import fitz
import typer
app = typer.Typer(add_completion=False)

# Utility: rect IoU
def _iou(a, b):
    try:
        ra=fitz.Rect(*a); rb=fitz.Rect(*b)
    except Exception:
        return 0.0
    inter=ra & rb
    if inter.is_empty: return 0.0
    return inter.get_area()/(ra.get_area()+rb.get_area()-inter.get_area())

def _safe_load(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None

def _draw_box(page: fitz.Page, bbox: List[float], color: Tuple[float,float,float], text: str, lw: float=0.8):
    try:
        rect = fitz.Rect(*bbox)
    except Exception:
        return
    page.draw_rect(rect, color=color, width=lw, fill=None)
    label_rect = fitz.Rect(rect.x0 + 1, rect.y0 - 10, rect.x0 + 240, rect.y0 + 2)
    page.insert_textbox(label_rect, text, fontsize=6.5, color=color, overlay=True)

@app.command()
def main(
    input_pdf: Path = typer.Option(..., exists=True),
    results: Path   = typer.Option(..., exists=True),
    output: Path    = typer.Option(Path('scripts/artifacts/annotated.pdf')),
    export_pages: bool = typer.Option(False, help='Also export annotated pages as PNGs'),
):
    output.parent.mkdir(parents=True, exist_ok=True)
    p02 = results / '02_marker_extractor/json_output/02_marker_blocks.json'
    j02 = _safe_load(p02)
    p04 = results / '04_section_builder/json_output/04_sections.json'
    j04 = _safe_load(p04)
    p05 = results / '05_table_extractor/json_output/05_tables.json'
    j05 = _safe_load(p05)
    table_boxes = []
    table_boxes_by_page = {}
    if j05 and 'tables' in j05:
        for t in j05['tables']:
            if t.get('bbox'):
                table_boxes.append(t['bbox'])
                try:
                    pg = int(t.get('page_number', 1)) - 1
                except Exception:
                    pg = 0
                table_boxes_by_page.setdefault(pg, []).append(t['bbox'])
    p06 = results / '06_figure_extractor/json_output/06_figures.json'
    j06 = _safe_load(p06)
    p07 = results / '07_reflow_section/json_output/07_reflowed.json'
    j07 = _safe_load(p07)
    doc = fitz.open(str(input_pdf))
    if j02 and 'blocks' in j02:
        for i,b in enumerate(j02['blocks']):
            try:
                page_idx = int(b.get('page', b.get('page_idx', 0)))
                bbox = b.get('bbox') or b.get('rect')
                btype = (b.get('block_type') or b.get('type') or 'Block')
                if bbox is None or page_idx >= len(doc):
                    continue
                txt = str(b.get('text') or '').strip()
                label=f'02 {btype} #{i} (p{page_idx+1})'
                color=(0.5,0.5,0.0)
                bt=str(btype).lower()
                if 'section' in bt:
                    # Heuristic demotion: colon-trailing or sentence-like → not a header
                    if txt.endswith(':'):
                        label=f'02 NotHeader (colon) #{i} (p{page_idx+1})'
                        color=(0.7,0.3,0.0)
                    elif txt.endswith('.') or txt.endswith(';'):
                        label=f'02 NotHeader (paragraph) #{i} (p{page_idx+1})'
                        color=(0.7,0.3,0.0)
                    else:
                        label=f'02 CandidateHeader #{i} (p{page_idx+1})'
                if 'table' in bt:
                    # cross-validate with Stage 05 tables; downgrade if no overlap
                    has_overlap = any(_iou(bbox, tb)>0.2 for tb in table_boxes)
                    if not has_overlap:
                        # If it's sentence-like text and no real tables just above, label as text-not-table
                        above = table_boxes_by_page.get(page_idx, [])
                        try:
                            y0 = float(bbox[1])
                        except Exception:
                            y0 = 0.0
                        any_above = any((tb[3] <= y0 and (y0 - tb[3]) < 200.0) for tb in above)
                        if (txt.endswith('.') or txt.endswith(';') or len(txt.split()) >= 8) and not any_above:
                            label=f'02 Text (was Table?) #{i} (p{page_idx+1})'
                            color=(0.4,0.4,0.4)
                        else:
                            label=f'02 SuspectTable #{i} (p{page_idx+1})'
                            color=(0.7,0.3,0.0)
                _draw_box(doc[page_idx], bbox, color, label)
            except Exception:
                continue
    if j04 and 'sections' in j04:
        for s in j04['sections']:
            anchor = s.get('anchor') or {}
            bbox = anchor.get('bbox')
            page_idx = anchor.get('page_idx')
            title = s.get('title') or 'Section'
            if bbox and isinstance(page_idx, int) and 0 <= page_idx < len(doc):
                _draw_box(doc[page_idx], bbox, (1.0,0.5,0.0), f'04 Section: {title[:32]} (p{page_idx+1})')
    if j05 and 'tables' in j05:
        for k,t in enumerate(j05['tables']):
            page_num = int(t.get('page_number',1))
            page_idx = page_num - 1
            bbox = t.get('bbox')
            shape = t.get('pandas_metrics',{}).get('shape') or []
            tag = f'05 Table #{k}'
            if shape and isinstance(shape,list) and len(shape)==2:
                # skip header-only fragments like 1xN
                if int(shape[0]) == 1:
                    continue
                tag += f' {shape[0]}x{shape[1]}'
            if bbox and 0 <= page_idx < len(doc):
                _draw_box(doc[page_idx], bbox, (0.0,0.4,0.8), tag + f' (p{page_num})')
    if j06 and 'figures' in j06:
        for k,f in enumerate(j06['figures']):
            page_num = int(f.get('page_number',1))
            page_idx = page_num - 1
            bbox = f.get('bbox')
            if bbox and 0 <= page_idx < len(doc):
                _draw_box(doc[page_idx], bbox, (0.9,0.0,0.8), f'06 Figure #{k} (p{page_num})')
    if j07 and 'reflowed_sections' in j07:
        for s in j07['reflowed_sections']:
            for k,t in enumerate(s.get('tables') or []):
                page_num = int(t.get('page_number',1))
                page_idx = page_num - 1
                bbox = t.get('bbox')
                if bbox and 0 <= page_idx < len(doc):
                    _draw_box(doc[page_idx], bbox, (0.3,0.7,1.0), f'07 Table (S) #{k} (p{page_num})')
    doc.save(str(output))
    # Optional: export per-page PNGs if requested
    if typer.Option is not None:
        pass
    
    if export_pages:
        outdir=output.parent/ (output.stem + '_pages')
        outdir.mkdir(parents=True, exist_ok=True)
        for idx in range(len(doc)):
            pm = doc[idx].get_pixmap(dpi=150)
            (outdir/f'page_{idx+1}.png').write_bytes(pm.tobytes('png'))
        print(str(outdir))
    print(str(output))

if __name__ == '__main__':
    app()
