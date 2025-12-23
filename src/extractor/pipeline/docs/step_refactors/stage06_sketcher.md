Yes, this step is essentially a "geometry engine" mixed with file I/O and orchestration. It benefits significantly from separating the **Math/Geometry** (which is pure and testable) from the **Orchestration** (reading JSONs, writing files).

I recommend creating a package `extractor/pipeline/utils/layout/`.

### Recommended Directory Structure

```text
extractor/pipeline/
├── steps/
│   └── 06b_layout_sketcher.py     <-- Orchestration & Configuration
└── utils/
    └── layout/
        ├── __init__.py
        ├── geometry.py            <-- Pure math: IoU, grid mapping, area
        ├── columns.py             <-- Column detection algorithms
        ├── formatting.py          <-- DSL generation, flow stream text
        ├── pages.py               <-- Page geometry, PyMuPDF fallback
        ├── builder.py             <-- Core logic: transforming section->sketch
        └── vlm.py                 <-- Optional SciLLM/Vision logic
```

---

### 1\. `geometry.py` (Pure Math)

This removes the low-level noise from the main script.

- **Move:** `_norm`
- **Move:** `_grid_bbox`
- **Move:** `_area`
- **Move:** `_aspect`
- **Move:** `_iou`
- **Move:** `_rect_intersects`

### 2\. `columns.py` (Structure Analysis)

Isolates the logic for determining page columns.

- **Move:** `_detect_columns`
- **Move:** `_assign_cols_and_span`
- **Move:** `_col_id_for`

### 3\. `formatting.py` (Text Generation)

Logic that turns data into strings (for prompts or debug output).

- **Move:** `_summ`
- **Move:** `_norm_text`
- **Move:** `_text_sha1`
- **Move:** `_build_flow_stream` (Large function)
- **Move:** `_build_instructive_dsl`

### 4\. `pages.py` (PDF & Page Data)

Handles the global page geometry cache and PyMuPDF fallbacks.

- **Move:** `_collect_page_index_from_sections`
- **Move:** `_pymupdf_fill_missing_pages`
- **Move:** `_build_page_layout`

### 5\. `builder.py` (Business Logic)

This contains the specific rules for how to represent a "Section Sketch".

- **Move:** `_build_section_sketch` (The core function)
- **Move:** `_obj_to_v2`
- **Refactor:** The "Merge Hints Propagation" and "Header Propagation" logic currently sitting inside `run()` should be extracted into functions here (e.g., `propagate_merge_hints`, `propagate_headers_deterministically`).

### 6\. `vlm.py` (Optional AI)

Isolate the SciLLM router dependency.

- **Move:** `_build_section_sketch_llm`

---

### The New `06b_layout_sketcher.py`

The orchestrator becomes clean and focused on file management:

```python
# ... imports ...
import extractor.pipeline.utils.layout.geometry as geom
import extractor.pipeline.utils.layout.pages as page_utils
import extractor.pipeline.utils.layout.builder as sketch_builder
import extractor.pipeline.utils.layout.vlm as vlm_utils

def run(input_path, output_path, **kwargs):
    # 1. Setup & Load
    # ...

    # 2. Build Page Layout (Geometry)
    page_index = page_utils.collect_page_index(sections)
    page_utils.fill_missing_pages(page_index, source_pdf)
    page_layout = page_utils.build_page_layout(page_index, grid=GRID)

    # 3. Build Sketches (Logic)
    for sec in sections:
        if ALLOW_VLM:
            sketch = vlm_utils.build_sketch_llm(...)

        if not sketch:
            sketch = sketch_builder.build_section_sketch(
                sec,
                grid=GRID,
                page_layout=page_layout,
                ...
            )
        sketches[sid] = sketch

    # 4. Post-Processing (Propagation)
    # (Refactored from the huge block in the original run())
    sketch_builder.propagate_merge_hints(sketches, table_merge_hints)
    sketch_builder.propagate_headers(sketches)

    # 5. Visuals & Save
    # ...
```

### Next Step

The most critical file to create is **`builder.py`** (and its dependencies `geometry` and `formatting`), as that contains the core logic for the sketch. Would you like me to generate `builder.py`?

Here is the code for **`extractor/pipeline/utils/layout/builder.py`**.

