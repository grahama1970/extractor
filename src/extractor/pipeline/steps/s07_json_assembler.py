#!/usr/bin/env python3
"""
Stage 07: JSON Assembler

Replaces the DuckDB ingest (s07_duckdb_ingest.py) and text cleaner (s07b_text_cleaner.py).
Reads JSON artifacts from Stages 01-06, assembles them into a single
``assembled_content.json`` that downstream stages consume directly.

No DuckDB write locks, no database files — just JSON.

Key Responsibilities:
1.  Read sections & blocks from S04.
2.  Read tables from S05c (or S05b / S05).
3.  Read figures from S06b (or S06).
4.  Assign assets to sections via spatial / page logic.
5.  Suppress text blocks that overlap with tables / figures.
6.  Merge contiguous text blocks into paragraphs (S07b logic).
7.  Write ``assembled_content.json``.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from extractor.pipeline.utils.step_sanity import run_step_sanity

STEP_NAME = "07_assembled"

# Maximum reasonable page dimensions (in points)
MAX_BBOX_COORD = 50000.0
MAX_PAGE_NUM = 100000


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_int(value, default: int = 0, min_val: int = None, max_val: int = None, field_name: str = None) -> int:
    if min_val is None:
        min_val = -2147483648
    if max_val is None:
        max_val = 2147483647
    try:
        val = int(value) if value is not None else default
        if not (min_val <= val <= max_val):
            if field_name:
                logger.warning(f"Integer overflow in {field_name}: {value}, clamping")
            val = max(min_val, min(val, max_val))
        return val
    except (TypeError, ValueError, OverflowError):
        return default


def validate_bbox(bbox: list, block_id: str = None) -> list:
    if not bbox or len(bbox) != 4:
        return [0.0, 0.0, 0.0, 0.0]
    validated = []
    had_invalid = False
    for coord in bbox:
        try:
            val = float(coord)
            if not (-MAX_BBOX_COORD <= val <= MAX_BBOX_COORD):
                had_invalid = True
                val = max(0.0, min(val, MAX_BBOX_COORD)) if val > 0 else 0.0
            validated.append(val)
        except (TypeError, ValueError):
            had_invalid = True
            validated.append(0.0)
    if had_invalid and block_id:
        logger.warning(f"Invalid bbox clamped for {block_id}: {bbox} -> {validated}")
    return validated


def clean_text(text: str) -> str:
    if text is None:
        return ""
    return text.replace("\x00", "")


def calculate_sort_order(page: int, x0: float, y0: float, page_width: float = 612.0) -> int:
    mid_page = page_width / 2
    column = 0 if x0 < mid_page else 1
    return int(page * 1_000_000 + column * 100_000 + y0)


# ---------------------------------------------------------------------------
# JSON loaders
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON {path}: {e}")
        return {}


# ---------------------------------------------------------------------------
# Section & Block ingestion (from S04)
# ---------------------------------------------------------------------------

def _ingest_sections_and_blocks(sections_json: Path) -> Tuple[List[Dict], List[Dict]]:
    data = _load_json(sections_json)
    if not data:
        return [], []

    sections_list = data.get("sections", [])
    logger.info(f"Ingesting {len(sections_list)} sections from {sections_json.name}")

    sections = []
    blocks = []

    for section in sections_list:
        s_id = section.get("id")
        title = section.get("title") or section.get("display_title") or section.get("title_display")
        page_start = section.get("page_start")
        page_end = section.get("page_end")
        parent_id = section.get("parent_id")

        sections.append({
            "id": s_id,
            "title": title,
            "page_start": page_start,
            "page_end": page_end,
            "parent_id": parent_id,
            "llm_summary": None,
            "llm_key_concepts": None,
            "llm_metadata": None,
        })

        for block_idx, block in enumerate(section.get("blocks", [])):
            b_id = block.get("id") or block.get("block_id")
            if not b_id:
                b_id = f"{s_id}_block_{block_idx}"

            page = validate_int(block.get("page"), default=0, min_val=0, max_val=MAX_PAGE_NUM)
            bbox = validate_bbox(block.get("bbox", [0, 0, 0, 0]), block_id=b_id)
            x0, y0, x1, y1 = bbox
            text = clean_text(block.get("text", ""))
            b_type = block.get("block_type", "Text")
            is_eq = bool(block.get("is_equation", False))
            latex = clean_text(block.get("latex_content", ""))

            blocks.append({
                "id": b_id,
                "page": page,
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "text": text,
                "type": b_type,
                "section_id": s_id,
                "is_equation": is_eq,
                "latex_content": latex,
            })

    return sections, blocks


# ---------------------------------------------------------------------------
# Table ingestion (from S05/05b/05c)
# ---------------------------------------------------------------------------

def _ingest_tables(tables_json: Path) -> List[Dict]:
    data = _load_json(tables_json)
    if not data:
        return []

    tables_list = data.get("tables", [])
    logger.info(f"Ingesting {len(tables_list)} tables from {tables_json.name}")

    tables = []
    for idx, table in enumerate(tables_list):
        t_id = table.get("id") or table.get("table_id") or table.get("normalized_id")
        if not t_id:
            page_num = table.get("page_number") or table.get("page_index", 0)
            table_idx = table.get("table_index", idx)
            t_id = f"table_p{page_num}_t{table_idx}"

        page = table.get("page_index")
        if page is None:
            pn = table.get("page_number")
            page = (pn - 1) if pn else 0
        page = validate_int(page, default=0, min_val=0, max_val=MAX_PAGE_NUM)

        bbox = validate_bbox(table.get("bbox", [0, 0, 0, 0]), block_id=t_id)
        x0, y0, x1, y1 = bbox

        csv_data = clean_text(table.get("csv", ""))
        if not csv_data and "pandas_df" in table:
            try:
                p_data = table["pandas_df"]
                if p_data and isinstance(p_data, list):
                    import io, csv as csv_mod
                    headers = list(p_data[0].keys())
                    try:
                        headers.sort(key=lambda x: int(x))
                    except ValueError:
                        headers.sort()
                    output = io.StringIO()
                    writer = csv_mod.DictWriter(output, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(p_data)
                    csv_data = output.getvalue()
            except Exception as e:
                logger.warning(f"Failed to convert pandas_df to csv for {t_id}: {e}")

        html_data = clean_text(table.get("html", ""))
        section_id = table.get("section_id")
        sort_order = table.get("sort_order")
        if sort_order is None:
            sort_order = calculate_sort_order(page, x0, y0)

        llm_title = table.get("llm_title") or table.get("ai_title") or table.get("title")
        llm_desc = table.get("llm_description") or table.get("ai_description") or table.get("description")
        image_path = table.get("table_image_path")

        tables.append({
            "id": t_id,
            "page": page,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "csv_data": csv_data,
            "html_data": html_data,
            "section_id": section_id,
            "sort_order": sort_order,
            "llm_title": llm_title,
            "llm_description": llm_desc,
            "image_path": image_path,
        })

    tables.sort(key=lambda t: t["sort_order"])
    return tables


# ---------------------------------------------------------------------------
# Figure ingestion (from S06/06b)
# ---------------------------------------------------------------------------

def _ingest_figures(figures_json: Path) -> List[Dict]:
    data = _load_json(figures_json)
    if not data:
        return []

    figures_list = data.get("figures", [])
    logger.info(f"Ingesting {len(figures_list)} figures from {figures_json.name}")

    figures = []
    for fig in figures_list:
        f_id = fig.get("figure_id") or fig.get("id")
        if not f_id:
            continue

        page = fig.get("page")
        if page is None:
            page = fig.get("page_index", 0)
        page = validate_int(page, default=0, min_val=0, max_val=MAX_PAGE_NUM)

        bbox = validate_bbox(fig.get("bbox", [0, 0, 0, 0]), block_id=f_id)
        x0, y0, x1, y1 = bbox
        image_path = fig.get("image_path", "")
        section_id = fig.get("section_id")

        sort_order = fig.get("sort_order")
        if sort_order is None:
            sort_order = calculate_sort_order(page, x0, y0)

        llm_title = fig.get("llm_title") or fig.get("title")
        llm_desc = fig.get("llm_description") or fig.get("ai_description") or fig.get("description")

        figures.append({
            "id": f_id,
            "page": page,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "image_path": image_path,
            "section_id": section_id,
            "sort_order": sort_order,
            "llm_title": llm_title,
            "llm_description": llm_desc,
        })

    figures.sort(key=lambda f: f["sort_order"])
    return figures


# ---------------------------------------------------------------------------
# Annotation / TOC ingestion
# ---------------------------------------------------------------------------

def _ingest_annotations(annotations_json: Path) -> List[Dict]:
    data = _load_json(annotations_json)
    if not data:
        return []
    annots = data.get("annotations", [])
    result = []
    for a in annots:
        a_id = a.get("id")
        page = validate_int(a.get("page"), default=0, min_val=0, max_val=MAX_PAGE_NUM)
        rect = validate_bbox(a.get("original_rect") or [0, 0, 0, 0], block_id=a_id)
        x0, y0, x1, y1 = rect
        result.append({
            "id": a_id, "page": page, "type": a.get("type", "FreeText"),
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "human_note": a.get("human_note", ""),
            "image_path": a.get("image_path", ""),
            "provenance": a.get("provenance", ""),
        })
    return result


def _ingest_toc_entries(marker_json: Path) -> List[Dict]:
    data = _load_json(marker_json)
    if not data:
        return []
    toc_entries = data.get("toc_entries", [])
    result = []
    for entry in toc_entries:
        result.append({
            "id": validate_int(entry.get("id"), default=0),
            "level": validate_int(entry.get("level"), default=1, min_val=1, max_val=100),
            "title": clean_text(entry.get("title", "")),
            "page": validate_int(entry.get("page"), default=0, min_val=0, max_val=MAX_PAGE_NUM),
            "dest": entry.get("dest", ""),
            "matched_section_id": None,
            "match_confidence": None,
            "match_status": "pending",
        })
    return result


# ---------------------------------------------------------------------------
# Spatial section assignment (ported from SQL logic)
# ---------------------------------------------------------------------------

def _assign_assets_to_sections(
    blocks: List[Dict],
    tables: List[Dict],
    figures: List[Dict],
    sections: List[Dict],
) -> None:
    """Assign tables/figures without section_id using spatial proximity then page range."""

    # Build lookup: page -> blocks on that page
    blocks_by_page: Dict[int, List[Dict]] = {}
    for b in blocks:
        blocks_by_page.setdefault(b["page"], []).append(b)

    def _assign_via_spatial(asset: Dict) -> bool:
        """Try to assign section_id from closest block on same page."""
        page_blocks = blocks_by_page.get(asset["page"], [])
        if not page_blocks:
            return False
        best = min(page_blocks, key=lambda b: abs(b["y0"] - asset["y0"]) + abs(b["x0"] - asset["x0"]))
        asset["section_id"] = best["section_id"]
        return True

    def _assign_via_page_range(asset: Dict) -> bool:
        """Assign using smallest section spanning the asset's page."""
        candidates = [
            s for s in sections
            if s.get("page_start") is not None
            and s.get("page_end") is not None
            and s["page_start"] <= asset["page"] <= s["page_end"]
        ]
        if not candidates:
            # Fallback: any section whose page_start <= asset page
            candidates = [
                s for s in sections
                if s.get("page_start") is not None and s["page_start"] <= asset["page"]
            ]
        if not candidates:
            return False
        best = min(candidates, key=lambda s: (
            (s.get("page_end") or s["page_start"]) - s["page_start"],
            -s["page_start"],
        ))
        asset["section_id"] = best["id"]
        return True

    for asset_list in (tables, figures):
        for asset in asset_list:
            if asset.get("section_id"):
                continue
            if not _assign_via_spatial(asset):
                _assign_via_page_range(asset)

    # Log counts
    t_assigned = sum(1 for t in tables if t.get("section_id"))
    f_assigned = sum(1 for f in figures if f.get("section_id"))
    logger.info(f"Assigned {t_assigned}/{len(tables)} tables and {f_assigned}/{len(figures)} figures to sections.")


