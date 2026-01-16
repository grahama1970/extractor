#!/usr/bin/env python3
"""
Stage 14: Report Generator
==========================

Generates a comprehensive report (JSON and Markdown) summarizing the entire pipeline run.

Refactored to be self-contained (merged from utils/report_runner.py).
"""

import sys
import json
import os
import asyncio
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, date
from loguru import logger
from rich.console import Console
import duckdb

# Internal
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    make_event,
    gpu_metrics_available,
)
from extractor.pipeline.utils.step_sanity import run_step_sanity

STEP_NAME = "14_report_generator"
console = Console(stderr=True)


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


def load_results(pipeline_dir: Path) -> Dict[str, Any]:
    """Load results from all pipeline stages (JSON artifacts + DuckDB)."""
    results = {}

    # Map stage output files (Upstream stages that still produce JSONs)
    stage_files = {
        "02_marker": "02_marker_extractor/json_output/02_marker_blocks.json",
        "03_verification": "03_suspicious_headers/json_output/03_verified_blocks.json",
        "04_sections": "04_section_builder/json_output/04_sections.json",
        "04a_audit": "04a_layout_audit/json_output/04a_layout_audit.json",
        "05_tables": "05_table_extractor/json_output/05_tables.json",
        "06_figures": "06_figure_extractor/json_output/06_figures.json",
    }

    for key, rel_path in stage_files.items():
        try:
            path = pipeline_dir / rel_path
            if path.exists():
                text = path.read_text(encoding="utf-8")
                results[key] = json.loads(text)
            else:
                results[key] = None
        except Exception as e:
            logger.error(f"Failed to load {key}: {e}")
            results[key] = None

    # Load from DuckDB (The new Source of Truth for Assembler/Extractor)
    db_path = pipeline_dir / "pipeline.duckdb"
    if db_path.exists():
        try:
            con = duckdb.connect(str(db_path), read_only=True)
            
            # Stats for Stage 07 (Assembler)
            b_count = con.execute("SELECT count(*) FROM blocks").fetchone()[0]
            t_count = con.execute("SELECT count(*) FROM tables").fetchone()[0]
            f_count = con.execute("SELECT count(*) FROM figures").fetchone()[0]
            s_count = con.execute("SELECT count(*) FROM sections").fetchone()[0]
            
            # Stats for Stage 08 (Extractor)
            r_count = 0
            # Check if requirements table exists (it should)
            has_reqs = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='requirements'").fetchone()[0]
            if has_reqs:
                r_count = con.execute("SELECT count(*) FROM requirements").fetchone()[0]
                
            results["db_stats"] = {
                "blocks": b_count,
                "tables": t_count, 
                "figures": f_count,
                "sections": s_count,
                "requirements": r_count
            }
            con.close()
        except Exception as e:
            logger.error(f"Failed to load stats from DuckDB: {e}")
            results["db_stats"] = None
    else:
        results["db_stats"] = None

    return results