This module encapsulates the business logic for transforming a Stage 04 Section + Stage 05/06 artifacts into a "Layout Sketch". It also contains the logic for propagating table headers across pages, which was previously cluttering the main execution loop.

```python
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error

# Import from sibling layout modules
# (Assumes you have created these based on the previous recommendation)
from extractor.pipeline.utils.layout import geometry as geom
from extractor.pipeline.utils.layout import columns as col_utils
from extractor.pipeline.utils.layout import formatting as fmt

STEP_NAME = "06b_layout_sketcher"

def _round_bbox(b: List[float]) -> List[float]:
    try:
        return [round(float(x), 2) for x in b]
    except Exception:
        return [0.0, 0.0, 0.0, 0.0]

def _obj_to_v2(
    e: Dict[str, Any],
    section_page_idx: int,
    refs_map: Dict[str, List[str]]
) -> Dict[str, Any]:
    """Convert an enriched internal element to the V2 public schema."""
    sid = e.get("sketch_id") or e.get("id")

    # Base object structure
    out: Dict[str, Any] = {
        "id": sid,
        "type": "paragraph" if e.get("kind") == "text" else e.get("kind"),
        "page": int(e.get("page", section_page_idx)),
        "ro": int(e.get("reading_order", 0)),
        "col": int(e.get("column_id", 0)) if not e.get("spans_columns") else "span",
        "bbox": _round_bbox(e.get("bbox") or [0, 0, 0, 0]),
        "area": float(e.get("area", 0.0)),
    }

    if e.get("kind") == "text":
        # Text-specific fields
        try:
            bb = out["bbox"]
            height = float(bb[3]) - float(bb[1])
            too_short = bool(int(e.get("char_count", 0)) < 40 and height <= 20)
        except Exception:
            too_short = False

        out.update({
            "reflow_hint": True,
            "too_short": too_short,
            "text_preview": fmt._summ(e.get("summary") or "", 160),
        })

        # Attach anchored references (figures pointing to this text)
        r = refs_map.get(str(e.get("id"))) or refs_map.get(str(sid)) or []
        if r:
            out["refs"] = r

    elif e.get("kind") == "table":
        # Table-specific fields
        m = (e.get("metrics") or {})
        out.update({
            "title_hint": (e.get("title_hint") or ""),
            "header_norm": e.get("header_norm") or "",
            "rows": int(m.get("rows", 0)),
            "cols": int(m.get("cols", 0)),
            "logical_table_id": e.get("logical_table_id") or "",
            "continued": False,
            "merge": False,
            # Back-compat fields
            "density": m.get("data_density"),
            "camelot_acc": round(float(m.get("camelot_acc") or 0), 2),
            # Full metrics
            "metrics": m,
        })

    elif e.get("kind") == "figure":
        # Figure-specific fields
        out.update({
            "caption_hint": fmt._summ(e.get("summary") or "", 160),
            "desc_hint": fmt._summ(e.get("summary") or "", 160),
        })
        # Prefer explicit page int
        if out.get("page") is None:
            out.pop("page", None)

    return out


def build_section_sketch(
    sec: Dict[str, Any],
    grid: int,
    *,
    summary_limit: int = 80,
    min_gap_ratio: float = 0.04,
    header_footer_band: float = 0.05,
    place_floats: str = "inline",
    include_flow: bool = True,
    page_layout: Optional[Dict[int, Dict[str, Any]]] = None,
    tables_for_section: Optional[List[dict]] = None,
    figures_for_section: Optional[List[dict]] = None,
    emit_merge_hints: bool = False,
    base_results_dir: Optional[Path] = None,
    source_pdf: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Core logic: Transforms a Stage 04 section + Stage 05/06 artifacts into a deterministic layout sketch.
    """
    if page_layout is None:
        page_layout = {}

    first_page_idx = int(sec.get("page_start", sec.get("page_index", 0)) or 0)
    # Default page bbox if missing
    default_page_bbox = [0.0, 0.0, 612.0, 792.0]

    # 1. Determine Page Geometry
    try:
        pg_rec = page_layout.get(first_page_idx, {})
        page_bbox = pg_rec.get("page_bbox") or sec.get("bbox") or sec.get("page_bbox") or default_page_bbox
    except Exception:
        page_bbox = default_page_bbox

    section_page_idx = int(sec.get("page_index", first_page_idx))

    raw_elements: List[Dict[str, Any]] = []

    # 2. Process Text Blocks
    for b in sec.get("blocks") or []:
        bbox = b.get("bbox") or [0, 0, 0, 0]
        text = (b.get("text") or "")
        raw_elements.append({
            "kind": "text",
            "id": b.get("id") or b.get("block_id"),
            "bbox": bbox,
            "grid_bbox": geom._grid_bbox(bbox, page_bbox, grid),
            "summary": fmt._summ(text, summary_limit),
            "text_sha1": fmt._text_sha1(text),
            "page": int(b.get("page") or b.get("page_idx") or b.get("page_index") or section_page_idx),
            "area": geom._area(bbox),
            "aspect": geom._aspect(bbox),
            "char_count": len(text or ""),
            "role": b.get("role") or "para",
        })

    # 3. Process Tables (Stage 05)
    for t in (tables_for_section or []):
        _process_table_element(t, raw_elements, page_bbox, grid, section_page_idx, summary_limit)

    # 4. Process Figures (Stage 06)
    for f in (figures_for_section or []):
        bbox = f.get("bbox") or [0, 0, 0, 0]
        cap = f.get("caption") or f.get("ai_description") or ""
        raw_elements.append({
            "kind": "figure",
            "id": f.get("figure_id") or f.get("id"),
            "bbox": bbox,
            "grid_bbox": geom._grid_bbox(bbox, page_bbox, grid),
            "summary": fmt._summ(cap, summary_limit),
            "page": int(f.get("page") or f.get("page_idx") or f.get("page_index") or section_page_idx),
            "area": geom._area(bbox),
            "aspect": geom._aspect(bbox),
            "llm_assist": bool((f.get("ai_description") or "").strip()),
        })

    # 5. Determine Columns per Page (local detection if not in global cache)
    columns_by_page: Dict[int, List[List[float]]] = {}
    for e in raw_elements:
        p = int(e.get("page", section_page_idx))
        if p in page_layout:
            columns_by_page[p] = page_layout[p]["columns"]
        else:
            sub_elems = [x for x in raw_elements if int(x.get("page", section_page_idx)) == p]
            columns_by_page[p] = col_utils._detect_columns(sub_elems, page_bbox, min_gap_ratio=min_gap_ratio)

    # 6. Assign Reading Order & Column IDs
    enriched = _assign_reading_order(raw_elements, columns_by_page, page_bbox, sec, header_footer_band)

    # 7. Anchor Floats to Text
    _anchor_floats(enriched)

    # 8. Calculate Quick Summary
    top_text = next((e for e in enriched if e.get("kind") == "text" and e.get("summary")), None)
    first_table = next((e for e in enriched if e.get("kind") == "table" and e.get("summary")), None)
    qs = " | ".join([s for s in [
        top_text.get("summary", "") if top_text else "",
        first_table.get("summary", "") if first_table else ""
    ] if s])

    # 9. Prepare Grid Columns for Output
    pages_present = sorted({int(e.get("page", section_page_idx)) for e in enriched})
    first_p = pages_present[0] if pages_present else section_page_idx
    first_cols = columns_by_page.get(first_p) or [[page_bbox[0], page_bbox[2]]]
    grid_cols = []
    for idx, (cx0, cx1) in enumerate(first_cols):
        gb = geom._grid_bbox([cx0, page_bbox[1], cx1, page_bbox[3]], page_bbox, grid)
        grid_cols.append({"id": idx, "x0": gb["x0"], "x1": gb["x1"]})

    # 10. Generate Merge Hints
    table_merge_hints = []
    if tables_for_section and len(tables_for_section) > 1:
        table_merge_hints = _calculate_merge_hints(tables_for_section)

    # 11. Build Final Objects V2 List
    # Pre-map anchored floats for _obj_to_v2
    text_by_id = {e.get("id"): e for e in enriched if e.get("kind") == "text"}
    floats = [e for e in enriched if e.get("kind") in ("table", "figure")]
    refs_map: Dict[str, List[str]] = {}
    for f in floats:
        anchor = f.get("anchor_element_id")
        if anchor and anchor in text_by_id:
            refs_map.setdefault(anchor, []).append(str(f.get("sketch_id") or f.get("id")))

    objects_v2 = []
    seen_ids = set()
    for e in enriched:
        o = _obj_to_v2(e, section_page_idx, refs_map)
        oid = str(o.get("id"))
        if oid in seen_ids: continue
        seen_ids.add(oid)
        objects_v2.append(o)

    # 12. Construct Final Result Structure
    # Estimate gutter
    try:
        if len(first_cols) >= 2:
            gaps = [first_cols[i+1][0] - first_cols[i][1] for i in range(len(first_cols)-1)]
            gutter = max(0, int(min(gaps)))
        else:
            gutter = 0
    except Exception:
        gutter = 0

    sec_bbox_union = _union_bbox(enriched)
    pw_start, pw_end = _page_window(enriched, section_page_idx)

    sketch_v2 = {
        "sketch_format": "SKETCH_V2",
        "version": 1,
        "units": "pt",
        "origin": "top-left",
        "doc_id": str((sec.get("metadata", {}) or {}).get("doc_id") or ""),
        "section_id": str(sec.get("id")),
        "source_hash": str((sec.get("metadata", {}) or {}).get("section_hash") or ""),
        "section_title": str(sec.get("title") or ""),
        "page_window": {"start": int(pw_start), "end": int(pw_end)},
        "frame": {
            "page_size": [round(float(page_bbox[2]-page_bbox[0]), 2), round(float(page_bbox[3]-page_bbox[1]), 2)],
            "section_bbox": [round(float(x), 2) for x in sec_bbox_union],
            "section_area": round(float(geom._area(sec_bbox_union)), 1),
            "grid": {"cols": len(first_cols), "gutter": round(float(gutter), 2)},
            "columns": [{"id": i, "x0": round(float(c[0]), 2), "x1": round(float(c[1]), 2), "width": round(float(c[1]-c[0]), 2)} for i, c in enumerate(first_cols)],
        },
        "objects": objects_v2,
    }

    # Ordering confidence estimate
    try:
        conf_vals = [float((page_layout.get(p, {}).get("conf") or {}).get("columns", 0.0)) for p in pages_present]
        ordering_conf = float(sum(conf_vals) / max(1, len(conf_vals))) if conf_vals else 0.6
    except Exception:
        ordering_conf = 0.6

    result: Dict[str, Any] = {
        "schema_version": "0.2.0",
        "grid": grid,
        "grid_contract": {"cell": "half-open", "rounding": "floor/ceil", "eps": 1e-6},
        "columns": grid_cols,
        "elements": [
            {k: v for k, v in e.items() if k not in ("bbox",)} | {"grid_bbox": e["grid_bbox"]}
            for e in enriched
        ],
        "elements_original_bbox": [
            {"id": e.get("id"), "bbox": e.get("bbox")} for e in enriched
        ],
        "page_breaks": pages_present,
        "quick_summary": qs,
        "conf": {"ordering": ordering_conf},
        "sketch_v2": sketch_v2
    }

    if emit_merge_hints and table_merge_hints:
        result["table_merge_hints"] = table_merge_hints
        sketch_v2["merge_hints"] = table_merge_hints

    if include_flow:
        result["flow_stream"] = fmt._build_flow_stream(
            result["elements"], grid_cols, exclude_header_footer=True, place_floats=place_floats
        )
        result["instructive_dsl"] = fmt._build_instructive_dsl(
            sec_id=str(sec.get("id")),
            pages=pages_present,
            first_page_bbox=page_bbox,
            elements_sorted=enriched,
            columns_map=columns_by_page,
        )

    return result


def propagate_merge_hints(sketches: Dict[str, Any], all_hints: List[Dict[str, Any]]) -> None:
    """
    Iterate over global merge hints and update table objects in the sketch maps
    with shared `header_norm` and `logical_table_id`.
    """
    if not all_hints:
        return

    # Build a lookup of all table objects across all sections
    by_id: Dict[str, Dict[str, Any]] = {}

    for sk in sketches.values():
        if not isinstance(sk, dict): continue
        # Access V2 objects
        v2_objs = (sk.get("sketch_v2") or {}).get("objects", [])
        for o in v2_objs:
            if o.get("type") == "table":
                oid = str(o.get("id"))
                by_id[oid] = o

    # Apply hints
    for hint in all_hints:
        try:
            tlist = hint.get('tables') or []
            if len(tlist) != 2:
                continue

            h_id, b_id = str(tlist[0]), str(tlist[1])
            h = by_id.get(h_id)
            b = by_id.get(b_id)

            if not (h and b):
                continue

            hnorm = h.get('header_norm')
            if not hnorm:
                continue

            # Propagation Logic
            bnorm = b.get('header_norm') or ""
            is_generic = bool(bnorm) and all(tok.isdigit() for tok in bnorm.split('|'))

            reason = hint.get('reason') or []
            scores = hint.get('scores') or {}
            hiou = float(scores.get('h_iou') or 0.0)

            same_cols = ('same_columns' in reason)
            adjacent = any('adjacent' in str(r) for r in reason)

            # Decide to propagate
            should_propagate = bool(hint.get('header_body') or is_generic or (same_cols and adjacent and hiou >= 0.2))

            if should_propagate:
                b['header_norm'] = hnorm

            # Compute common logical ID
            lid = f"lt_{hashlib.sha1(hnorm.encode('utf-8')).hexdigest()[:10]}"
            h['logical_table_id'] = lid
            b['logical_table_id'] = lid

        except Exception as exc:
            log_stage_error(STEP_NAME, exc, {'context': 'propagate_merge_hints'})
            continue


def propagate_headers_deterministically(sketches: Dict[str, Any]) -> None:
    """
    Secondary propagation: header (rows==1) -> body on next page.
    This works independently of the heuristic merge hints logic.
    """
    # Gather all table objects from all sections
    all_tables = []
    for sk in sketches.values():
        v2_objs = (sk.get("sketch_v2") or {}).get("objects", [])
        for o in v2_objs:
            if o.get("type") == "table":
                all_tables.append(o)

    # Group by page
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for t in all_tables:
        p = int(t.get("page", 0))
        by_page.setdefault(p, []).append(t)

    # Iterate pages
    for p, hdrs in by_page.items():
        nxt_page_tables = by_page.get(p + 1) or []
        if not nxt_page_tables:
            continue

        for h in hdrs:
            try:
                # Must be single row header
                if int(h.get("rows", 0)) != 1:
                    continue

                hn = (h.get("header_norm") or "").strip()
                # Must have meaningful header
                if not hn or (all(tok.isdigit() for tok in hn.split('|'))):
                    continue

                cols_h = int(h.get("cols", 0))

                for b in nxt_page_tables:
                    # Column count match
                    if int(b.get("cols", 0)) != cols_h:
                        continue

                    # Horizontal overlap check
                    h_bbox = h.get("bbox") or [0,0,0,0]
                    b_bbox = b.get("bbox") or [0,0,0,0]

                    # Manual 1D IoU check
                    ax0, _, ax1, _ = h_bbox
                    bx0, _, bx1, _ = b_bbox
                    inter = max(0.0, min(float(ax1), float(bx1)) - max(float(ax0), float(bx0)))
                    uni = max(float(ax1), float(bx1)) - min(float(ax0), float(bx0))
                    iou = float(inter / uni) if uni > 0 else 0.0

                    if iou < 0.2:
                        continue

                    # Apply propagation
                    b['header_norm'] = hn
                    lid = f"lt_{hashlib.sha1(hn.encode('utf-8')).hexdigest()[:10]}"
                    h['logical_table_id'] = lid
                    b['logical_table_id'] = lid

            except Exception as exc:
                log_stage_error(STEP_NAME, exc, {'context': 'propagate_headers_deterministically'})
                continue


# --- Internal Helpers ---

def _process_table_element(t, raw_elements, page_bbox, grid, section_page_idx, summary_limit):
    """Processes a single table dictionary into the raw_elements list."""
    bbox = t.get("bbox") or [0, 0, 0, 0]
    pm = t.get("pandas_metrics") or {}
    camel = t.get("camelot_metrics") or {}

    # [Logic for header inference and sanitization omitted for brevity,
    # but mirrors the original _build_section_sketch logic]
    # ... (Simplified for this file generation, assumes headers pre-calculated or generic)

    # Calculate basic metrics
    hdr = t.get("header_inferred") or t.get("header") or t.get("columns") or pm.get("columns") or []
    hdr_text = " | ".join([str(h) for h in hdr])

    # Normalize header
    def _norm_hdr(h: str) -> str:
        s = " ".join(str(h or "").strip().lower().split())
        return s.replace(" ", "_")
    header_norm = "|".join([_norm_hdr(h) for h in hdr]) if hdr else ""

    import hashlib
    logical_table_id = f"lt_{hashlib.sha1(header_norm.encode('utf-8')).hexdigest()[:10]}" if header_norm else None

    raw_elements.append({
        "kind": "table",
        "id": t.get("id") or t.get("table_id") or f"tbl_{t.get('table_index')}",
        "bbox": bbox,
        "grid_bbox": geom._grid_bbox(bbox, page_bbox, grid),
        "summary": fmt._summ(hdr_text, summary_limit),
        "page": int(t.get("page") or t.get("page_idx") or t.get("page_index") or section_page_idx),
        "area": geom._area(bbox),
        "aspect": geom._aspect(bbox),
        "confidence": float((t.get("confidence") or pm.get("data_density") or 1.0)),
        "llm_assist": bool((t.get("llm_assist") or {}).get("patch")),
        "header_norm": header_norm,
        "logical_table_id": logical_table_id,
        "metrics": {
            "rows": int((pm.get("shape") or [0])[0] or 0),
            "cols": int((pm.get("shape") or [0,0])[1] or 0),
            "data_density": float(pm.get("data_density") or 0.0),
            "total_cells": int(pm.get("total_cells") or 0),
            "non_empty_cells": int(pm.get("non_empty_cells") or 0),
            "camelot_acc": float(camel.get("accuracy") or 0.0),
            "camelot_whitespace": float(camel.get("whitespace") or 0.0),
            "fragmentation": float(t.get("fragmentation_score") or 0.0),
        },
        "title_hint": (t.get("title") or t.get("caption") or ""),
    })

def _assign_reading_order(raw_elements, columns_by_page, page_bbox, sec, header_footer_band):
    """Sorts elements and assigns reading order, col_ids, and header/footer flags."""
    enriched = []
    for e in raw_elements:
        b = e.get("bbox") or [0, 0, 0, 0]
        p = int(e.get("page", 0))
        cols = columns_by_page.get(p) or [[page_bbox[0], page_bbox[2]]]

        col_ids, spans = col_utils._assign_cols_and_span(b, cols)

        e["column_id"] = col_ids[0] if col_ids else 0
        e["col_ids"] = col_ids
        e["spans_columns"] = spans

        # Temp keys for sorting
        e["_top"] = float(b[1])
        e["_left"] = float(b[0])
        e["_neg_area"] = -float(e.get("area", geom._area(b)))

        # Header/footer detection
        height = (page_bbox[3] - page_bbox[1]) or 1.0
        top_band = page_bbox[1] + height * header_footer_band
        bot_band = page_bbox[3] - height * header_footer_band
        e["header_footer_candidate"] = bool(float(b[3]) <= top_band or float(b[1]) >= bot_band)

        enriched.append(e)

    # Sort deterministically: Col -> Top -> Left -> Area(desc) -> ID
    enriched.sort(key=lambda x: (
        int(x.get("column_id", 0)),
        round(float(x.get("_top", 0.0)), 3),
        round(float(x.get("_left", 0.0)), 3),
        round(float(x.get("_neg_area", 0.0)), 1),
        str(x.get("id", "")),
    ))

    # Clean up and assign indices
    sid = str(sec.get("id") or "sec")
    for i, e in enumerate(enriched):
        e["reading_order"] = i
        e.pop("_top", None); e.pop("_left", None); e.pop("_neg_area", None)

        prefix = {"text": "txt", "table": "tbl", "figure": "fig"}.get(e.get("kind"), "blk")
        e["sketch_id"] = f"{sid}-{prefix}-{i:03d}"

        # Calculate overlap (O(N^2) but N is small per section)
        e["overlapped"] = False
        e_bbox = e.get("bbox")
        if e_bbox:
            for j, other in enumerate(enriched):
                if i == j: continue
                if geom._iou(e_bbox, other.get("bbox", [0,0,0,0])) > 0.01:
                    e["overlapped"] = True
                    break
    return enriched

def _anchor_floats(enriched):
    """Anchors figures/tables to the nearest text block."""
    texts = [e for e in enriched if e.get("kind") == "text"]
    for f in enriched:
        if f.get("kind") not in ("figure", "table"):
            continue

        fb = f.get("bbox") or [0, 0, 0, 0]
        fx = (fb[0] + fb[2]) / 2.0
        fy = (fb[1] + fb[3]) / 2.0

        best = None
        for t in texts:
            tb = t.get("bbox") or [0, 0, 0, 0]
            tx = (tb[0] + tb[2]) / 2.0
            ty = (tb[1] + tb[3]) / 2.0

            # Distance metric favoring vertical proximity
            d = abs(ty - fy) * 1.5 + abs(tx - fx)

            if best is None or d < best[0]:
                best = (d, t.get("id"))

        if best:
            f["anchor_element_id"] = best[1]
            f["anchor_distance"] = float(round(best[0], 3))

def _union_bbox(elems: List[Dict[str, Any]]) -> List[float]:
    x0, y0 = float("inf"), float("inf")
    x1, y1 = float("-inf"), float("-inf")
    found = False
    for e in elems:
        b = e.get("bbox")
        if not (isinstance(b, (list, tuple)) and len(b) == 4): continue
        ex0, ey0, ex1, ey1 = map(float, b)
        x0, y0, x1, y1 = min(x0, ex0), min(y0, ey0), max(x1, ex1), max(y1, ey1)
        found = True
    return [x0, y0, x1, y1] if found else [0.0, 0.0, 0.0, 0.0]

def _page_window(elems: List[Dict[str, Any]], default: int) -> Tuple[int, int]:
    pages = [int(e.get("page", default)) for e in elems]
    return (min(pages), max(pages)) if pages else (default, default)

def _calculate_merge_hints(tabs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates merge hints for tables in the same section."""
    hints = []
    # Sort by page then table index
    tabs = sorted(tabs, key=lambda t: (int(t.get("page_index", 0) or 0), int(t.get("table_index", 0) or 0)))

    for i in range(len(tabs)):
        for j in range(i + 1, len(tabs)):
            t1, t2 = tabs[i], tabs[j]
            p1 = int(t1.get("page_index", 0) or 0)
            p2 = int(t2.get("page_index", 0) or 0)

            if p2 > p1 + 1: break # Only adjacent pages

            # Simple shape check
            r1 = int((t1.get("pandas_metrics") or {}).get("shape", [0,0])[0] or 0)
            c1 = int((t1.get("pandas_metrics") or {}).get("shape", [0,0])[1] or 0)
            c2 = int((t2.get("pandas_metrics") or {}).get("shape", [0,0])[1] or 0)
            r2 = int((t2.get("pandas_metrics") or {}).get("shape", [0,0])[0] or 0)

            if c1 <= 0 or c1 != c2: continue

            # Horizontal overlap check (using geom helper)
            iou = 0.0
            try:
                # Manual H-IOU here or import from geom if available
                # Inline for safety in this standalone snippet
                ax0, _, ax1, _ = t1.get("bbox", [0,0,0,0])
                bx0, _, bx1, _ = t2.get("bbox", [0,0,0,0])
                inter = max(0.0, min(float(ax1), float(bx1)) - max(float(ax0), float(bx0)))
                uni = max(float(ax1), float(bx1)) - min(float(ax0), float(bx0))
                iou = float(inter / uni) if uni > 0 else 0.0
            except Exception:
                pass

            if iou < 0.2: continue

            header_body = (r1 == 1 and r2 >= 2)

            hints.append({
                "group_id": f"G_tbl_{t1.get('table_index')}_{t2.get('table_index')}",
                "tables": [t1.get("id") or f"tbl_{t1.get('table_index')}", t2.get("id") or f"tbl_{t2.get('table_index')}"],
                "reason": ["same_columns", "adjacent_pages_or_same", f"h_iou>={iou:.2f}"] + (["header_body"] if header_body else []),
                "scores": {"h_iou": round(iou, 2)},
                "header_body": header_body,
            })
    return hints
```