# ---------------------------------------------------------------------------
# Overlap suppression (ported from suppress_overlapping_blocks)
# ---------------------------------------------------------------------------

def _suppress_overlapping_blocks(blocks: List[Dict], tables_json: Path) -> List[Dict]:
    """Remove text blocks whose center falls within a table suppression zone."""
    data = _load_json(tables_json)
    raw_tables = data.get("tables", [])
    if not raw_tables:
        return blocks

    zones: List[Tuple[int, float, float, float, float]] = []
    for t in raw_tables:
        comps = t.get("components")
        if comps:
            for c in comps:
                p = c.get("page_index", 0)
                b = c.get("bbox")
                if b and len(b) == 4:
                    zones.append((p, b[0], b[1], b[2], b[3]))
        else:
            p = t.get("page_index")
            if p is None:
                pn = t.get("page_number")
                p = (pn - 1) if pn else 0
            b = t.get("bbox")
            if b and len(b) == 4:
                zones.append((p, b[0], b[1], b[2], b[3]))

    if not zones:
        return blocks

    count_before = len(blocks)
    kept = []
    for blk in blocks:
        if blk["type"] != "Text":
            kept.append(blk)
            continue
        cx = (blk["x0"] + blk["x1"]) / 2
        cy = (blk["y0"] + blk["y1"]) / 2
        suppressed = False
        for zp, zx0, zy0, zx1, zy1 in zones:
            if blk["page"] == zp and zx0 <= cx <= zx1 and zy0 <= cy <= zy1:
                suppressed = True
                break
        if not suppressed:
            kept.append(blk)

    logger.info(f"Suppressed {count_before - len(kept)} overlapping text blocks.")
    return kept


