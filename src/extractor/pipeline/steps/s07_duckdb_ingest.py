#!/usr/bin/env python3
"""
Stage 07: DuckDB Ingest

Ingests JSON artifacts from Stages 01-06 into a structured DuckDB database.

Key Responsibilities:
1.  Initialize DuckDB Schema.
2.  Ingest Sections & Blocks (from 04_sections.json).
3.  Ingest Tables (from 05_tables.json or 05c_tables.json).
4.  Ingest Figures (from 06_figures.json or 06b_figures.json).
5.  Assign assets to sections via spatial/page logic.
6.  Create merged_content view for reading order.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import duckdb

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=False)

from extractor.pipeline.utils.db.connection import get_connection
from extractor.pipeline.utils.db.schema import create_schema
from extractor.pipeline.utils.step_sanity import run_step_sanity
from loguru import logger

STEP_NAME = "07_duckdb_ingest"


def sanity() -> int:
    """Run sanity check for this step."""
    return run_step_sanity(STEP_NAME)


def clean_text(text: str) -> str:
    if text is None:
        return ""
    return text.replace("\x00", "") # Remove null bytes

def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logger.warning(f"Artifact not found: {path} (skipping)")
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON {path}: {e}")
        return {}

def calculate_sort_order(page: int, x0: float, y0: float, page_width: float = 612.0) -> int:
    """
    Calculate sort order with column detection.
    
    For multi-column PDFs, this detects columns using x-coordinate bucketing
    and sorts column-by-column (not strictly top-to-bottom).
    
    Args:
        page: Page number (0-indexed)
        x0: Left x-coordinate of bbox
        y0: Top y-coordinate of bbox (PyMuPDF coords: y=0 at bottom)
        page_width: PDF page width in points (default 612 = US Letter)
    
    Returns:
        Integer sort order for reading sequence
    """
    # Simple heuristic: if x0 is in the right half, it's column 2
    # This works for standard 2-column layouts where each column is ~50% width
    # For more complex layouts, we'd need to analyze the full page's x0 distribution
    mid_page = page_width / 2
    column = 0 if x0 < mid_page else 1
    
    # Sort by: page → column → y-coordinate
    # Page gets 1M range, column gets 100k range, y0 gets remaining precision
    return int(page * 1000000 + column * 100000 + y0)


def ingest_sections_and_blocks(con: duckdb.DuckDBPyConnection, sections_json: Path):
    """
    Ingests Sections and their nested Blocks from Stage 04 output.
    """
    path = sections_json
    data = load_json(path)
    if not data:
        return

    sections_list = data.get("sections", [])
    logger.info(f"Ingesting {len(sections_list)} sections from {path.name}")
    
    # Prepare rows
    section_rows = []
    block_rows = []
    
    for section in sections_list:
        # Section Metadata
        s_id = section.get("id")
        title = section.get("title") or section.get("display_title") or section.get("title_display")
        page_start = section.get("page_start")
        page_end = section.get("page_end")
        parent_id = section.get("parent_id")
        
        section_rows.append((s_id, title, page_start, page_end, parent_id))
        
        # Nested Blocks
        blocks = section.get("blocks", [])
        for block in blocks:
            b_id = block.get("id")
            # If block has no ID, we skip it or generate one? Stage 04 usually has IDs.
            if not b_id:
                continue
                
            page = block.get("page")
            bbox = block.get("bbox", [0,0,0,0])
            if not bbox or len(bbox) != 4:
                bbox = [0,0,0,0]
            
            x0, y0, x1, y1 = bbox
            text = clean_text(block.get("text", ""))
            b_type = block.get("block_type", "Text")
            
            # Note: We associate block with section_id immediately since we are reading from 04
            block_rows.append((b_id, page, x0, y0, x1, y1, text, b_type, s_id))

    if section_rows:
        logger.info(f"Inserting {len(section_rows)} sections...")
        con.executemany("INSERT OR REPLACE INTO sections (id, title, page_start, page_end, parent_id) VALUES (?, ?, ?, ?, ?)", section_rows)
        
    if block_rows:
        logger.info(f"Inserting {len(block_rows)} blocks...")
        con.executemany("INSERT OR REPLACE INTO blocks (id, page, x0, y0, x1, y1, text, type, section_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", block_rows)


def get_page_heights(annotations_json: Path) -> Dict[int, float]:
    """
    Extracts page heights from the source PDF (found relative to annotations).
    """
    try:
        import fitz
        if not annotations_json or not annotations_json.exists():
            return {}
        # Expecting json_output/01_annotations.json -> up one -> *clean.pdf
        pdf_dir = annotations_json.parent.parent
        try:
            pdf_path = next(pdf_dir.glob("*_clean.pdf"))
        except StopIteration:
            logger.warning("No clean PDF found for height extraction. Assuming 842.0 (A4/Letter approx).")
            return {}
            
        doc = fitz.open(pdf_path)
        heights = {i: page.rect.height for i, page in enumerate(doc)}
        doc.close()
        return heights
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed. Cannot determine page heights.")
        return {}
    except Exception as e:
        logger.error(f"Failed to extract page heights: {e}")
        return {}

def ingest_tables(con: duckdb.DuckDBPyConnection, tables_json: Path):
    """
    Ingests Tables from Stage 05.
    """
    path = tables_json
    data = load_json(path)
    if not data:
        return
        
    tables_list = data.get("tables", [])
    logger.info(f"Ingesting {len(tables_list)} tables from {path.name}")
    
    rows = []
    
    for idx, table in enumerate(tables_list):
        t_id = table.get("id") or table.get("table_id") or table.get("normalized_id")
        if not t_id:
             page_num = table.get("page_number") or table.get("page_index", 0)
             table_idx = table.get("table_index", idx)
             t_id = f"table_p{page_num}_t{table_idx}"
             
        # Stage 05 outputs page_number (1-indexed) and page_index (0-indexed)
        page = table.get("page_index")
        if page is None:
            pn = table.get("page_number")
            page = (pn - 1) if pn else 0
            
        bbox = table.get("bbox", [0,0,0,0])
        x0, y0, x1, y1 = bbox if bbox and len(bbox)==4 else [0,0,0,0]
        
        csv_data = clean_text(table.get("csv", ""))
        
        # Polyfill: Convert pandas_df list-of-dicts to CSV if missing
        if not csv_data and "pandas_df" in table:
            try:
                p_data = table["pandas_df"]
                if p_data and isinstance(p_data, list):
                    import io
                    import csv
                    # Infer headers from first row
                    headers = list(p_data[0].keys())
                    # Sort numerically if possible (0, 1, 2...)
                    try:
                        headers.sort(key=lambda x: int(x))
                    except ValueError:
                        headers.sort()
                        
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(p_data)
                    csv_data = output.getvalue()
            except Exception as e:
                logger.warning(f"Failed to convert pandas_df to csv for table {t_id}: {e}")

        html_data = clean_text(table.get("html", ""))
        section_id = None
        sort_order = calculate_sort_order(page, x0, y0)
        
        # Capture metadata for summarizer context
        llm_title = table.get("llm_title") or table.get("ai_title") or table.get("title")
        llm_desc = table.get("llm_description") or table.get("ai_description") or table.get("description")
        image_path = table.get("table_image_path")
        
        rows.append((t_id, page, x0, y0, x1, y1, csv_data, html_data, section_id, sort_order, llm_title, llm_desc, image_path))
        
    if rows:
        rows.sort(key=lambda r: r[9])
        con.executemany("INSERT OR REPLACE INTO tables (id, page, x0, y0, x1, y1, csv_data, html_data, section_id, sort_order, llm_title, llm_description, image_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

def ingest_figures(con: duckdb.DuckDBPyConnection, figures_json: Path):
    """
    Ingests Figures from Stage 06.
    """
    path = figures_json
    
    display_path = str(path)
    logger.info(f"Using Figures from: {display_path}")
        
    data = load_json(path)
    if not data:
        return
        
    figures_list = data.get("figures", [])
    logger.info(f"Ingesting {len(figures_list)} figures from {path.name}")
    
    rows = []
    for fig in figures_list:
        f_id = fig.get("figure_id") or fig.get("id")
        if not f_id:
            continue
            
        page = fig.get("page")
        if page is None:
            page = fig.get("page_index", 0)
        bbox = fig.get("bbox", [0,0,0,0])
        x0, y0, x1, y1 = bbox if bbox and len(bbox)==4 else [0,0,0,0]
        image_path = fig.get("image_path", "")
        section_id = None # Initially NULL
        sort_order = calculate_sort_order(page, x0, y0)
        
        # Capture metadata for summarizer context
        llm_title = fig.get("llm_title") or fig.get("title")
        llm_desc = fig.get("llm_description") or fig.get("ai_description") or fig.get("description")
        
        rows.append((f_id, page, x0, y0, x1, y1, image_path, section_id, sort_order, llm_title, llm_desc))
        
    if rows:
        # Sort by reading order before inserting
        rows.sort(key=lambda r: r[8])  # sort_order is at index 8
        con.executemany("INSERT OR REPLACE INTO figures (id, page, x0, y0, x1, y1, image_path, section_id, sort_order, llm_title, llm_description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

def ingest_annotations(con: duckdb.DuckDBPyConnection, annotations_json: Path):
    path = annotations_json
    data = load_json(path)
    if not data:
        return
        
    annots_list = data.get("annotations", [])
    logger.info(f"Ingesting {len(annots_list)} annotations from {path.name}")
    
    rows = []
    for a in annots_list:
        a_id = a.get("id")
        page = a.get("page", 0)
        a_type = a.get("type", "FreeText")
        # Ensure rect is valid
        rect = a.get("original_rect") or [0,0,0,0]
        x0, y0, x1, y1 = rect if isinstance(rect, list) and len(rect) == 4 else [0,0,0,0]
        
        human_note = a.get("human_note", "")
        image_path = a.get("image_path", "")
        provenance = a.get("provenance", "")
        
        rows.append((a_id, page, a_type, x0, y0, x1, y1, human_note, image_path, provenance))
        
    if rows:
        con.executemany("INSERT OR REPLACE INTO annotations (id, page, type, x0, y0, x1, y1, human_note, image_path, provenance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

def assign_assets_to_sections(con: duckdb.DuckDBPyConnection):
    """
    Post-processing step to assign Tables and Figures to Sections using Spatial and Page Logic.
    
    Strategies:
    1. Spatial Proximity: Closest text block on the same page (same section_id).
    2. Page Range Fallback: Smallest section containing the asset's page.
    """
    logger.info("Assigning Tables and Figures to Sections...")
    
    # 1. Spatial Proximity (Update Tables)
    con.execute("""
        UPDATE tables
        SET section_id = (
            SELECT b.section_id
            FROM blocks b
            WHERE b.page = tables.page
            ORDER BY (ABS(b.y0 - tables.y0) + ABS(b.x0 - tables.x0)) ASC
            LIMIT 1
        )
        WHERE section_id IS NULL;
    """)
    
    # 2. Page Range Fallback (Update Tables)
    con.execute("""
        UPDATE tables
        SET section_id = (
            SELECT s.id
            FROM sections s
            WHERE s.page_start <= tables.page AND s.page_end >= tables.page
            ORDER BY (s.page_end - s.page_start) ASC, s.page_start DESC
            LIMIT 1
        )
        WHERE section_id IS NULL;
    """)

    # 3. Spatial Proximity (Update Figures)
    con.execute("""
        UPDATE figures
        SET section_id = (
            SELECT b.section_id
            FROM blocks b
            WHERE b.page = figures.page
            ORDER BY (ABS(b.y0 - figures.y0) + ABS(b.x0 - figures.x0)) ASC
            LIMIT 1
        )
        WHERE section_id IS NULL;
    """)

    # 4. Page Range Fallback (Update Figures)
    con.execute("""
        UPDATE figures
        SET section_id = (
            SELECT s.id
            FROM sections s
            WHERE s.page_start <= figures.page AND s.page_end >= figures.page
            ORDER BY (s.page_end - s.page_start) ASC, s.page_start DESC
            LIMIT 1
        )
        WHERE section_id IS NULL;
    """)
    
    # Log counts
    t_assigned = con.sql("SELECT count(*) FROM tables WHERE section_id IS NOT NULL").fetchone()[0]
    f_assigned = con.sql("SELECT count(*) FROM figures WHERE section_id IS NOT NULL").fetchone()[0]
    t_total = con.sql("SELECT count(*) FROM tables").fetchone()[0]
    f_total = con.sql("SELECT count(*) FROM figures").fetchone()[0]
    logger.info(f"Assigned {t_assigned}/{t_total} tables and {f_assigned}/{f_total} figures to sections.")


def run_assemble_corpus(
    results_db_path: Path,
    sections_json: Path,
    tables_json: Path,
    figures_json: Path,
    annotations_json: Path = None,
    preset_config: Optional[Dict[str, Any]] = None,
):
    """
    Main entry point for Assembler.
    """
    logger.info(f"Starting Stage 07: Assemble Corpus")
    logger.info(f"DB Path: {results_db_path}")
    
    con = get_connection(results_db_path)
    
    # 1. Initialize Schema
    create_schema(con)
    
    # 1b. Clear existing data to ensure fresh run (idempotency)
    # This is critical to prevent "Phantom Tables" from previous runs persisting.
    logger.info("Clearing existing data for strict idempotency...")
    tables_to_clear = ["merged_content", "tables", "figures", "blocks", "sections", "requirements"]
    for tname in tables_to_clear:
        try:
             # Only delete if table exists
             con.execute(f"DELETE FROM {tname}")
        except Exception:
             pass # Table might not exist yet
    
    # 2. Ingest
    con.begin() # Transaction for speed
    try:
        if sections_json:
            ingest_sections_and_blocks(con, sections_json)
        if tables_json:
            ingest_tables(con, tables_json)
        if figures_json:
            ingest_figures(con, figures_json)
        if annotations_json:
            ingest_annotations(con, annotations_json)
        
        assign_assets_to_sections(con)
        con.commit()
    except Exception as e:
        con.rollback()
        logger.error(f"Transaction failed: {e}")
        raise
    
    # 3. Suppress Text Blocks that overlap with Tables
    # This prevents "Garbled Text" (OCR artifacts) from appearing alongside clean tables.
    if tables_json:
        suppress_overlapping_blocks(con, tables_json)

    # 4. Validation / Stats
    try:
        blocks_count = con.sql("SELECT count(*) FROM blocks").fetchone()[0]
        suppressed = con.sql("SELECT count(*) FROM blocks WHERE suppressed=TRUE").fetchone() if False else [0] # suppressed col doesn't exist, we delete
        logger.info(f"Total Blocks: {blocks_count}")
    except Exception:
        pass
    
    con.close()
    logger.info("Stage 07 Completed Successfully.")

def suppress_overlapping_blocks(con: duckdb.DuckDBPyConnection, tables_json: Path):
    """
    Remove ('Text') blocks that are significantly covered by Tables.
    Uses 'components' from S05c (Merged Tables) to suppress duplicate text 
    across all pages spanned by the table.
    """
    logger.info("Suppressing overlapping text blocks...")
    data = load_json(tables_json)
    tables = data.get("tables", [])
    
    if not tables:
        return

    zones = []
    for t in tables:
        # Check for multi-page components (from S05c table merger)
        comps = t.get("components")
        if comps:
            for c in comps:
                p = c.get("page_index", 0)
                b = c.get("bbox")
                if b and len(b) == 4:
                    zones.append((p, b[0], b[1], b[2], b[3]))
        else:
            # Fallback to single table bbox
            p = t.get("page_index")
            if p is None:
                # Convert page_number to page_index if needed
                pn = t.get("page_number")
                p = (pn - 1) if pn else 0
            
            b = t.get("bbox")
            if b and len(b) == 4:
                 zones.append((p, b[0], b[1], b[2], b[3]))
                 
    if not zones:
        return
        
    logger.info(f"Identified {len(zones)} suppression zones from tables.")
    
    try:
        con.execute("CREATE TEMP TABLE suppression_zones (page INTEGER, x0 DOUBLE, y0 DOUBLE, x1 DOUBLE, y1 DOUBLE)")
        con.executemany("INSERT INTO suppression_zones VALUES (?, ?, ?, ?, ?)", zones)
        
        # Delete blocks whose center falls within a suppression zone
        query = """
        DELETE FROM blocks 
        WHERE type = 'Text' 
        AND EXISTS (
            SELECT 1 FROM suppression_zones z 
            WHERE z.page = blocks.page 
            AND (blocks.x0 + blocks.x1)/2 >= z.x0 
            AND (blocks.x0 + blocks.x1)/2 <= z.x1 
            AND (blocks.y0 + blocks.y1)/2 >= z.y0 
            AND (blocks.y0 + blocks.y1)/2 <= z.y1
        )
        """
        count_before = con.sql("SELECT count(*) FROM blocks").fetchone()[0]
        con.execute(query)
        count_after = con.sql("SELECT count(*) FROM blocks").fetchone()[0]
        
        logger.success(f"Suppressed {count_before - count_after} overlapping text blocks.")
        
        con.execute("DROP TABLE suppression_zones")
        
    except Exception as e:
        logger.warning(f"Suppression failed: {e}")


# Standard entry point alias for consistency across pipeline steps
run = run_assemble_corpus


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 07: DuckDB Ingest")
    parser.add_argument("--pipeline-dir", type=Path, required=True)
    args = parser.parse_args()
    
    pipeline_dir = args.pipeline_dir
    db_path = pipeline_dir / "pipeline.duckdb"
    
    # Inputs
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
    
    try:
        run_assemble_corpus(
            results_db_path=db_path,
            sections_json=sections_json if sections_json.exists() else None,
            tables_json=tables_json if tables_json.exists() else None,
            figures_json=figures_json if figures_json.exists() else None,
            annotations_json=annotations_json if annotations_json.exists() else None
        )
    except Exception as e:
        logger.error(f"S07 execution failed: {e}")
        sys.exit(1)
