#!/usr/bin/env python3
"""
Stage-02: Marker Extractor
--------------------------
Extract native JSON blocks from a PDF using Marker.

Purpose:
- Emit native PDF blocks (text + bbox + page_idx) with optional suspicious flags.
- Preserves all blocks; filtering happens in later stages.

Refactored to be self-contained (merged from utils/marker_runner.py).
"""

import json
import hashlib
import os
import re
import uuid
import time
import multiprocessing as mp
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Third-party
from loguru import logger
from rich.console import Console
import ftfy

# Internal
from collections import Counter

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.marker_extractor_utils import fallback_simple_extract
from extractor.pipeline.utils.section_builder_utils import canonical_block_order_key
from extractor.pipeline.utils.sections.heuristics import is_probable_pdf_section_header
from extractor.core.schema import BlockTypes
from extractor.pipeline.utils.step_sanity import run_step_sanity

try:
    import psutil
except ImportError:
    psutil = None

console = Console(stderr=True)
STEP_NAME = "02_marker_extractor"


def _normalize_text(text: str) -> str:
    """Normalize text using ftfy and project-specific regex patterns from text_toolz.
    
    Handles PDF-specific issues like hyphenation at line breaks, ligatures, 
    and varied Unicode whitespace/punctuation that ftfy might not fully resolve 
    for document extraction purposes.
    """
    import unicodedata
    import re
    if not text:
        return ""

    # 1. First-pass encoding fix (handles mojibake and legacy encodings)
    text = ftfy.fix_text(text, normalization="NFKC")

    # 2. Project-specific mappings (from text_toolz / normalize skill)
    
    # Remove directional formatting characters
    directional_pattern = "[\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069]"
    text = re.sub(directional_pattern, "", text)

    # Remove control characters (C0/C1) but preserve newlines/tabs
    control_pattern = "[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]"
    text = re.sub(control_pattern, "", text)

    # Specific hyphen/dash normalization (sometimes missed by NFKC)
    hyphen_map = {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
        "\u2014": "-", "\u2015": "-", "\u2212": "-", "\u00ad": "",
    }
    for old, new in hyphen_map.items():
        text = text.replace(old, new)

    # Quote normalization
    quote_map = {
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
        "\u00ab": '"', "\u00bb": '"',
    }
    for old, new in quote_map.items():
        text = text.replace(old, new)

    # Bullet points (crucial for consistent list detection later)
    bullet_chars = "\u2022\u25cf\u25e6\u25cb\u25aa\u25ab\u25a0\u25a1\u2023\u2043"
    for bc in bullet_chars:
        text = text.replace(bc, "-")

    # Microsoft Symbol font PUA characters (U+F000-U+F0FF)
    # These appear when PDFs use Symbol, Wingdings, or ZapfDingbats fonts
    symbol_font_map = {
        "\uf020": " ",      # space
        "\uf02d": "-",      # minus/hyphen
        "\uf06e": "-",      # en-dash variant
        "\uf0a7": "*",      # section marker / bullet
        "\uf0a8": "[ ]",    # checkbox/box
        "\uf0b7": "-",      # bullet (middle dot)
        "\uf0d8": "-",      # bullet variant (diamond/arrow)
        "\uf0e0": "->",     # right arrow
        "\uf0e8": "-",      # dash variant
        "\uf0fc": "[x]",    # checkmark
        "\uf076": "[x]",    # checkmark variant
    }
    for old, new in symbol_font_map.items():
        text = text.replace(old, new)

    # Catch-all: strip remaining PUA characters (U+E000-U+F8FF)
    # that weren't explicitly mapped above
    text = re.sub(r"[\ue000-\uf8ff]", "", text)

    # Ligature expansion (some survive NFKC in complex PDFs)
    ligature_map = {
        "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
        "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st"
    }
    for old, new in ligature_map.items():
        text = text.replace(old, new)

    # 3. Structural Fixes (Critical for PDF extraction)
    
    # Fix hyphenated words at line breaks: "intro-\nduction" -> "introduction"
    # This is a key feature of the text_toolz integration
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # 4. Final Cleanup
    # Collapse multiple whitespace to single space
    text = " ".join(text.split())
    
    return text.strip()


