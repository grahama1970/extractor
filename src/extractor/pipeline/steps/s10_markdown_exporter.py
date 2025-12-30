#!/usr/bin/env python3
"""
Stage-10: Markdown Exporter — Convert DuckDB corpus to linear Markdown.

Purpose:
- Generate a human/LLM-readable representation of the extracted content.
- Supports "Full Document" mode (one large MD file) and "Per Section" mode.
- Formats tables as Markdown pipes (standard) or CSV (dense).
- Includes AI-enriched descriptions for figures and tables.

Output:
- `data/results/pipeline/10_markdown_exporter/markdown_output/full_document.md`
- `data/results/pipeline/10_markdown_exporter/markdown_output/sections/*.md`
"""

import sys
import os
import json
import duckdb
from pathlib import Path
from loguru import logger
from rich.console import Console
from extractor.pipeline.utils.step_sanity import run_step_sanity
import pandas as pd
import io

# Initialize
console = Console()
STEP_NAME = "10_markdown_exporter"

def sanity() -> int:
    return run_step_sanity(STEP_NAME)

def format_markdown_table(csv_data: str) -> str:
    """Convert CSV string to Markdown table format."""
    try:
        if not csv_data or not csv_data.strip():
            return ""
        df = pd.read_csv(io.StringIO(csv_data))
        if df.empty:
            return ""
        # Convert to markdown
        return df.to_markdown(index=False)
    except Exception:
        return f"```csv\n{csv_data}\n```"

def escape_md(text: str) -> str:
    """Basic escape for markdown text to prevent broken rendering."""
    if not text:
        return ""
    # We might not want to aggressively escape, as the text might already contain valid md.
    # For now, just return as is, assuming source is clean text.
    return text

def run(input_path: Path, output_dir: Path = None):
    """
    Run the Markdown Export step.
    Args:
        input_path: Path to `07_assemble_corpus` output or the db file itself?
                    Actually, the pipeline passes the *previous* step output.
                    Stage 09 (Summarizer) modifies the DB in place.
                    Usage conventions imply pointing to the pipeline root or DuckDB file.
    """
    pipeline_dir = input_path.parent.parent if input_path.is_file() else input_path
    
    # Locate DuckDB
    db_path = pipeline_dir / "corpus.duckdb"
    if not db_path.exists():
        # Fallback for previous steps output pattern
        db_path = pipeline_dir / "07_assemble_corpus" / "corpus.duckdb"
    
    if not db_path.exists():
        logger.error(f"DuckDB not found at {db_path}")
        return

    # Output setup
    stage_dir = (output_dir or pipeline_dir) / STEP_NAME
    md_out_dir = stage_dir / "markdown_output"
    sec_out_dir = md_out_dir / "sections"
    md_out_dir.mkdir(parents=True, exist_ok=True)
    sec_out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Connecting to {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)

    # 1. Fetch Sections (Tree traversal or flat ordered? Flat ordered by page/y0 is safest for "linear" reading)
    # Actually, we want hierarchical headers. "Sections" table has parent_id.
    # For linear export, we can sort by `page_start`, `page_end`.
    
    sections = con.execute("""
        SELECT id, title, page_start 
        FROM sections 
        ORDER BY page_start, id
    """).fetchall()

    full_doc_lines = ["# Full Document Export", ""]
    
    for sec_id, sec_title, p_start in sections:
        sec_header = f"## {sec_title} (ID: {sec_id})"
        sec_lines = [sec_header, ""]
        
        # Query Content for this Section
        # We UNION blocks, tables, and figures, sorting by `sort_order`.
        # Note: sort_order was calc'd as page * 10000 + y0.
        
        query = """
            SELECT type, text_content as content, sort_order, meta
            FROM (
                SELECT 'text' as type, text as text_content, (page * 10000 + y0) as sort_order, NULL as meta
                FROM blocks WHERE section_id = ?
                
                UNION ALL
                
                SELECT 'table' as type, csv_data as text_content, sort_order, 
                       json_object('title', llm_title, 'desc', llm_description) as meta
                FROM tables WHERE section_id = ?
                
                UNION ALL
                
                SELECT 'figure' as type, image_path as text_content, sort_order, 
                       json_object('title', llm_title, 'desc', llm_description) as meta
                FROM figures WHERE section_id = ?
            )
            ORDER BY sort_order
        """
        
        items = con.execute(query, [sec_id, sec_id, sec_id]).fetchall()
        
        for itype, content, sort_order, meta_json in items:
            meta = json.loads(meta_json) if meta_json else {}
            
            if itype == 'text':
                if content and content.strip():
                    sec_lines.append(content.strip())
                    sec_lines.append("")
                    
            elif itype == 'table':
                title = meta.get('title') or "Table"
                desc = meta.get('desc') or ""
                sec_lines.append(f"### {title}")
                if desc:
                    sec_lines.append(f"> *{desc}*")
                sec_lines.append("")
                sec_lines.append(format_markdown_table(content))
                sec_lines.append("")
                
            elif itype == 'figure':
                title = meta.get('title') or "Figure"
                desc = meta.get('desc') or ""
                path_rel = Path(content).name if content else "unknown.png"
                # We assume images are in ../06_figure_extractor/image_output relative to the final MD?
                # Actually, absolute paths in DB. We'll just put the filename for simplicity or a relative link if known.
                sec_lines.append(f"### {title}")
                sec_lines.append(f"![{title}]({content})")
                if desc:
                    sec_lines.append(f"> *{desc}*")
                sec_lines.append("")

        # Add to full doc
        full_doc_lines.extend(sec_lines)
        
        # Write Section File
        (sec_out_dir / f"{sec_id}.md").write_text("\n".join(sec_lines), encoding="utf-8")
        
    # Write Full Doc
    full_path = md_out_dir / "full_document.md"
    full_path.write_text("\n".join(full_doc_lines), encoding="utf-8")
    
    logger.info(f"Exported {len(sections)} sections to {md_out_dir}")
    con.close()
    return full_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", nargs="?", choices=["sanity", "run"], default="run")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    
    if args.cmd == "sanity":
        sanity()
    else:
        run(args.input or Path("data/results/pipeline"), args.output)