# ---------------------------------------------------------------------------
# v_clean_blocks filter (ported from SQL view)
# ---------------------------------------------------------------------------

def _box_overlap(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1) -> float:
    return max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(0.0, min(ay1, by1) - max(ay0, by0))


def _box_area(x0, y0, x1, y1) -> float:
    return (x1 - x0) * (y1 - y0)


def _get_clean_blocks(blocks: List[Dict], tables: List[Dict], figures: List[Dict]) -> List[Dict]:
    """Filter blocks that overlap >50% with tables or figures (v_clean_blocks equivalent)."""
    clean = []
    for b in blocks:
        b_area = _box_area(b["x0"], b["y0"], b["x1"], b["y1"])
        if b_area <= 0:
            clean.append(b)
            continue
        covered = False
        for t in tables:
            if b["page"] == t["page"]:
                overlap = _box_overlap(b["x0"], b["y0"], b["x1"], b["y1"],
                                       t["x0"], t["y0"], t["x1"], t["y1"])
                if overlap >= 0.5 * b_area:
                    covered = True
                    break
        if not covered:
            for f in figures:
                if b["page"] == f["page"]:
                    overlap = _box_overlap(b["x0"], b["y0"], b["x1"], b["y1"],
                                           f["x0"], f["y0"], f["x1"], f["y1"])
                    if overlap >= 0.5 * b_area:
                        covered = True
                        break
        if not covered:
            clean.append(b)
    return clean


