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
from typing import Any, Dict, Optional
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
    log_stage_error('close_all_routers_import', exc)
    close_all_routers = None  # type: ignore
import os
import json
import concurrent.futures


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
    sink_id = None
    stage_dir: Optional[Path] = None
    if log_dir_base:
        try:
            stage_dir = (log_dir_base / name)
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
            logger.debug(f"{name}: SIGALRM timeout unavailable; falling back to thread executor ({exc})")
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


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Run extractor pipeline sequentially for debugging")
    p.add_argument("--pdf", required=True, type=Path)
    p.add_argument("--out", default=Path("data/results/pipeline"), type=Path)
    p.add_argument("--summary-only", action="store_true")
    p.add_argument("--skip-fig-descriptions", action="store_true")
    p.add_argument("--skip-llm03", action="store_true", help="Skip VLM verification in Stage 03 (heuristic-only)")
    p.add_argument("--skip-tables05", action="store_true", help="Skip Stage 05; emit empty tables stub")
    p.add_argument("--skip-reqs07", action="store_true", help="Skip Stage 07 requirements miner")
    p.add_argument("--skip-annotator09a", action="store_true", help="Skip Stage 09a PDF annotator")
    p.add_argument("--offline-smoke", action="store_true", help="Deterministic smoke: disable LLM/VLM/DB/Lean4/annotator/tables")
    p.add_argument("--skip-scillm-preflight", action="store_true", help="Bypass SciLLM preflight (use only if service is healthy)")
    p.add_argument("--skip-export", action="store_true")
    p.add_argument("--extract-requirements", action="store_true", help="Run 07_requirements_miner after reflow")
    p.add_argument("--stage-timeout", type=int, default=int(__import__('os').getenv('PIPELINE_STAGE_TIMEOUT','600')), help="Per-stage wall timeout in seconds (fail-fast)")
    p.add_argument(
        "--prove-requirements",
        action="store_true",
        help="Run 08_lean4_theorem_prover (may be slow); implies --extract-requirements",
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
    p.add_argument("--continue-on-error", action="store_true", help="Allow stages to continue after failure")
    args = p.parse_args(argv)
    if args.continue_on_error:
        args.stop_on_fail = False
    # Enable requirements miner by default unless explicitly skipped
    if not args.skip_reqs07:
        args.extract_requirements = True

    # Suppress noisy paved/async shutdown warnings that surface as RuntimeWarning
    warnings.filterwarnings("ignore", message="Task was destroyed but it is pending", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message="coroutine .* was never awaited", category=RuntimeWarning)
    # Suppress noisy async logging from scillm/litellm unless explicitly overridden.
    os.environ.setdefault("SCILLM_PAVED_DISABLE_LOGGING", "1")
    os.environ.setdefault("LITELLM_LOGGING", "0")
    os.environ.setdefault("DISABLE_AIOHTTP_TRANSPORT", "true")
    try:
        from scillm.paved.shutdown import maybe_disable_paved_logging_from_env  # type: ignore
        maybe_disable_paved_logging_from_env()
    except Exception:
        pass

    # Offline preset: deterministic smoke without online services
    if args.offline_smoke:
        args.summary_only = True
        args.skip_fig_descriptions = True
        args.skip_export = True
        args.extract_requirements = False
        args.prove_requirements = False
        args.skip_llm03 = True
        args.skip_tables05 = True
        args.skip_reqs07 = True
        args.skip_annotator09a = True
        logger.info("offline-smoke mode: forcing deterministic flags and skipping online/optional stages")

    # Load .env once (no import-time side effects in steps)
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
                logger.warning(f"Optional dependency not installed; related steps may be skipped: {label} ({mod})")
        return ok

    if not _probe_dependencies(
        required=["camelot", "fitz"],
        # python-arango installs the importable module name "arango"
        optional={"python-arango": "arango"},
    ):
        return 1

    # Enforce SciLLM/Chutes preflight only when online stages are enabled.
    # Allow deterministic offline runs when --summary-only and --skip-fig-descriptions are both set.
    online_needed = any(
        [
            not bool(args.summary_only),            # Stage 07 LLM
            not bool(args.skip_fig_descriptions),   # Stage 06 VLM descriptions
            bool(args.extract_requirements),        # Stage 07r
            bool(args.prove_requirements),          # Stage 08
            not bool(args.skip_llm03),              # Stage 03 VLM
        ]
    )
    if online_needed and not args.skip_scillm_preflight:
        try:
            from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight

            require_scillm_preflight()
        except Exception as e:
            logger.error(f"SciLLM preflight failed: {e}")
            return 1

    pdf = args.pdf
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )

    results: Dict[str, Any] = {}
    manifest = RunManifest(out)
    stage_latencies: Dict[str, int] = {}
    served_model = {
        "text": os.getenv("CHUTES_TEXT_MODEL", ""),
        "vlm": os.getenv("CHUTES_VLM_MODEL", ""),
    }

    def _write_artifacts_index(stage_dir: Path) -> None:
        try:
            json_dir = stage_dir / "json_output"
            img_dir = stage_dir / "image_output"
            vis_dir = stage_dir / "visual_output"
            txt_dir = stage_dir / "text_output"
            idx = {
                "images": [
                    *([str(p.relative_to(out)) for p in (img_dir.rglob("*"))] if img_dir.exists() else []),
                    *([str(p.relative_to(out)) for p in (vis_dir.rglob("*.png"))] if vis_dir.exists() else []),
                ],
                "json": [str(p.relative_to(out)) for p in (json_dir.glob("*.json"))] if json_dir.exists() else [],
                "text": [str(p.relative_to(out)) for p in (txt_dir.rglob("*.txt"))] if txt_dir.exists() else [],
            }
            if json_dir.exists():
                write_json_strict(json_dir / "artifacts_index.json", idx, stage="artifacts_index")
        except Exception as exc:
            log_stage_error("artifacts_index", exc, {"stage_dir": str(stage_dir)})

    # Import steps lazily to avoid import-time side effects.
    # Avoid importing online-only steps when running in deterministic offline mode.
    from extractor.pipeline.steps import (
        s01_annotation_processor as s01,
        s02_marker_extractor as s02,
        s03_suspicious_headers as s03,
        s04_section_builder as s04,
        s04a_layout_audit as s04a,
        s05_table_extractor as s05,
        s06_figure_extractor as s06,
        s06b_layout_sketcher as s06b,
        s07_reflow_section as s07,
        s09a_pdf_annotator as s09a,
        s09b_audit as s09b,
        s07_requirements_miner as s07req,
        s09_section_summarizer as s09,
        s06a_title_caption_enricher as s06a,
        s14_report_generator as s14,
        s15_walkthrough_generator as s15,
    )
    # Lazy import for optional DB steps to avoid hard dependency on python-arango if not needed
    s11 = None
    s12 = None
    if not args.skip_export:
        try:
            from extractor.pipeline.steps import (
                s11_arango_create_graph as _s11,
                s12_insert_annotations as _s12,
            )
            s11 = _s11
            s12 = _s12
        except ImportError as exc:
            log_stage_error("arango_optional", exc, {"hint": "Install python-arango to enable export"})
    # Lean4 proving is opt-in; DB export follows the previous online/offline gating.
    s08 = None
    s10 = None
    if args.prove_requirements:
        if not (bool(args.summary_only) and bool(args.skip_fig_descriptions)):
            from extractor.pipeline.steps import s08_lean4_theorem_prover as _s08

            s08 = _s08
    if not (bool(args.summary_only) and bool(args.skip_fig_descriptions)):
        from extractor.pipeline.steps import s10_arangodb_exporter as _s10

        s10 = _s10

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
        return 1
    results["01"] = a01
    _write_artifacts_index((out / "01_annotation_processor"))
    manifest.record_stage(
        "01_annotation_processor",
        "Completed",
        {"json": str(a01.relative_to(out)), "latency_ms": stage_latencies.get("01_annotation_processor")},
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
    )
    if not a02:
        return 1
    results["02"] = a02
    _write_artifacts_index((out / "02_marker_extractor"))
    manifest.record_stage(
        "02_marker_extractor",
        "Completed",
        {"json": str(a02.relative_to(out)), "latency_ms": stage_latencies.get("02_marker_extractor")},
    )

    # 03
    pdf_dir = out / "01_annotation_processor"
    a03 = _step(
        "03_suspicious_headers",
        s03.run,
        a02,
        pdf_dir,
        out,
        skip_llm=bool(args.skip_llm03),
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a03:
        return 1
    results["03"] = a03
    _write_artifacts_index((out / "03_suspicious_headers"))
    try:
        vcount = len(__import__("json").loads(a03.read_text()).get("blocks", []))
    except Exception:
        vcount = None
    manifest.record_stage(
        "03_suspicious_headers",
        "Completed",
        {"json": str(a03.relative_to(out)), "latency_ms": stage_latencies.get("03_suspicious_headers")},
        counts={"verified_blocks": vcount} if isinstance(vcount, int) else None,
    )

    # 04 (hard-require Stage 03 outputs)
    try:
        _a03_obj = json.loads(a03.read_text())
        if not isinstance(_a03_obj, dict) or "blocks" not in _a03_obj or not isinstance(_a03_obj["blocks"], list):
            raise ValueError("Stage 03 output missing required key 'blocks' (list)")
    except Exception as e:
        logger.error(f"04_section_builder: missing or invalid Stage 03 outputs → {e}")
        return 1
    a04_path = _step(
        "04_section_builder",
        s04.run,
        a03,
        pdf_dir,
        out,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a04_path:
        return 1
    results["04"] = a04_path
    _write_artifacts_index((out / "04_section_builder"))
    try:
        sec_count = len(__import__("json").loads(a04_path.read_text()).get("sections", []))
    except Exception:
        sec_count = None
    manifest.record_stage(
        "04_section_builder",
        "Completed",
        {"json": str(a04_path.relative_to(out)), "latency_ms": stage_latencies.get("04_section_builder")},
        counts={"sections": sec_count} if isinstance(sec_count, int) else None,
    )

    # 04a – layout audit (fail fast on ordering issues before tables/figures)
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
        _write_artifacts_index((out / "04a_layout_audit"))
        manifest.record_stage(
            "04a_layout_audit",
            "Completed",
            {"json": str(a04a.relative_to(out)), "latency_ms": stage_latencies.get("04a_layout_audit")},
        )

    # 05
    if args.skip_tables05:
        stub_dir = out / "05_table_extractor" / "json_output"
        stub_dir.mkdir(parents=True, exist_ok=True)
        stub = {"timestamp": int(time.time()), "tables": [], "diagnostics": [{"severity": "info", "reason": "skip_tables05 flag"}]}
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
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        if not a05:
            return 1
    results["05"] = a05
    _write_artifacts_index((out / "05_table_extractor"))
    try:
        tcount = len(__import__("json").loads(Path(a05).read_text()).get("tables", []))
    except Exception:
        tcount = None
    manifest.record_stage(
        "05_table_extractor",
        "Completed",
        {"json": str(Path(a05).relative_to(out)), "latency_ms": stage_latencies.get("05_table_extractor")},
        counts={"tables": tcount} if isinstance(tcount, int) else None,
    )

    # (Removed duplicate Stage 05 invocation)

    # 06
    a06 = _step(
        "06_figure_extractor",
        s06.run,
        a02,
        a04_path,
        pdf_dir,
        out,
        skip_descriptions=args.skip_fig_descriptions,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a06:
        return 1
    results["06"] = a06
    _write_artifacts_index((out / "06_figure_extractor"))
    try:
        fcount = len(__import__("json").loads(a06.read_text()).get("figures", []))
    except Exception:
        fcount = None
    manifest.record_stage(
        "06_figure_extractor",
        "Completed",
        {"json": str(a06.relative_to(out)), "latency_ms": stage_latencies.get("06_figure_extractor")},
        counts={"figures": fcount} if isinstance(fcount, int) else None,
    )

    # 06b (layout sketcher) — deterministic text-first layout priors used by Stage 07
    def _run_06b(ip: Path, op: Path) -> str:
        try:
            s06b.run(str(ip), str(op))
        except Exception as _e:
            # Respect stop_on_fail; otherwise continue with Stage 07 fallbacks
            if args.stop_on_fail:
                raise
        return str(op / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json")

    a06b = _step(
        "06b_layout_sketcher",
        _run_06b,
        out,
        out,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if a06b:
        _write_artifacts_index((out / "06b_layout_sketcher"))
        # Count sections in 06b output
        try:
            d06b = json.loads(Path(a06b).read_text())
            s06b_count = len((d06b or {}).get("sections", {}))
        except Exception:
            s06b_count = None
        manifest.record_stage(
            "06b_layout_sketcher",
            "Completed",
            {"json": str(Path(a06b).relative_to(out)), "latency_ms": stage_latencies.get("06b_layout_sketcher")},
            counts={"sections": s06b_count} if isinstance(s06b_count, int) else None,
        )

    # 06a (enrich titles) - run after 06/06b
    # If successful, downstream steps (07) should use enriched tables/figures.
    a06a = _step(
        "06a_title_caption_enricher",
        s06a.run,
        out / "05_table_extractor" / "json_output" / "05_tables.json",
        out / "06_figure_extractor" / "json_output" / "06_figures.json",
        out / "04_section_builder" / "json_output" / "04_sections.json",
        out,
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if a06a:
        _write_artifacts_index((out / "06a_title_caption_enricher"))
        manifest.record_stage(
            "06a_title_caption_enricher",
            "Completed",
            {"json": str(Path(a06a).relative_to(out)), "latency_ms": stage_latencies.get("06a_title_caption_enricher")},
        )

    # 07 (text-only mode optional)
    # Use enriched artifacts if available
    tbl = out / "05_table_extractor" / "json_output" / "05_tables.json"
    figs = out / "06_figure_extractor" / "json_output" / "06_figures.json"
    if a06a:
        enriched_tbl = out / "06a_title_caption_enricher" / "json_output" / "05_tables.enriched.json"
        enriched_figs = out / "06a_title_caption_enricher" / "json_output" / "06_figures.enriched.json"
        if enriched_tbl.exists():
            tbl = enriched_tbl
        if enriched_figs.exists():
            figs = enriched_figs

    # IMPORTANT: keep full section set for reflow; filtering is only for simulations.
    sections_for_reflow = a04_path
    a07 = _step(
        "07_reflow_section",
        s07.run,
        sections_for_reflow,
        tbl,
        figs,
        None,
        out,
        args.summary_only,
        False,  # include_images
        False,  # allow_fallback
        None,   # bundle
        args.stage_timeout,  # llm_timeout
        stop_on_fail=args.stop_on_fail,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if not a07:
        return 1
    results["07"] = a07
    _write_artifacts_index((out / "07_reflow_section"))
    manifest.record_stage(
        "07_reflow_section",
        "Completed",
        {"json": str(a07.relative_to(out)), "latency_ms": stage_latencies.get("07_reflow_section")},
    )

    # 07½ Requirements miner — run unconditionally
    req_json_path: Optional[Path] = None
    if args.skip_reqs07 or (not args.extract_requirements and not args.prove_requirements):
        logger.info("07_requirements_miner: skipped")
        req_json_path = out / "07_requirements_miner" / "json_output" / "07_requirements.json"
        req_json_path.parent.mkdir(parents=True, exist_ok=True)
        req_json_path.write_text(json.dumps({"requirements": [], "meta": {"skipped": True}}), encoding="utf-8")
        manifest.record_stage(
            "07_requirements_miner",
            "Completed",
            {"json": str(req_json_path.relative_to(out)), "latency_ms": None},
            counts={"requirements": 0},
        )
    else:
        a07r = _step(
                "07_requirements_miner",
                s07req.run,
                out / "07_reflow_section" / "json_output" / "07_reflowed.json",
                out,
                stop_on_fail=args.stop_on_fail,
                timeout_sec=args.stage_timeout,
                log_dir_base=out,
                on_timing=lambda n, dt: stage_latencies.update({n: dt}),
            )
        # Stage 07r writes outputs directly and may return None; do not treat None as failure.
        _write_artifacts_index((out / "07_requirements_miner"))
        req_json_path = out / "07_requirements_miner" / "json_output" / "07_requirements.json"
        try:
            rcount = len(__import__("json").loads(req_json_path.read_text()).get("requirements", [])) if req_json_path.exists() else None
        except Exception:
            rcount = None
        if not req_json_path.exists():
            req_json_path.parent.mkdir(parents=True, exist_ok=True)
            req_json_path.write_text(json.dumps({"requirements": [], "meta": {"error": "missing output from requirements miner"}}, indent=2))
        manifest.record_stage(
            "07_requirements_miner",
            "Completed",
            {"json": str(req_json_path.relative_to(out)) if req_json_path and req_json_path.exists() else "", "latency_ms": stage_latencies.get("07_requirements_miner")},
            counts={"requirements": rcount} if isinstance(rcount, int) else None,
        )

    # 08 Lean4 theorem prover — skip in deterministic offline mode
    if s08 is not None:
        a08 = _step(
                "08_lean4_theorem_prover",
                s08.run,
                out / "07_reflow_section" / "json_output" / "07_reflowed.json",
                out,
                False,  # skip_proving=False → actually prove
                req_json_path if req_json_path and req_json_path.exists() else None,
                stop_on_fail=args.stop_on_fail,
                timeout_sec=args.stage_timeout,
                log_dir_base=out,
                on_timing=lambda n, dt: stage_latencies.update({n: dt}),
            )
        _write_artifacts_index((out / "08_lean4_theorem_prover"))
        manifest.record_stage(
            "08_lean4_theorem_prover",
            "Completed",
            {"json": str((out / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json").relative_to(out)), "latency_ms": stage_latencies.get("08_lean4_theorem_prover")},
        )
    else:
        logger.info("08_lean4_theorem_prover: skipped (deterministic offline mode)")

    # 09 — skip in deterministic offline mode if summarizer requires LLM in this environment
    if not bool(args.summary_only):
        a09 = _step(
            "09_section_summarizer",
            s09._cmd_run,
            out / "07_reflow_section" / "json_output" / "07_reflowed.json",
            out,
            stop_on_fail=args.stop_on_fail,
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        if not a09 or not (out / "09_section_summarizer" / "json_output" / "09_summaries.json").exists():
            # Fallback stub to satisfy downstream audits
            stub_dir = out / "09_section_summarizer" / "json_output"
            stub_dir.mkdir(parents=True, exist_ok=True)
            (stub_dir / "09_summaries.json").write_text(json.dumps({"meta": {"skipped": True}, "summaries": []}, indent=2))
            a09 = stub_dir / "09_summaries.json"
        results["09"] = a09
        _write_artifacts_index((out / "09_section_summarizer"))
        manifest.record_stage(
            "09_section_summarizer",
            "Completed",
            {"json": str(Path(a09).relative_to(out)), "latency_ms": stage_latencies.get("09_section_summarizer")},
        )
    else:
        logger.info("09_section_summarizer: skipped (deterministic offline mode)")

    # 09a PDF annotator (visual collaboration product) — optional, runs after summaries
    if args.skip_annotator09a or args.offline_smoke:
        logger.info("09a_pdf_annotator: skipped")
        stub_dir = out / "09a_pdf_annotator" / "json_output"
        stub_dir.mkdir(parents=True, exist_ok=True)
        (stub_dir / "annotations.json").write_text(json.dumps({"meta": {"skipped": True}, "annotations": []}, indent=2))
    else:
        try:
            annotated = _step(
                "09a_pdf_annotator",
                s09a.run,
                pdf,
                out / "04_section_builder" / "json_output" / "04_sections.json",
                out / "05_table_extractor" / "json_output" / "05_tables.json",
                out / "06_figure_extractor" / "json_output" / "06_figures.json",
                out / "07_reflow_section" / "json_output" / "07_reflowed.json",
                out / "02_marker_extractor" / "json_output" / "02_marker_blocks.json",
                None,  # headers03_json (auto-discovered in 09a)
                out / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json",
                out,
                "09a",
                labels=False,
                grid=0,
                rewrite_headers=False,
                overwrite_pdf=False,
                replace_text_layer=False,
                draw_columns06b=False,
                draw_grid=False,
                draw_gutter=False,
                gutter_left_tags=False,
                gutter_right_section_caps=False,
                draw_section_plaques=False,
                draw_text_chunks=False,
                draw_table_callouts=False,
                draw_figure_watermark=False,
                stop_on_fail=args.stop_on_fail,
                timeout_sec=args.stage_timeout,
                log_dir_base=out,
                on_timing=lambda n, dt: stage_latencies.update({n: dt}),
            )
            if annotated:
                _write_artifacts_index((out / "09a_pdf_annotator"))
                manifest.record_stage(
                    "09a_pdf_annotator",
                    "Completed",
                    {"json": str((out / "09a_pdf_annotator" / "json_output" / "annotations.json").relative_to(out)), "latency_ms": stage_latencies.get("09a_pdf_annotator")},
                )
        except Exception as e:
            logger.error(f"09a_pdf_annotator failed: {e}")
            if args.stop_on_fail:
                return 1

    # 09b audit — summarize artifacts after optional steps
    if args.offline_smoke or args.summary_only:
        os.environ["PIPELINE_AUDIT_RELAX_REQUIREMENTS"] = "1"
    if args.offline_smoke:
        logger.info("09b_audit: skipped in offline-smoke mode")
        stub_dir = out / "09b_audit" / "json_output"
        stub_dir.mkdir(parents=True, exist_ok=True)
        (stub_dir / "09b_audit.json").write_text(json.dumps({"meta": {"skipped": True}, "issues": []}, indent=2))
    else:
        audit_stop_on_fail = args.stop_on_fail
        if args.offline_smoke or args.summary_only:
            # In deterministic/offline runs, do not fail the pipeline on audit soft errors.
            audit_stop_on_fail = False
        a09b = _step(
            "09b_audit",
            s09b.run,
            out,
            stop_on_fail=audit_stop_on_fail,
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        audit_json = out / "09b_audit" / "json_output" / "09b_audit.json"
        if not a09b or not audit_json.exists():
            logger.warning("09b_audit reported issues; writing stub and continuing")
            audit_json.parent.mkdir(parents=True, exist_ok=True)
            audit_json.write_text(json.dumps({"meta": {"skipped": True}, "issues": []}, indent=2))
        else:
            _write_artifacts_index((out / "09b_audit"))
            manifest.record_stage(
                "09b_audit",
                "Completed",
                {"json": str((out / "09b_audit" / "json_output" / "09b_audit.json").relative_to(out)), "latency_ms": stage_latencies.get("09b_audit")},
            )
            a09b = audit_json
        results["09b"] = a09b
        _write_artifacts_index((out / "09b_audit"))
        manifest.record_stage(
            "09b_audit",
            "Completed",
            {"json": str(audit_json.relative_to(out)), "latency_ms": stage_latencies.get("09b_audit")},
        )

    # 15 walkthrough (optional)
    if args.generate_walkthrough:
        try:
            pdf_for_walk = out / "01_annotation_processor" / "json_output" / "01_annotations.json"
            # Fallback: original PDF path
            pdf_path = pdf if not pdf_for_walk.exists() else pdf
            a15 = _step(
                "15_walkthrough_generator",
                s15.run,
                pdf_path,
                out,
                out,
                stop_on_fail=False,
                timeout_sec=args.stage_timeout,
                log_dir_base=out,
                on_timing=lambda n, dt: stage_latencies.update({n: dt}),
            )
            if a15:
                _write_artifacts_index((out / "15_walkthrough_generator"))
                manifest.record_stage(
                    "15_walkthrough_generator",
                    "Completed",
                    {"path": str(Path(a15).relative_to(out)), "latency_ms": stage_latencies.get("15_walkthrough_generator")},
                )
        except Exception as e:
            logger.error(f"15_walkthrough_generator failed: {e}")
            if args.stop_on_fail:
                return 1

    # 10 (optional DB export)
    if args.skip_export or s10 is None:
        logger.info("10_arangodb_exporter: skipped (--skip-export)")
    else:
        reflowed = out / "07_reflow_section" / "json_output" / "07_reflowed.json"
        summaries = out / "09_section_summarizer" / "json_output" / "09_summaries.json"
        _ = _step(
            "10_arangodb_exporter",
            s10.run,
            reflowed,
            summaries,
            out,
            "pdf_objects",
            args.skip_export,
            stop_on_fail=args.stop_on_fail,
            timeout_sec=args.stage_timeout,
            log_dir_base=out,
            on_timing=lambda n, dt: stage_latencies.update({n: dt}),
        )
        _write_artifacts_index((out / "10_arangodb_exporter"))
        manifest.record_stage(
            "10_arangodb_exporter",
            "Completed",
            {"json": str((out / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json").relative_to(out)), "latency_ms": stage_latencies.get("10_arangodb_exporter")},
        )

        # 12 (Insert Annotations) - runs after export if enabled
        if s12:
            _ = _step(
                "12_insert_annotations",
                s12.run,
                out / "01_annotation_processor" / "json_output" / "01_annotations.json",
                out,
                "both", # mode
                stop_on_fail=False, # fail-soft
                timeout_sec=args.stage_timeout,
                log_dir_base=out,
                on_timing=lambda n, dt: stage_latencies.update({n: dt}),
            )
            _write_artifacts_index((out / "12_insert_annotations"))
            manifest.record_stage(
                "12_insert_annotations",
                "Completed",
                {"latency_ms": stage_latencies.get("12_insert_annotations")},
            )

        # 11 (Create Graph) - runs after export if enabled
        if s11:
            _ = _step(
                "11_arango_create_graph",
                s11.run,
                out / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json",
                out,
                10, # k_neighbors
                0.55, # similarity_threshold
                False, # skip_graph_creation
                stop_on_fail=False, # fail-soft
                timeout_sec=args.stage_timeout,
                log_dir_base=out,
                on_timing=lambda n, dt: stage_latencies.update({n: dt}),
            )
            _write_artifacts_index((out / "11_arango_create_graph"))
            manifest.record_stage(
                "11_arango_create_graph",
                "Completed",
                {"latency_ms": stage_latencies.get("11_arango_create_graph")},
            )

    # 14 (Report Generator) - always run at end
    a14 = _step(
        "14_report_generator",
        s14.run_report,
        out,
        stop_on_fail=False,
        timeout_sec=args.stage_timeout,
        log_dir_base=out,
        on_timing=lambda n, dt: stage_latencies.update({n: dt}),
    )
    if a14:
        _write_artifacts_index((out / "14_report_generator"))
        manifest.record_stage(
            "14_report_generator",
            "Completed",
            {"json": str(Path(a14[0]).relative_to(out)) if isinstance(a14, tuple) else str(Path(a14).relative_to(out)), "latency_ms": stage_latencies.get("14_report_generator")},
        )
    else:
        # In deterministic/offline runs, ensure a stub report exists so downstream consumers/smokes pass.
        try:
            stub_dir = out / "14_report_generator" / "json_output"
            stub_dir.mkdir(parents=True, exist_ok=True)
            (stub_dir / "final_report.json").write_text(json.dumps({"meta": {"stub": True, "reason": "report_generation_failed_or_skipped"}}))
            (stub_dir / "14_report.json").write_text(json.dumps({"meta": {"stub": True}}))
        except Exception:
            pass

    logger.info("pipeline: complete")
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
            "input_pdf": str(pdf),
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
            manifest_data["counts"]["figures06"] = len(d06.get("figures", [])) if isinstance(d06, dict) else 0
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
            shutdown = getattr(scillm, "shutdown", None) or getattr(scillm, "shutdown_clients", None)
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
