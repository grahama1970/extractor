#!/usr/bin/env python3
"""
Stage-02: Extract native JSON blocks from a PDF using Marker

Agent instructions (read before running):
- Purpose: emit native PDF blocks (text + bbox + page_idx) with optional suspicious flags.
- Expectations: include required top-level keys (timestamp, source_pdf, status, block_count,
  suspicious_block_count, blocks) and ensure at least one `SectionHeader` candidate so downstream
  stages (03 suspicious_headers, 04 section_builder) can filter/refine. Misclassified headers are
  acceptable here; precision happens later.
- Do NOT prune/merge aggressively; preserve all blocks with basic metadata.
- Sanity: block_count must equal len(blocks); suspicious_block_count >= 0.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import os
import time
from extractor.pipeline.utils.reliability import log_stage_error

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None
import multiprocessing as mp
from extractor.pipeline.utils.marker_extractor_utils import fallback_simple_extract
from extractor.pipeline.utils.section_builder_utils import canonical_block_order_key

## Typer removed; plain function signatures for easier debugging

from loguru import logger
from rich.console import Console
import uuid


# Workaround: some versions of `surya` import QuantizedCacheConfig from transformers,
# which is missing in transformers<4.58. To keep the pipeline runnable without
# altering global deps, inject a minimal stub if absent before importing Marker internals.
try:
    import transformers as _tx

    if not hasattr(_tx, "QuantizedCacheConfig"):

        class QuantizedCacheConfig:  # type: ignore
            pass

        _tx.QuantizedCacheConfig = QuantizedCacheConfig  # type: ignore[attr-defined]
except Exception as exc:
    log_stage_error('02_marker_extractor', exc, {'context': '02'})
    raise
    pass
from extractor.core.schema import BlockTypes
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    make_event,
    gpu_metrics_available,
)
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.utils.marker_runner import run

# --------------------------------------------------------------------------- #
# Marker import
# --------------------------------------------------------------------------- #
# Note: Removed unused Marker import guard that exited the program on import error.
# We access PdfConverter directly inside extract_blocks() where errors are handled.

# --------------------------------------------------------------------------- #
# Logging / CLI
# --------------------------------------------------------------------------- #
# Do not mutate global logger configuration at import time
# Stage-scoped logging is configured within the CLI run() function.
console = Console()
STEP_NAME = "02_marker_extractor"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)

DEBUG = False


# --------------------------------------------------------------------------- #
# Move multiprocessing worker to top-level for cross-platform compatibility (spawn/fork)
def _worker(pdf_str: str, q: "mp.Queue[Dict[str, Any]]", dump_dir_str: str):
    try:
        blocks_local, presence = extract_blocks(Path(pdf_str))
        # Avoid large objects over mp.Queue → write to temp JSON and return small message
        dump_dir = Path(dump_dir_str)
        dump_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = dump_dir / f"02_blocks_{uuid.uuid4().hex}.json"
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"blocks": blocks_local, "predictors": presence}, f, ensure_ascii=False)
        q.put({"ok": True, "path": str(tmp_path)})
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        q.put({"ok": False, "error": str(exc)})




def extract_blocks(pdf_path: Path) -> tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """
    Return the native JSON list of blocks produced by Marker.

    Since convert_single_pdf returns a MarkdownOutput object with markdown text,
    we need to access the converter directly to get the blocks.
    """
    try:
        from extractor.core.converters.pdf import PdfConverter
        from extractor.core.models import create_model_dict
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        # If imports fail, attempt simple fallback if allowed
        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
            blocks = fallback_simple_extract(pdf_path, tmp)
            return blocks, {}
        raise RuntimeError(
            "Marker internals unavailable. Ensure project-specific Marker modules are installed "
            "(extractor.core.converters/pdf and extractor.core.models)."
        ) from e

    # Create model dictionary (predictors may be missing in offline mode)
    models = create_model_dict()
    predictor_presence = {
        "detection_model": bool(models.get("detection_model")),
        "layout_model": bool(models.get("layout_model")),
        "recognition_model": bool(models.get("recognition_model")),
        "table_rec_model": bool(models.get("table_rec_model")),
        "texify_model": bool(models.get("texify_model")),
    }

    # Create config as simple dict
    config = {
        "use_llm": False,  # Disable LLM for speed - suspicious detection in post-processing
        "batch_multiplier": 1,
        "disable_multiprocessing": True,
    }

    # Create the PDF converter
    _strict_mode = os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"0", "false"}
    converter = PdfConverter(
        artifact_dict=models,
        config=config,
    )

    # Build the document (this creates and processes all blocks)
    try:
        document = converter.build_document(str(pdf_path))
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        logger.error(f"Marker document building failed: {e}")
        # If predictor presence is weak and fallback is allowed, try simple extractor
        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            logger.warning("Falling back to simple extraction mode")
            try:
                tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
                blocks = fallback_simple_extract(pdf_path, tmp)
                logger.info(f"Simple extraction succeeded, extracted {len(blocks)} blocks")
                return blocks, predictor_presence
            except Exception as exc:
                log_stage_error('02_marker_extractor', exc, {'context': '02'})
                raise
                logger.error(f"Simple extraction fallback also failed: {fallback_error}")
                if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                    raise RuntimeError(f"Both marker and simple extraction failed: {e}") from e
                # Return empty blocks to allow pipeline to continue
                logger.warning("Returning empty blocks to allow pipeline continuation")
                return [], predictor_presence
        else:
            # Fallback disabled, fail according to pipeline policy
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                raise RuntimeError(f"Marker extraction failed: {e}") from e
            else:
                logger.warning("STAGE02_ALLOW_SIMPLE disabled, returning empty blocks")
                return [], predictor_presence

    # Color enrichment via PyMuPDF is disabled to comply with Stage‑02 policy
    fitz_doc = None

    blocks: List[Dict[str, Any]] = []
    for page in document.pages:
        # Get blocks from children (includes all processed blocks)
        if hasattr(page, "children") and page.children:
            for block in page.children:
                # Only include high-level blocks, not Spans/Lines
                if block.block_type.name in [
                    "SectionHeader",
                    "Text",
                    "Table",
                    "Figure",
                    "ListItem",
                ]:
                    block_dict = {
                        "block_type": block.block_type.name,
                        "page_idx": page.page_id,
                        "page": page.page_id,  # convenience alias used by later stages
                    }

                    # Get text content
                    if hasattr(block, "raw_text"):
                        try:
                            block_dict["text"] = block.raw_text(document)
                        except Exception as exc:
                            log_stage_error('02_marker_extractor', exc, {'context': '02'})
                            raise
                            block_dict["text"] = getattr(block, "text", "")
                    else:
                        block_dict["text"] = getattr(block, "text", "")

                    # Add first span font information if available
                    try:
                        spans = block.contained_blocks(document, (BlockTypes.Span,))
                        if spans:
                            s0 = spans[0]
                            font_name = getattr(s0, "font", None)
                            font_size_val = getattr(s0, "font_size", None)
                            try:
                                font_size = (
                                    float(font_size_val) if font_size_val is not None else None
                                )
                            except Exception as exc:
                                log_stage_error('02_marker_extractor', exc, {'context': '02'})
                                raise
                                font_size = None
                            first_span_font = {"name": font_name, "size": font_size}
                            # Also capture basic style flags for heuristics
                            try:
                                formats = getattr(s0, "formats", []) or []
                                is_bold = bool("bold" in formats)
                                is_italic = bool("italic" in formats)
                                font_weight = getattr(s0, "font_weight", None)
                                if font_weight is not None:
                                    try:
                                        font_weight = float(font_weight)
                                    except Exception as exc:
                                        log_stage_error('02_marker_extractor', exc, {'context': '02'})
                                        raise
                                        font_weight = None
                                first_span_font["bold"] = is_bold
                                first_span_font["italic"] = is_italic
                                if font_weight is not None:
                                    first_span_font["weight"] = font_weight
                            except Exception as exc:
                                log_stage_error('02_marker_extractor', exc, {'context': '02'})
                                raise
                                pass
                            # Try to enrich with color via PyMuPDF if available
                            if (
                                fitz_doc is not None
                                and hasattr(block, "polygon")
                                and getattr(block, "polygon")
                            ):
                                try:
                                    page_index = int(getattr(block, "page_id", 0) or 0)
                                    page_obj = fitz_doc[page_index]
                                    bbox = getattr(block.polygon, "bbox", None)
                                    if bbox:
                                        x0, y0, x1, y1 = bbox

                                        def _overlap(b1, b2):
                                            ax0, ay0, ax1, ay1 = b1
                                            bx0, by0, bx1, by1 = b2
                                            return not (
                                                ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0
                                            )

                                        page_text_cache = locals().get("page_text_cache") or {}
                                        if page_index in page_text_cache:
                                            tdict = page_text_cache[page_index]
                                        else:
                                            tdict = page_obj.get_text("dict")
                                            page_text_cache[page_index] = tdict
                                        found_color = None
                                        for tb in tdict.get("blocks", []):
                                            if tb.get("type") != 0:
                                                continue
                                            bb = tb.get("bbox")
                                            if not bb or not _overlap(bb, bbox):
                                                continue
                                            for ln in tb.get("lines", []):
                                                for sp in ln.get("spans", []):
                                                    if sp.get("color") is not None:
                                                        found_color = sp.get("color")
                                                        break
                                                if found_color is not None:
                                                    break
                                            if found_color is not None:
                                                break
                                        if found_color is not None:
                                            first_span_font["color"] = found_color
                                            try:
                                                r = (int(found_color) >> 16) & 255
                                                g = (int(found_color) >> 8) & 255
                                                b = int(found_color) & 255
                                                first_span_font["color_rgb"] = [r, g, b]
                                                first_span_font["color_hex"] = (
                                                    f"#{r:02X}{g:02X}{b:02X}"
                                                )
                                                # Coarse color bucket using HSV
                                                import colorsys

                                                h, s, v = colorsys.rgb_to_hsv(
                                                    r / 255.0, g / 255.0, b / 255.0
                                                )
                                                h_deg = h * 360.0
                                                bucket = "unknown"
                                                if s < 0.10:
                                                    if v < 0.20:
                                                        bucket = "black"
                                                    elif v < 0.40:
                                                        bucket = "dark_gray"
                                                    elif v < 0.70:
                                                        bucket = "gray"
                                                    elif v < 0.90:
                                                        bucket = "light_gray"
                                                    else:
                                                        bucket = "white"
                                                else:
                                                    if h_deg < 15 or h_deg >= 345:
                                                        bucket = "red"
                                                    elif h_deg < 45:
                                                        bucket = "orange"
                                                    elif h_deg < 75:
                                                        bucket = "yellow"
                                                    elif h_deg < 165:
                                                        bucket = "green"
                                                    elif h_deg < 195:
                                                        bucket = "cyan"
                                                    elif h_deg < 255:
                                                        bucket = "blue"
                                                    elif h_deg < 285:
                                                        bucket = "purple"
                                                    elif h_deg < 345:
                                                        bucket = "magenta"
                                                first_span_font["color_bucket"] = bucket
                                            except Exception as exc:
                                                log_stage_error('02_marker_extractor', exc, {'context': '02'})
                                                raise
                                                pass
                                except Exception as exc:
                                    log_stage_error('02_marker_extractor', exc, {'context': '02'})
                                    raise
                                    pass
                            block_dict["first_span_font"] = first_span_font
                    except Exception as exc:
                        log_stage_error('02_marker_extractor', exc, {'context': '02'})
                        raise
                        pass

                    # Add bbox if available - ensure JSON-safe list of floats
                    if hasattr(block, "polygon") and getattr(block, "polygon"):
                        try:
                            bx = getattr(block.polygon, "bbox", None)
                            if bx is not None:
                                block_dict["bbox"] = [float(v) for v in bx]
                        except Exception as exc:
                            log_stage_error('02_marker_extractor', exc, {'context': '02'})
                            raise
                            pass

                    # Add Surya/marker confidence and derived quality score
                    try:
                        surya_conf = getattr(block, "confidence", None)
                        if surya_conf is not None:
                            block_dict["surya_confidence"] = float(surya_conf)
                    except Exception as exc:
                        log_stage_error('02_marker_extractor', exc, {'context': '02'})
                        raise
                        pass
                    try:
                        # Derive quick quality score factoring suspicion
                        # Uses Block.calculate_quality_score() which applies penalties
                        # based on suspicion confidence and number of reasons.
                        if hasattr(block, "calculate_quality_score"):
                            q = block.calculate_quality_score()
                            block_dict["quality_score"] = float(q)
                    except Exception as exc:
                        log_stage_error('02_marker_extractor', exc, {'context': '02'})
                        raise
                        pass
                    try:
                        req_review = getattr(block, "requires_review", None)
                        if req_review:
                            block_dict["requires_review"] = True
                    except Exception as exc:
                        log_stage_error('02_marker_extractor', exc, {'context': '02'})
                        raise
                        pass

                    # Include suspicion fields from base Block class
                    try:
                        is_suspicious_val = bool(getattr(block, "is_suspicious", False))
                        block_dict["is_suspicious"] = is_suspicious_val
                        # Only include reasons when present (avoid empty arrays unless populated)
                        reasons = getattr(block, "suspicious_reasons", None)
                        if reasons:
                            block_dict["suspicious_reasons"] = reasons
                        susp_conf = getattr(block, "suspicion_confidence", None)
                        if susp_conf is not None:
                            block_dict["suspicion_confidence"] = float(susp_conf)
                    except Exception as exc:
                        log_stage_error('02_marker_extractor', exc, {'context': '02'})
                        raise
                        pass

                    # Derive 'suspicious_header' for Stage 03 compatibility; include only when True
                    if block_dict.get("block_type") == "SectionHeader":
                        sh = False
                        if block_dict.get("is_suspicious"):
                            sh = True
                        elif any(
                            "header" in str(r).lower()
                            for r in block_dict.get("suspicious_reasons", [])
                        ):
                            sh = True
                        if sh:
                            block_dict["suspicious_header"] = True

                    # normalize required keys for downstream stages
                    block_dict.setdefault("text", "")
                    block_dict.setdefault("bbox", [0.0, 0.0, 0.0, 0.0])
                    block_dict.setdefault(
                        "page_idx", int(page.page_id) if hasattr(page, "page_id") else 0
                    )
                    # Add identifiers to aid downstream correlation and ordering
                    try:
                        block_dict["block_id"] = int(getattr(block, "block_id", -1))
                        # block.id is a pydantic model; stringify for portability
                        if hasattr(block, "id"):
                            block_dict["id"] = str(block.id)
                    except Exception as exc:
                        log_stage_error('02_marker_extractor', exc, {'context': '02'})
                        raise
                        pass
                    blocks.append(block_dict)

    # Close PyMuPDF if used
    try:
        if fitz_doc is not None:
            fitz_doc.close()
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        pass

    return blocks, predictor_presence


# --------------------------------------------------------------------------- #
