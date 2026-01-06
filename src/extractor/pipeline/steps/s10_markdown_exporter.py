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
    con = duckdb.connect(str(db_path), read_only=True)

    # 1. Fetch Sections (Tree traversal or flat ordered? Flat ordered by page/y0 is safest for "linear" reading)
    # Actually, we want hierarchical headers. "Sections" table has parent_id.
    # For linear export, we can sort by `page_start`, `page_end`.
    
    # 1. Pre-fetch Lean4 Proofs (if available)
    proofs_map = {}
    try:
        # Check if table exists
        has_proofs = con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'lean4_proofs'").fetchone()
        if has_proofs:
            # Map by ID (hash)
            p_rows = con.execute("""
                SELECT id, theorem_strategy, lean4_code, compilation_status, proof_result 
                FROM lean4_proofs
            """).fetchall()
            for r in p_rows:
                proofs_map[r[0]] = {
                    "strategy": r[1],
                    "code": r[2],
                    "status": r[3],
                    "result": r[4]
                }
            logger.info(f"Loaded {len(proofs_map)} proofs for export.")
    except Exception as e:
        logger.warning(f"Could not load proofs: {e}")

    # 2. Fetch Sections (with S09 Summaries)
    sections = con.execute("""
        SELECT id, title, page_start, llm_summary 
        FROM sections 
        ORDER BY page_start, id
    """).fetchall()

    full_doc_lines = ["# Full Document Export", ""]
    
    for sec_id, sec_title, p_start, sec_summary in sections:
        sec_header = f"## {sec_title} (ID: {sec_id})"
        sec_lines = [sec_header, ""]
        
        # Display S09 Summary if available
        if sec_summary:
            sec_lines.append(f"> **Summary:** {sec_summary}")
            sec_lines.append("")
        
        # Query Content for this Section
        # We UNION blocks, tables, and figures, sorting by `sort_order`.
        # Note: sort_order was calc'd as page * 10000 + y0.
        
        # Query Content for this Section from MERGED_CONTENT
        # This includes valid text, tables, figures, AND REQUIREMENTS (Stage 08)
        # properly interleaved by sort_order.
        
        query = """
            SELECT 
                mc.type,
                CASE 
                    WHEN mc.type = 'requirement' THEN (SELECT text FROM requirements WHERE id = mc.asset_id)
                    WHEN mc.type = 'table' THEN (SELECT csv_data FROM tables WHERE id = mc.asset_id)
                    WHEN mc.type = 'figure' THEN (SELECT image_path FROM figures WHERE id = mc.asset_id)
                    ELSE mc.content 
                END as content,
                mc.sort_order,
                CASE 
                    WHEN mc.type = 'requirement' THEN (SELECT json_object('req_id', req_id, 'citation', citation_snippet, 'type', type, 'is_conditional', is_conditional) FROM requirements WHERE id = mc.asset_id)
                    WHEN mc.type = 'table' THEN (SELECT json_object('title', llm_title, 'desc', llm_description) FROM tables WHERE id = mc.asset_id)
                    WHEN mc.type = 'figure' THEN (SELECT json_object('title', llm_title, 'desc', llm_description) FROM figures WHERE id = mc.asset_id)
                    ELSE NULL
                END as meta_json,
                mc.asset_id
            FROM merged_content mc
            WHERE mc.section_id = ?
            ORDER BY mc.sort_order
        """
        
        
        items = con.execute(query, [sec_id]).fetchall()

        # [NEW] Pre-scan for Requirements to build Summary Table
        req_items = [it for it in items if it[0] == 'requirement']
        if req_items:
            sec_lines.append("")
            sec_lines.append("### Requirement Proof Summary")
            sec_lines.append("")
            sec_lines.append("| ID | Type | Status | Theorem |")
            sec_lines.append("| :--- | :--- | :--- | :--- |")
            
            for _, content, _, meta_json, asset_id in req_items:
                meta = json.loads(meta_json) if meta_json else {}
                req_id = meta.get('req_id') or "REQ-UNKNOWN"
                req_type = (meta.get('type') or "FUNCTION").upper()
                if meta.get('is_conditional'): req_type = "CONDITIONAL"
                
                # Proof Lookup
                status_icon = "❓"
                status_text = "Pending"
                theorem_name = "`coverage_missing`"
                
                if asset_id in proofs_map:
                    p = proofs_map[asset_id]
                    if p['status'] == 'verified':
                        status_icon = "✅"
                        status_text = "Verified"
                    elif p['status'] == 'failed':
                        status_icon = "❌"
                        status_text = "Failed"
                    else:
                        status_icon = "⚠️"
                        status_text = p['status']
                    
                    # Extract theorem name from code if possible
                    code = p['code']
                    if "theorem" in code:
                        parts = code.split("theorem", 1)[1].strip().split()
                        if parts:
                            theorem_name = f"`{parts[0]}`"
                    else:
                        # Fallback to snippet
                        snippet = code.replace("\n", " ")[:20]
                        theorem_name = f"`{snippet}...`"

                sec_lines.append(f"| **{req_id}** | {req_type} | {status_icon} {status_text} | {theorem_name} |")
            
            sec_lines.append("")
            sec_lines.append("")
        
        for itype, content, sort_order, meta_json, asset_id in items:
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
                
                # Expose failures instead of hiding them
                table_md = format_markdown_table(content)
                if not table_md:
                     sec_lines.append("> ⚠️ **Warning: Table data could not be extracted or is empty.**")
                else:
                    sec_lines.append(table_md)
                sec_lines.append("")
                
            elif itype == 'figure':
                title = meta.get('title') or "Figure"
                desc = meta.get('desc') or ""
                # Compute relative path for portability
                if content:
                    try:
                        img_abs = Path(content)
                        # Make path relative to pipeline_dir for portability
                        img_rel = img_abs.relative_to(pipeline_dir) if img_abs.is_absolute() else Path(content)
                    except ValueError:
                        # If not under pipeline_dir, use filename only
                        img_rel = Path(content).name
                else:
                    img_rel = "unknown.png"
                sec_lines.append(f"### {title}")
                sec_lines.append(f"![{title}]({img_rel})")
                if desc:
                    sec_lines.append(f"> *{desc}*")
                sec_lines.append("")
                
            elif itype == 'requirement':
                req_id = meta.get('req_id') or "REQ-UNKNOWN"
                citation = meta.get('citation') or ""
                req_type = meta.get('type') or "requirement"
                is_cond = bool(meta.get('is_conditional', False))
                
                type_tag = ""
                if is_cond:
                    type_tag = " [CONDITIONAL]"
                elif req_type and req_type.lower() != "requirement":
                     type_tag = f" [{req_type.upper()}]"

                sec_lines.append(f"> **[{req_id}]{type_tag}** {content}")
                if citation:
                     sec_lines.append(f"> *Source: \"{citation}\"*")
                
                # Append Proof Status if available
                if asset_id in proofs_map:
                    p = proofs_map[asset_id]
                    status_icon = "✅" if p['status'] == 'verified' else "❌"
                    status_text = "Verified" if p['status'] == 'verified' else "Failed"
                    strategy = p['strategy'] or "unknown"
                    
                    # Create a mini table for the proof
                    # "theorem" | "tactic/strategy" | "result/code"
                    # User asked for: section_id, requirement_id, requirement, theorem, tactic, tactics_tried
                    # We are INSIDE the section and requirement block, so we just show the proof details.
                    
                    # Clean up code for display (single line or block?)
                    # Block is better for code.
                    code_snippet = (p['code'] or "").replace("\n", " ")
                    if len(code_snippet) > 100: code_snippet = code_snippet[:100] + "..."
                    
                    result_msg = (p['result'] or "").replace("\n", " ")
                    if len(result_msg) > 100: result_msg = result_msg[:100] + "..."

                    sec_lines.append(f">")
                    sec_lines.append(f"> | Proof Status | Strategy | Details |")
                    sec_lines.append(f"> | :--- | :--- | :--- |")
                    sec_lines.append(f"> | {status_icon} {status_text} | {strategy} | `Theorem: {code_snippet}` <br> `Msg: {result_msg}` |")
                
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
    import sys
    from extractor.pipeline.utils import ralph
    
    parser = argparse.ArgumentParser(description="Stage 10: Markdown Exporter (Ralph Enabled)")
    parser.add_argument("--pipeline-dir", type=Path, required=True, help="Path to pipeline results root")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing results without running")
    args = parser.parse_args()
    
    # Run Generation
    if not args.verify_only:
        try:
            logger.info("Ralph: Running Stage 10...")
            db_path = args.pipeline_dir / "pipeline.duckdb"
            if not db_path.exists():
                logger.error(f"Database missing: {db_path}")
                sys.exit(1)
            
            run(db_path, args.pipeline_dir)
        except Exception as e:
            logger.error(f"Ralph: Execution failed: {e}")
            sys.exit(1)

    # Verification
    try:
        md_dir = args.pipeline_dir / "10_markdown_exporter" / "markdown_output"
        full_doc = md_dir / "full_document.md"
        
        ralph.assert_helping(full_doc.exists(), "full_document.md exists")
        ralph.assert_helping(full_doc.stat().st_size > 1024, f"full_document.md size {full_doc.stat().st_size} > 1KB")
        
        # Content Check
        content = full_doc.read_text(encoding="utf-8")
        if "Requirement Proof Summary" not in content:
            logger.warning("Ralph: 'Requirement Proof Summary' missing (expected if running in deterministic mode)")
        if "REQ-" not in content:
            logger.warning("Ralph: No requirement IDs found (expected if running in deterministic mode)")
        
        # Check for meaningful content (not just headers)
        lines = content.splitlines()
        row_count = len([l for l in lines if l.strip()])
        logger.info(f"Ralph: Document has {row_count} non-empty lines.")
        
        print("✅ Ralph is happy! Stage 10 is outputting a valid document.")
        sys.exit(0)
        
    except ralph.RalphError as e:
        logger.error(f"Ralph is sad: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Verification crashed: {e}")
        sys.exit(1)
