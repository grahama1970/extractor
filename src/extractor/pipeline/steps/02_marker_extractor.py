#!/usr/bin/env python3
"""
Stage-02: Extract native JSON blocks from a PDF using Marker
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import os
import time

try:
    import psutil  # type: ignore
except Exception:
    psutil = None
import multiprocessing as mp

import typer

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
except Exception:
    pass
from extractor.core.schema import BlockTypes
import subprocess
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    make_event,
    gpu_metrics_available,
)

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

DEBUG = False


# --------------------------------------------------------------------------- #
# Move multiprocessing worker to top-level for cross-platform compatibility (spawn/fork)
def _worker(pdf_str: str, q: "mp.Queue[Dict[str, Any]]"):
    try:
        blocks_local, presence = extract_blocks(Path(pdf_str))
        q.put({"ok": True, "blocks": blocks_local, "predictors": presence})
    except Exception as exc:
        q.put({"ok": False, "error": str(exc)})


def _fallback_simple_extract(pdf_path: Path, out_json: Path) -> List[Dict[str, Any]]:
    """Fallback: call the bundled simple_marker_extract to produce blocks JSON."""
    out_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        os.environ.get("PYTHON", "python"),
        "-m",
        "extractor.core.scripts.simple_marker_extract",
        str(pdf_path),
        str(out_json),
    ]
    try:
        subprocess.run(cmd, check=True)
        data = json.loads(out_json.read_text())
        return data.get("blocks") or []
    except Exception as e:
        raise RuntimeError(f"Fallback simple extraction failed: {e}")


def extract_blocks(pdf_path: Path) -> tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """
    Return the native JSON list of blocks produced by Marker.

    Since convert_single_pdf returns a MarkdownOutput object with markdown text,
    we need to access the converter directly to get the blocks.
    """
    try:
        from extractor.core.converters.pdf import PdfConverter
        from extractor.core.models import create_model_dict
    except Exception as e:
        # If imports fail, attempt simple fallback if allowed
        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
            blocks = _fallback_simple_extract(pdf_path, tmp)
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
    strict_mode = os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"0", "false"}
    converter = PdfConverter(
        artifact_dict=models,
        config=config,
    )

    # Build the document (this creates and processes all blocks)
    try:
        document = converter.build_document(str(pdf_path))
    except Exception as e:
        # If predictor presence is weak and fallback is allowed, try simple extractor
        if os.getenv("STAGE02_ALLOW_SIMPLE", "1").lower() in ("1", "true", "yes", "y"):
            tmp = Path(os.getenv("STAGE02_TMP", "/tmp")) / f"marker_simple_{uuid.uuid4().hex}.json"
            blocks = _fallback_simple_extract(pdf_path, tmp)
            return blocks, predictor_presence
        raise

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
                        except:
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
                            except Exception:
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
                                    except Exception:
                                        font_weight = None
                                first_span_font["bold"] = is_bold
                                first_span_font["italic"] = is_italic
                                if font_weight is not None:
                                    first_span_font["weight"] = font_weight
                            except Exception:
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
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                            block_dict["first_span_font"] = first_span_font
                    except Exception:
                        pass

                    # Add bbox if available - ensure JSON-safe list of floats
                    if hasattr(block, "polygon") and getattr(block, "polygon"):
                        try:
                            bx = getattr(block.polygon, "bbox", None)
                            if bx is not None:
                                block_dict["bbox"] = [float(v) for v in bx]
                        except Exception:
                            pass

                    # Add Surya/marker confidence and derived quality score
                    try:
                        surya_conf = getattr(block, "confidence", None)
                        if surya_conf is not None:
                            block_dict["surya_confidence"] = float(surya_conf)
                    except Exception:
                        pass
                    try:
                        # Derive quick quality score factoring suspicion
                        # Uses Block.calculate_quality_score() which applies penalties
                        # based on suspicion confidence and number of reasons.
                        if hasattr(block, "calculate_quality_score"):
                            q = block.calculate_quality_score()
                            block_dict["quality_score"] = float(q)
                    except Exception:
                        pass
                    try:
                        req_review = getattr(block, "requires_review", None)
                        if req_review:
                            block_dict["requires_review"] = True
                    except Exception:
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
                    except Exception:
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
                    except Exception:
                        pass
                    blocks.append(block_dict)

    # Close PyMuPDF if used
    try:
        if fitz_doc is not None:
            fitz_doc.close()
    except Exception:
        pass

    return blocks, predictor_presence


# --------------------------------------------------------------------------- #
def run(
    pdf_path: Path = typer.Argument(..., help="Path to the clean PDF file from Stage 01."),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "--output-dir", "-o", help="Parent directory for pipeline results."
    ),
    timeout: int = typer.Option(
        int(os.getenv("STAGE02_TIMEOUT", "600")),
        "--timeout",
        help="Max seconds allowed for extraction before timing out (default from STAGE02_TIMEOUT).",
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Enable verbose logging to a stage log file."
    ),
    no_spawn: bool = typer.Option(
        False, "--no-spawn/--spawn", help="Run extraction inline (no subprocess, easier debugging)."
    ),
    mark_all_headers_suspicious: bool = typer.Option(
        False,
        "--mark-all-headers-suspicious/--no-mark-all-headers-suspicious",
        help="Force every SectionHeader to include 'suspicious_header': true to feed Stage 03 verification.",
    ),
    output_suffix: str = typer.Option(
        "",
        "--output-suffix",
        help="Append a suffix to the output JSON filename (e.g., 'verify_all' → 02_marker_blocks_verify_all.json)",
    ),
):
    """
    Extracts text and layout blocks from a PDF using Marker and saves them to a structured output directory.
    """
    # Strict-mode preflight: ensure predictors exist
    try:
        strict = os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"0", "false"}
        if strict:
            from extractor.core.models import create_model_dict
            m = create_model_dict()
            required = [
                "detection_model",
                "layout_model",
                "ocr_error_model",
                "recognition_model",
                "table_rec_model",
            ]
            miss = [k for k in required if k not in m or m.get(k) is None]
            if miss:
                console.print("[red]Strict mode: missing predictors -> " + ", ".join(miss) + "[/red]")
                console.print("[yellow]Hint: activate venv and run: `uv sync --extra accurate`[/yellow]")
                raise typer.Exit(1)
    except Exception as _e:
        console.print(f"[red]Strict preflight failed: {_e}[/red]")
        console.print("[yellow]Hint: `uv sync --extra accurate`[/yellow]")
        raise typer.Exit(1)
    run_id = uuid.uuid4().hex
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    # Force CPU usage to avoid CUDA OOM (set only for this stage process)
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    if not pdf_path.exists():
        console.print(f"[red]Error: PDF not found: {pdf_path}[/red]")
        raise typer.Exit(1)

    # Define clear output paths for this stage
    stage_output_dir = output_dir / "02_marker_extractor"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    # Configure logging sink per stage run
    try:
        logger.remove()
        logger.add(
            str(stage_output_dir / "stage_02_marker.log"),
            level="DEBUG" if debug else "INFO",
            enqueue=True,
            backtrace=True,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
    except Exception:
        pass

    console.print(f"Extracting blocks from: {pdf_path.name} (timeout {timeout}s)")
    stage_start_ts = __import__("datetime").datetime.now().isoformat()
    t_stage0 = time.monotonic()
    start_time = time.time()
    resources = {}
    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event(
                    "02_marker_extractor",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception:
        pass
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_start"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_start"] = int(getattr(vm, "used", 0) / (1024 * 1024))
    except Exception:
        pass

    if no_spawn:
        # Inline execution (best for debugging)
        try:
            t_ex0 = time.monotonic()
            blocks, predictor_presence = extract_blocks(pdf_path)
            extract_duration_ms = int((time.monotonic() - t_ex0) * 1000)
        except Exception as e:
            logger.exception("Stage 02 failed during inline extraction")
            console.print(f"[red]Stage 02 failed: {e}[/red]")
            raise typer.Exit(1)
    else:
        # Run extraction in a separate process so we can enforce a hard timeout
        # Worker moved to top-level to be picklable in 'spawn' start method environments (Windows/macOS).
        q: "mp.Queue[Dict[str, Any]]" = mp.Queue()
        p = mp.Process(target=_worker, args=(str(pdf_path), q), daemon=True)
        t_ex0 = time.monotonic()
        p.start()
        p.join(timeout)

        if p.is_alive():
            console.print(
                f"[red]Stage 02 timed out after {timeout}s. Terminating extractor...[/red]"
            )
            try:
                diagnostics.append(
                    make_event(
                        "02_marker_extractor",
                        "error",
                        "extractor_timeout",
                        f"Timed out after {timeout}s",
                        {"pdf_path": str(pdf_path), "timeout": timeout},
                    )
                )
                errors_count += 1
            except Exception:
                pass
            try:
                p.terminate()
                p.join(2)
            finally:
                if p.is_alive():
                    p.kill()
                    p.join(1)
            raise typer.Exit(1)

        extract_duration_ms = int((time.monotonic() - t_ex0) * 1000)
        if q.empty():
            console.print("[red]Stage 02 failed: no data returned from extractor process[/red]")
            raise typer.Exit(1)

        result = q.get()
        if not result.get("ok", False):
            logger.exception("Stage 02 failed during extraction")
            try:
                diagnostics.append(
                    make_event(
                        "02_marker_extractor",
                        "error",
                        "extractor_process_error",
                        str(result.get("error", "Unknown error")),
                        {"pdf_path": str(pdf_path)},
                    )
                )
                errors_count += 1
            except Exception:
                pass
            console.print(f"[red]Stage 02 failed: {result.get('error', 'Unknown error')}[/red]")
            raise typer.Exit(1)

        blocks = result["blocks"]
        predictor_presence = result.get("predictors", {})

    # Optional: force-tag all SectionHeader blocks as suspicious_header for Stage 03 testing
    if mark_all_headers_suspicious:
        try:
            for b in blocks:
                if b.get("block_type") == "SectionHeader":
                    b["suspicious_header"] = True
        except Exception:
            pass

    suspicious_blocks = [b for b in blocks if b.get("is_suspicious")]
    # predictor mode flags
    strict = os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"0", "false"}
    missing = [k for k, v in (predictor_presence or {}).items() if not v]
    fallback_mode = (not strict) and bool(missing)
    if strict:
        predictor_mode = "strict_all_present"
    else:
        predictor_mode = "lenient_missing_predictors" if missing else "lenient_all_present"

    stage_end_ts = __import__("datetime").datetime.now().isoformat()
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_end"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_end"] = int(getattr(vm, "used", 0) / (1024 * 1024))
    except Exception:
        pass
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = {
        "stage_start_ts": stage_start_ts,
        "stage_end_ts": stage_end_ts,
        "stage_duration_ms": int((time.monotonic() - t_stage0) * 1000),
        "extract_duration_ms": int(locals().get("extract_duration_ms", 0)),
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
        "fallback_mode": fallback_mode,
        "predictor_mode": predictor_mode,
    }

    base = "02_marker_blocks"
    if output_suffix:
        safe = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in output_suffix.strip()
        )
        if safe:
            base = f"{base}_{safe}"
    out_path = json_output_dir / f"{base}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    console.print(f"📄 Saved {len(blocks)} blocks to: {out_path}")
    if suspicious_blocks:
        console.print(
            f"⚠️  Found {len(suspicious_blocks)} suspicious blocks for Stage 03 verification."
        )


# --------------------------------------------------------------------------- #
def test():
    """Smoke test."""
    console.print("[yellow]Test mode[/yellow]")
    blocks = [
        {"block_type": "SectionHeader", "text": "4.1.5.4 BHT submodule", "page_idx": 0},
        {"block_type": "Text", "text": "BHT is implemented as a memory...", "page_idx": 0},
    ]
    console.print(json.dumps(blocks, indent=2))


def debug_bundle(
    bundle: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Bundle JSON with key 'clean_pdf'",
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
):
    """Run Stage 02 from a single JSON bundle."""
    stage_output_dir = Path(output_dir) / "02_marker_extractor"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    try:
        data = json.loads(bundle.read_text())
        clean_pdf = Path(data.get("clean_pdf") or "")
        if not clean_pdf.exists():
            raise ValueError("Bundle must include existing 'clean_pdf' path")
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    try:
        blocks, _predictors = extract_blocks(clean_pdf)
    except Exception as e:
        typer.secho(f"Extraction failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    suspicious_blocks = [b for b in blocks if b.get("is_suspicious")]
    _timings = {
        "stage_start_ts": datetime.now().isoformat(),
        "stage_end_ts": datetime.now().isoformat(),
        "stage_duration_ms": 0,
    }
    _resources = {}
    result = {
        "timestamp": datetime.now().isoformat(),
        "source_pdf": str(clean_pdf),
        "status": "Completed",
        "block_count": len(blocks),
        "suspicious_block_count": len(suspicious_blocks),
        "blocks": blocks,
        "timings": _timings,
        "resources": _resources,
    }
    out_path = json_output_dir / "02_marker_blocks.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    console.print(f"[green]Debug bundle: saved {len(blocks)} blocks to {out_path}")


# --------------------------------------------------------------------------- #
def build_cli():
    import typer as _typer

    app = _typer.Typer(help="Stage-02: native JSON block extractor")
    app.command(name="run")(run)
    app.command(name="test")(test)
    app.command(name="debug-bundle")(debug_bundle)
    return app


if __name__ == "__main__":
    build_cli()()
