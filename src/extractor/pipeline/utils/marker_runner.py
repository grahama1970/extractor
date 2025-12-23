"""Stage 02 marker extractor runner."""
import json, os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error
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
                raise RuntimeError("Strict preflight: missing predictors")
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        console.print(f"[red]Strict preflight failed: {_e}[/red]")
        console.print("[yellow]Hint: `uv sync --extra accurate`[/yellow]")
        raise RuntimeError(f"Strict preflight failed: {_e}")
    run_id = uuid.uuid4().hex
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    # Force CPU usage to avoid CUDA OOM (set only for this stage process)
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    if not pdf_path.exists():
        console.print(f"[red]Error: PDF not found: {pdf_path}[/red]")
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

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
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
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
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        pass
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_start"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_start"] = int(getattr(vm, "used", 0) / (1024 * 1024))
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        pass

    # Allow env override to force inline (no-spawn) execution — useful on
    # platforms where multiprocessing.Queue triggers PermissionError.
    if not no_spawn and os.getenv("STAGE02_NO_SPAWN", "0").lower() in ("1", "true", "yes", "y"):
        no_spawn = True

    if no_spawn:
        # Inline execution (best for debugging)
        try:
            t_ex0 = time.monotonic()
            blocks, predictor_presence = extract_blocks(pdf_path)
            extract_duration_ms = int((time.monotonic() - t_ex0) * 1000)
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            logger.exception("Stage 02 failed during inline extraction")
            console.print(f"[red]Stage 02 failed: {e}[/red]")
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                raise RuntimeError("Stage 02 inline extraction failed") from e
            else:
                logger.warning("Continuing with empty blocks due to fail-fast disabled")
                blocks = []
                predictor_presence = False
                extract_duration_ms = int((time.monotonic() - t_ex0) * 1000)
    else:
        # Run extraction in a separate process with temp-file handoff to avoid mp.Queue backpressure
        q: "mp.Queue[Dict[str, Any]]" = mp.Queue()
        p = mp.Process(target=_worker, args=(str(pdf_path), q, str(json_output_dir)), daemon=True)
        t_ex0 = time.monotonic()
        p.start()

        # Read small result first, then join (prevents child blocking on q.put for large payloads)
        try:
            result = q.get(timeout=timeout)
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            elapsed = int((time.monotonic() - t_ex0))
            pid = p.pid if p and p.pid else None
            console.print(
                f"[red]Stage 02 extractor produced no result within {timeout}s (pid={pid}, elapsed={elapsed}s)[/red]"
            )
            try:
                diagnostics.append(
                    make_event(
                        "02_marker_extractor",
                        "error",
                        "extractor_timeout",
                        f"No result within {timeout}s (pid={pid}, elapsed={elapsed}s)",
                        {"pdf_path": str(pdf_path), "timeout": timeout, "pid": pid, "elapsed_sec": elapsed},
                    )
                )
                errors_count += 1
            except Exception as exc:
                log_stage_error('02_marker_extractor', exc, {'context': '02'})
                raise
                pass
            # Stop sampler explicitly on timeout
            try:
                samples = stop_resource_sampler(sampler) if sampler else []
                if samples:
                    resources.setdefault("resource_samples", samples)
            except Exception as exc:
                log_stage_error('02_marker_extractor', exc, {'context': '02'})
                raise
                pass
            if p.is_alive():
                try:
                    p.terminate()
                    p.join(2)
                finally:
                    if p.is_alive():
                        p.kill()
                        p.join(1)
            raise TimeoutError(f"Stage 02 extractor timed out after {timeout}s")

        # Allow child to exit; do not block indefinitely
        p.join(5)
        extract_duration_ms = int((time.monotonic() - t_ex0) * 1000)

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
            except Exception as exc:
                log_stage_error('02_marker_extractor', exc, {'context': '02'})
                raise
                pass
            console.print(f"[red]Stage 02 failed: {result.get('error', 'Unknown error')}[/red]")
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                raise RuntimeError(f"Stage 02 failed: {result.get('error', 'Unknown error')}")
            else:
                logger.warning("Continuing with empty blocks due to fail-fast disabled")
                blocks = []
                predictor_presence = False
                extract_duration_ms = int((time.monotonic() - t_ex0) * 1000)

        # Load large payload from temp file written by the child process
        tmp_path = Path(result.get("path", ""))
        if not tmp_path.exists():
            console.print("[red]Stage 02 failed: extractor output path missing[/red]")
            raise FileNotFoundError("Extractor output path missing")
        try:
            tmp_data = json.loads(tmp_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            console.print(f"[red]Stage 02 failed: could not read extractor output: {e}[/red]")
            raise RuntimeError(f"Could not read extractor output: {e}")
        blocks = tmp_data.get("blocks") or []
        predictor_presence = tmp_data.get("predictors", {})
        try:
            tmp_path.unlink()
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            pass

    # Optional: force-tag all SectionHeader blocks as suspicious_header for Stage 03 testing
    if mark_all_headers_suspicious:
        try:
            for b in blocks:
                if b.get("block_type") == "SectionHeader":
                    b["suspicious_header"] = True
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            pass

    # --- Optional: synthesize Figure blocks from embedded images when none exist ---
    try:
        # Always enable synthesis when offline/lenient mode is allowed
        offline_enabled = os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"1", "true", "yes", "y"}
        synth_fig_env = os.getenv("STAGE02_FIGURE_FROM_IMAGES", "")
        synth_fig = True if offline_enabled else (synth_fig_env.lower() in {"", "1", "true", "yes", "y"})

        # Tunables (env)
        try:
            synth_min_w = int(os.getenv("STAGE02_SYNTH_FIG_MIN_WIDTH", "24"))
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            synth_min_w = 24
        try:
            synth_min_h = int(os.getenv("STAGE02_SYNTH_FIG_MIN_HEIGHT", "24"))
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            synth_min_h = 24
        try:
            synth_max_area_ratio = float(os.getenv("STAGE02_SYNTH_FIG_MAX_AREA_RATIO", "0.9"))
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            synth_max_area_ratio = 0.90

        has_fig = any((b.get("block_type") in ("Figure", "Image")) for b in blocks)
        if synth_fig and not has_fig:
            import fitz  # type: ignore

            def _iou(a: "fitz.Rect", b: "fitz.Rect") -> float:
                iw = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
                ih = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
                inter = iw * ih
                ua = (a.width * a.height) + (b.width * b.height) - inter
                return (inter / ua) if ua > 0 else 0.0

            doc = fitz.open(str(pdf_path))
            total_synth = 0
            per_page_counts: dict[int, int] = {}
            try:
                for pno in range(len(doc)):
                    try:
                        imgs = doc[pno].get_images(full=True)
                    except Exception as exc:
                        log_stage_error('02_marker_extractor', exc, {'context': '02'})
                        raise
                        imgs = []
                    if not imgs:
                        continue

                    page_rect = doc[pno].rect
                    collected: list["fitz.Rect"] = []

                    # Walk all images on the page and all their rects
                    for im in imgs:
                        try:
                            xref = im[0]
                            rects = doc[pno].get_image_rects(xref)
                        except Exception as exc:
                            log_stage_error('02_marker_extractor', exc, {'context': '02'})
                            raise
                            rects = []
                        if not rects:
                            continue

                        for r in rects:
                            rr = (r & page_rect)
                            if rr.is_empty:
                                continue

                            pa = float(page_rect.width * page_rect.height) or 1.0
                            ra = float(rr.width * rr.height)

                            # Size / area filters (configurable)
                            if rr.width < synth_min_w or rr.height < synth_min_h:
                                continue
                            if (ra / pa) > synth_max_area_ratio:
                                continue

                            # Deduplicate near-identical rects (by IoU)
                            if any(_iou(rr, ex) > 0.90 for ex in collected):
                                continue
                            collected.append(rr)

                    if not collected:
                        continue

                    # Emit one synthesized Figure per rect
                    per_page_counts[pno] = 0
                    for idx, rr in enumerate(collected):
                        blocks.append(
                            {
                                "block_type": "Figure",
                                "page_idx": pno,
                                "page": pno,
                                "bbox": [float(rr.x0), float(rr.y0), float(rr.x1), float(rr.y1)],
                                "id": f"SYNTHFIG_P{pno}_{idx}",
                                "source": "synth_image_fallback",
                            }
                        )
                        per_page_counts[pno] += 1
                        total_synth += 1

                # Diagnostics
                if total_synth == 0:
                    diagnostics.append(
                        make_event(
                            "02_marker_extractor",
                            "warning",
                            "figure_synth_failed",
                            "No images met synthesis thresholds on any page",
                            {
                                "min_width": synth_min_w,
                                "min_height": synth_min_h,
                                "max_area_ratio": synth_max_area_ratio,
                            },
                        )
                    )
                else:
                    diagnostics.append(
                        make_event(
                            "02_marker_extractor",
                            "info",
                            "figure_synth_applied",
                            f"Synthesized {total_synth} Figure block(s) from embedded images",
                            {
                                "pages_with_synth": len(per_page_counts),
                                "per_page_counts": per_page_counts,
                                "min_width": synth_min_w,
                                "min_height": synth_min_h,
                                "max_area_ratio": synth_max_area_ratio,
                                "offline_enabled": bool(offline_enabled),
                            },
                        )
                    )
            finally:
                try:
                    doc.close()
                except Exception as exc:
                    log_stage_error('02_marker_extractor', exc, {'context': '02'})
                    raise
                    pass
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        try:
            diagnostics.append(
                make_event(
                    "02_marker_extractor",
                    "error",
                    "figure_synth_exception",
                    str(_e),
                    {},
                )
            )
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            pass

    # Enforce deterministic reading order for all downstream consumers.
    # Sort at the very end so that both native and synthesized blocks are
    # included in the canonical layout.
    try:
        blocks.sort(key=canonical_block_order_key)
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        # Best-effort ordering; never fail Stage 02 solely on sort issues.
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
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        pass
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
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
    return out_path

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
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
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
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        print(f"Failed to load bundle: {e}")
        raise ValueError(f"Failed to load bundle: {e}")

    try:
        blocks, _predictors = extract_blocks(clean_pdf)
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        print(f"Extraction failed: {e}")
        raise RuntimeError(f"Extraction failed: {e}")

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
## CLI removed: call run(...) directly or use a debug harness.


