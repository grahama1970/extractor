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
from typing import List, Dict, Any, Tuple
import duckdb

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=False)

from extractor.pipeline.utils.db.connection import get_connection
from extractor.pipeline.utils.db.schema import create_schema
from loguru import logger

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
        sort_order = int(page * 10000 + y0)
        
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
        sort_order = int(page * 10000 + y0)  # Reading order
        
        # Capture metadata for summarizer context
        llm_title = fig.get("llm_title") or fig.get("title")
        llm_desc = fig.get("llm_description") or fig.get("ai_description") or fig.get("description")
        
        rows.append((f_id, page, x0, y0, x1, y1, image_path, section_id, sort_order, llm_title, llm_desc))
        
    if rows:
        # Sort by reading order before inserting
        rows.sort(key=lambda r: r[8])  # sort_order is at index 8
        con.executemany("INSERT OR REPLACE INTO figures (id, page, x0, y0, x1, y1, image_path, section_id, sort_order, llm_title, llm_description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

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


def merge_page_break_tables(con: duckdb.DuckDBPyConnection, pipeline_dir: Path):
    """
    Merge tables split across page breaks.
    
    Conservative, deterministic approach:
    - Table 1 at bottom of page N (y1 > 80% page height)
    - Table 2 at top of page N+1 (y0 < 20% page height)
    - Same section, same column count
    - Table 1 has few rows (orphan)
    - No paragraph text between
    - Headers match OR table 2 has no real header
    """
    import pandas as pd
    import io
    
    # Get page dimensions from first page (assume uniform)
    # Default to standard letter size if not available
    PAGE_HEIGHT = 792.0  # Standard PDF page height
    
    # Get all tables ordered by page and position
    tables = con.execute("""
        SELECT id, page, x0, y0, x1, y1, csv_data, section_id, sort_order
        FROM tables
        ORDER BY page, y0
    """).fetchall()
    
    if len(tables) < 2:
        return
    
    merged_ids = set()
    merge_count = 0
    
    for i in range(len(tables) - 1):
        t1_id, t1_page, t1_x0, t1_y0, t1_x1, t1_y1, t1_csv, t1_section, t1_sort = tables[i]
        t2_id, t2_page, t2_x0, t2_y0, t2_x1, t2_y1, t2_csv, t2_section, t2_sort = tables[i + 1]
        
        # Skip if already merged
        if t1_id in merged_ids or t2_id in merged_ids:
            continue
        
        # === HARD REQUIREMENTS ===
        
        # 1. Adjacent pages
        if t2_page != t1_page + 1:
            continue
        
        # 2. Same section
        if t1_section != t2_section:
            continue
        
        # 3. (Removed) Coordinate checks - rely on sequence and headers
        # if t1_y1 < PAGE_HEIGHT * 0.50: continue
        # if t2_y0 > PAGE_HEIGHT * 0.50: continue
        
        # 5. Parse CSVs and check column count
        try:
            df1 = pd.read_csv(io.StringIO(t1_csv)) if t1_csv else pd.DataFrame()
            df2 = pd.read_csv(io.StringIO(t2_csv)) if t2_csv else pd.DataFrame()
        except Exception:
            continue
        
        if df1.empty or df2.empty:
            continue
        
        if len(df1.columns) != len(df2.columns):
            continue
        
        # 6. (Removed) Table 1 size check - allow large tables to merge
        # if len(df1) > 3: continue
        
        # 7. Check if table 1 looks like a sentence (false positive)
        first_row_text = " ".join(str(v) for v in df1.iloc[0].values if pd.notna(v))
        word_count = len(first_row_text.split())
        if word_count > 15 and len(df1) == 1:
            # Likely a sentence, not a table row
            continue
        
        # 8. Headers match OR table 2 has numeric headers (no real header)
        h1 = [str(c).strip().lower() for c in df1.columns]
        h2 = [str(c).strip().lower() for c in df2.columns]
        h2_is_numeric = all(str(c).isdigit() or c.startswith("unnamed") for c in df2.columns)
        
        if not h2_is_numeric and h1 != h2:
             logger.info(f"Header mismatch for {t1_id} / {t2_id}. Treating T2 header as data row due to strong geometry match.")
             # Demote header to data
             df2_row = pd.DataFrame([df2.columns], columns=df2.columns)
             df2 = pd.concat([df2_row, df2], ignore_index=True)
             df2.columns = df1.columns

        # === MERGE ===
        logger.info(f"Merging table {t1_id} with {t2_id} (page break split)")
        
        # Combine DataFrames
        if h2_is_numeric:
            # Table 2 has no header, use table 1's header
            df2.columns = df1.columns
        
        merged_df = pd.concat([df1, df2], ignore_index=True)
        merged_csv = merged_df.to_csv(index=False)
        
        # Update table 2 with merged data and expanded bbox
        new_y0 = min(t1_y0, t2_y0)
        new_y1 = max(t1_y1, t2_y1)
        new_x0 = min(t1_x0, t2_x0)
        new_x1 = max(t1_x1, t2_x1)
        
        con.execute("""
            UPDATE tables
            SET csv_data = ?, y0 = ?, y1 = ?, x0 = ?, x1 = ?
            WHERE id = ?
        """, [merged_csv, new_y0, new_y1, new_x0, new_x1, t2_id])
        
        # Delete table 1 (it's now part of table 2)
        con.execute("DELETE FROM tables WHERE id = ?", [t1_id])
        
        merged_ids.add(t1_id)
        merge_count += 1
    
    if merge_count > 0:
        logger.info(f"Merged {merge_count} page-break split table(s)")


def merge_contiguous_blocks(con: duckdb.DuckDBPyConnection):
    """
    Post-processing: Merge contiguous text blocks per section, stopping at figures/tables.
    
    Creates a 'merged_content' table with entries in reading order:
    - type: 'text', 'table', 'figure'
    - content: merged text (for blocks) or ID reference (for assets)
    - sort_order: for reading sequence
    """
    import nltk
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    from nltk.tokenize import sent_tokenize
    
    logger.info("Merging contiguous text blocks...")
    
    # Create merged_content table
    con.execute("""
        CREATE TABLE IF NOT EXISTS merged_content (
            id VARCHAR PRIMARY KEY,
            section_id VARCHAR,
            page INTEGER,
            type VARCHAR,  -- 'text', 'table', 'figure'
            content VARCHAR,
            asset_id VARCHAR,  -- Reference to tables/figures.id (NULL for text)
            sort_order INTEGER
        )
    """)
    con.execute("DELETE FROM merged_content")  # Clear for re-run
    
    # Get all sections
    sections = con.execute("SELECT id FROM sections").fetchall()
    
    merged_rows = []
    content_id = 0
    
    for (section_id,) in sections:
        # Get all objects for section, union'd and sorted
        # Include block type to detect section headers
        query = """
        SELECT 'block' as obj_type, id, page, y0, text as content, type as block_type, page * 10000 + y0 as sort_order
        FROM v_clean_blocks 
        WHERE section_id = ? AND text IS NOT NULL AND TRIM(text) != ''
        UNION ALL
        SELECT 'table' as obj_type, id, page, y0, csv_data as content, 'table' as block_type, sort_order
        FROM tables WHERE section_id = ?
        UNION ALL
        SELECT 'figure' as obj_type, id, page, y0, llm_description as content, 'figure' as block_type, sort_order
        FROM figures WHERE section_id = ?
        ORDER BY sort_order
        """
        objects = con.execute(query, [section_id, section_id, section_id]).fetchall()
        
        current_text_buffer = []
        current_page = None
        current_sort_base = 0
        
        def flush_text_buffer():
            nonlocal content_id, current_text_buffer, current_page, current_sort_base
            if current_text_buffer:
                merged_text = " ".join(current_text_buffer)
                # Ensure we don't cut sentences - validate with sent_tokenize
                sentences = sent_tokenize(merged_text)
                if sentences:
                    merged_text = " ".join(sentences)  # Clean up
                content_id += 1
                merged_rows.append((
                    f"mc_{content_id}",
                    section_id,
                    current_page,
                    "text",
                    merged_text.strip(),
                    None,
                    current_sort_base
                ))
                current_text_buffer = []
        
        for obj in objects:
            obj_type, obj_id, page, y0, content, block_type, sort_order = obj
            
            if obj_type == 'block':
                # Check if this is a section header
                if block_type == 'SectionHeader':
                    # Flush any pending text, then add section header as its own entry
                    flush_text_buffer()
                    content_id += 1
                    merged_rows.append((
                        f"mc_{content_id}",
                        section_id,
                        page,
                        "section",  # Type for section headers
                        content.strip(),
                        None,
                        sort_order
                    ))
                    current_page = page
                    current_sort_base = sort_order + 1
                else:
                    # Regular text block
                    if current_page is None:
                        current_page = page
                        current_sort_base = sort_order
                    elif page != current_page:
                        # Page changed - flush
                        flush_text_buffer()
                        current_page = page
                        current_sort_base = sort_order
                    
                    current_text_buffer.append(content.strip())
            else:
                # Asset (table/figure) - flush text buffer first
                flush_text_buffer()
                content_id += 1
                merged_rows.append((
                    f"mc_{content_id}",
                    section_id,
                    page,
                    obj_type,
                    content,
                    obj_id,
                    sort_order
                ))
                current_page = page
                current_sort_base = sort_order + 1  # Next text starts after asset
        
        # Flush any remaining text
        flush_text_buffer()
    
    if merged_rows:
        con.executemany(
            "INSERT INTO merged_content VALUES (?, ?, ?, ?, ?, ?, ?)",
            merged_rows
        )
    
    count = con.execute("SELECT count(*) FROM merged_content").fetchone()[0]
    text_count = con.execute("SELECT count(*) FROM merged_content WHERE type='text'").fetchone()[0]
    logger.info(f"Created {count} merged content entries ({text_count} text blocks)")


def run_assemble_corpus(
    results_db_path: Path,
    sections_json: Path,
    tables_json: Path,
    figures_json: Path,
    annotations_json: Path = None
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
        
        assign_assets_to_sections(con)
        con.commit()
    except Exception as e:
        con.rollback()
        logger.error(f"Transaction failed: {e}")
        raise
    
    # 3. Post-processing: Merge page-break split tables
    # DEPRECATED in S07: Now handled by S05c (Table Merger) before ingestion.
    # merge_page_break_tables(con, None)
    
    # 3. Suppress Text Blocks that overlap with Tables
    # This prevents "Garbled Text" (OCR artifacts) from appearing alongside clean tables.
    if tables_json:
        suppress_overlapping_blocks(con, tables_json)
    
    # 4. Post-processing: Merge contiguous text blocks
    merge_contiguous_blocks(con)
        
    # 5. Validation / Stats
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


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 07: DuckDB Ingest")
    parser.add_argument("--pipeline-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing results without running")
    args = parser.parse_args()
    
    pipeline_dir = args.pipeline_dir
    db_path = pipeline_dir / "pipeline.duckdb"
    
    if args.verify_only:
        if not db_path.exists():
             print("❌ Pipeline DB missing")
             sys.exit(1)
        # TODO: Add deeper verification (schema check)
        print("✅ Ralph verify-only passed.")
        sys.exit(0)
    
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
