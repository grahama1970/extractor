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
from extractor.pipeline.utils.markdown_renderer import MarkdownRenderer

# Initialize
console = Console()
STEP_NAME = "10_markdown_exporter"

def sanity() -> int:
    return run_step_sanity(STEP_NAME)


def run(input_path: Path, output_dir: Path = None):
    """
    Run the Markdown Export step.
    Args:
        input_path: Path to `07_assemble_corpus` output or the db file itself.
    """
    db_path = None
    pipeline_dir = input_path

    if input_path.suffix == ".duckdb" and input_path.exists():
        db_path = input_path
        pipeline_dir = input_path.parent
    else:
        pipeline_dir = input_path.parent.parent if input_path.is_file() else input_path
        
        # Locate DuckDB - prefer canonical name used by enrichment stages
        db_path = pipeline_dir / "pipeline.duckdb"
        if not db_path.exists():
            # Legacy fallback
            db_path = pipeline_dir / "corpus.duckdb"
        if not db_path.exists():
            # Fallback for Stage 07 output pattern
            db_path = pipeline_dir / "07_assemble_corpus" / "corpus.duckdb"
    
    if not db_path.exists():
        logger.error(f"DuckDB not found. Tried: pipeline.duckdb, corpus.duckdb, 07_assemble_corpus/corpus.duckdb in {pipeline_dir}")
        return

    # Output setup
    stage_dir = (output_dir or pipeline_dir) / STEP_NAME
    md_out_dir = stage_dir / "markdown_output"
    sec_out_dir = md_out_dir / "sections"
    md_out_dir.mkdir(parents=True, exist_ok=True)
    sec_out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Connecting to {db_path}")
    
    # Initialize Repo
    from extractor.pipeline.utils.content_query import ContentRepository
    repo = ContentRepository(db_path)

    # 1. Pre-fetch Lean4 Proofs (if available)
    proofs_map = repo.get_proofs()
    if proofs_map:
        logger.info(f"Loaded {len(proofs_map)} proofs for export.")

    # Initialize Renderer
    renderer = MarkdownRenderer(proofs_map=proofs_map, pipeline_dir=pipeline_dir)

    # 2. Fetch Sections (with S09 Summaries)
    sections = repo.get_sections()

    full_doc_lines = ["# Full Document Export", ""]
    
    for sec_id, sec_title, p_start, sec_summary in sections:
        sec_header = f"## {sec_title} (ID: {sec_id})"
        sec_lines = [sec_header, ""]
        
        # Display S09 Summary if available
        if sec_summary:
            sec_lines.append(f"> **Summary:** {sec_summary}")
            sec_lines.append("")
        
        # Fetch Content
        items = repo.get_section_content(sec_id)

        req_items = [it for it in items if it[0] == 'requirement']
        if req_items:
            sec_lines.extend(renderer.render_summary_table(req_items))
        
        for itype, content, sort_order, meta_json, asset_id in items:
            meta = json.loads(meta_json) if meta_json else {}
            
            if itype == 'text':
                sec_lines.extend(renderer.render_text(content))
                    
            elif itype == 'table':
                sec_lines.extend(renderer.render_table(content, meta))
                
            elif itype == 'figure':
                sec_lines.extend(renderer.render_figure(content, meta))
                
            elif itype == 'requirement':
                sec_lines.extend(renderer.render_requirement(content, meta, asset_id))

        # Add to full doc
        full_doc_lines.extend(sec_lines)
        
        # Write Section File
        (sec_out_dir / f"{sec_id}.md").write_text("\n".join(sec_lines), encoding="utf-8")
        
    # Write Full Doc
    full_path = md_out_dir / "full_document.md"
    full_path.write_text("\n".join(full_doc_lines), encoding="utf-8")
    
    logger.info(f"Exported {len(sections)} sections to {md_out_dir}")
    return full_path

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 10: Markdown Exporter")
    parser.add_argument("--pipeline-dir", type=Path, required=True, help="Path to pipeline results root")
    args = parser.parse_args()
    
    try:
        logger.info("Running Stage 10...")
        db_path = args.pipeline_dir / "pipeline.duckdb"
        if not db_path.exists():
            logger.error(f"Database missing: {db_path}")
            sys.exit(1)
        
        run(db_path, args.pipeline_dir)
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