def sanity() -> int:
    """Run sanity check for this step."""
    return run_step_sanity(STEP_NAME)


# Workaround: some versions of `surya` import QuantizedCacheConfig from transformers
try:
    import transformers as _tx

    if not hasattr(_tx, "QuantizedCacheConfig"):

        class QuantizedCacheConfig:
            pass

        _tx.QuantizedCacheConfig = QuantizedCacheConfig
except Exception as _polyfill_exc:
    # Optional polyfill for older transformers versions - safe to ignore
    logger.debug(f"Transformers QuantizedCacheConfig polyfill skipped: {_polyfill_exc}")


# --------------------------------------------------------------------------- #
# TOC EXTRACTION
# --------------------------------------------------------------------------- #

# TOC detection patterns (based on text_toolz)
_TOC_HEADER_PATTERNS = [
    re.compile(r"^\s*(Table\s+of\s+Contents|Contents|TOC)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(Inhaltsverzeichnis|Sommaire|Indice)\s*$", re.IGNORECASE),  # German/French/Italian
]

# TOC entry pattern: number + title + dots/spaces + page number
# Handles: "1. Introduction .......... 5" or "1.1 Background ... 7"
_TOC_ENTRY_PATTERN = re.compile(
    r"""^\s*
        (?P<num>\d+(?:\.\d+)*)       # Section number (1, 1.1, 1.2.3)
        \.?\s+                       # Optional dot, then space
        (?P<title>.+?)               # Section title (non-greedy)
        \s*[.\s·…]+\s*               # Dots, spaces, or ellipsis (TOC leader)
        (?P<page>\d+)                # Page number at end
        \s*$                         # End of line
    """,
    re.VERBOSE
)

# Alternative: title without number + page at end
_TOC_ENTRY_NO_NUM_PATTERN = re.compile(
    r"""^\s*
        (?P<title>[A-Z][A-Za-z\s]{3,50}?)  # Title starting with capital
        \s*[.\s·…]+\s*               # Dots, spaces, or ellipsis
        (?P<page>\d+)                # Page number
        \s*$
    """,
    re.VERBOSE
)


def _detect_toc_from_text(blocks: List[Dict[str, Any]], max_pages: int = 10) -> List[Dict[str, Any]]:
    """Detect TOC entries from text blocks in the first pages.

    Unlike PDF bookmarks, this finds TOC as visible text content.
    TOC entries have a distinctive pattern: title followed by dots/spaces and page number.

    Args:
        blocks: List of extracted text blocks
        max_pages: Only search first N pages for TOC

    Returns:
        List of TOC entries: [{"title": str, "page": int, "num": str, "source": "text"}, ...]
    """
    toc_entries = []
    in_toc_section = False
    toc_page_start = None

    for block in blocks:
        page_idx = block.get("page_idx", block.get("page", 0))
        if page_idx >= max_pages:
            break

        text = block.get("text", "").strip()
        if not text:
            continue

        # Check for TOC header
        for pat in _TOC_HEADER_PATTERNS:
            if pat.match(text):
                in_toc_section = True
                toc_page_start = page_idx
                logger.debug(f"Found TOC header on page {page_idx}: '{text}'")
                break

        # If we're in TOC section, look for entries
        if in_toc_section:
            # TOC usually spans 1-3 pages max
            if toc_page_start is not None and page_idx > toc_page_start + 3:
                in_toc_section = False
                continue

            # Try to match TOC entry patterns
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # Pattern 1: numbered entry with page
                m = _TOC_ENTRY_PATTERN.match(line)
                if m:
                    toc_entries.append({
                        "num": m.group("num"),
                        "title": m.group("title").strip().rstrip("."),
                        "page": int(m.group("page")) - 1,  # Convert to 0-indexed
                        "source": "text",
                    })
                    continue

                # Pattern 2: unnumbered entry with page
                m = _TOC_ENTRY_NO_NUM_PATTERN.match(line)
                if m:
                    toc_entries.append({
                        "num": "",
                        "title": m.group("title").strip().rstrip("."),
                        "page": int(m.group("page")) - 1,
                        "source": "text",
                    })

    if toc_entries:
        logger.info(f"Detected {len(toc_entries)} TOC entries from text content")

    return toc_entries