## No __main__: import and call run(...)
if __name__ == "__main__":
    # Minimal entry: PDF path and optional OUT_DIR
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv())
    except Exception as exc:
        log_stage_error('02_marker_extractor', exc, {'context': '02'})
        raise
        pass
    import sys
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.02_marker_extractor INPUT_PDF [OUT_DIR]",
            file=sys.stderr,
        )
        sys.exit(2)
    if argv[0] == "sanity":
        sys.exit(sanity())
    # Compatibility with runners using `run <PDF> -o <OUT>`
    if argv[0] == "run":
        try:
            pdf_path = Path(argv[1])
        except Exception as exc:
            log_stage_error('02_marker_extractor', exc, {'context': '02'})
            raise
            print("Missing input PDF", file=sys.stderr)
            sys.exit(2)
        out_dir = Path("data/results/pipeline")
        if "-o" in argv:
            try:
                out_dir = Path(argv[argv.index("-o") + 1])
            except Exception as exc:
                log_stage_error('02_marker_extractor', exc, {'context': '02'})
                raise
                pass
    else:
        pdf_path = Path(argv[0])
        out_dir = Path(argv[1]) if len(argv) > 1 else Path("data/results/pipeline")
    out = run(pdf_path=pdf_path, output_dir=out_dir)
    print(str(out))
