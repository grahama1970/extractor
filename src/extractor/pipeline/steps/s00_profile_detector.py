#!/usr/bin/env python3
"""Stage-00: Profile Detector — fast PDF assessment via PyMuPDF.

Single-pass PDF analysis that detects domain, layout, structure, elements,
and preset match.  Two-pass table detection: cheap line-drawing scan on all
pages, then targeted find_tables() on candidate pages only.

Outputs: profile.json + pipeline_context.json
Failure: Falls back to analyze_fallback() on any PDF-level error
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, Any

from loguru import logger
from extractor.core.presets import COMPLEXITY_THRESHOLDS
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.utils.confidence_router import ConfidenceRouter

# Import from profile utility modules
from extractor.pipeline.utils.profile.toc import extract_toc, extract_toc_from_doc
from extractor.pipeline.utils.profile.timeout import estimate_timeout
from extractor.pipeline.utils.profile.sections import (
    detect_formulas,
    detect_section_style,
    detect_requirements,
    estimate_section_count,
    estimate_section_count_by_font,
    estimate_sections_from_font_data,
)
from extractor.pipeline.utils.profile.tables import (
    MIN_TABLE_LINES,
    LINE_TOLERANCE,
)
from extractor.pipeline.utils.profile.classifier import (
    ensure_torch,
    load_classifier_lazily,
    predict_with_classifier_images,
)
from extractor.pipeline.utils.profile.preset import match_preset

try:
    import pymupdf.layout  # GNN-based ML layout — must import BEFORE pymupdf4llm/fitz
except ImportError:
    logger.debug("pymupdf.layout not available, GNN-based ML layout disabled")

try:
    import fitz
    _HAVE_FITZ = True
except ImportError:
    _HAVE_FITZ = False

try:
    from pymupdf4llm.helpers.multi_column import column_boxes as _column_boxes
    _HAVE_COLUMN_BOXES = True
except ImportError:
    _HAVE_COLUMN_BOXES = False

from PIL import Image

STEP_NAME = "00_profile_detector"
_CONFIDENCE_ROUTER = ConfidenceRouter(threshold=0.9)


def analyze_with_pymupdf4llm(pdf_path: Path) -> Dict[str, Any]:
    """Comprehensive single-pass PDF analysis.

    Opens the PDF once and extracts everything downstream stages need:
    - Table detection via page.find_tables() (direct, not markdown regex)
    - Multi-column detection via pymupdf4llm column_boxes()
    - Image counting via page.get_images()
    - TOC via doc.get_toc() + text-based scan
    - Font-based section estimation (heading detection by font size/bold)
    - Table region estimation via line drawings
    - Full text for formula/requirement/section pattern detection
    - Classifier page images
    """
    if not _HAVE_FITZ:
        logger.warning("fitz not available, using fallback")
        return analyze_fallback(pdf_path)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.error(f"Failed to open PDF: {e}")
        return analyze_fallback(pdf_path)

    try:
        page_count = len(doc)

        # Per-page accumulators
        table_pages_direct = 0
        total_table_count = 0
        max_tables_per_page = 0
        image_pages = 0
        multi_col_pages = 0
        full_text = ""

        # Table region estimation (line drawings)
        drawing_table_regions = 0
        drawing_table_pages = 0
        drawing_max_per_page = 0
        drawing_density: list[tuple[int, int]] = []

        # Font analysis
        all_font_sizes: list[float] = []
        page_font_lines: list[list[dict]] = []

        caption_re = re.compile(
            r"^\s*(?:Table|Figure|Fig\.?|Listing|Algorithm|Exhibit)\s+\d",
            re.IGNORECASE,
        )
        section_number_re = re.compile(
            r"^\s*(?:"
            r"\d{1,2}(?:\.\d{1,3}){0,3}"
            r"|[A-Z](?:\.\d{1,3}){0,2}"
            r"|[IVXLC]{1,5}"
            r")\s+[A-Z]",
        )

        # Font sampling indices (spread evenly)
        font_sample_count = min(20, page_count)
        if font_sample_count >= page_count:
            font_sample_indices = set(range(page_count))
        else:
            step = page_count / font_sample_count
            font_sample_indices = {int(i * step) for i in range(font_sample_count)}

        # Classifier image collection
        classifier_images: list = []

        # Table detection budget
        TABLE_BUDGET_MAX = 50
        drawing_candidate_pages: set[int] = set()

        # Column sample indices
        COL_SAMPLE_MAX = 20
        if page_count <= COL_SAMPLE_MAX:
            col_sample_indices = set(range(page_count))
        else:
            col_sample_indices = set()
            step = page_count / COL_SAMPLE_MAX
            for i in range(COL_SAMPLE_MAX):
                col_sample_indices.add(int(i * step))

        # ══ PASS 1: Cheap signals on ALL pages (~2ms/page) ══
        for page_idx in range(page_count):
            page = doc[page_idx]

            # Multi-column detection (sampled)
            if _HAVE_COLUMN_BOXES and page_idx in col_sample_indices:
                try:
                    if len(_column_boxes(page)) > 1:
                        multi_col_pages += 1
                except Exception as e:
                    logger.debug(f"Column detection failed on page {page_idx}: {e}")

            # Image detection
            try:
                if page.get_images(full=False):
                    image_pages += 1
            except Exception as e:
                logger.debug(f"Image detection failed on page {page_idx}: {e}")

            # Text extraction
            page_text = page.get_text()
            full_text += page_text + "\n"

            # Table region estimation via line drawings
            _scan_page_drawings(
                page, page_idx,
                drawing_candidate_pages, drawing_density,
            )

            # Font data collection (sampled)
            if page_idx in font_sample_indices:
                _collect_font_data(page, all_font_sizes, page_font_lines)

            # Classifier images (first 3)
            if page_idx < 3 and ensure_torch():
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img = img.resize((224, 224))
                    classifier_images.append(img)
                except Exception as e:
                    logger.debug(f"Classifier image capture failed on page {page_idx}: {e}")

        # Tally drawing results
        for _, region_count in drawing_density:
            drawing_table_regions += region_count
            drawing_table_pages += 1
            drawing_max_per_page = max(drawing_max_per_page, region_count)

        # ══ PASS 2: Targeted find_tables() (~800ms/page) ══
        baseline_pages = {p for p in (0, 1, 2) if p < page_count}

        if drawing_candidate_pages:
            table_target_pages = drawing_candidate_pages | baseline_pages
        else:
            spread_count = min(TABLE_BUDGET_MAX, max(10, int(page_count ** 0.5)))
            step = page_count / spread_count
            spread_pages = {int(i * step) for i in range(spread_count)}
            table_target_pages = spread_pages | baseline_pages

        if len(table_target_pages) > TABLE_BUDGET_MAX:
            drawing_density.sort(key=lambda x: x[1], reverse=True)
            top_pages = {p for p, _ in drawing_density[:TABLE_BUDGET_MAX - 3]}
            table_target_pages = top_pages | baseline_pages

        table_sample_size = len(table_target_pages)
        for page_idx in sorted(table_target_pages):
            page = doc[page_idx]
            try:
                tabs = page.find_tables()
                n_tables = len(tabs.tables)
                if n_tables > 0:
                    table_pages_direct += 1
                    total_table_count += n_tables
                    max_tables_per_page = max(max_tables_per_page, n_tables)
            except Exception as e:
                logger.debug(f"find_tables() failed on page {page_idx}: {e}")

        # TOC extraction (from open doc)
        toc_info = extract_toc_from_doc(doc)
        doc.close()

        # Full-text analysis
        has_formulas = detect_formulas(full_text)
        has_requirements = detect_requirements(full_text)
        section_style = detect_section_style(full_text)
        section_estimate = estimate_section_count(full_text)

        # Font-based section estimation
        font_estimate = estimate_sections_from_font_data(
            all_font_sizes, page_font_lines, font_sample_count, page_count,
            caption_re, section_number_re,
        )

        toc_estimate = toc_info.get("entry_count", 0)
        drawing_density.sort(key=lambda x: x[1], reverse=True)

        # Extrapolate table counts
        if table_sample_size < page_count and table_pages_direct > 0:
            sample_ratio = page_count / table_sample_size
            extrapolated_table_pages = int(table_pages_direct * sample_ratio)
            extrapolated_table_count = int(total_table_count * sample_ratio)
        else:
            extrapolated_table_pages = table_pages_direct
            extrapolated_table_count = total_table_count

        # Table style classification
        has_bordered = drawing_table_pages > 0
        has_borderless = table_pages_direct > drawing_table_pages
        if has_bordered and has_borderless:
            table_style = "mixed"
        elif has_borderless:
            table_style = "borderless"
        elif has_bordered:
            table_style = "bordered"
        else:
            table_style = "none"

        # Extrapolate multi-column
        col_sample_size = len(col_sample_indices)
        if col_sample_size < page_count and multi_col_pages > 0:
            extrapolated_col_pages = int(multi_col_pages * (page_count / col_sample_size))
        else:
            extrapolated_col_pages = multi_col_pages

        return {
            "page_count": page_count,
            "has_tables": table_pages_direct > 0 or drawing_table_pages > 0,
            "table_pages": extrapolated_table_pages,
            "total_table_count": extrapolated_table_count,
            "has_images": image_pages > 0,
            "image_pages": image_pages,
            "has_multi_column": extrapolated_col_pages > page_count * 0.3,
            "multi_col_pages": extrapolated_col_pages,
            "has_formulas": has_formulas,
            "has_requirements": has_requirements,
            "section_style": section_style,
            "section_estimate": section_estimate,
            "font_section_estimate": font_estimate,
            "toc_section_estimate": toc_estimate,
            "toc_info": toc_info,
            "has_toc": toc_info.get("has_toc", False),
            "full_text_sample": full_text[:2000],
            "table_regions": {
                "estimated_table_count": drawing_table_regions,
                "table_pages_drawing": drawing_table_pages,
                "table_density_top10": drawing_density[:10],
                "max_tables_per_page": drawing_max_per_page,
            },
            "table_style": table_style,
            "_classifier_images": classifier_images,
        }

    except Exception as e:
        logger.error(f"pymupdf4llm analysis failed: {e}")
        try:
            doc.close()
        except Exception as e:
            logger.debug(f"Failed to close PDF document: {e}")
        return analyze_fallback(pdf_path)


def _scan_page_drawings(
    page: Any,
    page_idx: int,
    candidate_pages: set,
    density: list,
) -> None:
    """Scan a page's line drawings for table grid patterns.

    Populates candidate_pages and density in-place.
    """
    try:
        drawings = page.get_drawings()
        h_lines: list[tuple[float, float, float]] = []
        v_lines: list[tuple[float, float, float]] = []
        for d in drawings:
            for item in d.get("items", []):
                if item[0] == "l":
                    p1, p2 = item[1], item[2]
                    dx = abs(p1.x - p2.x)
                    dy = abs(p1.y - p2.y)
                    if dy < LINE_TOLERANCE and dx > 10:
                        h_lines.append((min(p1.y, p2.y), min(p1.x, p2.x), max(p1.x, p2.x)))
                    elif dx < LINE_TOLERANCE and dy > 10:
                        v_lines.append((min(p1.x, p2.x), min(p1.y, p2.y), max(p1.y, p2.y)))

        if len(h_lines) < MIN_TABLE_LINES or len(v_lines) < 2:
            return

        # Validate table-like grid (not flowchart)
        h_widths = [x2 - x1 for _, x1, x2 in h_lines]
        page_width = page.rect.width

        if h_widths and page_width > 0:
            if max(h_widths) < page_width * 0.25:
                return
            if len(h_widths) > 1:
                mean_w = sum(h_widths) / len(h_widths)
                if mean_w > 0:
                    std_w = (sum((w - mean_w) ** 2 for w in h_widths) / len(h_widths)) ** 0.5
                    if std_w / mean_w > 0.6:
                        return

        # Vertical line column structure check
        if len(v_lines) >= 2:
            v_xs = sorted(x for x, _, _ in v_lines)
            x_clusters: list[tuple[float, int]] = []
            for x in v_xs:
                matched = False
                for i, (cx, count) in enumerate(x_clusters):
                    if abs(x - cx) < 5.0:
                        x_clusters[i] = ((cx * count + x) / (count + 1), count + 1)
                        matched = True
                        break
                if not matched:
                    x_clusters.append((x, 1))
            if len(x_clusters) > 20:
                return
            if sum(1 for _, c in x_clusters if c >= 2) < 2:
                return

        h_ys = sorted(set(round(y, 0) for y, _, _ in h_lines))
        if not h_ys:
            return

        region_count = 1
        for i in range(1, len(h_ys)):
            if h_ys[i] - h_ys[i - 1] > 30:
                region_count += 1

        candidate_pages.add(page_idx)
        density.append((page_idx, region_count))
    except Exception as e:
        logger.debug(f"Drawing scan failed on page {page_idx}: {e}")


def _collect_font_data(
    page: Any,
    all_sizes: list,
    page_lines: list,
) -> None:
    """Collect font size and line data from a page for section estimation."""
    try:
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        lines_on_page: list[dict] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                for span in spans:
                    sz = span.get("size", 0)
                    txt = span.get("text", "").strip()
                    if sz > 0 and len(txt) > 0:
                        all_sizes.append(sz)
                first_span = spans[0]
                line_text = "".join(s.get("text", "") for s in spans).strip()
                lines_on_page.append({
                    "text": line_text,
                    "size": first_span.get("size", 0),
                    "flags": first_span.get("flags", 0),
                })
        page_lines.append(lines_on_page)
    except Exception as e:
        logger.debug(f"Font data collection failed: {e}")


def analyze_fallback(pdf_path: Path) -> Dict[str, Any]:
    """Fallback analysis using raw PyMuPDF (fitz)."""
    try:
        import fitz as _fitz
    except ImportError:
        return {"error": "PyMuPDF not available"}

    try:
        doc = _fitz.open(pdf_path)
        page_count = len(doc)

        text = ""
        for i in range(min(3, page_count)):
            text += doc[i].get_text() + "\n"

        return {
            "page_count": page_count,
            "has_tables": False,
            "has_images": len(doc[0].get_images()) > 0 if page_count > 0 else False,
            "has_multi_column": False,
            "has_formulas": detect_formulas(text),
            "has_requirements": detect_requirements(text),
            "section_style": detect_section_style(text),
            "full_text_sample": text[:2000],
            "fallback": True,
        }
    except Exception as e:
        return {"error": str(e)}


def infer_domain(analysis: Dict, filename: str) -> str:
    """Infer document domain from features and filename."""
    fname = filename.lower()

    if any(t in fname for t in ["arxiv", "paper", "journal", "proceedings"]):
        return "scientific"
    if any(t in fname for t in ["spec", "requirement", "bht", "boeing", "std"]):
        return "engineering"
    if any(t in fname for t in ["contract", "agreement", "legal"]):
        return "legal"

    if analysis.get("has_formulas") and analysis.get("has_multi_column"):
        return "scientific"
    if analysis.get("has_requirements"):
        return "engineering"
    if analysis.get("section_style") == "decimal" and not analysis.get("has_formulas"):
        return "engineering"
    if analysis.get("section_style") == "chapter":
        return "book"

    return "general"


def compute_route(analysis: Dict) -> Dict[str, Any]:
    """Compute complexity score and route recommendation."""
    th = COMPLEXITY_THRESHOLDS
    score = 0
    hits: list[str] = []

    if analysis.get("has_multi_column"):
        score += 1
        hits.append("multi_column")
    if analysis.get("has_tables"):
        score += 1
        hits.append("has_tables")
    if analysis.get("has_formulas"):
        score += 2
        hits.append("has_formulas")
    if analysis.get("page_count", 0) >= th.get("page_count", 50):
        hits.append("high_page_count")

    route = "accurate" if score >= th.get("min_complexity", 2) else "fast"

    return {"route": route, "complexity_score": score, "thresholds_hit": hits}


def _build_hierarchy(analysis: Dict) -> Dict[str, Any]:
    """Build hierarchy dict from regex and font-based section estimates."""
    regex_count = analysis.get("section_estimate", {}).get("estimated_count", 0)
    font_info = analysis.get("font_section_estimate", {})
    font_count = font_info.get("estimated_count", 0)
    toc_count = analysis.get("toc_section_estimate", 0)

    if toc_count > 0:
        combined = toc_count
    elif regex_count > 0 and font_count > 0:
        # When regex and font diverge heavily (>3x), regex is likely counting
        # inline references/equations as sections. Use the geometric mean to
        # dampen outliers instead of blindly taking max.
        ratio = max(regex_count, font_count) / min(regex_count, font_count)
        if ratio > 3.0:
            combined = int((regex_count * font_count) ** 0.5)
        else:
            combined = max(regex_count, font_count)
    else:
        combined = max(regex_count, font_count)

    return {
        "section_style": analysis.get("section_style"),
        "has_structure": analysis.get("section_style") is not None,
        "estimated_sections": combined,
        "estimated_sections_regex": regex_count,
        "estimated_sections_font": font_count,
        "estimated_sections_toc": toc_count,
        "font_body_size": font_info.get("body_font_size", 0),
        "section_breakdown": analysis.get("section_estimate", {}).get("by_pattern", {}),
    }


def detect_preset(pdf_path: Path, verbose_preset: bool = False) -> Dict[str, Any]:
    """Main entry point: produce comprehensive profile for PDF."""
    if not pdf_path.exists():
        return {"error": "File not found"}

    file_size_bytes = pdf_path.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)

    analysis = analyze_with_pymupdf4llm(pdf_path)
    if "error" in analysis:
        return analysis

    domain = infer_domain(analysis, pdf_path.name)
    route_info = compute_route(analysis)
    preset_info = match_preset(analysis, pdf_path.name, domain, verbose=verbose_preset)
    heuristic_preset = preset_info.get("matched")

    # Classifier prediction (shadow mode)
    classifier_model = load_classifier_lazily()
    routing_info: dict = {}

    if classifier_model:
        t_cls = time.monotonic()
        try:
            classifier_images = analysis.pop("_classifier_images", [])
            pred_label, pred_conf = predict_with_classifier_images(
                classifier_images, analysis,
            )
            duration_ms = int((time.monotonic() - t_cls) * 1000)

            final_label, source, metadata = _CONFIDENCE_ROUTER.route(
                ml_result=pred_label,
                ml_confidence=float(pred_conf),
                heuristic_result=heuristic_preset,
            )

            routing_info = {
                "classifier_result": pred_label,
                "classifier_confidence": round(float(pred_conf), 3),
                "heuristic_result": heuristic_preset,
                "selected_source": source,
                "final_label": final_label,
                "routing_metadata": metadata,
                "inference_ms": duration_ms,
            }

            if pred_label:
                match_status = "MATCH" if pred_label == heuristic_preset else "MISMATCH"
                log_level = "INFO" if match_status == "MATCH" else "WARNING"
                logger.log(
                    log_level,
                    f"[Shadow Mode] {match_status} | Classifier: {pred_label} "
                    f"({pred_conf:.2f}) | Heuristic: {heuristic_preset}",
                )
        except Exception as e:
            logger.error(f"Classifier prediction failed: {e}")
    else:
        analysis.pop("_classifier_images", None)

    # Table estimation
    table_est = analysis.get("table_regions", {})
    estimated_table_count = (
        analysis.get("total_table_count", 0)
        or table_est.get("estimated_table_count", 0)
    )

    toc_info = analysis.get("toc_info", {})

    # Timeout estimation
    page_count = analysis.get("page_count", 0)
    table_pages = analysis.get("table_pages", 0)
    image_pages = analysis.get("image_pages", 0)
    has_formulas = analysis.get("has_formulas", False)
    has_requirements = analysis.get("has_requirements", False)

    hierarchy_info = _build_hierarchy(analysis)
    estimated_sections = hierarchy_info.get("estimated_sections", 0)

    estimated_timeout, timeout_source = estimate_timeout(
        page_count=page_count,
        file_size_mb=file_size_mb,
        table_pages=table_pages,
        estimated_table_count=estimated_table_count,
        image_pages=image_pages,
        has_formulas=has_formulas,
        has_requirements=has_requirements,
        domain=domain,
        estimated_sections=estimated_sections,
    )

    # Build profile
    profile = {
        "domain": domain,
        "page_count": page_count,
        "file_size_mb": round(file_size_mb, 2),
        "estimated_timeout_seconds": estimated_timeout,
        "timeout_source": timeout_source,
        "layout": {
            "columns": 2 if analysis.get("has_multi_column") else 1,
            "style": "double" if analysis.get("has_multi_column") else "single",
        },
        "hierarchy": hierarchy_info,
        "elements": {
            "tables": analysis.get("has_tables", False) or estimated_table_count > 0,
            "table_pages": table_pages,
            "estimated_table_count": estimated_table_count,
            "max_tables_per_page": max(
                analysis.get("total_table_count", 0) and table_est.get("max_tables_per_page", 0),
                table_est.get("max_tables_per_page", 0),
            ),
            "table_pages_drawing": table_est.get("table_pages_drawing", 0),
            "table_density_top10": table_est.get("table_density_top10", []),
            "figures": analysis.get("has_images", False),
            "image_pages": image_pages,
            "formulas": has_formulas,
            "requirements": has_requirements,
        },
        "preset_match": preset_info,
        "toc": toc_info,
        **route_info,
        "detected_preset": preset_info.get("matched"),
        "classifier": routing_info,
        "table_style": analysis.get("table_style", "none"),
        "has_multi_column": analysis.get("has_multi_column", False),
    }

    return profile


def run(pdf_path: Path, output_dir: Path, verbose_preset: bool = False) -> Path:
    """Run Step 00."""
    t0 = time.monotonic()

    stage_dir = output_dir / STEP_NAME
    stage_dir.mkdir(parents=True, exist_ok=True)

    logger.add(stage_dir / "stage_00.log")
    logger.info(f"Profiling {pdf_path.name} with pymupdf4llm...")

    result = detect_preset(pdf_path, verbose_preset=verbose_preset)
    result["file"] = str(pdf_path)
    result["timestamp"] = time.time()
    result["duration_ms"] = int((time.monotonic() - t0) * 1000)

    out_file = stage_dir / "profile.json"
    out_file.write_text(json.dumps(result, indent=2))

    # Write pipeline_context.json
    context_file = output_dir / "pipeline_context.json"
    context: dict = {}
    if context_file.exists():
        try:
            context = json.loads(context_file.read_text())
        except Exception as e:
            logger.warning(f"Failed to read existing pipeline_context.json: {e}")
    elements = result.get("elements", {})
    toc_info = result.get("toc", {})
    context.update({
        "estimated_timeout_seconds": result.get("estimated_timeout_seconds", 600),
        "page_count": result.get("page_count", 0),
        "file_size_mb": result.get("file_size_mb", 0),
        "table_pages": elements.get("table_pages", 0),
        "estimated_table_count": elements.get("estimated_table_count", 0),
        "max_tables_per_page": elements.get("max_tables_per_page", 0),
        "image_pages": elements.get("image_pages", 0),
        "table_style": result.get("table_style", "none"),
        "domain": result.get("domain", "general"),
        "has_multi_column": elements.get("multi_column", False),
        "has_formulas": elements.get("formulas", False),
        "has_toc": toc_info.get("has_toc", False),
        "toc_entry_count": toc_info.get("entry_count", 0),
        "toc_max_depth": toc_info.get("max_depth", 0),
        "toc_entries": toc_info.get("entries", []),
    })
    context_file.write_text(json.dumps(context, indent=2))

    # Log summary
    logger.info(
        f"Domain: {result.get('domain')} | Pages: {result.get('page_count')} "
        f"| Size: {result.get('file_size_mb', 0):.1f}MB"
    )
    logger.info(
        f"Estimated timeout: {result.get('estimated_timeout_seconds', 600)}s "
        f"({result.get('estimated_timeout_seconds', 600) // 60} min)"
    )
    logger.info(
        f"Elements: Tables={elements.get('tables')}, "
        f"EstimatedTableCount={elements.get('estimated_table_count', 0)}, "
        f"MaxTablesPerPage={elements.get('max_tables_per_page', 0)}, "
        f"Formulas={elements.get('formulas')}, "
        f"Requirements={elements.get('requirements')}"
    )
    hierarchy = result.get('hierarchy', {})
    section_count = hierarchy.get('estimated_sections', 0)
    if section_count > 0:
        logger.info(
            f"Estimated sections: {section_count} "
            f"(regex={hierarchy.get('estimated_sections_regex', 0)}, "
            f"font={hierarchy.get('estimated_sections_font', 0)})"
        )
    logger.info(f"Preset: {result.get('detected_preset')} | Route: {result.get('route')}")
    if result.get("preset_match", {}).get("errors"):
        logger.info(f"Anticipated Errors: {result['preset_match']['errors']}")
    if toc_info.get("has_toc"):
        logger.info(
            f"TOC: {toc_info.get('entry_count', 0)} entries, "
            f"depth={toc_info.get('max_depth', 0)}"
        )

    if verbose_preset and "preset_match" in result:
        _print_preset_summary(result["preset_match"], pdf_path.name)

    return out_file


def _print_preset_summary(pm: dict, filename: str) -> None:
    """Print verbose preset detection summary to stdout."""
    print(f"\n{'=' * 60}\nPRESET DETECTION SUMMARY\n{'=' * 60}")
    print(f"Filename: {filename}\n\nMatching Scores:")
    selected = pm.get("matched")
    for name, score in sorted(pm.get("all_scores", {}).items(), key=lambda x: -x[1]):
        print(f"  {name}: {score}{' (SELECTED)' if name == selected else ''}")
        if "match_details" in pm:
            d = pm["match_details"].get(name, {})
            if d.get("keyword_matches"):
                print(f"    - Keywords: {', '.join(m['keyword'] for m in d['keyword_matches'][:5])}")
            if d.get("filename_triggers"):
                print(f"    - Filename triggers: {', '.join(d['filename_triggers'])}")
            if d.get("layout_match"):
                print(f"    - Layout: {d['layout_match']}")
            if d.get("section_pattern_match"):
                print("    - Section pattern matched (+4)")
            if d.get("domain_boost"):
                print("    - Domain category matched (+5)")
    if "selection_reason" in pm:
        print(f"\nSelection Reason: {pm['selection_reason']}")
    print("=" * 60)


def sanity() -> int:
    """Run sanity check for this step."""
    return run_step_sanity(STEP_NAME)


if __name__ == "__main__":
    import typer

    def main(
        pdf: Path = typer.Argument(..., help="Path to PDF file"),
        out: Path = typer.Option(Path("data/results/pipeline"), "-o", "--out"),
        verbose_preset: bool = typer.Option(False, "--verbose-preset", help="Show detailed preset selection explanation"),
    ) -> None:
        run(pdf, out, verbose_preset=verbose_preset)

    typer.run(main)