def _extract_toc(doc) -> List[Dict[str, Any]]:
    """Extract Table of Contents from PDF outline/bookmarks.

    Args:
        doc: PyMuPDF document object

    Returns:
        List of TOC entries: [{"level": int, "title": str, "page": int, "dest": str}, ...]
    """
    try:
        toc = doc.get_toc(simple=False)  # Returns [[level, title, page, dest], ...]
        entries = []
        for idx, item in enumerate(toc):
            level = item[0] if len(item) > 0 else 1
            title = item[1] if len(item) > 1 else ""
            page = item[2] if len(item) > 2 else 0
            dest = str(item[3]) if len(item) > 3 else ""

            # Clean the title (remove excessive whitespace)
            title = " ".join(title.split()) if title else ""

            if title:  # Only include entries with titles
                entries.append({
                    "id": idx,
                    "level": level,
                    "title": title,
                    "page": page - 1 if page > 0 else 0,  # Convert to 0-indexed
                    "dest": dest,
                })
        return entries
    except Exception as e:
        logger.warning(f"Failed to extract PDF TOC: {e}")
        return []


# --------------------------------------------------------------------------- #
# CORE LOGIC
# --------------------------------------------------------------------------- #


def extract_blocks(
    pdf_path: Path, use_llm: bool = False, page_range: List[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """Return the native JSON list of blocks produced by Marker.

    Args:
        pdf_path: Path to PDF file
        use_llm: If True, use LLM service for improved accuracy (tables, math)
        page_range: Optional list of page indices to process (for chunking)
    """

    # 0. Configure Surya batch sizes to prevent memory exhaustion
    # Default RECOGNITION_BATCH_SIZE=512 uses ~20GB VRAM - reduce for stability
    # Each batch item uses ~40MB VRAM
    if "RECOGNITION_BATCH_SIZE" not in os.environ:
        # Default to 64 (2.5GB VRAM) for stability on large PDFs
        os.environ["RECOGNITION_BATCH_SIZE"] = os.getenv("STAGE02_RECOGNITION_BATCH_SIZE", "64")
    if "DETECTOR_BATCH_SIZE" not in os.environ:
        os.environ["DETECTOR_BATCH_SIZE"] = os.getenv("STAGE02_DETECTOR_BATCH_SIZE", "8")
    if "LAYOUT_BATCH_SIZE" not in os.environ:
        os.environ["LAYOUT_BATCH_SIZE"] = os.getenv("STAGE02_LAYOUT_BATCH_SIZE", "8")

    logger.debug(f"Surya batch sizes: RECOGNITION={os.environ.get('RECOGNITION_BATCH_SIZE')}, "
                 f"DETECTOR={os.environ.get('DETECTOR_BATCH_SIZE')}, "
                 f"LAYOUT={os.environ.get('LAYOUT_BATCH_SIZE')}")

    # 1. Imports (lazy)
    try:
        from extractor.core.converters.pdf import PdfConverter
        from extractor.core.models import create_model_dict
    except Exception as exc:
        # Fallback check
        if os.getenv("STAGE02_ALLOW_SIMPLE", "0").lower() in ("1", "true", "yes", "y"):
            tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
            blocks = fallback_simple_extract(pdf_path, tmp)
            return blocks, {}
        # If strict mode (default), raise error if internals missing
        raise RuntimeError("Marker internals unavailable and STAGE02_ALLOW_SIMPLE=0") from exc

    # 2. Config
    models = create_model_dict()
    predictor_presence = {
        "detection_model": bool(models.get("detection_model")),
        "layout_model": bool(models.get("layout_model")),
        "recognition_model": bool(models.get("recognition_model")),
        "table_rec_model": bool(models.get("table_rec_model")),
        "texify_model": bool(models.get("texify_model")),
    }

    # Log predictor presence for debugging
    predictor_status = []
    for k, v in predictor_presence.items():
        predictor_status.append(f"{k}={'✓' if v else '✗'}")
    logger.info(f"Model predictors loaded: {', '.join(predictor_status)}")

    # Warn if layout model missing (critical for Figure detection)
    if not predictor_presence.get("layout_model"):
        logger.warning("⚠️ layout_model NOT loaded - Figure/Image detection will fail")

    config = {
        "use_llm": use_llm,
        "batch_multiplier": 1,
        "disable_multiprocessing": True,
        "force_ocr": False,  # Disabled - we use Camelot for table extraction
    }

    # Add page range if specified (for chunked processing)
    if page_range is not None:
        config["page_range"] = page_range
        logger.info(f"Processing page chunk: pages {min(page_range)}-{max(page_range)} ({len(page_range)} pages)")

    # LLM Service Configuration (Chutes.ai / OpenAI-compatible)
    if use_llm:
        from extractor.core.presets import LLM_CONFIG

        api_key = os.getenv(LLM_CONFIG.get("api_key_env", "CHUTES_API_KEY"))
        if api_key:
            config["llm_service"] = LLM_CONFIG.get("service")
            config["openai_api_key"] = api_key
            config["openai_base_url"] = LLM_CONFIG.get("base_url")
            config["openai_model"] = LLM_CONFIG.get("model")
            logger.info(f"LLM Mode: Using {LLM_CONFIG.get('model')} via Chutes.ai")
        else:
            logger.warning(
                f"LLM Mode requested but {LLM_CONFIG.get('api_key_env')} not set. Falling back to non-LLM."
            )
            config["use_llm"] = False

    # 3. Convert
    converter = PdfConverter(artifact_dict=models, config=config)

    try:
        document = converter.build_document(str(pdf_path))
    except Exception as exc:
        import traceback

        # Gather diagnostic information
        diag_info = {
            "pdf_path": str(pdf_path),
            "pdf_size_mb": round(pdf_path.stat().st_size / (1024 * 1024), 2) if pdf_path.exists() else "N/A",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "models_loaded": {k: bool(v) for k, v in models.items()},
            "predictor_presence": predictor_presence,
        }

        # Memory info if psutil available
        if psutil:
            try:
                mem = psutil.virtual_memory()
                diag_info["memory"] = {
                    "total_gb": round(mem.total / (1024**3), 1),
                    "available_gb": round(mem.available / (1024**3), 1),
                    "percent_used": mem.percent,
                }
                proc = psutil.Process()
                diag_info["process_memory_mb"] = round(proc.memory_info().rss / (1024**2), 1)
            except Exception:
                pass

        # Log comprehensive error info
        logger.error(f"Marker document building failed for {pdf_path.name}")
        logger.error(f"  Error: {type(exc).__name__}: {exc}")
        logger.error(f"  PDF size: {diag_info['pdf_size_mb']} MB")
        logger.error(f"  Models loaded: {diag_info['models_loaded']}")
        if "memory" in diag_info:
            logger.error(f"  Memory: {diag_info['memory']['available_gb']}GB available of {diag_info['memory']['total_gb']}GB ({diag_info['memory']['percent_used']}% used)")
            logger.error(f"  Process memory: {diag_info.get('process_memory_mb', 'N/A')} MB")
        logger.error(f"  Full traceback:\n{traceback.format_exc()}")

        # Store diagnostic info for later analysis
        log_stage_error(STEP_NAME, exc, context=diag_info)

        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            logger.warning("Falling back to simple extraction mode")
            tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
            blocks = fallback_simple_extract(pdf_path, tmp)
            return blocks, predictor_presence
        raise

    # 4. Extract Blocks
    blocks: List[Dict[str, Any]] = []

    for page in document.pages:
        if hasattr(page, "children") and page.children:
            for block in page.children:
                if block.block_type.name in [
                    "SectionHeader",
                    "Text",
                    "Table",
                    "Figure",
                    "ListItem",
                    "Picture",
                    "Formula",
                    "Equation",
                ]:
                    block_dict = {
                        "block_type": block.block_type.name,
                        "page_idx": page.page_id,
                        "page": page.page_id,
                    }

                    # Text - extract and normalize immediately
                    raw_text = ""
                    if hasattr(block, "raw_text"):
                        try:
                            raw_text = block.raw_text(document)
                        except Exception:
                            raw_text = getattr(block, "text", "")
                    else:
                        raw_text = getattr(block, "text", "")
                    
                    # Normalize using ftfy
                    block_dict["text"] = _normalize_text(raw_text)

                    # Math detection
                    if block.block_type.name in ["Formula", "Equation"]:
                        block_dict["is_equation"] = True
                        block_dict["latex_content"] = block_dict["text"]

                    # Font Info
                    try:
                        spans = block.contained_blocks(document, (BlockTypes.Span,))
                        if spans:
                            s0 = spans[0]
                            font_name = getattr(s0, "font", None)
                            font_size = None
                            try:
                                font_size = float(getattr(s0, "font_size", 0))
                            except Exception:
                                pass

                            first_span_font = {"name": font_name, "size": font_size}
                            formats = getattr(s0, "formats", []) or []
                            first_span_font["bold"] = bool("bold" in formats)
                            first_span_font["italic"] = bool("italic" in formats)
                            block_dict["first_span_font"] = first_span_font
                    except Exception:
                        pass

                    # BBox
                    if hasattr(block, "polygon") and getattr(block, "polygon"):
                        try:
                            bx = getattr(block.polygon, "bbox", None)
                            if bx:
                                block_dict["bbox"] = [float(v) for v in bx]
                        except Exception:
                            pass

                    # Metrics
                    try:
                        if hasattr(block, "confidence"):
                            block_dict["surya_confidence"] = float(block.confidence)
                        if hasattr(block, "calculate_quality_score"):
                            block_dict["quality_score"] = float(block.calculate_quality_score())
                        if getattr(block, "requires_review", False):
                            block_dict["requires_review"] = True
                    except Exception:
                        pass

                    # Suspicion
                    try:
                        block_dict["is_suspicious"] = bool(getattr(block, "is_suspicious", False))
                        if getattr(block, "suspicious_reasons", None):
                            block_dict["suspicious_reasons"] = block.suspicious_reasons
                    except Exception:
                        pass

                    # Header Flag
                    if block_dict.get("block_type") == "SectionHeader":
                        if block_dict.get("is_suspicious") or any(
                            "header" in str(r).lower()
                            for r in block_dict.get("suspicious_reasons", [])
                        ):
                            block_dict["suspicious_header"] = True

                    # Normalize
                    block_dict.setdefault("text", "")
                    block_dict.setdefault("bbox", [0.0, 0.0, 0.0, 0.0])
                    block_dict.setdefault(
                        "page_idx", int(page.page_id) if hasattr(page, "page_id") else 0
                    )

                    try:
                        if hasattr(block, "block_id"):
                            block_dict["block_id"] = int(block.block_id)
                        if hasattr(block, "id"):
                            block_dict["id"] = str(block.id)
                    except Exception:
                        pass

                    # Skip empty Text blocks - they provide no useful content
                    if block_dict.get("block_type") == "Text" and not block_dict.get("text", "").strip():
                        logger.debug(f"Skipping empty Text block on page {block_dict.get('page_idx')}")
                        continue

                    # Content hash for stable identity across re-runs
                    hash_input = f"{block_dict.get('page_idx', 0)}:{block_dict.get('block_type', '')}:{block_dict.get('text', '')}"
                    block_dict["content_hash"] = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

                    blocks.append(block_dict)

    return blocks, predictor_presence


def _worker_func(pdf_str: str, dump_dir_str: str, use_llm: bool, page_range: List[int]):
    """Worker function for ProcessPoolExecutor."""
    try:
        blocks_local, presence = extract_blocks(Path(pdf_str), use_llm=use_llm, page_range=page_range)
        dump_dir = Path(dump_dir_str)
        dump_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = dump_dir / f"02_blocks_{uuid.uuid4().hex}.json"
        
        # Serialize to disk to avoid pickle size limits with massive blocks
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"blocks": blocks_local, "predictors": presence}, f, ensure_ascii=False)
            
        return {"ok": True, "path": str(tmp_path)}
    except Exception as exc:
        logger.error(f"Worker failed: {exc}")
        return {"ok": False, "error": str(exc)}


