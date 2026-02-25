#!/usr/bin/env python3
"""
Sequential extractor pipeline runner (function-first steps).

Location rationale
- Lives under `src/extractor/pipeline` to keep the pipeline’s main
  entrypoint co-located with the steps it orchestrates.
- Keeps imports local and predictable for VS Code debugging and for
  agents that import and call `main()` directly.

Usage
  python -m extractor.pipeline \
    --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
    --out data/results/pipeline \
    --summary-only  # optional; runs Stage 07 without LLM

Flags
  --skip-fig-descriptions  Skip Stage 06 VLM descriptions (faster, no network)
  --summary-only           Make Stage 07 text-only (no SciLLM calls)
  --skip-export            Do not write to ArangoDB in Stage 10
  --stop-on-fail           Stop at first failing step (opt-in)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
import signal
from typing import Any, Dict, Optional, Tuple
import importlib
import warnings

from dotenv import find_dotenv, load_dotenv
from loguru import logger

from extractor.pipeline.utils.run_manifest import RunManifest
from extractor.pipeline.utils.reliability import log_stage_error, write_json_strict

try:
    # Best-effort import for legacy router shutdown (kept as fallback)
    from extractor.pipeline.utils.scillm_router import close_all_routers  # type: ignore
except ImportError:
    close_all_routers = None  # type: ignore
except Exception as exc:  # pragma: no cover - unexpected
    log_stage_error("close_all_routers_import", exc)
    close_all_routers = None  # type: ignore
import os
import json
import concurrent.futures

# PDF decryption utilities
try:
    from extractor.pipeline.utils.pdf_decrypt import is_encrypted, decrypt_pdf
except ImportError:
    is_encrypted = None  # type: ignore
    decrypt_pdf = None  # type: ignore


def _maybe_decrypt_pdf(
    pdf_path: Path,
    output_dir: Path,
    args: argparse.Namespace,
) -> Tuple[Path, Optional[Dict[str, Any]], bool]:
    """Decrypt encrypted PDF if auto_decrypt is enabled.

    Returns:
        Tuple of (pdf_path_to_use, decrypt_info, was_skipped)
    """
    if pdf_path.suffix.lower() != ".pdf":
        return pdf_path, None, False

    # Check if decryption is available
    if is_encrypted is None or decrypt_pdf is None:
        return pdf_path, None, False

    # Check if PDF is encrypted
    try:
        encrypted = is_encrypted(pdf_path)
    except Exception as exc:
        logger.warning(f"Encryption check failed for {pdf_path.name}: {exc}")
        return pdf_path, None, False

    if not encrypted:
        return pdf_path, None, False

    logger.info(f"Encrypted PDF detected: {pdf_path.name}")

    # Check if auto-decrypt is enabled (defaults to True)
    auto_decrypt = getattr(args, "auto_decrypt", True)
    if not auto_decrypt:
        logger.warning(
            f"Skipping encrypted PDF {pdf_path.name} (--no-auto-decrypt). "
            "Use --auto-decrypt or provide --decrypt-password to process."
        )
        # Write skip manifest
        _write_decrypt_skip_manifest(output_dir, pdf_path, "auto_decrypt_disabled")
        return pdf_path, {"encrypted": True, "skipped": True, "reason": "auto_decrypt_disabled"}, True

    # Attempt decryption
    user_password = getattr(args, "decrypt_password", None)
    decrypted_path = output_dir / f"{pdf_path.stem}_decrypted.pdf"

    result = decrypt_pdf(
        pdf_path,
        password=user_password,
        output_path=decrypted_path,
    )

    # Write decryption info
    _write_decrypt_info(output_dir, result)

    if result.get("success"):
        logger.info(
            f"PDF decrypted successfully (method: {result.get('method', 'unknown')})"
        )
        return Path(result["decrypted_path"]), result, False
    else:
        logger.warning(
            f"PDF decryption failed for {pdf_path.name}: {result.get('error', 'unknown')}. "
            f"Use --decrypt-password to provide the correct password."
        )
        # Continue with original (may fail downstream)
        return pdf_path, result, False


def _write_decrypt_info(output_dir: Path, decrypt_info: Dict[str, Any]) -> None:
    """Write decryption info to output directory."""
    try:
        (output_dir / "decrypt_info.json").write_text(
            json.dumps(decrypt_info, indent=2)
        )
    except Exception as exc:
        logger.warning(f"Failed to write decrypt_info.json: {exc}")


def _write_decrypt_skip_manifest(
    output_dir: Path, pdf_path: Path, reason: str
) -> None:
    """Write manifest for skipped encrypted PDF."""
    try:
        from extractor.pipeline.utils.run_manifest import RunManifest

        manifest = RunManifest(output_dir)
        manifest.payload["status"] = "Skipped"
        manifest.payload["reason"] = f"encrypted_pdf_{reason}"
        manifest.payload["input_pdf"] = str(pdf_path)
        manifest.finalize("Skipped")
    except Exception as exc:
        logger.warning(f"Failed to write skip manifest: {exc}")

    try:
        manifest_data = {
            "input_pdf": str(pdf_path),
            "status": "Skipped",
            "reason": f"encrypted_pdf_{reason}",
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest_data, indent=2)
        )
    except Exception as exc:
        logger.warning(f"Failed to write manifest.json for skipped PDF: {exc}")


def _filter_simulated_sections(src: Path, results_root: Path) -> Path:
    """Drop simulated wrapper sections before reflow to match gold outputs.

    Returns the path to the filtered sections JSON if filtering succeeded and
    yielded at least one section; otherwise returns the original path.
    """
    dest = src.parent / "04_sections_filtered.json"
    try:
        data = json.loads(src.read_text())
        sections = data.get("sections")
        if not isinstance(sections, list):
            return src
        filtered = []
        for s in sections:
            title = str(s.get("title") or "").lower()
            wrapper = (s.get("metadata") or {}).get("normalized_wrapper")
            if "(simulated)" in title or wrapper in {"requirements_simulated", "short_colon"}:
                continue
            filtered.append(s)
        if not filtered:
            return src
        data["sections"] = filtered
        data["section_count"] = len(filtered)
        dest.write_text(json.dumps(data, indent=2))
        logger.info(
            f"04_section_builder: filtered simulated wrappers → {len(filtered)} sections (was {len(sections)})"
        )
        return dest
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"04_section_builder: failed to filter simulated wrappers: {e}")
        return src


def clean_step_artifacts(step_name: str, results_root: Path) -> None:
    """Enforce pipeline hygiene by nuking downstream artifacts before a step runs.

    This ensures that if a step fails or is skipped, we don't accidentally
    use stale data from a previous run.
    """
    import shutil

    # Map of Step -> Artifacts to Delete
    # Note: We delete artifacts that THIS step produces (to ensure fresh write)
    # AND artifacts of IMMEDIATE downstream steps (to break the chain).

    # Paths
    s04_out = results_root / "04_section_builder/json_output/04_sections.json"
    s05_out = results_root / "05_table_extractor/json_output/05_tables.json"
    s05b_out = results_root / "05_table_extractor/json_output/05b_table_descriptions.json"
    s05c_out = results_root / "05_table_extractor/json_output/05c_tables.json"
    s06_out = results_root / "06_figure_extractor/json_output/06_figures.json"
    s08_out = results_root / "08_extract_requirements/json_output/08_requirements.json"
    s08b_out = results_root / "08_lean4_theorem_prover"
    s09_out = results_root / "09_llm_enrichment/json_output/09_enriched.json"

    to_delete = []

    if "04_section_builder" in step_name:
        to_delete.extend(
            [s04_out, s05_out, s05b_out, s05c_out, s06_out, s08_out, s08b_out, s09_out]
        )

    elif "05_table_extractor" in step_name:
        # Standard S05 runs before S05b/S05c, so nuke them
        to_delete.extend([s05_out, s05b_out, s05c_out])

    elif "05b_table_describer" in step_name:
        to_delete.extend([s05b_out, s05c_out])

    elif "05c_table_merger" in step_name:
        to_delete.extend([s05c_out])

    elif "06_figure_extractor" in step_name:
        to_delete.extend([s06_out])

    elif "08_extract_requirements" in step_name:
        to_delete.extend([s08_out, s08b_out, s09_out])

    elif "08b_lean4_theorem_prover" in step_name:
        to_delete.extend([s08b_out])

    elif "09_llm_enrichment" in step_name:
        to_delete.extend([s09_out])

    # S07 and S10 handle their own DB/File cleaning internally/explicitly

    for p in to_delete:
        if p.exists():
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                logger.info(f"Hygiene: Deleted stale artifact {p.name}")
            except Exception as e:
                logger.warning(f"Hygiene: Failed to delete {p.name}: {e}")


def _step(
    name: str,
    fn,
    *fargs,
    stop_on_fail: bool = True,
    timeout_sec: int = 0,
    log_dir_base: Optional[Path] = None,
    on_timing=None,
    **fkw,
) -> Optional[Path]:
    logger.info(f"{name}: start")

    # 1. Enforce Hygiene (Nuke Artifacts)
    # We infer results_root from fkw if available (usually 'output_dir')
    # pipeline/steps usually take 'output_dir' as 2nd arg or kwarg.
    # Here run_pipeline passes `results_dir` (Path) as one of *fargs.
    # Typically fargs[1] is output_dir based on main() calls below.
    # Let's try to find a Path argument that looks like results dir.
    results_dir = None
    for arg in fargs:
        if isinstance(arg, Path) and "results" in str(arg):
            results_dir = arg
            break

    if results_dir:
        clean_step_artifacts(name, results_dir)

    sink_id = None

    stage_dir: Optional[Path] = None
    if log_dir_base:
        try:
            stage_dir = log_dir_base / name
            stage_dir.mkdir(parents=True, exist_ok=True)
            sink_id = logger.add(
                stage_dir / "stage.log",
                level="DEBUG",
                enqueue=True,
                rotation="5 MB",
                retention=3,
            )
        except Exception:
            sink_id = None
    t0_mono = time.monotonic()
    t0_wall = time.time()
    used_alarm = False
    old_handler = None

    def _handler(signum, frame):  # noqa: ARG001
        raise TimeoutError(f"{name} exceeded {timeout_sec}s")

    if timeout_sec and timeout_sec > 0 and hasattr(signal, "SIGALRM"):
        try:
            old_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, _handler)
            signal.alarm(timeout_sec)
            used_alarm = True
        except Exception as exc:
            logger.debug(
                f"{name}: SIGALRM timeout unavailable; falling back to thread executor ({exc})"
            )
            used_alarm = False
            old_handler = None

    try:
        # Cross-platform timeout fallback using a worker thread when SIGALRM is unavailable.
        if timeout_sec and timeout_sec > 0 and not used_alarm:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(fn, *fargs, **fkw)
                try:
                    rv = fut.result(timeout=timeout_sec)
                except concurrent.futures.TimeoutError:
                    raise TimeoutError(f"{name} exceeded {timeout_sec}s")
        else:
            rv = fn(*fargs, **fkw)

        dt_ms = int((time.monotonic() - t0_mono) * 1000)
        path_like = rv[0] if isinstance(rv, (list, tuple)) and rv else rv
        if path_like is None:
            err = RuntimeError(f"{name} returned no result")
            log_stage_error(name, err)
            if stop_on_fail:
                raise err
            return None
        logger.info(f"{name}: ok in {dt_ms} ms → {path_like}")
        # Emit timing line for observability
        if log_dir_base:
            try:
                (log_dir_base).mkdir(parents=True, exist_ok=True)
                timing_line = {
                    "stage": name,
                    "start_ts": t0_wall,
                    "end_ts": time.time(),
                    "latency_ms": dt_ms,
                }
                with (log_dir_base / "timings.jsonl").open("a", encoding="utf-8") as fp:
                    fp.write(json.dumps(timing_line) + "\n")
            except Exception:
                pass
        if callable(on_timing):
            try:
                on_timing(name, dt_ms)
            except Exception:
                pass
        return Path(path_like) if path_like is not None else None
    except Exception as e:
        log_stage_error(name, e)
        if stop_on_fail:
            raise
        return None
    finally:
        if used_alarm:
            try:
                signal.alarm(0)
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)
            except Exception:
                pass
        if sink_id is not None:
            try:
                logger.remove(sink_id)
            except Exception:
                pass


def _s00_timeout(out: Path, default: int) -> int:
    """Read S00's estimated_timeout_seconds from pipeline_context.json.

    Returns the larger of (S00 estimate, default) so the global
    --stage-timeout always acts as a minimum floor.
    """
    try:
        ctx = json.loads((out / "pipeline_context.json").read_text())
        est = int(ctx.get("estimated_timeout_seconds", 0))
        if est > 0:
            return max(est, default)
    except Exception:
        pass
    return default


def _detect_scanned_pdf_path(pdf_path: Path) -> Optional[Dict[str, Any]]:
    try:
        import fitz
        from extractor.pipeline.steps.s02_pymupdf_extractor import _detect_scanned_pdf

        with fitz.open(str(pdf_path)) as doc:
            return _detect_scanned_pdf(doc)
    except Exception as exc:
        logger.warning(f"Scanned PDF detection failed for {pdf_path.name}: {exc}")
        return None


def _write_scanned_info(output_dir: Path, scanned_info: Dict[str, Any]) -> None:
    try:
        (output_dir / "scanned_pdf.json").write_text(
            json.dumps(scanned_info, indent=2)
        )
    except Exception as exc:
        logger.warning(f"Failed to write scanned_pdf.json: {exc}")


def _write_scanned_skip_manifest(
    output_dir: Path, pdf_path: Path, scanned_info: Dict[str, Any]
) -> None:
    try:
        from extractor.pipeline.utils.run_manifest import RunManifest

        manifest = RunManifest(output_dir)
        manifest.payload["status"] = "Skipped"
        manifest.payload["reason"] = "scanned_pdf"
        manifest.payload["input_pdf"] = str(pdf_path)
        manifest.payload["scanned_pdf_detection"] = scanned_info
        manifest.finalize("Skipped")
    except Exception as exc:
        logger.warning(f"Failed to write skip manifest: {exc}")

    try:
        manifest_data = {
            "input_pdf": str(pdf_path),
            "status": "Skipped",
            "reason": "scanned_pdf",
            "scanned_pdf_detection": scanned_info,
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest_data, indent=2)
        )
    except Exception as exc:
        logger.warning(f"Failed to write manifest.json for skipped PDF: {exc}")


def _maybe_prepare_scanned_pdf(
    pdf_path: Path,
    output_dir: Path,
    args: argparse.Namespace,
) -> Tuple[Path, Optional[Dict[str, Any]], bool]:
    if pdf_path.suffix.lower() != ".pdf":
        return pdf_path, None, False

    scanned_info = _detect_scanned_pdf_path(pdf_path)
    if not scanned_info:
        return pdf_path, None, False

    _write_scanned_info(output_dir, scanned_info)

    if scanned_info.get("is_scanned"):
        if getattr(args, "skip_scanned", False):
            logger.warning(
                f"Skipping scanned PDF {pdf_path.name} "
                f"(confidence: {scanned_info.get('confidence', 0):.0%})."
            )
            _write_scanned_skip_manifest(output_dir, pdf_path, scanned_info)
            return pdf_path, scanned_info, True

        # auto_ocr defaults to True (set in argparse), use True as getattr default too
        if getattr(args, "auto_ocr", True):
            try:
                from extractor.pipeline.utils.ocr_preprocess import maybe_ocr_preprocess, is_ocrmypdf_available
                
                # Check if OCRmyPDF is available first
                available, method = is_ocrmypdf_available()
                if not available:
                    logger.warning(
                        f"OCRmyPDF not available. Scanned PDF {pdf_path.name} will not be OCR'd. "
                        f"Install ocrmypdf locally or build Docker image: cd docker/ocrmypdf && docker build -t extractor-ocr ."
                    )
                else:
                    logger.info(f"OCR preprocessing triggered for scanned PDF {pdf_path.name} (method: {method})")

                ocr_path, scanned_info = maybe_ocr_preprocess(
                    pdf_path,
                    scanned_info,
                    auto_ocr=True,
                    output_dir=output_dir,
                    language=getattr(args, "ocr_lang", "eng"),
                    skip_text=not getattr(args, "ocr_force", False),
                    deskew=getattr(args, "ocr_deskew", False),
                    timeout=getattr(args, "ocr_timeout", 600),
                )
                _write_scanned_info(output_dir, scanned_info)
                return ocr_path, scanned_info, False
            except Exception as exc:
                logger.warning(f"OCR preprocessing failed: {exc}")
        else:
            logger.info(f"auto_ocr=False, skipping OCR for scanned PDF {pdf_path.name}")

    return pdf_path, scanned_info, False


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Run extractor pipeline sequentially")

    # Positional or named argument for PDF
    p.add_argument("pdf_pos", nargs="?", type=Path, help="Input PDF file path")
    p.add_argument("--pdf", type=Path, help="Input PDF file path (legacy flag)")

    # Output directory (with aliases)
    p.add_argument(
        "--out",
        "--output_dir",
        "--output-dir",
        dest="out",
        default=Path("data/results/pipeline"),
        type=Path,
        help="Output directory root",
    )

    p.add_argument("--summary-only", action="store_true")
    p.add_argument("--skip-fig-descriptions", action="store_true")
    p.add_argument(
        "--skip-llm03",
        action="store_true",
        help="Skip VLM verification in Stage 03 (heuristic-only)",
    )
    p.add_argument(
        "--skip-tables05", action="store_true", help="Skip Stage 05; emit empty tables stub"
    )
    p.add_argument("--skip-reqs07", action="store_true", help="Skip Stage 07 requirements miner")
    p.add_argument("--skip-annotator09a", action="store_true", help="Skip Stage 09a PDF annotator")
    p.add_argument(
        "--offline-smoke",
        action="store_true",
        help="Deterministic smoke: disable LLM/VLM/DB/Lean4/annotator/tables",
    )
    p.add_argument(
        "--fast-batch",
        action="store_true",
        help="Fast batch mode: skip heavy stages (summarizer, prover, table/fig descriptions) for quick extraction",
    )
    p.add_argument(
        "--skip-scillm-preflight",
        action="store_true",
        help="Bypass SciLLM preflight (use only if service is healthy)",
    )
    p.add_argument("--skip-export", action="store_true")
    p.add_argument(
        "--extract-requirements", action="store_true", help="Run 07_requirements_miner after reflow"
    )
    p.add_argument(
        "--stage-timeout",
        type=int,
        default=int(__import__("os").getenv("PIPELINE_STAGE_TIMEOUT", "900")),
        help="Per-stage wall timeout in seconds (fail-fast). Recommended: 900s for batch, 600s for interactive",
    )
    p.add_argument(
        "--skip-proving",
        action="store_true",
        help="Skip 08_lean4_theorem_prover (enabled by default)",
    )
    p.add_argument(
        "--annotate-pdf",
        action="store_true",
        help="Run 09a_pdf_annotator to generate an annotated PDF with overlays",
    )
    p.add_argument(
        "--generate-walkthrough",
        action="store_true",
        help="Generate Markdown walkthrough with page images/overlays after other stages (step 15)",
    )
    p.add_argument("--stop-on-fail", action="store_true", default=True)
    p.add_argument(
        "--continue-on-error", action="store_true", help="Allow stages to continue after failure"
    )
    p.add_argument(
        "--use-llm", action="store_true", help="Use LLM for improved accuracy in s02 (Chutes.ai)"
    )
    p.add_argument(
        "--auto-ocr",
        dest="auto_ocr",
        action="store_true",
        default=True,
        help="Run OCRmyPDF on scanned PDFs before extraction (default: on)",
    )
    p.add_argument(
        "--no-auto-ocr",
        dest="auto_ocr",
        action="store_false",
        help="Disable OCRmyPDF preprocessing for scanned PDFs",
    )
    p.add_argument(
        "--skip-table-descriptions",
        action="store_true",
        help="Skip Stage 05b VLM table descriptions (faster, save tokens)",
    )
    p.add_argument(
        "--skip-scanned",
        action="store_true",
        help="Skip scanned PDFs (log + write skip manifest)",
    )
    p.add_argument(
        "--ocr-lang",
        type=str,
        default="eng",
        help="OCR language(s) for OCRmyPDF (e.g., eng or eng+deu)",
    )
    p.add_argument(
        "--ocr-deskew",
        action="store_true",
        help="Deskew scanned pages during OCR preprocessing",
    )
    p.add_argument(
        "--ocr-force",
        action="store_true",
        help="Force OCR even if text exists (disables --skip-text)",
    )

    # PDF Decryption arguments
    p.add_argument(
        "--auto-decrypt",
        dest="auto_decrypt",
        action="store_true",
        default=True,
        help="Attempt to decrypt encrypted PDFs automatically (default: on)",
    )
    p.add_argument(
        "--no-auto-decrypt",
        dest="auto_decrypt",
        action="store_false",
        help="Disable automatic PDF decryption; skip encrypted PDFs",
    )
    p.add_argument(
        "--decrypt-password",
        type=str,
        default=None,
        help="Password to use for decrypting encrypted PDFs",
    )

    p.add_argument(
        "--ocr-timeout",
        type=int,
        default=int(__import__("os").getenv("OCR_TIMEOUT", "600")),
        help="OCRmyPDF timeout in seconds",
    )

    # Preset override (skip auto-detection)
    p.add_argument(
        "--preset",
        type=str,
        help="Force a specific preset instead of auto-detection (skips s00)",
    )

    # Batch control
    p.add_argument(
        "--workers", type=int, default=1, help="Number of concurrent workers (default: 1)"
    )
    p.add_argument(
        "--glob",
        type=str,
        default="**/*.pdf",
        help="Glob pattern for directory scan (default: **/*.pdf)",
    )

    args = p.parse_args(argv)

    # Resolution logic for PDF argument
    input_path = args.pdf_pos or args.pdf
    if not input_path:
        p.error("the following arguments are required: pdf (file or directory)")

    # Discovery
    files_to_process = []
    if input_path.is_dir():
        # Directory input: scan recursively using glob
        logger.info(f"Scanning directory {input_path} for '{args.glob}'...")
        files_to_process = sorted(list(input_path.rglob(args.glob)))
        if not files_to_process:
            logger.error(f"No files found in {input_path} matching {args.glob}")
            return 1
        logger.info(f"Found {len(files_to_process)} files to process.")
    else:
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            return 1
        files_to_process = [input_path]

    # Pre-flight logic: Derive 'prove_requirements' from flags
    # Default is TRUE, unless skipped or in offline smoke mode
    args.prove_requirements = not args.skip_proving

    # Pre-flight checks (dependency/env)
    if args.continue_on_error:
        args.stop_on_fail = False
    if not args.skip_reqs07:
        args.extract_requirements = True

    # Suppress warnings & setup env (moved from below)
    warnings.filterwarnings(
        "ignore", message="Task was destroyed but it is pending", category=RuntimeWarning
    )
    warnings.filterwarnings(
        "ignore", message="coroutine .* was never awaited", category=RuntimeWarning
    )
    os.environ.setdefault("SCILLM_PAVED_DISABLE_LOGGING", "1")
    os.environ.setdefault("LITELLM_LOGGING", "0")
    os.environ.setdefault("DISABLE_AIOHTTP_TRANSPORT", "true")
    try:
        from scillm.paved.shutdown import maybe_disable_paved_logging_from_env

        maybe_disable_paved_logging_from_env()
    except Exception:
        pass

    if args.offline_smoke:
        args.summary_only = True
        args.skip_fig_descriptions = True
        args.skip_export = True
        args.extract_requirements = False
        args.prove_requirements = False  # Force disable in smoke tests
        args.skip_proving = True  # Consistency
        args.skip_llm03 = True
        args.skip_tables05 = True
        args.skip_reqs07 = True
        args.skip_annotator09a = True
        if args.auto_ocr:
            logger.warning("offline-smoke: disabling --auto-ocr for determinism")
            args.auto_ocr = False
        logger.info(
            "offline-smoke mode: forcing deterministic flags and skipping online/optional stages"
        )

    if args.fast_batch:
        # Fast batch mode: skip expensive stages but keep basic extraction
        args.summary_only = True  # Skip LLM summarization
        args.skip_fig_descriptions = True  # Skip VLM figure descriptions
        args.prove_requirements = False  # Skip Lean4 proving
        args.skip_proving = True
        args.skip_llm03 = True  # Skip VLM header verification
        args.skip_scillm_preflight = True  # No LLM needed, skip preflight
        logger.info(
            "fast-batch mode: skipping heavy stages (summarizer, prover, descriptions, LLM) for speed"
        )

    try:
        load_dotenv(find_dotenv(), override=True)
    except Exception:
        pass

    def _probe_dependencies(required: list[str], optional: Dict[str, str]) -> bool:
        ok = True
        missing_required = []
        for mod in required:
            if importlib.util.find_spec(mod) is None:
                missing_required.append(mod)
        if missing_required:
            logger.error(f"Missing required dependencies: {missing_required}")
            ok = False
        for label, mod in optional.items():
            if importlib.util.find_spec(mod) is None:
                logger.warning(
                    f"Optional dependency not installed; related steps may be skipped: {label} ({mod})"
                )
        return ok

    if not _probe_dependencies(required=["camelot", "fitz"], optional={"python-arango": "arango"}):
        return 1

    # Online needed check
    online_needed = any(
        [
            not bool(args.summary_only),
            not bool(args.skip_fig_descriptions),
            bool(args.extract_requirements),
            bool(args.prove_requirements),
            not bool(args.skip_llm03),
        ]
    )
    if online_needed and not args.skip_scillm_preflight:
        try:
            from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight

            require_scillm_preflight()
        except Exception as e:
            logger.error(f"SciLLM preflight failed: {e}")
            return 1

    # Execution Loop
    failed_files = []

    # Configure logging format once
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )

    def process_file_safe(pdf: Path) -> bool:
        """Wrapper to process a single file and handle expected output directory structure."""
        # Calculate sub-output directory:
        # If single file input -> Use --out directly (standard behavior)
        # If directory input -> Use --out / stem (batch behavior)
        if len(files_to_process) > 1 or input_path.is_dir():
            # Batch mode: create subdirectory
            file_out = args.out / pdf.stem
        else:
            # Single mode: use root
            file_out = args.out

        file_out.mkdir(parents=True, exist_ok=True)

        if pdf.suffix.lower() == ".html":
            strategy_name = "HTML"
            strategy_fn = _run_html_strategy
        else:
            strategy_name = "PDF"
            strategy_fn = _run_pdf_strategy

        logger.info(f"Processing {pdf.name} -> {file_out} [Strategy: {strategy_name}]")

        pdf_to_process = pdf
        if strategy_name == "PDF":
            # Step 1: Decrypt encrypted PDFs first
            pdf_to_process, decrypt_info, decrypt_skipped = _maybe_decrypt_pdf(
                pdf, file_out, args
            )
            if decrypt_skipped:
                return True
            if decrypt_info and decrypt_info.get("success"):
                logger.info(f"Using decrypted PDF: {pdf_to_process.name}")

            # Step 2: Handle scanned PDFs (may need OCR after decryption)
            pdf_to_process, scanned_info, skipped = _maybe_prepare_scanned_pdf(
                pdf_to_process, file_out, args
            )
            if skipped:
                return True
            if scanned_info and scanned_info.get("is_scanned"):
                logger.info(
                    f"Scanned PDF detected (confidence: {scanned_info.get('confidence', 0):.0%})."
                )
            if pdf_to_process != pdf:
                logger.info(f"Using preprocessed PDF: {pdf_to_process.name}")

        try:
            result_code = strategy_fn(pdf_to_process, file_out, args)
            if result_code != 0:
                logger.error(f"Failed to process {pdf.name}")
                return False
            return True
        except Exception as e:
            logger.exception(f"Exception processing {pdf.name}: {e}")
            return False

    # Run processing
    # Sequential for now to ensure stability before threading
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeRemainingColumn,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("[green]Processing files...", total=len(files_to_process))

        for i, pdf_file in enumerate(files_to_process):
            progress.update(
                task,
                description=f"[green]Processing {pdf_file.name} ({i+1}/{len(files_to_process)})",
            )
            logger.info(f"[{i+1}/{len(files_to_process)}] Starting: {pdf_file.name}")

            if not process_file_safe(pdf_file):
                failed_files.append(str(pdf_file))
                if args.stop_on_fail and not args.continue_on_error:
                    logger.error("Stopping due to failure (use --continue-on-error to ignore).")
                    return 1
            progress.advance(task)

    if failed_files:
        logger.error(f"Run completed with {len(failed_files)} failures: {failed_files}")
        return 1

    logger.info("All files processed successfully.")
    return 0


def _write_artifacts_index(out: Path, stage_dir: Path) -> None:
    """Helper to write artifact index for a stage directory."""
    try:
        json_dir = stage_dir / "json_output"
        img_dir = stage_dir / "visual_output"
        legacy_img_dir = stage_dir / "image_output"
        stage_dir / "visual_output"
        txt_dir = stage_dir / "text_output"
        idx = {
            "images": [
                *(
                    [str(p.relative_to(out)) for p in (img_dir.rglob("*"))]
                    if img_dir.exists()
                    else []
                ),
                *(
                    [str(p.relative_to(out)) for p in (legacy_img_dir.rglob("*"))]
                    if legacy_img_dir.exists()
                    else []
                ),
            ],
            "json": (
                [str(p.relative_to(out)) for p in (json_dir.glob("*.json"))]
                if json_dir.exists()
                else []
            ),
            "text": (
                [str(p.relative_to(out)) for p in (txt_dir.rglob("*.txt"))]
                if txt_dir.exists()
                else []
            ),
        }
        if json_dir.exists():
            write_json_strict(json_dir / "artifacts_index.json", idx, stage="artifacts_index")
    except Exception as exc:
        log_stage_error("artifacts_index", exc, {"stage_dir": str(stage_dir)})


def _run_html_strategy(html_path: Path, out: Path, args: argparse.Namespace) -> int:
    """HTML ingestion strategy (UnifiedDocument -> Stage 07)."""
    logger.info(f"HTML Strategy invoked for {html_path.name}")

    results: Dict[str, Any] = {}
    manifest = RunManifest(out)
    stage_latencies: Dict[str, int] = {}
    served_model = {
        "text": os.getenv("CHUTES_TEXT_MODEL", ""),
        "vlm": os.getenv("CHUTES_VLM_MODEL", ""),
    }

    try:
        # 1. Parse HTML -> UnifiedDocument
        from extractor.pipeline.ingest.html_provider import HTMLProvider

        logger.info("Parsing HTML with HTMLProvider...")
        provider = HTMLProvider(html_path)
        unified_doc = provider.parse()
        logger.info(f"Parsed {len(unified_doc.blocks)} blocks from HTML")

        # 2. Convert UnifiedDocument -> Pipeline Artifacts
        from extractor.pipeline.adapters.unified_adapter import UnifiedAdapter

        logger.info("Converting to pipeline artifacts with UnifiedAdapter...")
        adapter = UnifiedAdapter(unified_doc, out)
        adapter.write_artifacts()

        # 3. Run common downstream stages (07-14)
        logger.info("Running common pipeline stages (S07-S14)...")
        return _run_common_stages(
            out,
            args,
            manifest,
            results,
            stage_latencies,
            served_model,
            pdf=None,
            preset_config=None,
        )

    except Exception as e:
        logger.exception(f"HTML Strategy failed: {e}")
        return 1


def _run_pdf_strategy(pdf: Path, out: Path, args: argparse.Namespace) -> int:
    """Standard PDF pipeline strategy (S01-S06 -> S07)."""

    results: Dict[str, Any] = {}
    manifest = RunManifest(out)
    stage_latencies: Dict[str, int] = {}

    served_model = {
        "text": os.getenv("CHUTES_TEXT_MODEL", ""),
        "vlm": os.getenv("CHUTES_VLM_MODEL", ""),
    }

    # Import steps lazily to avoid import-time side effects.
    # Avoid importing online-only steps when running in deterministic offline mode.

    # Select s02 extractor based on environment variable
    # STAGE02_EXTRACTOR=pymupdf (default, fast, no ML dependencies)
    # STAGE02_EXTRACTOR=marker (requires Surya, slower but may have better layout detection)
    extractor_mode = os.getenv("STAGE02_EXTRACTOR", "pymupdf").lower()
    if extractor_mode == "marker":
        from extractor.pipeline.steps import s02_marker_extractor as s02
        logger.info("Using Marker/Surya extractor (STAGE02_EXTRACTOR=marker)")
    else:
        from extractor.pipeline.steps import s02_pymupdf_extractor as s02
        logger.info("Using PyMuPDF extractor (STAGE02_EXTRACTOR=pymupdf)")

    from extractor.pipeline.steps import (
        s01_annotation_processor as s01,
        s03_suspicious_headers as s03,
        s04_section_builder as s04,
        s04a_layout_audit as s04a,
        s05_table_extractor as s05,
        s05b_table_describer as s05b,
        s05c_table_merger as s05c,
        s06_figure_extractor as s06,
        s06b_figure_describer as s06b,
    )

    # Lazy import for optional DB steps to avoid hard dependency on python-arango if not needed
    if not args.skip_export:
        try:
            from extractor.pipeline.steps import (
                s11_arango_create_graph as _s11,
                s12_insert_annotations as _s12,
            )
            _ = (_s11, _s12)

        except ImportError as exc:
            log_stage_error(
                "arango_optional", exc, {"hint": "Install python-arango to enable export"}
            )
    # Lean4 proving is opt-in; DB export follows the previous online/offline gating.

    if args.prove_requirements:
        if not (bool(args.summary_only) and bool(args.skip_fig_descriptions)):
            pass

    # 00: Profile Detector (Context Injection)
    # ----------------------------------------------------
    preset_config = {}
    preset_name = None
    forced_preset = getattr(args, "preset", None)

    if forced_preset and forced_preset != "auto":
        # User specified --preset; skip s00 auto-detection
        from extractor.core.presets import PRESET_REGISTRY

        preset_name = forced_preset
        logger.info(f"00_profile_detector: SKIPPED - Using forced preset '{preset_name}'")

        if preset_name in PRESET_REGISTRY:
            preset_config = PRESET_REGISTRY[preset_name]
            logger.info(f"00_profile_detector: Loaded config for forced preset '{preset_name}'")
        else:
            logger.warning(
                f"00_profile_detector: Forced preset '{preset_name}' not in registry. Using defaults."
            )

        # Save Context Artifact for forced preset
        context_data = {
            "preset_name": preset_name,
            "config": preset_config,
            "timestamp": time.time(),
            "profile_path": None,
            "forced": True,
        }
        (out / "pipeline_context.json").write_text(json.dumps(context_data, indent=2))

        # Write a minimal profile.json so downstream consumers find it
        # (discovery.py, review-pdf, etc. expect 00_profile_detector/profile.json)
        s00_dir = out / "00_profile_detector"
        s00_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = Path(args.pdf) if hasattr(args, "pdf") and args.pdf else None
        page_count = 0
        file_size_mb = 0.0
        if pdf_path and pdf_path.exists():
            file_size_mb = round(pdf_path.stat().st_size / (1024 * 1024), 2)
            try:
                import fitz
                with fitz.open(str(pdf_path)) as doc:
                    page_count = len(doc)
            except Exception:
                pass
        minimal_profile = {
            "domain": preset_name or "unknown",
            "page_count": page_count,
            "file_size_mb": file_size_mb,
            "estimated_timeout_seconds": 0,
            "layout": {},
            "hierarchy": {},
            "elements": {},
            "preset_match": {"matched": preset_name, "confidence": 1.0, "forced": True},
            "route": "forced_preset",
            "complexity_score": 0.0,
            "thresholds_hit": [],
            "detected_preset": preset_name,
            "file": str(pdf_path) if pdf_path else "",
            "timestamp": time.time(),
            "duration_ms": 0,
        }
        (s00_dir / "profile.json").write_text(json.dumps(minimal_profile, indent=2))
        logger.info(f"00_profile_detector: Wrote minimal profile.json for forced preset '{preset_name}'")

    elif not getattr(args, "skip_s00", False):
        try:
            from extractor.pipeline.steps import s00_profile_detector as s00
            from extractor.core.presets import PRESET_REGISTRY

            logger.info("00_profile_detector: Running profile detection...")

            # Run S00
            s00_out_file = _step(
                "00_profile_detector",
                s00.run,
                pdf,
                out,
                stop_on_fail=False,  # Don't crash pipeline if profile fails, just warn
                timeout_sec=args.stage_timeout,
                log_dir_base=out,
            )

            # Load Profile and Context
            if s00_out_file and s00_out_file.exists():
                try:
                    profile_data = json.loads(s00_out_file.read_text())
                    preset_name = profile_data.get("detected_preset")
                    logger.info(f"00_profile_detector: Detected Preset = {preset_name}")

                    if preset_name in PRESET_REGISTRY:
                        preset_config = PRESET_REGISTRY[preset_name]
                        logger.info(f"00_profile_detector: Loaded config for {preset_name}")
                    elif preset_name:
                        logger.warning(
                            f"00_profile_detector: Preset '{preset_name}' not in registry. Using defaults."
                        )

                except Exception as e:
                    logger.warning(f"00_profile_detector: Failed to load profile JSON: {e}")
            else:
                logger.warning("00_profile_detector: No output file produced.")

            # Save Context Artifact — merge with S00's existing data (timeout, table estimates)
            context_file = out / "pipeline_context.json"
            context_data = {}
            if context_file.exists():
                try:
                    context_data = json.loads(context_file.read_text())
                except Exception:
                    pass
            context_data.update({
                "preset_name": preset_name,
                "config": preset_config,
                "timestamp": time.time(),
                "profile_path": str(s00_out_file) if s00_out_file else None,
            })
            context_file.write_text(json.dumps(context_data, indent=2))

        except ImportError:
            logger.warning("00_profile_detector: Module not found. Skipping context injection.")
        except Exception as e:
            logger.error(f"00_profile_detector: Unexpected failure: {e}")

    # Enforce implications: proving implies requirements miner
    if args.prove_requirements and not args.extract_requirements:
        args.extract_requirements = True

    # 01
    a01 = _step(
        "01_annotation_processor",
        s01.run,
        pdf,
        out,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        timeout=args.stage_timeout,
    )
    if not a01:
        if args.stop_on_fail:
            return 1
        logger.warning("Stage 01 failed, continuing with empty result")
    results["01"] = a01
    _write_artifacts_index(out, (out / "01_annotation_processor"))
    manifest.record_stage(
        "01_annotation_processor",
        "Completed",
        {
            "json": str(a01.relative_to(out)),
            "latency_ms": stage_latencies.get("01_annotation_processor"),
        },
    )

    # 02
    a02 = _step(
        "02_marker_extractor",
        s02.run,
        pdf,
        out,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        timeout=args.stage_timeout,
        use_llm=getattr(args, "use_llm", False),
    )
    if not a02:
        if args.stop_on_fail:
            return 1
        logger.warning("Stage 02 failed, continuing with empty result")
    results["02"] = a02
    _write_artifacts_index(out, (out / "02_marker_extractor"))
    manifest.record_stage(
        "02_marker_extractor",
        "Completed",
        {
            "json": str(a02.relative_to(out)),
            "latency_ms": stage_latencies.get("02_marker_extractor"),
        },
    )

    # 02b (Equation Extractor) — REMOVED: S02 pymupdf already has font-based
    # equation detection via _detect_equation(). Future: /create-classifier for
    # vision-based equation region detection + /create-gpt for Unicode→LaTeX.

    # 03
    pdf_dir = out / "01_annotation_processor"
    a03 = _step(
        "03_suspicious_headers",
        s03.run,
        a02,
        pdf_dir,
        out,
        skip_llm=False,  # Always run candidate generator (rendering etc.)
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a03:
        if args.stop_on_fail:
            return 1
        logger.warning("Stage 03 failed, continuing with empty result")
    results["03"] = a03
    _write_artifacts_index(out, (out / "03_suspicious_headers"))
    try:
        vcount = len(__import__("json").loads(a03.read_text()).get("blocks", []))
    except Exception:
        vcount = None
    manifest.record_stage(
        "03_suspicious_headers",
        "Completed",
        {
            "json": str(a03.relative_to(out)),
            "latency_ms": stage_latencies.get("03_suspicious_headers"),
        },
        counts={"candidates": vcount} if isinstance(vcount, int) else None,
    )

    # 04 (hard-require Stage 03 outputs)
    try:
        _a03_obj = json.loads(a03.read_text())
        if (
            not isinstance(_a03_obj, dict)
            or "blocks" not in _a03_obj
            or not isinstance(_a03_obj["blocks"], list)
        ):
            raise ValueError("Stage 03 output missing required key 'blocks' (list)")
    except Exception as e:
        logger.warning(f"04_section_builder: Stage 03 outputs validation failed → {e}")
        # Proceed with a03 as-is (if it exists) or None; s04 handles None.
    a04_path = _step(
        "04_section_builder",
        s04.run,
        a03,
        pdf_dir,
        out,
        preset_config=preset_config,  # Validate with context
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a04_path:
        if args.stop_on_fail:
            return 1
        logger.warning("Stage 04 failed, continuing with empty result")
    results["04"] = a04_path
    _write_artifacts_index(out, (out / "04_section_builder"))
    try:
        sec_count = len(__import__("json").loads(a04_path.read_text()).get("sections", []))
    except Exception:
        sec_count = None
    manifest.record_stage(
        "04_section_builder",
        "Completed",
        {
            "json": str(a04_path.relative_to(out)),
            "latency_ms": stage_latencies.get("04_section_builder"),
        },
        counts={"sections": sec_count} if isinstance(sec_count, int) else None,
    )

    # 04a – layout audit (fail fast on ordering issues before tables/figures)
    skip_04a = False
    if isinstance(sec_count, int) and sec_count == 0:
        try:
            scanned_info_path = out / "scanned_pdf.json"
            if scanned_info_path.exists():
                scanned_info = json.loads(scanned_info_path.read_text())
            else:
                scanned_info = {}
        except Exception:
            scanned_info = {}
        if scanned_info.get("is_scanned"):
            skip_04a = True
            logger.warning(
                "04a_layout_audit: skipped (scanned PDF with zero sections)."
            )
            manifest.record_stage(
                "04a_layout_audit",
                "Skipped",
                {},
                extra={"reason": "scanned_pdf_zero_sections"},
            )

    if not skip_04a:
        a04a = _step(
            "04a_layout_audit",
            s04a.run,
            out,
            stop_on_fail=args.stop_on_fail,
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        if not a04a and args.stop_on_fail:
            return 1
        if a04a:
            _write_artifacts_index(out, (out / "04a_layout_audit"))
            manifest.record_stage(
                "04a_layout_audit",
                "Completed",
                {
                    "json": str(a04a.relative_to(out)),
                    "latency_ms": stage_latencies.get("04a_layout_audit"),
                },
            )

    # 04b (Footnote Detector) — REMOVED: S02 pymupdf already tags blocks with
    # block_type="Footnote" using font/layout heuristics. Downstream filters by type.

    # 05
    if args.skip_tables05:
        stub_dir = out / "05_table_extractor" / "json_output"
        stub_dir.mkdir(parents=True, exist_ok=True)
        stub = {
            "timestamp": int(time.time()),
            "tables": [],
            "diagnostics": [{"severity": "info", "reason": "skip_tables05 flag"}],
        }
        stub_path = stub_dir / "05_tables.json"
        stub_path.write_text(json.dumps(stub, indent=2))
        a05 = stub_path
        logger.info("05_table_extractor: skipped via --skip-tables05")
    else:
        a05 = _step(
            "05_table_extractor",
            s05.run,
            a04_path,
            pdf_dir,
            out,
            stop_on_fail=args.stop_on_fail,
            timeout_sec=_s00_timeout(out, args.stage_timeout),
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        if not a05:
            logger.warning("05_table_extractor: failed, continuing")
    results["05"] = a05
    _write_artifacts_index(out, (out / "05_table_extractor"))
    try:
        tcount = len(__import__("json").loads(Path(a05).read_text()).get("tables", []))
    except Exception:
        tcount = None
    manifest.record_stage(
        "05_table_extractor",
        "Completed",
        {
            "json": str(Path(a05).relative_to(out)),
            "latency_ms": stage_latencies.get("05_table_extractor"),
        },
        counts={"tables": tcount} if isinstance(tcount, int) else None,
    )

    # 05b (VLM Descriptions)
    a05b = _step(
        "05b_table_describer",
        s05b.run,
        out / "05_table_extractor",  # Input dir
        out,  # Output dir
        skip_descriptions=bool(args.summary_only)
        or bool(args.skip_tables05)
        or bool(args.skip_table_descriptions),
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a05b and args.stop_on_fail and not args.skip_tables05 and not args.skip_table_descriptions:
        logger.warning("05b_table_describer: failed, continuing")
    results["05b"] = a05b

    # 05c (Table Merger)
    a05c = _step(
        "05c_table_merger",
        s05c.run,
        out,  # Input dir (searches for 05b or 05)
        out,  # Output dir
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a05c and args.stop_on_fail and not args.skip_tables05:
        logger.warning("05c_table_merger: failed, continuing")
    results["05c"] = a05c

    # 06 (deterministic extraction, VLM descriptions done in 06b)
    a06 = _step(
        "06_figure_extractor",
        s06.run,
        a02,
        a04_path,
        pdf_dir,
        out,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a06:
        logger.warning("06_figure_extractor: failed, continuing")
    results["06"] = a06
    _write_artifacts_index(out, (out / "06_figure_extractor"))
    try:
        fcount = len(__import__("json").loads(a06.read_text()).get("figures", []))
    except Exception:
        fcount = None
    manifest.record_stage(
        "06_figure_extractor",
        "Completed",
        {
            "json": str(a06.relative_to(out)),
            "latency_ms": stage_latencies.get("06_figure_extractor"),
        },
        counts={"figures": fcount} if isinstance(fcount, int) else None,
    )

    # 06b (VLM Descriptions - decoupled)
    a06b = _step(
        "06b_figure_describer",
        s06b.run,
        out / "06_figure_extractor",  # Input dir
        out,  # Output root
        skip_descriptions=args.skip_fig_descriptions,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a06b:
        if args.stop_on_fail:
            logger.warning("06b_figure_describer: failed, continuing")
    else:
        results["06b"] = a06b
        _write_artifacts_index(out, (out / "06b_figure_describer"))
        manifest.record_stage(
            "06b_figure_describer",
            "Completed",
            {
                "json": str(a06b.relative_to(out)),
                "latency_ms": stage_latencies.get("06b_figure_describer"),
            },
        )

    # Common Downstream Stages (S07-S14)
    return _run_common_stages(
        out,
        args,
        manifest,
        results,
        stage_latencies,
        served_model,
        pdf=pdf,
        preset_config=preset_config,
    )


def _run_common_stages(
    out: Path,
    args: argparse.Namespace,
    manifest: RunManifest,
    results: Dict[str, Any],
    stage_latencies: Dict[str, int],
    served_model: Dict[str, str],
    pdf: Optional[Path] = None,
    preset_config: Optional[Dict[str, Any]] = None,
) -> int:
    """Shared pipeline stages (07 Assembler -> 14 Report) for all input formats."""

    # Lazy imports for shared stages
    from extractor.pipeline.steps import (
        s07_json_assembler as s07,
        s08_extract_requirements as s08,
        s09_section_summarizer as s09_summ,
        s14_report_generator as s14,
        s10_markdown_exporter as s10_export,
        s11_json_exporter as s11_export,
    )

    # Import s12_framework_mapper for control extraction (after s10 produces flattened data)
    s12 = None
    try:
        from extractor.pipeline.steps import s12_framework_mapper as _s12_fw
        s12 = _s12_fw
    except ImportError:
        logger.info("Stage 12 [Framework Mapper] not available: s12_framework_mapper module not found.")

    # Import s10_arangodb_exporter for JSON output (QRA/downstream compatibility)
    s10 = None
    try:
        from extractor.pipeline.steps import s10_arangodb_exporter as _s10

        s10 = _s10
    except ImportError:
        logger.info(
            "Stage 10 [Arango Export] not available: s10_arangodb_exporter module not found."
        )

    # 07 (JSON Assembler)
    json_path = out / "07_assembled" / "assembled_content.json"

    def _run_07(ip: Path, op: Path) -> str:
        s07.run_assemble_corpus(
            output_json_path=json_path,
            sections_json=results.get("04"),
            tables_json=results.get("05c")
            or results.get("05b")
            or results.get("05"),  # Prefer processed tables
            figures_json=results.get("06b") or results.get("06"),  # Prefer described figures
            annotations_json=results.get("01"),
            marker_json=results.get("02"),  # Stage 02 output with TOC entries
            scanned_info_json=out / "scanned_pdf.json",
            preset_config=preset_config,
        )
        return str(json_path)

    a07 = _step(
        "07_assemble_corpus",
        _run_07,
        out,
        out,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a07:
        logger.warning("07_assemble_corpus: failed (critical stage), continuing to report")
    manifest.record_stage(
        "07_assemble_corpus",
        "Completed",
        {
            "json": str(json_path.relative_to(out)),
            "latency_ms": stage_latencies.get("07_assemble_corpus"),
        },
    )

    # 07b (Text Cleaner) — folded into S07 JSON assembler; no separate step needed.

    # 08 (Extractor)
    if args.summary_only:
        logger.info("08_extract_requirements: skipped via --summary-only")
    else:

        def _run_08(ip: Path, op: Path) -> str:
            s08.run_extract_requirements(op, json_path)
            # Fetch count for manifest
            from extractor.pipeline.utils.content_query import ContentRepository
            repo = ContentRepository(json_path)
            return str(len(repo.requirements))

        a08 = _step(
            "08_extract_requirements",
            _run_08,
            out,
            out,
            stop_on_fail=args.stop_on_fail,
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        if not a08 and args.stop_on_fail:
            logger.warning("08_extract_requirements: failed, continuing")

        manifest.record_stage(
            "08_extract_requirements",
            "Completed",
            {"latency_ms": stage_latencies.get("08_extract_requirements")},
            counts={"requirements": int(str(a08)) if a08 and str(a08).isdigit() else 0},
        )

        # 08b (Lean4 Theorem Prover) - Context-Aware
        # Note: --skip-proving sets args.prove_requirements = False
        should_prove = getattr(args, "prove_requirements", False)
        if not should_prove and preset_config:
            # Only auto-enable if --skip-proving wasn't explicitly passed
            if preset_config.get("features", {}).get("enable_proving") is True and not getattr(
                args, "skip_proving", False
            ):
                should_prove = True
                logger.info("08b [Lean4] auto-enabled by preset config")

        if should_prove:

            def _run_08b(ip: Path, op: Path) -> str:
                import asyncio
                from extractor.pipeline.steps.s08_lean4_theorem_prover import prove_requirements

                asyncio.run(prove_requirements(json_path, op / "08_lean4_theorem_prover"))
                # Fetch proof count for manifest
                from extractor.pipeline.utils.content_query import ContentRepository
                repo = ContentRepository(json_path)
                return str(len(repo.lean4_proofs))

            a08b = _step(
                "08b_lean4_theorem_prover",
                _run_08b,
                out,
                out,
                stop_on_fail=False,  # Don't block pipeline if proving fails
                timeout_sec=args.stage_timeout * 3,  # Proofs take longer
                log_dir_base=out,
                on_timing=lambda n, dt: stage_latencies.update({n: dt}),
            )
            if a08b:
                manifest.record_stage(
                    "08b_lean4_theorem_prover",
                    "Completed",
                    {"latency_ms": stage_latencies.get("08b_lean4_theorem_prover")},
                    counts={"proofs": int(str(a08b)) if a08b and str(a08b).isdigit() else 0},
                )

    # 09b (Section Summarizer)
    if args.summary_only:
        logger.info("09_section_summarizer: skipped via --summary-only")
    else:

        def _run_09_summ(ip: Path, op: Path) -> Path:
            s09_summ.run_stage_09_summarizer(op, preset_config=preset_config)
            return op / "07_assembled" / "assembled_content.json"

        a09_summ = _step(
            "09_section_summarizer",
            _run_09_summ,
            out,
            out,
            stop_on_fail=args.stop_on_fail,
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        if a09_summ:
            manifest.record_stage(
                "09_section_summarizer",
                "Completed",
                {"output": None, "latency_ms": stage_latencies.get("09_section_summarizer")},
            )

    # 10 (Markdown Exporter) -- Always run (deterministic, high value)
    if True:
        # run(input_path, output_dir=None)
        # We pass 'out' as input_path (pipeline root) -> s10 finds DB there
        a10 = _step(
            "10_markdown_exporter",
            s10_export.run,
            out,
            stop_on_fail=args.stop_on_fail,
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        if a10:
            manifest.record_stage(
                "10_markdown_exporter",
                "Completed",
                {
                    "file": str(a10.relative_to(out)),
                    "latency_ms": stage_latencies.get("10_markdown_exporter"),
                },
            )

    # 11 (Structural JSON Exporter)
    if True:
        a11 = _step(
            "11_json_exporter",
            s11_export.run,
            out,
            stop_on_fail=args.stop_on_fail,
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        if a11:
            manifest.record_stage(
                "11_json_exporter",
                "Completed",
                {
                    "file": str(a11.relative_to(out)),
                    "latency_ms": stage_latencies.get("11_json_exporter"),
                },
            )

    # 10b (ArangoDB Exporter) -- ALWAYS run to produce 10_flattened_data.json for QRA/downstream
    # ArangoDB sync is optional (handled internally based on credentials)
    if s10 is not None:
        stage_10b_out = out / "10_arangodb_exporter"
        _step(
            "10_arangodb_exporter",
            s10.run,
            out,  # pipeline_dir
            stage_10b_out,  # output_dir
            preset_config,
            stop_on_fail=False,  # Don't fail pipeline if ArangoDB unavailable
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        # Check if JSON was produced
        json_path = stage_10b_out / "json_output" / "10_flattened_data.json"
        if json_path.exists():
            manifest.record_stage(
                "10_arangodb_exporter",
                "Completed",
                {
                    "json": str(json_path.relative_to(out)),
                    "latency_ms": stage_latencies.get("10_arangodb_exporter"),
                },
            )

    # 12 (Framework Mapper) - extract control references and create chunk→control edges
    if s12 is not None:
        json_path_10 = out / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
        if json_path_10.exists():
            stage_12_out = out / "12_framework_mapper"
            _step(
                "12_framework_mapper",
                s12.run,
                out,  # pipeline_dir
                stage_12_out,  # output_dir
                preset_config,
                stop_on_fail=False,  # Don't fail pipeline if control mapping fails
                timeout_sec=args.stage_timeout,
                log_dir_base=out,
                on_timing=lambda n, dt: stage_latencies.update({n: dt}),
            )
            map_path = stage_12_out / "json_output" / "12_framework_map.json"
            if map_path.exists():
                manifest.record_stage(
                    "12_framework_mapper",
                    "Completed",
                    {
                        "json": str(map_path.relative_to(out)),
                        "latency_ms": stage_latencies.get("12_framework_mapper"),
                    },
                )

    # 14 (Report Generator) - always run at end
    stage_14_out = out / "14_report_generator"
    a14 = _step(
        "14_report_generator",
        s14.run,
        out,
        stage_14_out,
        pdf,  # Pass source PDF for Visual Report
        stop_on_fail=False,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if a14:
        _write_artifacts_index(out, (out / "14_report_generator"))
        manifest.record_stage(
            "14_report_generator",
            "Completed",
            {
                "json": (
                    str(Path(a14[0]).relative_to(out))
                    if isinstance(a14, tuple)
                    else str(Path(a14).relative_to(out))
                ),
                "latency_ms": stage_latencies.get("14_report_generator"),
            },
        )
    else:
        # In deterministic/offline runs, ensure a stub report exists so downstream consumers/smokes pass.
        try:
            stub_dir = out / "14_report_generator" / "json_output"
            stub_dir.mkdir(parents=True, exist_ok=True)
            (stub_dir / "final_report.json").write_text(
                json.dumps(
                    {"meta": {"stub": True, "reason": "report_generation_failed_or_skipped"}}
                )
            )
        except Exception:
            pass

    # Close resources if needed
    try:
        pass
    except Exception:
        pass

    for k, v in results.items():
        logger.info(f"  {k} → {v}")

    # Write timings summary
    try:
        summary = {
            "total_ms": int(sum(v for v in stage_latencies.values())),
            "stages": [{"name": k, "latency_ms": int(v)} for k, v in stage_latencies.items()],
            "served_model": served_model,
        }
        (out / "timings_summary.json").write_text(json.dumps(summary, indent=2))
    except Exception:
        pass

    # Write manifests
    try:
        import json as _json

        manifest_data = {
            "input_pdf": str(out),  # Abstract input
            "outputs": {k: str(v) for k, v in results.items()},
            "counts": {},
            "flags": {
                "summary_only": bool(args.summary_only),
                "skip_fig_descriptions": bool(args.skip_fig_descriptions),
                "stop_on_fail": bool(args.stop_on_fail),
                "stage_timeout": int(args.stage_timeout),
            },
            "served_model": served_model,
            "timings_ms": stage_latencies,
        }

        # Best-effort counts
        def _safe_load(p):
            try:
                return _json.loads(Path(p).read_text())
            except Exception:
                return {}

        try:
            d02 = _safe_load(out / "02_marker_extractor/json_output/02_marker_blocks.json")
            manifest_data["counts"]["blocks02"] = len(d02.get("blocks", []))
        except Exception:
            pass
        try:
            d03 = _safe_load(out / "03_suspicious_headers/json_output/03_verified_blocks.json")
            manifest_data["counts"]["verified03"] = len(d03.get("blocks", []))
        except Exception:
            pass
        try:
            d04 = _safe_load(out / "04_section_builder/json_output/04_sections.json")
            manifest_data["counts"]["sections04"] = len(d04.get("sections", []))
        except Exception:
            pass
        try:
            d05 = _safe_load(out / "05_table_extractor/json_output/05_tables.json")
            manifest_data["counts"]["tables05"] = len(d05.get("tables", []))
        except Exception:
            pass
        try:
            d06 = _safe_load(out / "06_figure_extractor/json_output/06_figures.json")
            manifest_data["counts"]["figures06"] = (
                len(d06.get("figures", [])) if isinstance(d06, dict) else 0
            )
        except Exception:
            pass
        (out / "manifest.json").write_text(_json.dumps(manifest_data, indent=2))
    except Exception as exc:
        log_stage_error("manifest_write", exc, {"out": str(out)})
    try:
        manifest.finalize("Completed")
    except Exception:
        pass
    # Ensure any shared SciLLM clients are closed to prevent aiohttp warnings.
    # Prefer paved shutdown from scillm; keep router fallback for redundancy.
    try:
        try:
            from scillm.paved import shutdown as scillm_shutdown  # type: ignore

            scillm_shutdown()
        except ImportError:
            logger.debug("scillm.paved.shutdown not available")
        except Exception as exc:
            logger.warning(f"scillm paved shutdown failed: {exc}")

        try:
            import scillm  # type: ignore

            shutdown = getattr(scillm, "shutdown", None) or getattr(
                scillm, "shutdown_clients", None
            )
            if callable(shutdown):
                shutdown()
        except ImportError:
            logger.debug("scillm package not available for shutdown")
        except Exception as exc:
            logger.warning(f"scillm shutdown failed: {exc}")

        if callable(close_all_routers):
            try:
                close_all_routers()
            except Exception as exc:
                logger.warning(f"router shutdown failed: {exc}")

        try:
            import litellm  # type: ignore

            lt_shutdown = getattr(litellm, "shutdown", None)
            if callable(lt_shutdown):
                lt_shutdown()
        except ImportError:
            logger.debug("litellm not available for shutdown")
        except Exception as exc:
            logger.warning(f"litellm shutdown failed: {exc}")

        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task(loop)]
                for t in tasks:
                    t.cancel()
                if tasks:
                    loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception as exc:
            logger.debug(f"asyncio shutdown best-effort failed: {exc}")
    except Exception as exc:
        logger.debug(f"best-effort cleanup wrapper caught: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
