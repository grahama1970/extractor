#!/usr/bin/env python3
"""
Stage-02: Extract native JSON blocks from a PDF using Marker

Policy (2025-10-08):
- No PyMuPDF/text heuristic fallback is permitted for Stage 02 extraction.
- This stage MUST use Marker internals (PdfConverter + create_model_dict).
- PyMuPDF is allowed only for annotation handling/visualization in other stages.
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
import hashlib
from extractor.pipeline.utils.pipeline_event_logger import log_stage_event
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


def _safe_version(mod_name: str):
    try:
        mod = __import__(mod_name)
        for attr in ("__version__", "version", "VERSION"):
            v = getattr(mod, attr, None)
            if v:
                return str(v)
    except Exception:
        return None
    return None


def _write_env_snapshot(out_dir: Path, pdf_path: Path) -> None:
    """Write a compact environment + imports snapshot for debugging Stage 02 regressions."""
    try:
        import sys, platform
        # Selective env snapshot with redaction of sensitive keys
        keys = [
            "OFFLINE_PDF_PREDICTORS",
            "PYTHONPATH",
            "LITELLM_DEFAULT_MODEL",
            "LITELLM_VLM_MODEL",
            "LITELLM_MED_VLM_MODEL",
            "LITELLM_SMALL_VLM_MODEL",
            "CHUTES_API_BASE",
            "OPENAI_BASE_URL",
        ]
        redact_pat = (
            "api_key",
            "apikey",
            "authorization",
            "bearer",
            "token",
            "secret",
            "password",
            "access_key",
            "private_key",
            "client_secret",
        )
        env: Dict[str, Any] = {}
        for k in keys:
            v = os.getenv(k)
            if v is None:
                continue
            if any(pat in k.lower() for pat in redact_pat):
                env[k] = "<redacted>"
            else:
                env[k] = v
        imports = {
            "fitz": _safe_version("fitz"),
            "surya_ocr": _safe_version("surya_ocr"),
            "torch": _safe_version("torch"),
            "transformers": _safe_version("transformers"),
            "spacy": _safe_version("spacy"),
            "faiss": _safe_version("faiss"),
            "litellm": _safe_version("litellm"),
            "scillm": _safe_version("scillm"),
        }
        # Optional git rev
        git_rev = None
        try:
            import subprocess as _sp
            git_rev = (
                _sp.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(Path.cwd()))
                .decode()
                .strip()
            )
        except Exception:
            pass

        # Torch/CUDA snapshot
        cuda = None
        cuda_count = None
        try:
            import torch as _torch  # type: ignore
            cuda = bool(getattr(_torch, "cuda", None) and _torch.cuda.is_available())
            cuda_count = int(_torch.cuda.device_count()) if hasattr(_torch, "cuda") else 0
        except Exception:
            pass

        payload = {
            "timestamp": datetime.now().isoformat(),
            "python": sys.version,
            "platform": platform.platform(),
            "executable": sys.executable,
            "cwd": str(Path.cwd()),
            "pdf": str(pdf_path),
            "git_rev": git_rev,
            "cuda_available": cuda,
            "cuda_device_count": cuda_count,
            "env": env,
            "imports": imports,
            "sys_path_head": sys.path[:10],
        }
        (out_dir / "02_env_snapshot.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False)
        )
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Move multiprocessing worker to top-level for cross-platform compatibility (spawn/fork)
def _worker(pdf_str: str, q: "mp.Queue[Dict[str, Any]]"):
    try:
        blocks_local, presence = extract_blocks(Path(pdf_str))
        q.put({"ok": True, "blocks": blocks_local, "predictors": presence})
    except Exception as exc:
        # Persist a structured error for parent to pick up
        try:
            import traceback as _tb
            pdf_path = Path(pdf_str)
            err_dir = Path(os.getenv("STAGE02_ERROR_DIR", str(pdf_path.parent)))
            err_dir.mkdir(parents=True, exist_ok=True)
            (err_dir / "02_error.json").write_text(
                json.dumps(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "pdf": str(pdf_path),
                        "error": str(exc),
                        "where": "worker",
                        "traceback": _tb.format_exc(),
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        except Exception:
            pass
        q.put({"ok": False, "error": str(exc)})


def extract_blocks(pdf_path: Path) -> tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """
    Return the native JSON list of blocks produced by Marker.

    Since convert_single_pdf returns a MarkdownOutput object with markdown text,
    we need to access the converter directly to get the blocks.
    """
    # Enforce Marker-only extraction (no heuristics) regardless of env flags
    try:
        from extractor.core.converters.pdf import PdfConverter
        from extractor.core.models import create_model_dict
    except Exception as e:
        raise RuntimeError(
            "Stage 02 requires Marker internals (PdfConverter + create_model_dict). "
            "PyMuPDF/text heuristics are not allowed for extraction. Install extras: "
            "`uv sync --extra accurate`."
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
    try:
        logger.info("02:extract_blocks pdf=%s", pdf_path)
    except Exception:
        pass
    try:
        converter = PdfConverter(
            artifact_dict=models,
            config=config,
        )
    except Exception as exc:
        try:
            import traceback as _tb
            err_payload = {
                "timestamp": datetime.now().isoformat(),
                "pdf": str(pdf_path),
                "error": str(exc),
                "where": "PdfConverter.__init__",
                "traceback": _tb.format_exc(),
                "predictors_present": predictor_presence,
                "note": (
                    "Stage 02 must use Marker internals only. "
                    "No PyMuPDF/text heuristic fallback is allowed."
                ),
            }
            err_dir = Path(os.getenv("STAGE02_ERROR_DIR", str(pdf_path.parent)))
            err_dir.mkdir(parents=True, exist_ok=True)
            (err_dir / "02_error.json").write_text(
                json.dumps(err_payload, indent=2, ensure_ascii=False)
            )
        except Exception:
            pass
        try:
            logger.exception("Stage 02 PdfConverter init failed: %s", exc)
        except Exception:
            pass
        raise

    # Build the document (this creates and processes all blocks)
    # Hardened with explicit diagnostics so DI/config errors are actionable.
    try:
        document = converter.build_document(str(pdf_path))
    except Exception as exc:
        # Write a rich error payload for faster triage (used by CI + batch runners)
        try:
            import traceback as _tb
            err_payload = {
                "timestamp": datetime.now().isoformat(),
                "pdf": str(pdf_path),
                "error": str(exc),
                "traceback": _tb.format_exc(),
                "predictors_present": predictor_presence,
                "note": (
                    "Stage 02 must use Marker internals only. "
                    "No PyMuPDF/text heuristic fallback is allowed."
                ),
            }
            # Default to pipeline results if available, else alongside the PDF
            err_dir = (Path(os.getenv("STAGE02_ERROR_DIR", "")) or pdf_path.parent)
            if not isinstance(err_dir, Path):
                err_dir = Path(str(err_dir))
            # Prefer stage output dir when run() sets it; otherwise create sibling
            try:
                err_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            (Path(err_dir) / "02_error.json").write_text(
                json.dumps(err_payload, indent=2, ensure_ascii=False)
            )
        except Exception:
            pass
        # Mirror to logger with backtrace
        try:
            logger.exception("Stage 02 build_document failed: %s", exc)
        except Exception:
            pass
        raise

    # Optional: open PyMuPDF for span color extraction
    fitz_doc = None
    try:
        import fitz  # type: ignore

        try:
            fitz_doc = fitz.open(str(pdf_path))
        except Exception:
            fitz_doc = None
    except Exception:
        fitz_doc = None
    # Cache PyMuPDF page text once per page to avoid repeated parsing
    page_text_cache: Dict[int, Any] = {}

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
                        except Exception:
                            block_dict["text"] = getattr(block, "text", "")
                    else:
                        block_dict["text"] = getattr(block, "text", "")

                    # Capture the block bbox (if available) so overlays align with real content
                    try:
                        if getattr(block, "polygon", None) is not None and getattr(block.polygon, "bbox", None):
                            x0, y0, x1, y1 = block.polygon.bbox
                            block_dict["bbox"] = [float(x0), float(y0), float(x1), float(y1)]
                    except Exception:
                        pass

                    # Split inline header + body if present, e.g., "1.1 Title. Body text ..."
                    try:
                        if (
                            block_dict["block_type"] == "SectionHeader"
                            and isinstance(block_dict.get("text"), str)
                        ):
                            import re as _re
                            t = block_dict["text"].strip()
                            m = _re.match(r"^(?P<prefix>(?:\d+(?:[.\-](?:\d+|[A-Za-z]+))*|[IVXLCDM]+))[.)]?\s+(?P<title>[^.].*?)(?:\.|$)\s*(?P<body>.+)?$", t)
                            if m and m.group("body") and len(m.group("body").split()) >= 3:
                                header_text = f"{m.group('prefix')} {m.group('title').strip()}"
                                header_entry = dict(block_dict)
                                header_entry["text"] = header_text
                                blocks.append(header_entry)
                                body_entry = dict(block_dict)
                                body_entry["block_type"] = "Text"
                                body_entry["text"] = m.group("body").strip()
                                blocks.append(body_entry)
                                continue
                    except Exception:
                        pass

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
                    import re as _re
                    # Demote sentence-like table blocks to Paragraph
                    if block_dict.get("block_type") == "Table":
                        _t = (block_dict.get("text") or "").strip()
                        if _t:
                            words = _t.split()
                            letters = [ch for ch in _t if ch.isalpha()]
                            lower_ratio = (sum(ch.islower() for ch in letters)/len(letters)) if letters else 0.0
                            has_term = _t.endswith(".") or _t.endswith(";") or _t.endswith("?")
                            verbs={"is","are","was","were","be","been","being","has","have","had","can","could","should","may","might","will","shall","must","does","do","did"}
                            has_verb=any(w.lower().strip(",.;:!?") in verbs for w in words)
                            if (has_term or has_verb) and (len(words)>=4 or lower_ratio>=0.5):
                                block_dict["block_type"] = "Text"
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
    # Preflight: predictors must exist (no fallback allowed)
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
        miss = [k for k in required if k not in m or m.get(k) is None]
        if miss:
            console.print("[red]Missing predictors -> " + ", ".join(miss) + "[/red]")
            console.print("[yellow]Hint: activate venv and run: `uv sync --extra accurate`[/yellow]")
            raise typer.Exit(1)
    except Exception as _e:
        console.print(f"[red]Preflight failed: {_e}[/red]")
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
    # Ensure all error payloads land under this stage dir
    try:
        os.environ["STAGE02_ERROR_DIR"] = str(stage_output_dir)
    except Exception:
        pass
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

    # Write env/imports snapshot early for debugging setup regressions
    _write_env_snapshot(stage_output_dir, pdf_path)

    display_timeout = (f"{timeout}s" if timeout and timeout>0 else "no-limit")
    console.print(f"Extracting blocks from: {pdf_path.name} (timeout {display_timeout})")
    log_stage_event("02_marker_extractor", "start", run_id=run_id, pdf=str(pdf_path))
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
        # Allow the worker to spawn internal workers if underlying libs require it
        p = mp.Process(target=_worker, args=(str(pdf_path), q), daemon=False)
        t_ex0 = time.monotonic()
        p.start()
        p.join(None if (timeout is None or timeout<=0) else timeout)

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
                        "Timed out (no explicit limit)",
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
    # predictor mode flags (Stage 02 is strict-only by policy)
    missing = [k for k, v in (predictor_presence or {}).items() if not v]
    fallback_mode = False
    predictor_mode = "strict_missing_predictors" if missing else "strict_all_present"

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
    # Deterministic ordering & content hash
    try:
        def _blk_key(b):
            txt = (b.get("text") or "")[:64]
            h = hashlib.sha256(txt.encode("utf-8", "ignore")).hexdigest()[:8]
            return (int(b.get("page_idx", 0)), str(b.get("block_type", "")), int(b.get("block_id", 0) or 0), h)
        blocks = sorted(blocks, key=_blk_key)
    except Exception:
        pass
    try:
        hasher = hashlib.sha256()
        for b in blocks:
            core = {
                "p": b.get("page_idx"),
                "t": b.get("block_type"),
                "id": b.get("block_id"),
                "txt": (b.get("text") or "")[:200],
            }
            hasher.update(json.dumps(core, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        blocks_hash = hasher.hexdigest()
    except Exception:
        blocks_hash = None
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
        "blocks_content_hash": blocks_hash,
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
    console.print(f"📄 Saved {len(blocks)} blocks to: {out_path} (deterministic ordering applied)")
    log_stage_event(
        "02_marker_extractor",
        "end",
        run_id=run_id,
        blocks=len(blocks),
        suspicious=len(suspicious_blocks),
        content_hash=blocks_hash,
        status="Completed",
    )
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
        blk_tuple = extract_blocks(clean_pdf)
        if isinstance(blk_tuple, tuple):
            blocks, _presence = blk_tuple
        else:
            blocks = blk_tuple  # type: ignore
    except Exception as e:
        typer.secho(f"Extraction failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    # Snapshot for debug bundle run (predictor presence may be absent here)
    _write_env_snapshot(stage_output_dir, clean_pdf)

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
