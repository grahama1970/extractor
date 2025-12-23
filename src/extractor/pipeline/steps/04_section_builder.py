#!/usr/bin/env python3
"""
Stage-04: Section Builder — Build sections from verified blocks

Purpose:
- Build a section hierarchy from Stage 03 verified blocks.
- Validate headers with deterministic heuristics (font, numbering, context).
- Optionally capture visuals for each section from the clean PDF.

How hierarchy is built (read before editing):
- Pick header blocks (trust Stage 03; optionally uplift with light heuristics).
- Parse numbering/title spans -> derive section_number and depth list.
- Link parents by stripping the last number component (e.g., 4.1.5.4.1 → parent 4.1.5.4) and preserving document order.
- Assign IDs, section_hash (MD5 of title), breadcrumbs and breadcrumb_titles; copy breadcrumbs onto each block in the section.
- Normalize titles (number stripped) and keep header metadata (font/size/color if available).
- Optional: enrich header color from the clean PDF; optional header snapshots when enabled.

Inputs/Outputs:
- Input JSON: Stage 03 output (verified blocks), flat or pages[].blocks[].
- Clean PDF: Cleaned file from Stage 01 (for visuals).
from extractor.pipeline.utils.sections.runner import run
- Outputs under data/results/pipeline/04_section_builder/:
  - json_output/04_sections.json
  - image_output/section_*.png (optional visuals)

CLI:
- Run: python -m extractor.pipeline.steps.04_section_builder run <verified_json> --pdf-dir <dir-with-*_clean.pdf> -o <results-root>
- Debug-bundle: python -m extractor.pipeline.steps.04_section_builder debug-bundle /path/to/bundle.json -o <results-root>
  Bundle keys: {"verified_blocks": {...}, "clean_pdf": "/abs/path/to/*_clean.pdf"}

Notes:
- No import-time side effects; logging configured per run.
- File layout and CLI style mirror previous steps.
"""

import os
import sys
import json
import asyncio
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import base64

# Third-party
from loguru import logger
from rich.console import Console
from extractor.pipeline.utils.section_builder_utils import (
    pdf_analyze_section_numbering as _pdf_analyze_numbering,
)
# Import from new utils/sections package (primary section parsing functions)
from extractor.pipeline.utils.sections import (
    SECTION_NUMBER_PATTERNS,
    normalize_section_number,
    coerce_depth,
    derive_parent_number,
    analyze_section_numbering,
    derive_section_depth,
    extract_section_title,
    clean_section_title,
    detect_header_level,
    looks_like_header_text,
)
# Keep sbul for helpers not yet in utils/sections
import extractor.pipeline.utils.section_builder_utils_local as sbul
from extractor.pipeline.utils.section_builder_utils_local import (
    normalize_breadcrumbs,
    breadcrumb_label,
    enrich_header_colors,
    prepare_section_hierarchy,
)
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    make_event,
    snapshot_resources,
    build_stage_timings,
    get_run_id,
    gpu_metrics_available,
)
from extractor.pipeline.utils.step_sanity import run_step_sanity

# (removed unused report utils import)

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Stage 04 requires it.", file=sys.stderr)
    raise

# Initialize (console for printing). CLI factory provided below.
console = Console()
STEP_NAME = "04_section_builder"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)

# (env/log configured in CLI)

# Visuals
MAX_VISUAL_PAGES_DEFAULT = int(os.getenv("MAX_VISUAL_PAGES", "2"))
STAGE04_VISUAL_PROOF = os.getenv("STAGE04_VISUAL_PROOF", "").lower() in {"1", "true", "yes", "y"}
STAGE04_SOURCE_PDF = os.getenv("STAGE04_SOURCE_PDF", "").strip() or None

# Optional color enrichment for headers (first-span color via PyMuPDF)
STAGE04_COLOR_ENRICH = os.getenv("STAGE04_COLOR_ENRICH", "1").lower() in {"1", "true", "yes", "y"}

# Font analysis thresholds (env override via SPARTA_PDF_FONT_LARGE)
try:
    LARGE_FONT_THRESHOLD = float(os.getenv("SPARTA_PDF_FONT_LARGE", "14.0"))
except Exception:
    LARGE_FONT_THRESHOLD = 14.0
SMALL_FONT_THRESHOLD = 8.0
BOLD_WEIGHT_THRESHOLD = 600

# SECTION_NUMBER_PATTERNS imported from utils/sections


def _prepare_section_hierarchy(sections: List[Dict[str, Any]]) -> None:
    # Delegates to shared helper (prevents duplication in this file)
    prepare_section_hierarchy(sections)

# ================================
# COLOR ENRICHMENT UTILITIES
# ================================

## moved to utils: _rgb_to_hex, _bucket_color

def _enrich_header_colors(pdf_path: Path, sections: List[Dict[str, Any]]) -> None:
    """Delegates to shared helper; kept for backward compatibility in this step."""
    enrich_header_colors(pdf_path, sections)

# ============================================
# SOPHISTICATED HEADER DETECTION FUNCTIONS
# ============================================

# Core functions now imported from extractor.pipeline.utils.sections
# sbul-only helpers (normalize_breadcrumbs, breadcrumb_label, etc.) still from sbul

# Aliases for internal use (underscore prefix indicates private)
_normalize_section_number = normalize_section_number
_coerce_depth = coerce_depth
_derive_parent_number = derive_parent_number
_normalize_breadcrumbs = sbul.normalize_breadcrumbs
_breadcrumb_label = sbul.breadcrumb_label
_looks_like_header_text = looks_like_header_text
_enrich_header_colors = sbul.enrich_header_colors
_prepare_section_hierarchy = sbul.prepare_section_hierarchy