def _count_block_types(blocks: List[Dict[str, Any]]) -> Dict[str, int]:
    """Return a count of block types."""
    return dict(Counter(b.get("block_type", "Unknown") for b in blocks))


# --------------------------------------------------------------------------- #
# RUNNER
# --------------------------------------------------------------------------- #


def run(
    pdf_path: Path,
    output_dir: Path = Path("data/results/pipeline"),
    timeout: int = int(os.getenv("STAGE02_TIMEOUT", "600")),
    debug: bool = False,
    no_spawn: bool = False,
    mark_all_headers_suspicious: bool = False,
    output_suffix: str = "",
    use_llm: bool = False,
) -> Path:
    """Extracts text and layout blocks from a PDF using Marker."""

    # 1. Preflight
    if os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"0", "false"}:
        try:
            from extractor.core.models import create_model_dict

            m = create_model_dict()
            required = [
                "detection_model",
                "layout_model",
                "ocr_error_model",
                "recognition_model",
                "table_rec_model",
            ]
            if any(k not in m or m.get(k) is None for k in required):
                raise RuntimeError("Strict preflight: missing predictors")
        except Exception as exc:
            log_stage_error("02_marker_extractor", exc, {"context": "02"})
            raise

    # 2. Setup
    run_id = uuid.uuid4().hex
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    stage_output_dir = output_dir / "02_marker_extractor"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    logger.remove()
    logger.add(stage_output_dir / "stage_02.log", level="DEBUG" if debug else "INFO")

    console.print(f"Extracting blocks from: {pdf_path.name}")
    t0 = time.monotonic()

    if not no_spawn and os.getenv("STAGE02_NO_SPAWN", "0").lower() in ("1", "true", "yes", "y"):
        no_spawn = True

    # 2b. Page chunking for large PDFs
    page_chunks = None
    total_pages = 0
    pdf_size_mb = 0.0
    chunk_size = int(os.getenv("STAGE02_CHUNK_SIZE", "100"))
    chunk_threshold = int(os.getenv("STAGE02_CHUNK_THRESHOLD", "150"))

    try:
        import fitz
        with fitz.open(str(pdf_path)) as doc:
            total_pages = len(doc)
            pdf_size_mb = pdf_path.stat().st_size / (1024 * 1024)

        logger.info(f"PDF info: {total_pages} pages, {pdf_size_mb:.1f} MB")

        if total_pages > chunk_threshold:
            page_chunks = []
            for start in range(0, total_pages, chunk_size):
                end = min(start + chunk_size, total_pages)
                page_chunks.append(list(range(start, end)))
            logger.info(f"Large PDF detected ({total_pages} pages). Processing in {len(page_chunks)} chunks")
    except Exception as exc:
        logger.warning(f"Could not determine page count for chunking: {exc}")

    # 3. Execution
    blocks = []
    presence = {}

    if no_spawn:
        # Inline execution (no process pool)
        try:
            if page_chunks:
                for chunk_idx, chunk_pages in enumerate(page_chunks):
                    logger.info(f"Inline chunk {chunk_idx+1}/{len(page_chunks)}")
                    chunk_blocks, chunk_presence = extract_blocks(
                        pdf_path, use_llm=use_llm, page_range=chunk_pages
                    )
                    blocks.extend(chunk_blocks)
                    if not presence: 
                        presence = chunk_presence
            else:
                blocks, presence = extract_blocks(pdf_path, use_llm=use_llm)
        except Exception as exc:
            logger.exception("Step 02 Inline Failed")
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() == "1":
                raise
            blocks = []
    else:
        # Executor execution
        # We assume 1 worker to control VRAM usage (unless user overrides env vars, but code forces max_workers=1)
        # Marker/Surya is VRAM hungry, parallel workers usually crash OOM.
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            futures = []
            if page_chunks:
                for chunk_pages in page_chunks:
                    futures.append(
                        executor.submit(_worker_func, str(pdf_path), str(json_output_dir), use_llm, chunk_pages)
                    )
            else:
                futures.append(
                    executor.submit(_worker_func, str(pdf_path), str(json_output_dir), use_llm, None)
                )

            # Collect results
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    res = future.result(timeout=timeout)
                    if not res.get("ok"):
                        logger.error(f"Worker Error: {res.get('error')}")
                        if os.getenv("PIPELINE_FAIL_FAST", "0").lower() == "1":
                            raise RuntimeError(res.get("error"))
                        continue
                    
                    tmp = Path(res.get("path"))
                    if tmp.exists():
                        d = json.loads(tmp.read_text())
                        chunk_blocks = d.get("blocks", [])
                        chunk_presence = d.get("predictors", {})
                        blocks.extend(chunk_blocks)
                        if not presence:
                             presence = chunk_presence
                        tmp.unlink()
                except Exception as e:
                    logger.error(f"Worker Exception: {e}")
                    if os.getenv("PIPELINE_FAIL_FAST", "0").lower() == "1":
                        raise

    # 4. Post-processing
    trigger_fallback = False
    fallback_reason = ""

    if not blocks:
        trigger_fallback = True
        fallback_reason = "Marker produced 0 blocks"
    elif total_pages and total_pages > 0:
        text_blocks = sum(1 for b in blocks if b.get("block_type") in ("Text", "SectionHeader", "ListItem"))
        text_per_page = text_blocks / total_pages
        min_text_per_page = float(os.getenv("STAGE02_MIN_TEXT_PER_PAGE", "3"))
        
        if text_per_page < min_text_per_page:
            layout_loaded = presence.get("layout_model", False)
            if not layout_loaded:
                trigger_fallback = True
                fallback_reason = f"Suspiciously low text ({text_per_page:.1f}/page) and no layout model."
            else:
                logger.warning(f"Low text extraction ({text_per_page:.1f}/page) but layout loaded.")

    if trigger_fallback and os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
        logger.warning(f"{fallback_reason}. Triggering simple extraction fallback.")
        try:
            tmp_fallback = json_output_dir / f"fallback_{uuid.uuid4().hex}.json"
            fallback_blocks = fallback_simple_extract(pdf_path, tmp_fallback)
            if tmp_fallback.exists():
                tmp_fallback.unlink()
            if len(fallback_blocks) > len(blocks):
                logger.info(f"Fallback recovered {len(fallback_blocks)} blocks (vs {len(blocks)})")
                blocks = fallback_blocks
        except Exception as fb_exc:
            logger.error(f"Fallback failed: {fb_exc}")

    # Apply section header heuristics
    demoted_count = 0
    for b in blocks:
        if b.get("block_type") == "SectionHeader":
            text = (b.get("text") or "").strip()
            if text:
                result = is_probable_pdf_section_header(text)
                if not result.get("is_header", True):
                    b["block_type"] = "Text"
                    b["demoted_reason"] = result.get("reason", "heuristic_filter")
                    demoted_count += 1
    if demoted_count:
        logger.info(f"Demoted {demoted_count} false-positive headers")

    if mark_all_headers_suspicious:
        for b in blocks:
            if b.get("block_type") == "SectionHeader":
                b["suspicious_header"] = True

    blocks.sort(key=canonical_block_order_key)

    # 5. Optional visuals (debug contract enforcement)
    page_count = 0
    if os.getenv("CONTRACT_LOOP_DEBUG_VISUALS", "0").lower() in {"1", "true", "yes", "y"}:
        visual_output_dir = stage_output_dir / "visual_output"
        visual_output_dir.mkdir(exist_ok=True)
        try:
            import fitz

            doc = fitz.open(str(pdf_path))
        except Exception as exc:
            logger.error(f"Failed to open PDF for visuals: {exc}")
            doc = None
        if doc is not None:
            page_count = len(doc)
            for idx, block in enumerate(blocks):
                try:
                    page_idx = block.get("page_idx")
                    if page_idx is None:
                        page_idx = block.get("page", 0)
                    page_idx = int(page_idx or 0)
                    if page_idx < 0 or page_idx >= len(doc):
                        page_idx = 0
                    page = doc[page_idx]
                    bbox = block.get("bbox") or []
                    if not isinstance(bbox, list) or len(bbox) != 4:
                        bbox = [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1]
                    rect = fitz.Rect(*[float(v) for v in bbox])
                    if rect.is_empty or rect.width <= 0 or rect.height <= 0:
                        rect = fitz.Rect(page.rect)
                    rect = rect & page.rect
                    rect.x0 = max(page.rect.x0, rect.x0 - 2)
                    rect.y0 = max(page.rect.y0, rect.y0 - 2)
                    rect.x1 = min(page.rect.x1, rect.x1 + 2)
                    rect.y1 = min(page.rect.y1, rect.y1 + 2)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
                    out_name = f"block_{idx:06d}.png"
                    out_path = visual_output_dir / out_name
                    pix.save(str(out_path))
                    block["visual_path"] = str(out_path.relative_to(output_dir))
                except Exception as exc:
                    logger.warning(f"Failed to render block visual {idx}: {exc}")
            doc.close()

    # Fallback to get page count and extract TOC if visuals were skipped
    toc_entries = []
    if page_count == 0:
        try:
            import fitz

            with fitz.open(str(pdf_path)) as tmp_doc:
                page_count = len(tmp_doc)
                # Extract PDF outline/bookmarks (TOC)
                toc_entries = _extract_toc(tmp_doc)
        except Exception:
            pass
    else:
        # Visuals were rendered, but we still need TOC
        try:
            import fitz

            with fitz.open(str(pdf_path)) as tmp_doc:
                toc_entries = _extract_toc(tmp_doc)
        except Exception:
            pass

    if toc_entries:
        logger.info(f"Extracted {len(toc_entries)} TOC entries from PDF bookmarks")

    # Also detect TOC from text content (visible TOC pages)
    toc_from_text = _detect_toc_from_text(blocks, max_pages=10)
    if toc_from_text:
        # Mark bookmark entries with source
        for entry in toc_entries:
            entry["source"] = "bookmark"
        # Merge: text TOC often has more detail, bookmark TOC is more reliable
        # Use text TOC to supplement bookmark TOC
        if not toc_entries:
            toc_entries = toc_from_text
        else:
            # Add text entries that aren't in bookmark TOC
            bookmark_titles = {e["title"].lower().strip() for e in toc_entries}
            for text_entry in toc_from_text:
                if text_entry["title"].lower().strip() not in bookmark_titles:
                    toc_entries.append(text_entry)
            logger.info(f"Merged {len(toc_from_text)} text TOC entries with bookmarks")

    # 6. Output
    summary = {
        "timestamp": datetime.now().isoformat(),
        "run_id": run_id,
        "metadata": {
            "llm_used": use_llm,
            "page_count": page_count,
            "source_pdf": str(pdf_path),
            "toc_entry_count": len(toc_entries),
        },
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "block_count": len(blocks),
        "block_type_distribution": _count_block_types(blocks),
        "suspicious_block_count": len([b for b in blocks if b.get("is_suspicious")]),
        "blocks": blocks,
        "toc_entries": toc_entries,  # PDF outline/bookmarks for section validation
        "predictors_present": presence,
        "timings": {"duration_ms": int((time.monotonic() - t0) * 1000)},
    }

    base = "02_marker_blocks"
    if output_suffix:
        base += f"_{output_suffix}"
    out_path = json_output_dir / f"{base}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    console.print(f"✅ Extracted {len(blocks)} blocks")
    return out_path


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 02: Marker Extractor")
    parser.add_argument(
        "--pipeline-dir", type=Path, required=True, help="Path to pipeline results root"
    )
    args = parser.parse_args()

    pipeline_dir = args.pipeline_dir

    try:
        logger.info("Running Stage 02...")

        # Input Auto-detection: S01 PDF
        s01_dir = pipeline_dir / "01_annotation_processor"
        pdf_path = None
        if s01_dir.exists():
            candidates = list(s01_dir.glob("*_clean.pdf"))
            if candidates:
                pdf_path = candidates[0]

        if not pdf_path:
            logger.error(f"Missing input dependencies (Stage 01 clean PDF) in {s01_dir}")
            sys.exit(1)

        run(pdf_path=pdf_path, output_dir=pipeline_dir)

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
