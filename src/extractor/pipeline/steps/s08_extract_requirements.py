#!/usr/bin/env python3
"""
Stage 08: Focused Requirement Extraction

This stage implements the core "Pivot" logic:
1.  Query the "Clean Corpus" from DuckDB (Sections + Clean Blocks + Tables).
2.  Filter for relevant sections (heuristic: "shall", "must", or Table).
3.  Prompt the LLM (SciLLM/LiteLLM) to extract requirements with VERBATIM citation snippets.
4.  Store results in the `requirements` table.

This replaces the legacy Lean4 prover step for the initial extraction.
"""

import sys
import json
import logging
import re
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple
import duckdb
from rapidfuzz import fuzz
import json_repair
import os

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=False)

from extractor.pipeline.utils.db.connection import get_connection
from extractor.pipeline.utils.scillm_router import get_text_router
from loguru import logger

# Configuration
THRESHOLD_CONFIDENCE = 0.5
THRESHOLD_CITATION_MATCH = 80.0  # Fuzzy match score for citation verification
SORT_ORDER_PAGE_MULTIPLIER = 10000  # page * 10000 for sort_order base
SORT_ORDER_BLOCK_INCREMENT = 10  # Increment per requirement within section

def get_section_content(con: duckdb.DuckDBPyConnection, section_id: str) -> Tuple[str, List[str], List[str]]:
    """
    Fetches text, tables, and figures for a section.
    Returns: (concatenated_text, list_of_table_csvs, list_of_figure_paths)
    """
    # 1. Text from Clean Blocks - parameterized to prevent SQL injection
    blocks = con.execute("""
        SELECT text 
        FROM blocks 
        WHERE section_id = ?
        AND id IN (SELECT id FROM v_clean_blocks)
        ORDER BY page, round(y0/10)*10, x0
    """, [section_id]).fetchall()
    
    text_content = "\n".join([b[0] for b in blocks if b[0]])
    
    # 2. Tables - parameterized
    tables = con.execute("""
        SELECT csv_data 
        FROM tables 
        WHERE section_id = ?
    """, [section_id]).fetchall()
    table_content = [t[0] for t in tables if t[0]]
    
    # 3. Figures - parameterized
    figures = con.execute("""
        SELECT image_path 
        FROM figures 
        WHERE section_id = ?
    """, [section_id]).fetchall()
    figure_content = [f[0] for f in figures if f[0]]
    
    return text_content, table_content, figure_content

def heuristic_is_relevant(text: str, tables: List[str]) -> bool:
    """
    Fast filter to skip sections that are unlikely to contain requirements.
    """
    if tables:
        return True # Tables often contain specs
    
    keywords = ["shall", "must", "require", "constraint", "comply", "will", "should", "tied to"]
    text_lower = text.lower()
    for kw in keywords:
        if kw in text_lower:
            return True
            
    return False

def verify_citation(snippet: str, full_text: str, table_texts: List[str]) -> float:
    """
    Checks if the snippet exists in the source text or tables.
    Returns a score (0-100).
    """
    if not snippet:
        return 0.0
        
    # Check text
    score_text = fuzz.partial_ratio(snippet.lower(), full_text.lower())
    if score_text >= THRESHOLD_CITATION_MATCH:
        return score_text
        
    # Check tables
    for tbl in table_texts:
        score_tbl = fuzz.partial_ratio(snippet.lower(), tbl.lower())
        if score_tbl >= THRESHOLD_CITATION_MATCH:
            return score_tbl
            
    return score_text