# ---------------------------------------------------------------------------
# Paragraph merging (ported from s07b_text_cleaner)
# ---------------------------------------------------------------------------

def _merge_contiguous_blocks(
    sections: List[Dict],
    blocks: List[Dict],
    tables: List[Dict],
    figures: List[Dict],
) -> List[Dict]:
    """Merge contiguous text blocks into paragraphs per section, interleaving tables/figures."""

    clean_blocks = _get_clean_blocks(blocks, tables, figures)

    # Index by section_id
    blocks_by_sec: Dict[str, List[Dict]] = {}
    for b in clean_blocks:
        if b.get("text") and b["text"].strip():
            blocks_by_sec.setdefault(b["section_id"], []).append(b)

    tables_by_sec: Dict[str, List[Dict]] = {}
    for t in tables:
        tables_by_sec.setdefault(t.get("section_id"), []).append(t)

    figures_by_sec: Dict[str, List[Dict]] = {}
    for f in figures:
        figures_by_sec.setdefault(f.get("section_id"), []).append(f)

    merged_rows: List[Dict] = []
    content_id = 0

    for section in sections:
        section_id = section["id"]

        # Build unified object list
        objects: List[Tuple[str, Dict, int]] = []  # (obj_type, obj, sort_order)

        for b in blocks_by_sec.get(section_id, []):
            so = calculate_sort_order(b["page"], b["x0"], b["y0"])
            objects.append(("block", b, so))

        for t in tables_by_sec.get(section_id, []):
            objects.append(("table", t, t["sort_order"]))

        for f in figures_by_sec.get(section_id, []):
            objects.append(("figure", f, f["sort_order"]))

        objects.sort(key=lambda x: x[2])

        current_text_buffer: List[str] = []
        current_text_bboxes: List[Tuple[float, float, float, float]] = []
        current_page: Optional[int] = None
        current_sort_base: int = 0

        def flush_text_buffer():
            nonlocal content_id, current_text_buffer, current_text_bboxes, current_page, current_sort_base
            if not current_text_buffer:
                return
            merged_text = " ".join(current_text_buffer)
            # Hyphen removal
            merged_text = merged_text.replace("- ", "")
            merged_text = re.sub(r"\s+", " ", merged_text)

            # Compute envelope bbox
            env_x0 = env_y0 = env_x1 = env_y1 = None
            for bx0, by0, bx1, by1 in current_text_bboxes:
                env_x0 = bx0 if env_x0 is None else min(env_x0, bx0)
                env_y0 = by0 if env_y0 is None else min(env_y0, by0)
                env_x1 = bx1 if env_x1 is None else max(env_x1, bx1)
                env_y1 = by1 if env_y1 is None else max(env_y1, by1)

            content_id += 1
            merged_rows.append({
                "id": f"mc_{content_id}",
                "section_id": section_id,
                "page": current_page,
                "type": "text",
                "content": merged_text.strip(),
                "asset_id": None,
                "sort_order": current_sort_base,
                "x0": env_x0, "y0": env_y0, "x1": env_x1, "y1": env_y1,
            })
            current_text_buffer = []
            current_text_bboxes = []

        for obj_type, obj, sort_order in objects:
            if obj_type == "block":
                block_type = obj.get("type", "Text")

                if block_type == "SectionHeader":
                    flush_text_buffer()
                    content_id += 1
                    merged_rows.append({
                        "id": f"mc_{content_id}",
                        "section_id": section_id,
                        "page": obj["page"],
                        "type": "section",
                        "content": obj["text"].strip(),
                        "asset_id": None,
                        "sort_order": sort_order,
                        "x0": obj["x0"], "y0": obj["y0"],
                        "x1": obj["x1"], "y1": obj["y1"],
                    })
                    current_page = obj["page"]
                    current_sort_base = sort_order + 1
                elif obj.get("is_equation"):
                    flush_text_buffer()
                    content_id += 1
                    merged_rows.append({
                        "id": f"mc_{content_id}",
                        "section_id": section_id,
                        "page": obj["page"],
                        "type": "equation",
                        "content": obj.get("latex_content") or obj["text"],
                        "asset_id": obj["id"],
                        "sort_order": sort_order,
                        "x0": obj["x0"], "y0": obj["y0"],
                        "x1": obj["x1"], "y1": obj["y1"],
                    })
                    current_page = obj["page"]
                    current_sort_base = sort_order + 1
                else:
                    # Regular text
                    if current_page is None:
                        current_page = obj["page"]
                        current_sort_base = sort_order
                    elif obj["page"] != current_page:
                        flush_text_buffer()
                        current_page = obj["page"]
                        current_sort_base = sort_order

                    current_text_buffer.append(obj["text"].strip())
                    current_text_bboxes.append((obj["x0"], obj["y0"], obj["x1"], obj["y1"]))
            else:
                # Table or figure — flush text first
                flush_text_buffer()
                content_id += 1
                if obj_type == "table":
                    mc_content = obj.get("llm_title") or "Table"
                else:
                    mc_content = obj.get("llm_title") or "Figure"
                merged_rows.append({
                    "id": f"mc_{content_id}",
                    "section_id": section_id,
                    "page": obj["page"],
                    "type": obj_type,
                    "content": mc_content,
                    "asset_id": obj["id"],
                    "sort_order": sort_order,
                    "x0": obj["x0"], "y0": obj["y0"],
                    "x1": obj["x1"], "y1": obj["y1"],
                })
                current_page = obj["page"]
                current_sort_base = sort_order + 1

        flush_text_buffer()

    text_count = sum(1 for m in merged_rows if m["type"] == "text")
    logger.info(f"Created {len(merged_rows)} merged content entries ({text_count} text blocks)")
    return merged_rows


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_assemble_corpus(
    output_json_path: Path,
    sections_json: Optional[Path],
    tables_json: Optional[Path],
    figures_json: Optional[Path],
    annotations_json: Optional[Path] = None,
    marker_json: Optional[Path] = None,
    scanned_info_json: Optional[Path] = None,
    source_pdf: Optional[str] = None,
    preset_config: Optional[Dict[str, Any]] = None,
) -> Path:
    """Main entry point — assembles all upstream JSON into assembled_content.json."""
    logger.info("Starting Stage 07: JSON Assembler")
    logger.info(f"Output: {output_json_path}")

    # 1. Ingest
    sections, blocks = ([], [])
    if sections_json:
        sections, blocks = _ingest_sections_and_blocks(sections_json)

    tables = _ingest_tables(tables_json) if tables_json else []
    figures = _ingest_figures(figures_json) if figures_json else []
    annotations = _ingest_annotations(annotations_json) if annotations_json else []
    toc_entries = _ingest_toc_entries(marker_json) if marker_json else []

    # 2. Assign assets to sections
    _assign_assets_to_sections(blocks, tables, figures, sections)

    # 3. Suppress overlapping blocks
    if tables_json:
        blocks = _suppress_overlapping_blocks(blocks, tables_json)

    # 4. Merge contiguous text blocks (S07b logic)
    merged_content = _merge_contiguous_blocks(sections, blocks, tables, figures)

    # 5. Build metadata
    scanned_data = _load_json(scanned_info_json) if scanned_info_json else {}
    import datetime
    metadata = {
        "page_count": 0,
        "source_pdf": source_pdf or "",
        "is_scanned": scanned_data.get("is_scanned", False),
        "assembled_at": datetime.datetime.utcnow().isoformat(),
    }

    # 6. Assemble
    assembled = {
        "sections": sections,
        "blocks": blocks,
        "tables": tables,
        "figures": figures,
        "merged_content": merged_content,
        "requirements": [],
        "annotations": annotations,
        "toc_entries": toc_entries,
        "metadata": metadata,
        "document_metadata": {},
        "lean4_proofs": [],
    }

    # 7. Write
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with output_json_path.open("w", encoding="utf-8") as f:
        json.dump(assembled, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Stage 07 Completed. Wrote {len(sections)} sections, "
                f"{len(blocks)} blocks, {len(tables)} tables, "
                f"{len(figures)} figures, {len(merged_content)} merged entries.")
    return output_json_path


