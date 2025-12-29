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
THRESHOLD_CITATION_MATCH = 80.0  # Fuzzy match score check

def get_section_content(con: duckdb.DuckDBPyConnection, section_id: str) -> Tuple[str, List[str], List[str]]:
    """
    Fetches text, tables, and figures for a section.
    Returns: (concatenated_text, list_of_table_csvs, list_of_figure_paths)
    """
    # 1. Text from Clean Blocks (using v_clean_blocks via section_id)
    # Note: We rely on the section_id FK we populated in Stage 07 (or 04).
    # We sort by page, y0, x0 to ensure reading order.
    blocks = con.sql(f"""
        SELECT text 
        FROM blocks -- Use blocks directly as we trust Stage 07 assignment. 
                    -- Ideally check v_clean_blocks but filtering is subtle if section_id is used.
                    -- Let's use v_clean_blocks if possible, but v_clean_blocks might need section_id join.
                    -- Actually, Stage 07 populated blocks.section_id.
                    -- So we can query blocks. But we want 'clean' blocks.
                    -- Let's query blocks intersecting v_clean_blocks.
        WHERE section_id = '{section_id}'
        AND id IN (SELECT id FROM v_clean_blocks)
        ORDER BY page, round(y0/10)*10, x0
    """).fetchall()
    
    text_content = "\n".join([b[0] for b in blocks])
    
    # 2. Tables
    tables = con.sql(f"""
        SELECT csv_data 
        FROM tables 
        WHERE section_id = '{section_id}'
    """).fetchall()
    table_content = [t[0] for t in tables]
    
    # 3. Figures (path only for now, maybe caption later)
    figures = con.sql(f"""
        SELECT image_path 
        FROM figures 
        WHERE section_id = '{section_id}'
    """).fetchall()
    figure_content = [f[0] for f in figures]
    
    return text_content, table_content, figure_content

def heuristic_is_relevant(text: str, tables: List[str]) -> bool:
    """
    Fast filter to skip sections that are unlikely to contain requirements.
    """
    if tables:
        return True # Tables often contain specs
    
    keywords = ["shall", "must", "require", "constraint", "comply", "will"]
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

def extract_requirements_llm(router, title: str, text: str, tables: List[str]) -> List[Dict[str, Any]]:
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

Output strictly a JSON list of objects:
[
  {{
    "text": "The extracted requirement statement...",
    "type": "Function",
    "confidence": 0.95,
    "citation_snippet": "verbatim text...",
    "is_table_row": false
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
    
    # 1. Fetch Sections
    sections = con.sql("SELECT id, title FROM sections ORDER BY page_start, id").fetchall()
    logger.info(f"Found {len(sections)} sections in corpus.")
    
    router = get_text_router()
    
    processed_count = 0
    requirements_batch = []
    
    for s_id, title in sections:
        # Get Content
        text, tables, figures = get_section_content(con, s_id)
        
        # Heuristic Filter
        if not heuristic_is_relevant(text, tables):
            # logger.debug(f"Skipping section {s_id}: No keywords/tables")
            continue
            
        logger.info(f"Processing Section {s_id} ('{title}')...")
        
        # Extract
        extracted = extract_requirements_llm(router, str(title), text, tables)
        
        # Verify & Collect
        for item in extracted:
            req_text = item.get("text")
            req_type = item.get("type", "Unknown")
            conf = float(item.get("confidence", 0.5))
            citation = item.get("citation_snippet", "")
            is_tbl = bool(item.get("is_table_row", False))
            
            # Verification
            match_score = verify_citation(citation, text, tables)
            if match_score < THRESHOLD_CITATION_MATCH:
                logger.warning(f"Low citation match ({match_score:.1f}%) for: {req_text[:50]}...")
                # We still store it, but maybe penalize confidence?
                conf = conf * 0.8
            
            # ID generation using hash or UUID
            import uuid
            r_id = f"req_{uuid.uuid4().hex[:8]}"
            
            requirements_batch.append((
                r_id, s_id, req_text, req_type, conf, citation, is_tbl
            ))
            
        processed_count += 1
        
        # Batch Insert
        if len(requirements_batch) >= 10:
             con.executemany("INSERT OR REPLACE INTO requirements VALUES (?, ?, ?, ?, ?, ?, ?)", requirements_batch)
             requirements_batch = []
             
    # Flush remaining
    if requirements_batch:
        con.executemany("INSERT OR REPLACE INTO requirements VALUES (?, ?, ?, ?, ?, ?, ?)", requirements_batch)
        
    final_count = con.sql("SELECT count(*) FROM requirements").fetchone()[0]
    logger.info(f"Extraction Complete. Processed {processed_count} relevant sections.")
    logger.info(f"Total Requirements Extracted: {final_count}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", type=str, required=True)
    args = parser.parse_args()
    
    p_dir = Path(args.pipeline_dir)
    db_path = p_dir / "pipeline.duckdb"
    
    run_extract_requirements(p_dir, db_path)
