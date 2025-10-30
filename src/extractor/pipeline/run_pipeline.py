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

from dotenv import find_dotenv, load_dotenv
from loguru import logger

from extractor.pipeline.utils.run_manifest import RunManifest
try:
    # Best-effort import for global router shutdown to avoid aiohttp warnings
    from extractor.pipeline.utils.scillm_router import close_all_routers  # type: ignore
except Exception:  # pragma: no cover - optional import
    close_all_routers = None  # type: ignore
import os
import json
import concurrent.futures


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
        except Exception:
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
        logger.error(f"{name}: FAIL → {e}")
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
    p.add_argument("--skip-export", action="store_true")
    p.add_argument("--extract-requirements", action="store_true", help="Run 07_requirements_miner after reflow")
    p.add_argument("--stage-timeout", type=int, default=int(__import__('os').getenv('PIPELINE_STAGE_TIMEOUT','300')), help="Per-stage wall timeout in seconds (fail-fast)")
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
    p.add_argument("--stop-on-fail", action="store_true", default=False)
    args = p.parse_args(argv)

    # Load .env once (no import-time side effects in steps)
    try:
        load_dotenv(find_dotenv(), override=True)
    except Exception:
        pass

    # Enforce SciLLM/Chutes preflight for an online-only pipeline.
    # If Chutes is not reachable or misconfigured, fail fast (no offline bypasses).
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
                (json_dir / "artifacts_index.json").write_text(
                    __import__("json").dumps(idx, indent=2)
                )
        except Exception:
            pass

    # Import steps lazily to avoid import-time side effects
    from extractor.pipeline.steps import (
        s01_annotation_processor as s01,
        s02_marker_extractor as s02,
        s03_suspicious_headers as s03,
        s04_section_builder as s04,
        s05_table_extractor as s05,
        s06_figure_extractor as s06,
        s06b_layout_sketcher as s06b,
        s07_reflow_section as s07,
        s09a_pdf_annotator as s09a,
        s07_requirements_miner as s07req,
        s08_lean4_theorem_prover as s08,
        s09_section_summarizer as s09,
        s10_arangodb_exporter as s10,
    )

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

    # 05
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
        tcount = len(__import__("json").loads(a05.read_text()).get("tables", []))
    except Exception:
        tcount = None
    manifest.record_stage(
        "05_table_extractor",
        "Completed",
        {"json": str(a05.relative_to(out)), "latency_ms": stage_latencies.get("05_table_extractor")},
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

    # 07 (text-only mode optional)
    tbl = out / "05_table_extractor" / "json_output" / "05_tables.json"
    figs = out / "06_figure_extractor" / "json_output" / "06_figures.json"
    a07 = _step(
        "07_reflow_section",
        s07.run,
        a04_path,
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

    # 09a PDF annotator (visual collaboration product) — run unconditionally
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
            True,
            12,
            False,
            False,
            False,
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

    # 07½ Requirements miner — run unconditionally
    req_json_path: Optional[Path] = None
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
    manifest.record_stage(
        "07_requirements_miner",
        "Completed",
        {"json": str(req_json_path.relative_to(out)) if req_json_path and req_json_path.exists() else "", "latency_ms": stage_latencies.get("07_requirements_miner")},
        counts={"requirements": rcount} if isinstance(rcount, int) else None,
    )

    # 08 Lean4 theorem prover — run unconditionally
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
    # Stage 08 writes outputs directly and may return None; do not treat None as failure.
    _write_artifacts_index((out / "08_lean4_theorem_prover"))
    manifest.record_stage(
        "08_lean4_theorem_prover",
        "Completed",
        {"json": str((out / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json").relative_to(out)), "latency_ms": stage_latencies.get("08_lean4_theorem_prover")},
    )

    # 09
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
    if not a09:
        return 1
    results["09"] = a09
    _write_artifacts_index((out / "09_section_summarizer"))
    manifest.record_stage(
        "09_section_summarizer",
        "Completed",
        {"json": str(a09.relative_to(out)), "latency_ms": stage_latencies.get("09_section_summarizer")},
    )

    # 10 (optional DB export)
    if args.skip_export:
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
    except Exception:
        pass
    try:
        manifest.finalize("Completed")
    except Exception:
        pass
    # Ensure any shared SciLLM routers are closed to prevent aiohttp warnings.
    try:
        if callable(close_all_routers):
            close_all_routers()
    except Exception:
        # Do not fail the run on best-effort cleanup.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