def calculate_pipeline_statistics(results: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate comprehensive statistics across the pipeline."""
    stats = {
        "timestamp": datetime.now().isoformat(),
        "stages_present": [k for k, v in results.items() if v is not None],
        "metrics": {},
    }

    # 1. Extraction Metrics (02 Marker)
    if results.get("02_marker"):
        blocks = results["02_marker"].get("blocks", [])
        stats["metrics"]["total_blocks"] = len(blocks)
        avg_conf = np.mean([b.get("confidence", 0) for b in blocks if "confidence" in b] or [0])
        stats["metrics"]["avg_confidence"] = float(avg_conf)

    # 2. Verification Metrics (03 Verification)
    if results.get("03_verification"):
        blocks = results["03_verification"].get("blocks", [])
        stats["metrics"]["verified_blocks"] = len(blocks)
        suspicious = [b for b in blocks if b.get("is_suspicious")]
        stats["metrics"]["suspicious_rate"] = len(suspicious) / max(len(blocks), 1)

    # 3. Structure Metrics (04 Sections)
    if results.get("04_sections"):
        sections = results["04_sections"].get("sections", [])
        stats["metrics"]["total_sections"] = len(sections)
        raw_depths = [s.get("metadata", {}).get("section_depth") for s in sections]
        safe_depths = []
        for d in raw_depths:
            if isinstance(d, list):
                safe_depths.append(len(d))
            elif isinstance(d, int):
                safe_depths.append(d)
        stats["metrics"]["max_depth"] = max(safe_depths) if safe_depths else 0

    # 4. Content Metrics (DuckDB Primary)
    db = results.get("db_stats")
    if db:
        stats["metrics"]["total_blocks"] = db.get("blocks", 0) # Update total blocks specifically
        stats["metrics"]["total_tables"] = db.get("tables", 0)
        stats["metrics"]["total_figures"] = db.get("figures", 0)
        stats["metrics"]["total_sections"] = db.get("sections", 0)
        stats["metrics"]["requirements_extracted"] = db.get("requirements", 0)
    else:
        # Fallback
        if results.get("05_tables"):
            tables = results["05_tables"].get("tables", [])
            stats["metrics"]["total_tables"] = len(tables)

        if results.get("06_figures"):
            figures = results["06_figures"].get("figures", [])
            stats["metrics"]["total_figures"] = len(figures)

    return stats


def generate_content_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a high-level summary of the extracted content."""
    summary = {"toc": [], "key_entities": [], "major_sections": []}

    if results.get("04_sections"):
        sections = results["04_sections"].get("sections", [])
        for s in sections:
            lvl = s.get("level", 10)
            if isinstance(lvl, list):
                lvl = len(lvl)  # Best guess if level is list of path indices
            if isinstance(lvl, int) and lvl <= 2:  # Top-level sections
                summary["major_sections"].append(
                    {"title": s.get("title"), "level": lvl, "page": s.get("page_start")}
                )
            summary["toc"].append(
                {
                    "number": s.get("metadata", {}).get("section_number"),
                    "title": s.get("title"),
                    "page": s.get("page_start"),
                }
            )

    return summary


def _safe_json(data: Any) -> str:
    class CustomEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, (date, datetime)):
                return o.isoformat()
            if isinstance(o, set):
                return list(o)
            try:
                import numpy as np
                if isinstance(o, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
                    return int(o)
                if isinstance(o, (np.float_, np.float16, np.float32, np.float64)):
                    return float(o)
                if isinstance(o, (np.ndarray,)):
                    return o.tolist()
            except ImportError:
                pass
            return str(o)
    return json.dumps(data, cls=CustomEncoder, indent=2)


def _optional_metrics(results: Dict[str, Any]) -> str:
    lines = []
    db = results.get("db_stats")
    if db:
        lines.append(f"- **Tables**: {db.get('tables', 0)}")
        lines.append(f"- **Figures**: {db.get('figures', 0)}")
        lines.append(f"- **Sections**: {db.get('sections', 0)}")
        lines.append(f"- **Requirements Extracted**: {db.get('requirements', 0)}")
    else:
        # 05 tables
        if results.get("05_tables"):
            tabs = results["05_tables"].get("tables", [])
            lines.append(f"- **Tables Extracted**: {len(tabs)}")
        # 06 figures
        if results.get("06_figures"):
            figs = results["06_figures"].get("figures", [])
            lines.append(f"- **Figures Extracted**: {len(figs)}")
            
    return "\n".join(lines)


def generate_markdown_report(
    stats: Dict[str, Any], content_summary: Dict[str, Any], results: Dict[str, Any]
) -> str:
    """Generate a human-readable Markdown report."""
    md = [
        "# Pipeline Execution Report",
        f"**Date**: {stats['timestamp']}",
        "",
        "## 1. Executive Summary",
        f"- **Total Sections**: {stats['metrics'].get('total_sections', 0)}",
        f"- **Total Blocks**: {stats['metrics'].get('total_blocks', 0)}",
        _optional_metrics(results),
        "",
        "## 2. Table of Contents",
    ]

    for item in content_summary["toc"]:
        num = item["number"] or ""
        title = item["title"] or "Untitled"
        page = item["page"]
        md.append(f"- **{num}** {title} (p. {page})")

    md.append("")
    md.append("## 3. Pipeline Health")
    md.append(f"- **Stages Completed**: {len(stats['stages_present'])}")
    if stats['metrics'].get('suspicious_rate', 0) > 0.1:
        md.append(f"⚠️ **High Suspicion Rate**: {stats['metrics']['suspicious_rate']:.1%}")

    return "\n".join(md)


def generate_verification_report(results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate detailed verification report."""
    report = {
        "status": "PASS",
        "issues": [],
        "checks": {"structure_integrity": True, "content_completeness": True},
    }

    if not results.get("04_sections"):
        report["status"] = "FAIL"
        report["issues"].append("Missing sections output")
        report["checks"]["structure_integrity"] = False

    return report


def generate_visual_html_report(pdf_path: Path, results: Dict[str, Any], output_path: Path):
    """Generate side-by-side HTML report."""
    import fitz
    import base64
    
    doc = fitz.open(pdf_path)
    
    # Pre-index content by page
    sections_by_page = {}
    if results.get("04_sections"):
        for s in results["04_sections"].get("sections", []):
            p = s.get("page_start", 0)
            if p not in sections_by_page: sections_by_page[p] = []
            sections_by_page[p].append(s)
            
    html_parts = ["""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Visual Extraction Report</title>
        <style>
            body { font-family: sans-serif; margin: 0; padding: 0; background: #f0f0f0; }
            .container { display: flex; flex-direction: column; gap: 20px; padding: 20px; }
            .page-row { display: flex; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .pdf-pane { flex: 1; padding: 10px; border-right: 1px solid #ddd; text-align: center; }
            .pdf-pane img { max-width: 100%; border: 1px solid #999; }
            .content-pane { flex: 1; padding: 20px; overflow-y: auto; max-height: 100vh; }
            .feedback-pane { background: #eef; padding: 15px; border-top: 1px solid #ccd; }
            .section { border-left: 4px solid #007bff; padding-left: 10px; margin-bottom: 20px; }
            .meta { color: #666; font-size: 0.9em; }
            .form-question { margin-bottom: 10px; }
            h1 { text-align: center; color: #333; }
        </style>
    </head>
    <body>
        <h1>Visual Extraction Report: """ + pdf_path.name + """</h1>
        <div class="container">
    """]
    
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        
        # Render page
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img_data = pix.tobytes("png")
        b64_img = base64.b64encode(img_data).decode("utf-8")
        
        # Get content
        page_sections = sections_by_page.get(page_idx, [])
        content_html = ""
        for s in page_sections:
            title = s.get("title", "Untitled")
            depth = len(s.get("metadata", {}).get("section_id", "").split("."))
            margin = (depth - 1) * 20
            content_html += f"""
            <div class="section" style="margin-left: {margin}px">
                <h3>{title}</h3>
                <div class="meta">ID: {s.get("metadata", {}).get("section_id")}</div>
                <p><i>(Content extracted from this section...)</i></p>
            </div>
            """
            
        if not page_sections:
            content_html = "<p><i>No sections started on this page.</i></p>"
            
        html_parts.append(f"""
        <div class="page-row">
            <div class="pdf-pane">
                <h3>Page {page_idx + 1}</h3>
                <img src="data:image/png;base64,{b64_img}" />
            </div>
            <div class="content-pane">
                {content_html}
                <div class="feedback-pane">
                    <h4>👮 Agent Questions (Collaboration)</h4>
                    <form>
                        <div class="form-question">
                            <label>Does the extraction match the image?</label><br/>
                            <input type="radio" name="p{page_idx}_q1" value="yes"> Yes
                            <input type="radio" name="p{page_idx}_q1" value="no"> No
                        </div>
                        <div class="form-question">
                            <label>Are there missed tables?</label><br/>
                            <input type="checkbox" name="p{page_idx}_q2"> Missed Table
                        </div>
                        <textarea placeholder="Notes on page {page_idx + 1}..." rows="2" style="width:100%"></textarea>
                    </form>
                </div>
            </div>
        </div>
        """)
        
    html_parts.append("</div></body></html>")
    output_path.write_text("\n".join(html_parts), encoding="utf-8")


def run(
    results_dir: Path,
    output_dir: Path,
    source_pdf: Optional[Path] = None,
    preset_config: Optional[Dict[str, Any]] = None,
) -> Optional[Path]:
    try:
        # Inject source_pdf into results for reporting
        # Note: We can't easily modify the full comprehensive report signature without changing calls everywhere,
        # but we can rely on passing it inside 'results' or just handling it in wrapper.
        # Let's handle it by modifying how we call generate_comprehensive_report or overloading it.
        # Actually, simpler: just pass it via a side-channel or update the load_results logic?
        # Better: Update generate_comprehensive_report to accept source_pdf.
        
        json_path, _ = asyncio.run(
            generate_comprehensive_report(results_dir, output_dir or results_dir / "14_report_generator", source_pdf)
        )
        return json_path
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return None

# Updated signature to accept source_pdf
async def generate_comprehensive_report(
    pipeline_dir: Path, output_dir: Optional[Path] = None, source_pdf: Optional[Path] = None
) -> Tuple[Path, Dict[str, Any]]:
    """Generate comprehensive pipeline report."""

    # 1. Load all results
    results = load_results(pipeline_dir)
    if source_pdf:
        results["meta"] = results.get("meta", {})
        results["meta"]["source_pdf"] = str(source_pdf)

    # 2. Calculate Statistics
    stats = calculate_pipeline_statistics(results)

    # 3. Generate Content Summary
    content_summary = generate_content_summary(results)

    # 4. Generate Verification Report
    verification = generate_verification_report(results)

    # 5. Compile Final Report
    final_report = {
        "meta": {
            "version": "1.0",
            "pipeline_id": pipeline_dir.name,
            "generated_at": datetime.now().isoformat(),
            "source_pdf": str(source_pdf) if source_pdf else None,
        },
        "statistics": stats,
        "content_summary": content_summary,
        "verification": verification,
    }

    # 6. Generate Markdown Representation
    markdown_report = generate_markdown_report(stats, content_summary, results)

    # 7. Save Outputs (Logic continues above...)
    out_dir = output_dir or (pipeline_dir / "14_report_generator")
    json_dir = out_dir / "json_output"
    text_dir = out_dir / "text_output"
    html_dir = out_dir / "visual_output"
    
    json_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)

    json_path = json_dir / "final_report.json"
    md_path = text_dir / "report.md"
    html_path = html_dir / "visual_report.html"

    json_path.write_text(_safe_json(final_report), encoding="utf-8")
    md_path.write_text(markdown_report, encoding="utf-8")
    
    # 8. Visual Report
    if source_pdf and Path(source_pdf).exists():
        try:
            generate_visual_html_report(Path(source_pdf), results, html_path)
            console.print(f"  • Visual: {html_path}")
        except Exception as e:
            logger.error(f"Visual report generation failed: {e}")

    # 9. Log Summary
    console.print("[bold green]Pipeline Report Generated[/bold green]")
    console.print(f"  • JSON: {json_path}")
    console.print(f"  • Markdown: {md_path}")
    console.print(f"  • Sections: {stats['metrics'].get('total_sections', 0)}")
    console.print(f"  • Status: {verification['status']}")

    return json_path, final_report

def debug_bundle(bundle_path: Path, output_dir: Path):
    """Run report generator on a debug bundle."""
    if bundle_path.is_dir():
        run(bundle_path, output_dir)
    else:
        console.print("[red]Debug bundle for report generator must be a directory containing pipeline results[/red]")


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 14: Report Generator")
    parser.add_argument("--pipeline-dir", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=False, help="Source PDF for visual report")
    args = parser.parse_args()
    
    try:
        logger.info(f"Generating report for {args.pipeline_dir}...")
        out_path = run(args.pipeline_dir, args.pipeline_dir / "14_report_generator", args.pdf)
        if out_path and out_path.exists():
            logger.info(f"Report generated: {out_path}")
        else:
            logger.error("Report generation returned None or file missing")
            sys.exit(1)
    except Exception as e:
        logger.error(f"S14 execution failed: {e}")
        sys.exit(1)