def extract_requirements_llm(router, title: str, text: str, tables: List[str], section_number: str = "") -> List[Dict[str, Any]]:
    """
    Calls LLM to extract requirements.
    """
    prompt = f"""You are an expert Requirements Engineer. Extract all valid requirements, specifications, and layout constraints from the provided text and tables.

Target Section: "{title}"

--- TEXT CONTENT ---
{text}

--- TABLES ({len(tables)}) ---
{chr(10).join(tables)}

--- INSTRUCTIONS ---
1. Identify every statement that specifies a requirement, constraint, dimension, or logic rule.
2. Ignore general descriptions unless they imply a requirement.
3. For each extracted item, you MUST provide a "citation_snippet" that is a VERBATIM copy of the source text or table row that validates the requirement.
4. Assign a "type" (Function, Interface, Physical, Environmental, Design) and "confidence" (0.0-1.0).
5. If the requirement comes from a table, set "is_table_row": true.
6. If the requirement is CONDITIONAL (e.g., "When X is true, Y shall..."), set "is_conditional": true and extract the condition into "condition_text".
7. IMPORTANT: Maintain the ORDER in which requirements appear in the source text.

Output strictly a JSON list of objects:
[
  {{
    "text": "The extracted requirement statement...",
    "type": "Function",
    "confidence": 0.95,
    "citation_snippet": "verbatim text...",
    "is_table_row": false,
    "is_conditional": false,
    "condition_text": null
  }}
]
"""
    try:
        response = router.chat.completions.create(
            model=os.environ.get("CHUTES_TEXT_MODEL", "openai/gpt-4o"), # Fallback if env not set
            messages=[
                {"role": "system", "content": "You are a precise data extractor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        content = response.choices[0].message.content
        data = json_repair.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
             # Handle wrapped case
             return data.get("requirements", [])
        return []
        
    except Exception as e:
        logger.error(f"LLM Extraction failed for {title}: {e}")
        return []

def run_extract_requirements(pipeline_dir: Path, db_path: Path):
    logger.info("Starting Stage 08: Focused Extraction")
    con = get_connection(db_path)
    
    # 0. Check Resume State
    # TODO: Implement resume logic (check IDs in requirements table)
    
    # 1. Fetch Sections with page info for sort_order
    sections = con.sql("""
        SELECT id, title, page_start 
        FROM sections 
        ORDER BY page_start, id
    """).fetchall()
    logger.info(f"Found {len(sections)} sections in corpus.")
    
    router = get_text_router()
    
    processed_count = 0
    requirements_batch = []
    merged_content_batch = []
    
    # Global counter for req_id within document
    global_req_idx = 0
    
    # Get max sort_order from merged_content to append after existing content
    try:
        max_sort = con.sql("SELECT COALESCE(MAX(sort_order), 0) FROM merged_content").fetchone()[0]
    except Exception:
        max_sort = 0
    
    for s_id, title, page_start in sections:
        # Get Content
        text, tables, figures = get_section_content(con, s_id)
        
        # Heuristic Filter
        if not heuristic_is_relevant(text, tables):
            continue
            
        logger.info(f"Processing Section {s_id} ('{title}')...")
        
        # Extract section number from title (e.g., "4.1.5" from "4.1.5. BHT Submodule")
        section_number = ""
        num_match = re.match(r'^(\d+(?:\.\d+)*)', str(title or "").strip())
        if num_match:
            section_number = num_match.group(1)
        
        # Extract
        extracted = extract_requirements_llm(router, str(title), text, tables, section_number)
        
        # Get base sort_order for this section's content - parameterized query
        try:
            result = con.execute(
                "SELECT MIN(sort_order) FROM merged_content WHERE section_id = ?", [s_id]
            ).fetchone()
            section_sort_base = (result[0] if result and result[0] else None) or (page_start * SORT_ORDER_PAGE_MULTIPLIER)
        except duckdb.CatalogException as e:
            logger.debug(f"merged_content table may not exist yet: {e}")
            section_sort_base = page_start * SORT_ORDER_PAGE_MULTIPLIER if page_start else max_sort
        
        # Track position within section
        section_req_idx = 0
        
        # Verify & Collect
        for item in extracted:
            req_text = item.get("text")
            req_type = item.get("type", "Unknown")
            conf = float(item.get("confidence", 0.5))
            citation = item.get("citation_snippet", "")
            is_tbl = bool(item.get("is_table_row", False))
            is_conditional = bool(item.get("is_conditional", False))
            condition_text = item.get("condition_text") or None
            
            # Verification
            match_score = verify_citation(citation, text, tables)
            if match_score < THRESHOLD_CITATION_MATCH:
                logger.warning(f"Low citation match ({match_score:.1f}%) for: {req_text[:50]}...")
                conf = conf * 0.8
            
            # Generate IDs
            global_req_idx += 1
            section_req_idx += 1
            
            # UUID-based internal ID (uuid imported at top of file)
            r_id = f"req_{uuid.uuid4().hex[:8]}"
            
            # Human-readable req_id: REQ-4.1.5-001
            if section_number:
                req_id = f"REQ-{section_number}-{section_req_idx:03d}"
            else:
                req_id = f"REQ-{global_req_idx:04d}"
            
            # Calculate sort_order (position in reading order)
            sort_order = section_sort_base + section_req_idx * SORT_ORDER_BLOCK_INCREMENT
            page = page_start or 0
            
            # Append to requirements batch (id, req_id, section_id, text, type, confidence, 
            #                               citation, is_table_row, is_conditional, condition_text,
            #                               sort_order, page, y0)
            requirements_batch.append((
                r_id, req_id, s_id, req_text, req_type, conf, citation, 
                is_tbl, is_conditional, condition_text, sort_order, page, 0.0
            ))
            
            # Also insert into merged_content for reading order context
            mc_id = f"mc_req_{uuid.uuid4().hex[:6]}"
            # Format: REQ: REQ-4.1.5-001 [COND] Requirement text...
            prefix = "REQ: " + req_id
            if is_conditional:
                prefix += " [COND]"
            content_str = f"{prefix} {req_text}"
            
            merged_content_batch.append((
                mc_id, s_id, page, "requirement", content_str, r_id, sort_order
            ))
            
        processed_count += 1
        
        # Batch Insert
        if len(requirements_batch) >= 10:
            con.executemany("""
                INSERT OR REPLACE INTO requirements 
                (id, req_id, section_id, text, type, confidence, citation_snippet, 
                 is_table_row, is_conditional, condition_text, sort_order, page, y0) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, requirements_batch)
            con.executemany("""
                INSERT OR REPLACE INTO merged_content 
                (id, section_id, page, type, content, asset_id, sort_order) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, merged_content_batch)
            requirements_batch = []
            merged_content_batch = []
             
    # Flush remaining
    if requirements_batch:
        con.executemany("""
            INSERT OR REPLACE INTO requirements 
            (id, req_id, section_id, text, type, confidence, citation_snippet, 
             is_table_row, is_conditional, condition_text, sort_order, page, y0) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, requirements_batch)
        con.executemany("""
            INSERT OR REPLACE INTO merged_content 
            (id, section_id, page, type, content, asset_id, sort_order) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, merged_content_batch)
        
    final_count = con.sql("SELECT count(*) FROM requirements").fetchone()[0]
    cond_count = con.sql("SELECT count(*) FROM requirements WHERE is_conditional = true").fetchone()[0]
    logger.info(f"Extraction Complete. Processed {processed_count} relevant sections.")
    logger.info(f"Total Requirements Extracted: {final_count} ({cond_count} conditional)")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", type=str, required=True)
    args = parser.parse_args()
    
    p_dir = Path(args.pipeline_dir)
    db_path = p_dir / "pipeline.duckdb"
    
    run_extract_requirements(p_dir, db_path)
