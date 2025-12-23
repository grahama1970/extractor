"""Stage 02 marker extractor runner."""
import json, os, uuid, time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
import multiprocessing as mp

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

try:
    import psutil
except ImportError:
    psutil = None

console = Console(stderr=True)

# Workaround: some versions of `surya` import QuantizedCacheConfig from transformers
try:
    import transformers as _tx

    if not hasattr(_tx, "QuantizedCacheConfig"):
        class QuantizedCacheConfig:
            pass
        _tx.QuantizedCacheConfig = QuantizedCacheConfig
except Exception:
    pass


# --------------------------------------------------------------------------- #
# Worker Process for Isolation
# --------------------------------------------------------------------------- #
def _worker(pdf_str: str, q: "mp.Queue[Dict[str, Any]]", dump_dir_str: str):
    """Worker process to run extraction in isolation."""
    try:
        blocks_local, presence = extract_blocks(Path(pdf_str))
        # Avoid large objects over mp.Queue -> write to temp JSON and return small message
        dump_dir = Path(dump_dir_str)
        dump_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = dump_dir / f"02_blocks_{uuid.uuid4().hex}.json"
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"blocks": blocks_local, "predictors": presence}, f, ensure_ascii=False)
        q.put({"ok": True, "path": str(tmp_path)})
    except Exception as exc:
        # log locally but also send error back
        logger.error(f"Worker failed: {exc}")
        q.put({"ok": False, "error": str(exc)})


def extract_blocks(pdf_path: Path) -> tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """
    Return the native JSON list of blocks produced by Marker.
    """
    try:
        from extractor.core.converters.pdf import PdfConverter
        from extractor.core.models import create_model_dict
    except Exception as exc:
        # If imports fail, attempt simple fallback if allowed
        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
            blocks = fallback_simple_extract(pdf_path, tmp)
            return blocks, {}
        raise RuntimeError(
            "Marker internals unavailable. Ensure project-specific Marker modules are installed."
        ) from exc

    # Create model dictionary
    models = create_model_dict()
    predictor_presence = {
        "detection_model": bool(models.get("detection_model")),
        "layout_model": bool(models.get("layout_model")),
        "recognition_model": bool(models.get("recognition_model")),
        "table_rec_model": bool(models.get("table_rec_model")),
        "texify_model": bool(models.get("texify_model")),
    }

    # Create config
    config = {
        "use_llm": False,
        "batch_multiplier": 1,
        "disable_multiprocessing": True,
    }

    # Create the PDF converter
    converter = PdfConverter(
        artifact_dict=models,
        config=config,
    )

    # Build the document
    try:
        document = converter.build_document(str(pdf_path))
    except Exception as exc:
        logger.error(f"Marker document building failed: {exc}")
        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            logger.warning("Falling back to simple extraction mode")
            try:
                tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
                blocks = fallback_simple_extract(pdf_path, tmp)
                logger.info(f"Simple extraction succeeded, extracted {len(blocks)} blocks")
                return blocks, predictor_presence
            except Exception as fallback_error:
                logger.error(f"Simple extraction fallback also failed: {fallback_error}")
                if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                    raise RuntimeError(f"Both marker and simple extraction failed: {exc}") from exc
                return [], predictor_presence
        else:
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                raise RuntimeError(f"Marker extraction failed: {exc}") from exc
            return [], predictor_presence

    fitz_doc = None
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
                ]:
                    block_dict = {
                        "block_type": block.block_type.name,
                        "page_idx": page.page_id,
                        "page": page.page_id,
                    }

                    # Get text content
                    if hasattr(block, "raw_text"):
                        try:
                            block_dict["text"] = block.raw_text(document)
                        except Exception:
                            block_dict["text"] = getattr(block, "text", "")
                    else:
                        block_dict["text"] = getattr(block, "text", "")

                    # Font info logic (simplified)
                    try:
                        spans = block.contained_blocks(document, (BlockTypes.Span,))
                        if spans:
                            s0 = spans[0]
                            font_name = getattr(s0, "font", None)
                            font_size = None
                            try:
                                val = getattr(s0, "font_size", None)
                                if val is not None:
                                    font_size = float(val)
                            except Exception:
                                pass
                            
                            first_span_font = {"name": font_name, "size": font_size}
                            
                            # styles
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
                            if bx is not None:
                                block_dict["bbox"] = [float(v) for v in bx]
                        except Exception:
                            pass

                    # Confidence / Quality
                    try:
                        surya_conf = getattr(block, "confidence", None)
                        if surya_conf is not None:
                            block_dict["surya_confidence"] = float(surya_conf)
                    except Exception:
                        pass
                    
                    try:
                        if hasattr(block, "calculate_quality_score"):
                            block_dict["quality_score"] = float(block.calculate_quality_score())
                    except Exception:
                        pass
                    
                    try:
                        if getattr(block, "requires_review", False):
                            block_dict["requires_review"] = True
                    except Exception:
                        pass

                    # Suspicion
                    try:
                        block_dict["is_suspicious"] = bool(getattr(block, "is_suspicious", False))
                        reasons = getattr(block, "suspicious_reasons", None)
                        if reasons:
                            block_dict["suspicious_reasons"] = reasons
                        susp_conf = getattr(block, "suspicion_confidence", None)
                        if susp_conf is not None:
                            block_dict["suspicion_confidence"] = float(susp_conf)
                    except Exception:
                        pass

                    # Headers
                    if block_dict.get("block_type") == "SectionHeader":
                        sh = False
                        if block_dict.get("is_suspicious"):
                            sh = True
                        elif any("header" in str(r).lower() for r in block_dict.get("suspicious_reasons", [])):
                            sh = True
                        if sh:
                            block_dict["suspicious_header"] = True

                    # Normalize keys
                    block_dict.setdefault("text", "")
                    block_dict.setdefault("bbox", [0.0, 0.0, 0.0, 0.0])
                    block_dict.setdefault("page_idx", int(page.page_id) if hasattr(page, "page_id") else 0)
                    
                    try:
                        block_dict["block_id"] = int(getattr(block, "block_id", -1))
                        if hasattr(block, "id"):
                            block_dict["id"] = str(block.id)
                    except Exception:
                        pass
                        
                    blocks.append(block_dict)

    if fitz_doc:
        try:
            fitz_doc.close()
        except Exception:
            pass

    return blocks, predictor_presence


