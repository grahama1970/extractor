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
import os
import uuid
import time
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Third-party
from loguru import logger
from rich.console import Console

# Internal
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.marker_extractor_utils import fallback_simple_extract
from extractor.pipeline.utils.section_builder_utils import canonical_block_order_key
from extractor.core.schema import BlockTypes
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    make_event,
    gpu_metrics_available,
)
from extractor.pipeline.utils.step_sanity import run_step_sanity

try:
    import psutil
except ImportError:
    psutil = None

console = Console(stderr=True)
STEP_NAME = "02_marker_extractor"


# Workaround: some versions of `surya` import QuantizedCacheConfig from transformers
try:
    import transformers as _tx
    if not hasattr(_tx, "QuantizedCacheConfig"):
        class QuantizedCacheConfig: pass
        _tx.QuantizedCacheConfig = QuantizedCacheConfig
except Exception as _polyfill_exc:
    # Optional polyfill for older transformers versions - safe to ignore
    logger.debug(f"Transformers QuantizedCacheConfig polyfill skipped: {_polyfill_exc}")



# --------------------------------------------------------------------------- #
# CORE LOGIC
# --------------------------------------------------------------------------- #

def extract_blocks(pdf_path: Path, use_llm: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """Return the native JSON list of blocks produced by Marker.
    
    Args:
        pdf_path: Path to PDF file
        use_llm: If True, use LLM service for improved accuracy (tables, math)
    """
    
    # 1. Imports (lazy)
    try:
        from extractor.core.converters.pdf import PdfConverter
        from extractor.core.models import create_model_dict
    except Exception as exc:
        # Fallback check
        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
            blocks = fallback_simple_extract(pdf_path, tmp)
            return blocks, {}
        raise RuntimeError("Marker internals unavailable.") from exc

    # 2. Config
    models = create_model_dict()
    predictor_presence = {
        "detection_model": bool(models.get("detection_model")),
        "layout_model": bool(models.get("layout_model")),
        "recognition_model": bool(models.get("recognition_model")),
        "table_rec_model": bool(models.get("table_rec_model")),
        "texify_model": bool(models.get("texify_model")),
    }
    
    config = {
        "use_llm": use_llm,
        "batch_multiplier": 1,
        "disable_multiprocessing": True,
    }
    
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
            logger.warning(f"LLM Mode requested but {LLM_CONFIG.get('api_key_env')} not set. Falling back to non-LLM.")
            config["use_llm"] = False

    # 3. Convert
    converter = PdfConverter(artifact_dict=models, config=config)
    
    try:
        document = converter.build_document(str(pdf_path))
    except Exception as exc:
        logger.error(f"Marker document building failed: {exc}")
        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            logger.warning("Falling back to simple extraction mode")
            tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
            blocks = fallback_simple_extract(pdf_path, tmp)
            return blocks, predictor_presence
        raise

    # 4. Extract Blocks
    fitz_doc = None # Color enrichment disabled for now (kept primarily for compatibility if needed later)
    blocks: List[Dict[str, Any]] = []

    for page in document.pages:
        if hasattr(page, "children") and page.children:
            for block in page.children:
                if block.block_type.name in ["SectionHeader", "Text", "Table", "Figure", "ListItem"]:
                    block_dict = {
                        "block_type": block.block_type.name,
                        "page_idx": page.page_id,
                        "page": page.page_id,
                    }

                    # Text
                    if hasattr(block, "raw_text"):
                        try: block_dict["text"] = block.raw_text(document)
                        except: block_dict["text"] = getattr(block, "text", "")
                    else:
                        block_dict["text"] = getattr(block, "text", "")

                    # Font Info
                    try:
                        spans = block.contained_blocks(document, (BlockTypes.Span,))
                        if spans:
                            s0 = spans[0]
                            font_name = getattr(s0, "font", None)
                            font_size = None
                            try: font_size = float(getattr(s0, "font_size", 0))
                            except: pass
                            
                            first_span_font = {"name": font_name, "size": font_size}
                            formats = getattr(s0, "formats", []) or []
                            first_span_font["bold"] = bool("bold" in formats)
                            first_span_font["italic"] = bool("italic" in formats)
                            block_dict["first_span_font"] = first_span_font
                    except: pass

                    # BBox
                    if hasattr(block, "polygon") and getattr(block, "polygon"):
                        try:
                            bx = getattr(block.polygon, "bbox", None)
                            if bx: block_dict["bbox"] = [float(v) for v in bx]
                        except: pass

                    # Metrics
                    try:
                        if hasattr(block, "confidence"): block_dict["surya_confidence"] = float(block.confidence)
                        if hasattr(block, "calculate_quality_score"): block_dict["quality_score"] = float(block.calculate_quality_score())
                        if getattr(block, "requires_review", False): block_dict["requires_review"] = True
                    except: pass

                    # Suspicion
                    try:
                        block_dict["is_suspicious"] = bool(getattr(block, "is_suspicious", False))
                        if getattr(block, "suspicious_reasons", None):
                            block_dict["suspicious_reasons"] = block.suspicious_reasons
                    except: pass

                    # Header Flag
                    if block_dict.get("block_type") == "SectionHeader":
                        if block_dict.get("is_suspicious") or any("header" in str(r).lower() for r in block_dict.get("suspicious_reasons", [])):
                            block_dict["suspicious_header"] = True

                    # Normalize
                    block_dict.setdefault("text", "")
                    block_dict.setdefault("bbox", [0.0, 0.0, 0.0, 0.0])
                    block_dict.setdefault("page_idx", int(page.page_id) if hasattr(page, "page_id") else 0)
                    
                    try:
                        if hasattr(block, "block_id"): block_dict["block_id"] = int(block.block_id)
                        if hasattr(block, "id"): block_dict["id"] = str(block.id)
                    except: pass
                    
                    blocks.append(block_dict)

    return blocks, predictor_presence


def _worker(pdf_str: str, q: "mp.Queue[Dict[str, Any]]", dump_dir_str: str, use_llm: bool = False):
    """Worker process to run extraction in isolation."""
    try:
        blocks_local, presence = extract_blocks(Path(pdf_str), use_llm=use_llm)
        dump_dir = Path(dump_dir_str)
        dump_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = dump_dir / f"02_blocks_{uuid.uuid4().hex}.json"
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"blocks": blocks_local, "predictors": presence}, f, ensure_ascii=False)
        q.put({"ok": True, "path": str(tmp_path)})
    except Exception as exc:
        logger.error(f"Worker failed: {exc}")
        q.put({"ok": False, "error": str(exc)})


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
    """Extracts text and layout blocks from a PDF using Marker.
    
    Args:
        use_llm: If True, use LLM for improved accuracy (accurate mode).
    """
    
    # 1. Preflight
    if os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"0", "false"}:
        try:
            from extractor.core.models import create_model_dict
            m = create_model_dict()
            required = ["detection_model", "layout_model", "ocr_error_model", "recognition_model", "table_rec_model"]
            if any(k not in m or m.get(k) is None for k in required):
                raise RuntimeError("Strict preflight: missing predictors")
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise

    # 2. Setup
    run_id = uuid.uuid4().hex
    diagnostics = []
    errors = 0
    warnings = 0
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

    # 3. Execution
    blocks = []
    presence = {}
    
    if no_spawn:
        try:
            blocks, presence = extract_blocks(pdf_path, use_llm=use_llm)
        except Exception as exc:
            logger.exception("Step 02 Inline Failed")
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() == "1": raise
            blocks = []
    else:
        q = mp.Queue()
        p = mp.Process(target=_worker, args=(str(pdf_path), q, str(json_output_dir), use_llm), daemon=True)
        p.start()
        try:
            res = q.get(timeout=timeout)
            if not res.get("ok"):
                logger.error(f"Worker Error: {res.get('error')}")
                if os.getenv("PIPELINE_FAIL_FAST", "0").lower() == "1": raise RuntimeError(res.get("error"))
                blocks = []
            else:
                tmp = Path(res.get("path"))
                if tmp.exists():
                    d = json.loads(tmp.read_text())
                    blocks = d.get("blocks", [])
                    presence = d.get("predictors", {})
                    tmp.unlink()
        except Exception:
            try: p.terminate()
            except: pass
            logger.error("Worker Timeout/Crash")
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() == "1": raise
            blocks = []
        finally:
            p.join(1)

    # 4. Post-processing
    # Fallback if 0 blocks found (common with synthetic PDFs that Marker ignores)
    if not blocks and os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
        logger.warning("Marker produced 0 blocks. Triggering simple extraction fallback.")
        try:
            tmp_fallback = json_output_dir / f"fallback_{uuid.uuid4().hex}.json"
            blocks = fallback_simple_extract(pdf_path, tmp_fallback)
            if tmp_fallback.exists():
                tmp_fallback.unlink()
            logger.info(f"Fallback recovered {len(blocks)} blocks")
        except Exception as fb_exc:
            logger.error(f"Fallback failed: {fb_exc}")

    if mark_all_headers_suspicious:
        for b in blocks:
            if b.get("block_type") == "SectionHeader": b["suspicious_header"] = True
            
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

    # Fallback to get page count if visuals were skipped
    if page_count == 0:
        try:
            import fitz
            with fitz.open(str(pdf_path)) as tmp_doc:
                page_count = len(tmp_doc)
        except Exception:
            pass

    # 6. Output
    summary = {
        "timestamp": datetime.now().isoformat(),
        "run_id": run_id,
        "metadata": {
            "llm_used": use_llm,
            "page_count": page_count,
            "source_pdf": str(pdf_path),
        },
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "block_count": len(blocks),
        "suspicious_block_count": len([b for b in blocks if b.get("is_suspicious")]),
        "blocks": blocks,
        "predictors_present": presence,
        "timings": {"duration_ms": int((time.monotonic() - t0) * 1000)}
    }
    
    base = "02_marker_blocks"
    if output_suffix: base += f"_{output_suffix}"
    out_path = json_output_dir / f"{base}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    
    console.print(f"✅ Extracted {len(blocks)} blocks")
    return out_path


    return out_path


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 02: Marker Extractor")
    parser.add_argument("--pipeline-dir", type=Path, required=True, help="Path to pipeline results root")
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
