#!/usr/bin/env python3
"""
Stage 07b: Text Cleaner — Merge and clean text blocks.

Purpose:
- Reads raw `blocks`, `tables`, and `figures` from DuckDB.
- Merges contiguous text blocks into coherent paragraphs.
- cleans artifacts (hyphens, split words).
- Creates `merged_content` table (linear reading order).

Input: flattened blocks/assets in DuckDB.
Output: `merged_content` table.
"""

import sys
from typing import Any, Dict, Optional

import duckdb
from pathlib import Path
from loguru import logger
import nltk
from nltk.tokenize import sent_tokenize

from extractor.pipeline.utils.step_sanity import run_step_sanity

# Initialize
STEP_NAME = "07b_text_cleaner"

def sanity() -> int:
    return run_step_sanity(STEP_NAME)

def ensure_nltk():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)

def merge_contiguous_blocks(con: duckdb.DuckDBPyConnection):
    """
    Merge contiguous text blocks per section, stopping at figures/tables.
    
    Creates a 'merged_content' table with entries in reading order:
    - type: 'text', 'table', 'figure'
    - content: merged text (for blocks) or ID reference (for assets)
    - sort_order: for reading sequence
    """
    ensure_nltk()
    
    logger.info("Merging and cleaning contiguous text blocks...")
    
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
    
    # Check if v_clean_blocks exists, else use blocks
    # v_clean_blocks might be a view created in s07 or earlier schema.
    # Schema check:
    try:
        con.execute("SELECT 1 FROM v_clean_blocks LIMIT 1")
    except Exception:
        # Create it if missing (simplified view of blocks)
        con.execute("CREATE VIEW IF NOT EXISTS v_clean_blocks AS SELECT * FROM blocks")

    for (section_id,) in sections:
        # Get all objects for section, union'd and sorted
        # Include block type to detect section headers
        query = """
        SELECT 'block' as obj_type, id, page, y0, text as content, type as block_type, 
               CAST(page * 1000000 + (CASE WHEN x0 < 306 THEN 0 ELSE 1 END) * 100000 + y0 AS INTEGER) as sort_order
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
                
                # --- Text Cleaning Logic ---
                # 1. Hyphen removal (intro- duction -> introduction)
                merged_text = merged_text.replace("- ", "")
                # 2. Extract excessive whitespace
                import re
                merged_text = re.sub(r'\s+', ' ', merged_text)
                # ---------------------------

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


def run(
    pipeline_dir: Path,
    preset_config: Optional[Dict[str, Any]] = None,
):
    """Run Stage 07b."""
    db_path = pipeline_dir / "pipeline.duckdb"
    if not db_path.exists():
        logger.error(f"DB not found: {db_path}")
        sys.exit(1)

    logger.info(f"Connecting to {db_path}")
    con = duckdb.connect(str(db_path))
    
    try:
        merge_contiguous_blocks(con)
    finally:
        con.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stage 07b: Text Cleaner")
    parser.add_argument("--pipeline-dir", type=Path, required=True)
    args = parser.parse_args()
    
    try:
        run(args.pipeline_dir)
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