# Standard entry point alias
run = run_assemble_corpus


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 07: JSON Assembler")
    parser.add_argument("--pipeline-dir", type=Path, required=True)
    args = parser.parse_args()

    pipeline_dir = args.pipeline_dir

    sections_json = pipeline_dir / "04_section_builder/json_output/04_sections.json"
    tables_json = pipeline_dir / "05c_table_merger/json_output/05c_tables.json"
    if not tables_json.exists():
        tables_json = pipeline_dir / "05b_table_describer/json_output/05b_tables.json"
    if not tables_json.exists():
        tables_json = pipeline_dir / "05_table_extractor/json_output/05_tables.json"

    figures_json = pipeline_dir / "06b_figure_describer/json_output/06b_figures.json"
    if not figures_json.exists():
        figures_json = pipeline_dir / "06_figure_extractor/json_output/06_figures.json"

    annotations_json = pipeline_dir / "01_annotation_processor/json_output/01_annotations.json"
    marker_json = pipeline_dir / "02_marker_extractor/json_output/02_marker_blocks.json"

    out_path = pipeline_dir / "07_assembled" / "assembled_content.json"

    try:
        run_assemble_corpus(
            output_json_path=out_path,
            sections_json=sections_json if sections_json.exists() else None,
            tables_json=tables_json if tables_json.exists() else None,
            figures_json=figures_json if figures_json.exists() else None,
            annotations_json=annotations_json if annotations_json.exists() else None,
            marker_json=marker_json if marker_json.exists() else None,
            scanned_info_json=pipeline_dir / "scanned_pdf.json",
        )
    except Exception as e:
        logger.error(f"S07 execution failed: {e}")
        sys.exit(1)
