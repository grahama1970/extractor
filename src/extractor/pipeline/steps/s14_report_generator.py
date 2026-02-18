#!/usr/bin/env python3
"""
Stage 14: Report Generator
==========================

Generates a comprehensive report (JSON and Markdown) summarizing the entire pipeline run.

Refactored to be self-contained (merged from utils/report_runner.py).
"""

import sys
import json
import asyncio
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, date
from loguru import logger
from rich.console import Console
# Internal
from extractor.pipeline.utils.step_sanity import run_step_sanity

STEP_NAME = "14_report_generator"
console = Console(stderr=True)


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


def load_results(pipeline_dir: Path) -> Dict[str, Any]:
    """Load results from all pipeline stages (JSON artifacts)."""
    results = {}

    # Map stage output files (Upstream stages that still produce JSONs)
    stage_files = {
        "02_marker": "02_marker_extractor/json_output/02_marker_blocks.json",
        "03_verification": "03_suspicious_headers/json_output/03_verified_blocks.json",
        "04_sections": "04_section_builder/json_output/04_sections.json",
        "04a_audit": "04a_layout_audit/json_output/04a_layout_audit.json",
        "05_tables": "05_table_extractor/json_output/05_tables.json",
        "06_figures": "06_figure_extractor/json_output/06_figures.json",
        "00_profile": "00_profile_detector/profile.json",
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

    # Load from assembled_content.json
    json_path = pipeline_dir / "07_assembled" / "assembled_content.json"
    if json_path.exists():
        try:
            from extractor.pipeline.utils.content_query import ContentRepository
            repo = ContentRepository(json_path)

            results["db_stats"] = {
                "blocks": len(repo.blocks),
                "tables": len(repo.tables),
                "figures": len(repo.figures),
                "sections": len(repo.sections),
                "requirements": len(repo.requirements),
            }
        except Exception as e:
            logger.error(f"Failed to load stats from assembled content: {e}")
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

    # 4. Content Metrics (from assembled content)
    db = results.get("db_stats")
    if db:
        stats["metrics"]["total_blocks"] = db.get("blocks", 0)  # Update total blocks specifically
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

    # 5. Assessment Comparison (Stage 00 vs Reality)
    profile = results.get("00_profile")
    if profile:
        expected_tables = profile.get("elements", {}).get("table_pages", 0)
        actual_tables = stats["metrics"].get("total_tables", 0)
        expected_figures = profile.get("elements", {}).get("image_pages", 0)
        actual_figures = stats["metrics"].get("total_figures", 0)

        assessment = {
            "tables": {
                "expected_pages": expected_tables,
                "actual_count": actual_tables,
                "status": "OK",
            },
            "figures": {
                "expected_pages": expected_figures,
                "actual_count": actual_figures,
                "status": "OK",
            }
        }

        # Table heuristics
        if expected_tables > 0 and actual_tables == 0:
            assessment["tables"]["status"] = "MISSING"
            assessment["tables"]["reason"] = f"Expected tables (from {expected_tables} table pages) but found 0."
        elif expected_tables == 0 and actual_tables > 0:
            assessment["tables"]["status"] = "UNEXPECTED"
            assessment["tables"]["reason"] = f"Found {actual_tables} tables but S00 expected none."

        # Figure heuristics
        if expected_figures > 0 and actual_figures == 0:
            assessment["figures"]["status"] = "MISSING"
            assessment["figures"]["reason"] = f"Expected figures (from {expected_figures} image pages) but found 0."
        elif expected_figures == 0 and actual_figures > 0:
            assessment["figures"]["status"] = "UNEXPECTED"
            assessment["figures"]["reason"] = f"Found {actual_figures} figures but S00 expected none."

        # Sections
        expected_sections = profile.get("estimated_sections", 0)
        actual_sections = stats["metrics"].get("total_sections", 0)

        assessment["sections"] = {
            "expected": expected_sections,
            "actual": actual_sections,
            "status": "OK",
        }

        # Section Heuristics (Density check)
        if actual_sections > (expected_sections * 4) and actual_sections > 20:
             assessment["sections"]["status"] = "OVER_SEGMENTED"
             assessment["sections"]["reason"] = f"Found {actual_sections} sections, which is >4x the estimate ({expected_sections})."
        elif expected_sections > 5 and actual_sections < (expected_sections * 0.2):
             assessment["sections"]["status"] = "UNDER_SEGMENTED"
             assessment["sections"]["reason"] = f"Found only {actual_sections} sections, <20% of the estimate ({expected_sections})."

        # Overall quality signal
        overall_ok = (
            assessment["tables"]["status"] == "OK" 
            and assessment["figures"]["status"] == "OK"
            and assessment["sections"]["status"] == "OK"
        )
        stats["assessment_comparison"] = assessment
        stats["quality_signal"] = "REASONABLE" if overall_ok else "REVIEW_REQUIRED"

        # Special "UNKNOWN" prevention
        if stats["quality_signal"] == "REVIEW_REQUIRED":
            # Provide more details for debugging
            stats["review_reason"] = "; ".join([
                v.get("reason") for v in assessment.values() 
                if isinstance(v, dict) and v.get("status") != "OK" and v.get("reason")
            ])

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

                if isinstance(
                    o,
                    (
                        np.int_,
                        np.intc,
                        np.intp,
                        np.int8,
                        np.int16,
                        np.int32,
                        np.int64,
                        np.uint8,
                        np.uint16,
                        np.uint32,
                        np.uint64,
                    ),
                ):
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
    stats: Dict[str, Any],
    content_summary: Dict[str, Any],
    results: Dict[str, Any],
    toc_integrity: Optional[Dict[str, Any]] = None,
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
    
    # Assessment Comparison
    if stats.get("assessment_comparison"):
        comp = stats["assessment_comparison"]
        md.append("")
        md.append("### Assessment vs Reality (Stage 00 vs Final)")
        
        t_status = "✅" if comp["tables"]["status"] == "OK" else "❌"
        md.append(f"- {t_status} **Tables**: Expected (pages) ~{comp['tables']['expected_pages']}, Found {comp['tables']['actual_count']}")
        
        f_status = "✅" if comp["figures"]["status"] == "OK" else "❌"
        md.append(f"- {f_status} **Figures**: Expected (pages) ~{comp['figures']['expected_pages']}, Found {comp['figures']['actual_count']}")

    if stats["metrics"].get("suspicious_rate", 0) > 0.1:
        md.append(f"⚠️ **High Suspicion Rate**: {stats['metrics']['suspicious_rate']:.1%}")

    # TOC Integrity Section
    md.append("")
    md.append("## 4. Section Integrity (TOC Validation)")

    if toc_integrity and toc_integrity.get("has_toc"):
        score = toc_integrity.get("integrity_score", 0)
        matched = toc_integrity.get("matched", 0)
        total_toc = toc_integrity.get("toc_entry_count", 0)
        missing = toc_integrity.get("missing", [])
        extra = toc_integrity.get("extra", [])

        # Score emoji
        if score >= 0.9:
            status = "✅ EXCELLENT"
        elif score >= 0.7:
            status = "⚠️ GOOD"
        elif score >= 0.5:
            status = "⚠️ FAIR"
        else:
            status = "❌ POOR"

        md.append(f"- **Integrity Score**: {score:.0%} {status}")
        md.append(f"- **TOC Entries**: {total_toc}")
        md.append(f"- **Matched Sections**: {matched}/{total_toc}")

        if missing:
            md.append("")
            md.append("### Missing Sections (in TOC but not extracted)")
            for item in missing[:10]:  # Limit to first 10
                md.append(f"- ❌ {item['title']} (p. {item['page']})")
            if len(missing) > 10:
                md.append(f"- ... and {len(missing) - 10} more")

        if extra:
            md.append("")
            md.append("### Extra Sections (extracted but not in TOC)")
            for item in extra[:10]:  # Limit to first 10
                md.append(f"- ➕ {item['title']} (p. {item['page']})")
            if len(extra) > 10:
                md.append(f"- ... and {len(extra) - 10} more")
    else:
        md.append("- **No PDF outline/bookmarks found** - Cannot validate section integrity")
        md.append("- Note: Many PDFs don't have embedded outlines")

    return "\n".join(md)


def generate_toc_integrity_report(results: Dict[str, Any], pipeline_dir: Path) -> Dict[str, Any]:
    """Generate TOC vs Sections integrity report.

    Compares PDF outline/bookmarks against extracted sections to identify:
    - Missing sections (in TOC but not extracted)
    - Extra sections (extracted but not in TOC)
    - Mismatched nesting levels
    """
    from difflib import SequenceMatcher

    report = {
        "has_toc": False,
        "toc_entry_count": 0,
        "section_count": 0,
        "matched": 0,
        "missing": [],  # In TOC but not extracted
        "extra": [],    # Extracted but not in TOC
        "integrity_score": 1.0,
        "details": [],
    }

    # Get TOC entries from marker output
    marker_data = results.get("02_marker", {})
    toc_entries = marker_data.get("toc_entries", [])

    if not toc_entries:
        report["has_toc"] = False
        return report

    report["has_toc"] = True
    report["toc_entry_count"] = len(toc_entries)

    # Get sections from assembled_content.json
    sections = []
    json_path = pipeline_dir / "07_assembled" / "assembled_content.json"
    if json_path.exists():
        try:
            from extractor.pipeline.utils.content_query import ContentRepository
            repo = ContentRepository(json_path)
            sections = [
                {"id": s.get("id"), "title": s.get("title"), "page": s.get("page_start", 0)}
                for s in sorted(repo.sections, key=lambda s: (s.get("page_start") or 0, s.get("id", "")))
            ]
        except Exception as e:
            logger.warning(f"Failed to load sections from assembled content: {e}")

    if not sections and results.get("04_sections"):
        sections = [
            {"id": s.get("id"), "title": s.get("title"), "page": s.get("page_start", 0)}
            for s in results["04_sections"].get("sections", [])
        ]

    report["section_count"] = len(sections)

    if not sections:
        report["missing"] = [{"title": t["title"], "page": t["page"]} for t in toc_entries]
        report["integrity_score"] = 0.0
        return report

    # Match TOC entries to sections using title similarity
    def similarity(a: str, b: str) -> float:
        a_clean = " ".join(a.lower().split())
        b_clean = " ".join(b.lower().split())
        return SequenceMatcher(None, a_clean, b_clean).ratio()

    matched_sections = set()
    matched_toc = set()

    for toc_idx, toc in enumerate(toc_entries):
        toc_title = toc.get("title", "")
        toc_page = toc.get("page", 0)
        best_match = None
        best_score = 0.0

        for sec in sections:
            sec_title = sec.get("title", "")
            sec_page = sec.get("page", 0)

            # Title similarity
            title_sim = similarity(toc_title, sec_title)

            # Page proximity bonus (within 2 pages)
            page_bonus = 0.2 if abs(toc_page - sec_page) <= 2 else 0.0

            score = title_sim + page_bonus
            if score > best_score and sec["id"] not in matched_sections:
                best_score = score
                best_match = sec

        if best_match and best_score >= 0.6:
            matched_sections.add(best_match["id"])
            matched_toc.add(toc_idx)
            report["details"].append({
                "toc_title": toc_title,
                "section_title": best_match["title"],
                "confidence": round(best_score, 2),
                "status": "matched",
            })
        else:
            report["missing"].append({
                "title": toc_title,
                "page": toc_page,
                "best_candidate": best_match["title"] if best_match else None,
                "best_score": round(best_score, 2) if best_match else 0,
            })

    # Find extra sections (not in TOC)
    for sec in sections:
        if sec["id"] not in matched_sections:
            report["extra"].append({
                "title": sec["title"],
                "page": sec["page"],
            })

    report["matched"] = len(matched_sections)

    # Calculate integrity score
    if toc_entries:
        report["integrity_score"] = round(len(matched_sections) / len(toc_entries), 2)

    return report


def generate_verification_report(results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate detailed verification report with content quality checks."""
    report = {
        "status": "PASS",
        "issues": [],
        "warnings": [],
        "checks": {
            "structure_integrity": True,
            "content_completeness": True,
            "extraction_quality": True,
        },
    }

    # Check 1: Sections must exist
    if not results.get("04_sections"):
        report["status"] = "FAIL"
        report["issues"].append("Missing sections output")
        report["checks"]["structure_integrity"] = False

    # Check 2: Blocks must exist (0 blocks = extraction failure)
    total_blocks = results.get("db_stats", {}).get("blocks", 0)
    if total_blocks == 0:
        # Fallback to marker output if db extraction skipped
        if results.get("02_marker"):
            total_blocks = results["02_marker"].get("block_count", 0)

    if total_blocks == 0:
        report["status"] = "FAIL"
        report["issues"].append("Zero blocks extracted - likely Marker failure")
        report["checks"]["content_completeness"] = False

    # Check 3: Block type diversity (all Text = layout detection failure)
    block_types = results.get("02_marker", {}).get("block_type_distribution", {})
    if block_types and block_types.get("Text", 0) > 0:
        non_text = sum(v for k, v in block_types.items() if k != "Text")
        if non_text == 0 and total_blocks > 50:
            report["warnings"].append("All blocks are Text type - layout model may not be loaded")
            report["checks"]["extraction_quality"] = False

    # Check 4: Tables with generic headers
    if results.get("05_tables"):
        tables = results["05_tables"].get("tables", [])
        generic_header_count = 0
        for t in tables:
            # Check for pandas metric or inferred headers
            hdrs = t.get("pandas_metrics", {}).get("columns", [])
            # Also check if 'header_inferred' is missing and raw headers are generic
            if (
                not t.get("header_inferred")
                and hdrs
                and all(str(h).strip().isdigit() for h in hdrs)
            ):
                generic_header_count += 1

        if len(tables) > 0 and generic_header_count > len(tables) * 0.5:
            # If > 50% of tables have generic headers, that's a warning
            report["warnings"].append(
                f"{generic_header_count}/{len(tables)} tables have generic headers"
            )

    # Check 5: Figures for documents with images
    # We can't know for sure if a doc *should* have figures without VLM check,
    # but if 02_marker found Figure blocks and 06_figures found 0, that's a bug.
    marker_figures = block_types.get("Figure", 0) + block_types.get("Image", 0)

    start_figures = 0
    if results.get("06_figures"):
        start_figures = len(results["06_figures"].get("figures", []))

    if marker_figures > 0 and start_figures == 0:
        report["warnings"].append(
            f"Marker detected {marker_figures} potential figures but 0 extracted"
        )

    # Set status based on warnings
    if report["warnings"] and report["status"] == "PASS":
        report["status"] = "PASS_WITH_WARNINGS"

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
            if p not in sections_by_page:
                sections_by_page[p] = []
            sections_by_page[p].append(s)

    html_parts = [
        """
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
        <h1>Visual Extraction Report: """
        + pdf_path.name
        + """</h1>
        <div class="container">
    """
    ]

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

        html_parts.append(
            f"""
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
        """
        )

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
            generate_comprehensive_report(
                results_dir, output_dir or results_dir / "14_report_generator", source_pdf
            )
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

    # 4b. Generate TOC Integrity Report
    toc_integrity = generate_toc_integrity_report(results, pipeline_dir)

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
        "toc_integrity": toc_integrity,
    }

    # 6. Generate Markdown Representation
    markdown_report = generate_markdown_report(stats, content_summary, results, toc_integrity)

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
        console.print(
            "[red]Debug bundle for report generator must be a directory containing pipeline results[/red]"
        )


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
