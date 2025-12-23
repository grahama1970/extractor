"""Stage 14 report generator runner."""
import json
import os
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from loguru import logger
from rich.console import Console

# Internal
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    make_event,
    gpu_metrics_available,
)

console = Console(stderr=True)

def load_results(pipeline_dir: Path) -> Dict[str, Any]:
    """Load results from all pipeline stages."""
    results = {}

    # Map stage output files
    stage_files = {
        "02_marker": "02_marker_extractor/json_output/02_marker_blocks.json",
        "03_verification": "03_suspicious_headers/json_output/03_verified_blocks.json",
        "04_sections": "04_section_builder/json_output/04_sections.json",
        "04a_audit": "04a_layout_audit/json_output/04a_layout_audit.json",
        "05_tables": "05_table_extractor/json_output/05_tables.json",
        "06_figures": "06_figure_extractor/json_output/06_figures.json",
        "07_reflow": "07_reflow_section/json_output/07_reflowed.json",
        "07_requirements": "07_requirements_miner/json_output/07_requirements.json",
        "08_theorems": "08_lean4_theorem_prover/json_output/08_theorems.json",
        "09_summaries": "09_section_summarizer/json_output/09_summaries.json",
        "09a_annotator": "09a_pdf_annotator/json_output/annotations.json",
        "09b_audit": "09b_audit/json_output/09b_audit.json",
    }

    for key, rel_path in stage_files.items():
        try:
            path = pipeline_dir / rel_path
            if path.exists():
                text = path.read_text(encoding="utf-8")
                results[key] = json.loads(text)
            else:
                logger.warning(f"Results not found for {key}: {path}")
                results[key] = None
        except Exception as e:
            logger.error(f"Failed to load {key}: {e}")
            results[key] = None

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
        stats["metrics"]["avg_confidence"] = np.mean(
            [b.get("confidence", 0) for b in blocks if "confidence" in b] or [0]
        )

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

    # 4. Content Metrics (05 Tables, 06 Figures)
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
    from datetime import date, datetime
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
    # 05 tables
    if results.get("05_tables"):
        tabs = results["05_tables"].get("tables", [])
        lines.append(f"- **Tables Extracted**: {len(tabs)}")
        # breakdown by strategy if available
    # 06 figures
    if results.get("06_figures"):
        figs = results["06_figures"].get("figures", [])
        lines.append(f"- **Figures Extracted**: {len(figs)}")
    # 08 theorems
    if results.get("08_theorems"):
        thms = results["08_theorems"].get("all_theorems", [])
        proven = sum(1 for t in thms if t.get("status") == "proved")
        lines.append(f"- **Formal Theorems**: {len(thms)} (Proven: {proven})")
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

async def generate_comprehensive_report(
    pipeline_dir: Path, output_dir: Optional[Path] = None
) -> Tuple[Path, Dict[str, Any]]:
    """Generate comprehensive pipeline report."""

    # 1. Load all results
    results = load_results(pipeline_dir)

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
        },
        "statistics": stats,
        "content_summary": content_summary,
        "verification": verification,
    }

    # 6. Generate Markdown Representation
    markdown_report = generate_markdown_report(stats, content_summary, results)

    # 7. Save Outputs
    out_dir = output_dir or (pipeline_dir / "14_report_generator")
    json_dir = out_dir / "json_output"
    text_dir = out_dir / "text_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    json_path = json_dir / "final_report.json"
    md_path = text_dir / "report.md"

    json_path.write_text(_safe_json(final_report), encoding="utf-8")
    md_path.write_text(markdown_report, encoding="utf-8")

    # 8. Log Summary
    console.print("[bold green]Pipeline Report Generated[/bold green]")
    console.print(f"  • JSON: {json_path}")
    console.print(f"  • Markdown: {md_path}")
    console.print(f"  • Sections: {stats['metrics'].get('total_sections', 0)}")
    console.print(f"  • Status: {verification['status']}")

    return json_path, final_report

def run_report(results_dir: Path, output_dir: Optional[Path] = None) -> Tuple[Path, Dict[str, Any]]:
    """Synchronous entry point for report generation."""
    return asyncio.run(generate_comprehensive_report(results_dir, output_dir or results_dir / "14_report_generator"))

def debug_bundle(bundle_path: Path, output_dir: Path):
    """Run report generator on a debug bundle."""
    # For report generator, a bundle is essentially just the pipeline results directory
    # If bundle_path is a directory, use it.
    if bundle_path.is_dir():
        run_report(bundle_path, output_dir)
    else:
        console.print("[red]Debug bundle for report generator must be a directory containing pipeline results[/red]")