def run(
    pdf_path: Path,
    output_dir: Path = Path("data/results/pipeline"),
    timeout: int = int(os.getenv("STAGE02_TIMEOUT", "600")),
    debug: bool = False,
    no_spawn: bool = False,
    mark_all_headers_suspicious: bool = False,
    output_suffix: str = "",
) -> Path:
    """
    Extracts text and layout blocks from a PDF using Marker and saves them to a structured output directory.
    """
    # Strict-mode preflight
    try:
        strict = os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"0", "false"}
        if strict:
            from extractor.core.models import create_model_dict
            m = create_model_dict()
            required = ["detection_model", "layout_model", "ocr_error_model", "recognition_model", "table_rec_model"]
            miss = [k for k in required if k not in m or m.get(k) is None]
            if miss:
                console.print("[red]Strict mode: missing predictors -> " + ", ".join(miss) + "[/red]")
                raise RuntimeError("Strict preflight: missing predictors")
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise

    run_id = uuid.uuid4().hex
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    if not pdf_path.exists():
        console.print(f"[red]Error: PDF not found: {pdf_path}[/red]")
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    stage_output_dir = output_dir / "02_marker_extractor"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    # Logging setup per run
    try:
        logger.remove()
        logger.add(
            str(stage_output_dir / "stage_02_marker.log"),
            level="DEBUG" if debug else "INFO",
            enqueue=True,
            rotation="1 week",
            retention="14 days",
        )
    except Exception:
        pass

    console.print(f"Extracting blocks from: {pdf_path.name} (timeout {timeout}s)")
    stage_start_ts = datetime.now().isoformat()
    t_stage0 = time.monotonic()
    
    resources = {}
    sampler = None
    if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y"):
        sampler = start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
    
    # Check GPU metrics availability
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event("02_marker_extractor", "info", "gpu_metrics_unavailable", "NVML not available", {})
            )
    except Exception:
        pass

    # Record start resources
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_start"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_start"] = int(getattr(vm, "used", 0) / (1024 * 1024))
    except Exception:
        pass

    if not no_spawn and os.getenv("STAGE02_NO_SPAWN", "0").lower() in ("1", "true", "yes", "y"):
        no_spawn = True

    blocks = []
    predictor_presence = {}
    extract_duration_ms = 0

    if no_spawn:
        # Inline
        try:
            t_ex0 = time.monotonic()
            blocks, predictor_presence = extract_blocks(pdf_path)
            extract_duration_ms = int((time.monotonic() - t_ex0) * 1000)
        except Exception as exc:
            logger.exception("Stage 02 failed during inline extraction")
            console.print(f"[red]Stage 02 failed: {exc}[/red]")
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                raise RuntimeError("Stage 02 inline extraction failed") from exc
            else:
                blocks = []
    else:
        # Subprocess
        q: "mp.Queue[Dict[str, Any]]" = mp.Queue()
        p = mp.Process(target=_worker, args=(str(pdf_path), q, str(json_output_dir)), daemon=True)
        t_ex0 = time.monotonic()
        p.start()
        
        try:
            result = q.get(timeout=timeout)
        except Exception:
            elapsed = int((time.monotonic() - t_ex0))
            pid = p.pid
            console.print(f"[red]Stage 02 extractor timeout (pid={pid}, elapsed={elapsed}s)[/red]")
            diagnostics.append(make_event("02_marker_extractor", "error", "extractor_timeout", "Timeout", {}))
            errors_count += 1
            if p.is_alive():
                p.terminate()
                p.join(1)
                if p.is_alive():
                    p.kill()
            raise TimeoutError(f"Stage 02 extractor timed out after {timeout}s")
        
        p.join(5)
        extract_duration_ms = int((time.monotonic() - t_ex0) * 1000)

        if not result.get("ok", False):
            err_msg = result.get("error", "Unknown error")
            console.print(f"[red]Stage 02 failed: {err_msg}[/red]")
            diagnostics.append(make_event("02_marker_extractor", "error", "process_error", str(err_msg), {}))
            errors_count += 1
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                raise RuntimeError(f"Stage 02 failed: {err_msg}")
            
            # Continue empty
            blocks = []
        else:
            # Load from temp file
            tmp_path = Path(result.get("path", ""))
            if tmp_path.exists():
                try:
                    tmp_data = json.loads(tmp_path.read_text(encoding="utf-8"))
                    blocks = tmp_data.get("blocks") or []
                    predictor_presence = tmp_data.get("predictors", {})
                    tmp_path.unlink()
                except Exception as exc:
                    console.print(f"[red]Failed to read temp output: {exc}[/red]")
            else:
                console.print("[red]Temp output file missing[/red]")

    # Post-processing: Mark suspicious
    if mark_all_headers_suspicious:
        for b in blocks:
            if b.get("block_type") == "SectionHeader":
                b["suspicious_header"] = True

    # Deterministic sort
    try:
        blocks.sort(key=canonical_block_order_key)
    except Exception:
        pass

    suspicious_blocks = [b for b in blocks if b.get("is_suspicious")]
    
    stage_end_ts = datetime.now().isoformat()
    
    # End resources
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_end"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
    except Exception:
        pass

    if sampler:
        try:
            samples = stop_resource_sampler(sampler)
            if samples:
                resources["resource_samples"] = samples
        except Exception:
            pass

    timings = {
        "stage_start_ts": stage_start_ts,
        "stage_end_ts": stage_end_ts,
        "stage_duration_ms": int((time.monotonic() - t_stage0) * 1000),
        "extract_duration_ms": extract_duration_ms,
    }

    summary = {
        "timestamp": datetime.now().isoformat(),
        "run_id": run_id,
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "block_count": len(blocks),
        "suspicious_block_count": len(suspicious_blocks),
        "blocks": blocks,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
        "predictors_present": predictor_presence,
    }
    
    base = "02_marker_blocks"
    if output_suffix:
        base += f"_{output_suffix}"
    
    out_path = json_output_dir / f"{base}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    console.print(f"📄 Saved {len(blocks)} blocks to: {out_path}")
    
    return out_path
