#!/usr/bin/env python3
"""
Stage-00: Profile Detector
--------------------------
Fast PDF assessment using pymupdf4llm with page_chunks=True.

Detects:
1. Domain (scientific, engineering, legal, general)
2. Page count
3. Layout (single/double column)
4. Structure (section numbering style)
5. Elements (tables, figures, formulas, requirements)
6. Preset match recommendation

Pattern adapted from distill skill's pdf_preflight().
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger
from extractor.core.presets import PRESET_REGISTRY, COMPLEXITY_THRESHOLDS

STEP_NAME = "00_profile_detector"

# Formula/equation detection patterns
FORMULA_PATTERNS = [
    r"\$\$.+?\$\$",           # Display math $$...$$
    r"\$[^$]+\$",             # Inline math $...$
    r"\\begin\{equation\}",   # LaTeX equation environment
    r"\\frac\{",              # Fractions
    r"\\sum|\\int|\\prod",    # Operators
    r"\\alpha|\\beta|\\gamma|\\theta|\\pi",  # Greek letters
    r"[∑∫∂√∞±×÷≤≥≠≈]",        # Unicode math symbols
]

# Section style patterns (from distill)
SECTION_PATTERNS = {
    "decimal": r"^\d+\.\d+",           # 1.1, 2.3.1
    "roman": r"^[IVXLCDM]+\.",         # I. II. III.
    "chapter": r"^Chapter\s+\d+",      # Chapter 1
    "markdown": r"^#{1,6}\s+",         # ## Header
}

# Requirement patterns
REQUIREMENT_PATTERNS = [
    r"REQ-\d+",
    r"\bSHALL\b",
    r"\bMUST\b",
    r"\bSHOULD\b",
]


def detect_formulas(text: str) -> bool:
    """Check for LaTeX or math formulas in text."""
    for pat in FORMULA_PATTERNS:
        if re.search(pat, text, re.MULTILINE | re.DOTALL):
            return True
    return False


def detect_section_style(text: str) -> Optional[str]:
    """Detect section numbering style."""
    for style, pat in SECTION_PATTERNS.items():
        if re.search(pat, text, re.MULTILINE | re.IGNORECASE):
            return style
    return None


def detect_requirements(text: str) -> bool:
    """Check for requirement patterns."""
    for pat in REQUIREMENT_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def analyze_with_pymupdf4llm(pdf_path: Path) -> Dict[str, Any]:
    """Analyze PDF using pymupdf4llm with page_chunks=True.
    
    This gives us rich metadata without loading heavy ML models.
    """
    try:
        import pymupdf4llm
    except ImportError:
        logger.warning("pymupdf4llm not available, using fallback")
        return analyze_fallback(pdf_path)
    
    try:
        # Get page-level metadata (fast, no ML)
        pages = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
        
        if not isinstance(pages, list):
            return {"error": "Unexpected pymupdf4llm output format"}
        
        page_count = len(pages)
        
        # Aggregate detection across pages
        table_pages = 0
        image_pages = 0
        multi_col_pages = 0
        has_formulas = False
        has_requirements = False
        section_style = None
        
        full_text = ""
        
        for page in pages:
            if isinstance(page, dict):
                md = page.get("text", "") or page.get("md", "")
            else:
                md = str(page)
            
            full_text += md + "\n"
            
            # Table detection (markdown table syntax)
            if "|" in md and "---" in md:
                table_pages += 1
            
            # Image detection
            if "![" in md or "<img" in md.lower():
                image_pages += 1
            
            # Multi-column heuristic (many short lines)
            lines = md.split("\n")
            non_empty = [l for l in lines if l.strip()]
            if non_empty:
                short_lines = sum(1 for l in non_empty if 10 < len(l.strip()) < 45)
                if short_lines > len(non_empty) * 0.4:
                    multi_col_pages += 1
        
        # Full-text analysis
        has_formulas = detect_formulas(full_text)
        has_requirements = detect_requirements(full_text)
        section_style = detect_section_style(full_text)
        
        return {
            "page_count": page_count,
            "has_tables": table_pages > 0,
            "table_pages": table_pages,
            "has_images": image_pages > 0,
            "image_pages": image_pages,
            "has_multi_column": multi_col_pages > page_count * 0.3,
            "multi_col_pages": multi_col_pages,
            "has_formulas": has_formulas,
            "has_requirements": has_requirements,
            "section_style": section_style,
            "full_text_sample": full_text[:2000],  # For preset matching
        }
        
    except Exception as e:
        logger.error(f"pymupdf4llm analysis failed: {e}")
        return analyze_fallback(pdf_path)


def analyze_fallback(pdf_path: Path) -> Dict[str, Any]:
    """Fallback analysis using raw PyMuPDF (fitz)."""
    try:
        import fitz
    except ImportError:
        return {"error": "PyMuPDF not available"}
    
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        
        text = ""
        for i in range(min(3, page_count)):
            text += doc[i].get_text() + "\n"
        
        return {
            "page_count": page_count,
            "has_tables": False,  # Can't detect easily
            "has_images": len(doc[0].get_images()) > 0 if page_count > 0 else False,
            "has_multi_column": False,  # Can't detect easily
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
    
    # Filename hints
    if any(t in fname for t in ["arxiv", "paper", "journal", "proceedings"]):
        return "scientific"
    if any(t in fname for t in ["spec", "requirement", "bht", "boeing", "std"]):
        return "engineering"
    if any(t in fname for t in ["contract", "agreement", "legal"]):
        return "legal"
    
    # Feature-based inference
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
    hits = []
    
    if analysis.get("has_multi_column"):
        score += 1
        hits.append("multi_column")
    
    if analysis.get("has_tables"):
        score += 1
        hits.append("has_tables")
    
    if analysis.get("has_formulas"):
        score += 2  # Formulas are high-value for accurate mode
        hits.append("has_formulas")
    
    if analysis.get("page_count", 0) >= th.get("page_count", 50):
        hits.append("high_page_count")
    
    min_complexity = th.get("min_complexity", 2)
    route = "accurate" if score >= min_complexity else "fast"
    
    return {
        "route": route,
        "complexity_score": score,
        "thresholds_hit": hits,
    }


def match_preset(analysis: Dict, filename: str, detected_domain: str = None) -> Dict[str, Any]:
    """Match PDF against preset registry."""
    text = analysis.get("full_text_sample", "")
    
    best_score = 0
    best_preset = None
    scores = {}
    
    for name, config in PRESET_REGISTRY.items():
        detection = config.get("detection", {})
        if not detection:
            continue
        
        score = 0
        
        # Keywords
        for kw in detection.get("keywords", []):
            if kw.lower() in text.lower():
                score += 1
        
        # Layout match
        preset_layout = detection.get("layout")
        if preset_layout == "double" and analysis.get("has_multi_column"):
            score += 3
        elif preset_layout == "single" and not analysis.get("has_multi_column"):
            score += 2
        
        # Section pattern
        pat = detection.get("section_pattern")
        if pat and re.search(pat, text, re.MULTILINE):
            score += 4
        
        # Filename triggers
        for t in detection.get("filename_triggers", []):
            if t in filename.lower():
                score += 5
        
        # Domain Boost
        if detected_domain and config.get("category", "").lower() == detected_domain.lower():
            score += 5
        
        scores[name] = score
        if score >= detection.get("min_score", 1) and score > best_score:
            best_score = score
            best_preset = name
    
    return {
        "matched": best_preset,
        "confidence": best_score,
        "all_scores": scores,
        "needs_new_preset": best_preset is None,
    }


def detect_preset(pdf_path: Path) -> Dict[str, Any]:
    """Main entry point: Produce comprehensive profile for PDF."""
    if not pdf_path.exists():
        return {"error": "File not found"}
    
    # 1. Analyze with pymupdf4llm
    analysis = analyze_with_pymupdf4llm(pdf_path)
    
    if "error" in analysis:
        return analysis
    
    # 2. Infer domain
    domain = infer_domain(analysis, pdf_path.name)
    
    # 3. Compute route
    route_info = compute_route(analysis)
    
    # 4. Match preset
    preset_info = match_preset(analysis, pdf_path.name, domain)
    
    # 5. Build profile
    profile = {
        # Domain
        "domain": domain,
        
        # Page count
        "page_count": analysis.get("page_count", 0),
        
        # Layout
        "layout": {
            "columns": 2 if analysis.get("has_multi_column") else 1,
            "style": "double" if analysis.get("has_multi_column") else "single",
        },
        
        # Hierarchy
        "hierarchy": {
            "section_style": analysis.get("section_style"),
            "has_structure": analysis.get("section_style") is not None,
        },
        
        # Elements
        "elements": {
            "tables": analysis.get("has_tables", False),
            "figures": analysis.get("has_images", False),
            "formulas": analysis.get("has_formulas", False),
            "requirements": analysis.get("has_requirements", False),
        },
        
        # Preset match
        "preset_match": preset_info,
        
        # Routing
        **route_info,
        
        # For CLI display
        "detected_preset": preset_info.get("matched"),
    }
    
    return profile


def run(pdf_path: Path, output_dir: Path) -> Path:
    """Run Step 00."""
    t0 = time.monotonic()
    
    stage_dir = output_dir / STEP_NAME
    stage_dir.mkdir(parents=True, exist_ok=True)
    
    logger.add(stage_dir / "stage_00.log")
    logger.info(f"Profiling {pdf_path.name} with pymupdf4llm...")
    
    # Execute Detection
    result = detect_preset(pdf_path)
    result["file"] = str(pdf_path)
    result["timestamp"] = time.time()
    result["duration_ms"] = int((time.monotonic() - t0) * 1000)
    
    out_file = stage_dir / "profile.json"
    out_file.write_text(json.dumps(result, indent=2))
    
    # Log summary
    logger.info(f"Domain: {result.get('domain')} | Pages: {result.get('page_count')}")
    logger.info(f"Elements: Tables={result.get('elements', {}).get('tables')}, "
                f"Formulas={result.get('elements', {}).get('formulas')}, "
                f"Requirements={result.get('elements', {}).get('requirements')}")
    logger.info(f"Preset: {result.get('detected_preset')} | Route: {result.get('route')}")
    
    return out_file


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Step 00: Profile Detector")
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument("-o", "--out", type=Path, default=Path("data/results/pipeline"))
    args = parser.parse_args()
    
    run(args.pdf, args.out)
