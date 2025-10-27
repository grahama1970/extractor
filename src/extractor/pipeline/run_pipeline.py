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
  --stop-on-fail           Stop at first failing step (default)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import find_dotenv, load_dotenv
from loguru import logger

from extractor.pipeline.utils.run_manifest import RunManifest


def _step(name: str, fn, *fargs, stop_on_fail: bool = True, **fkw) -> Optional[Path]:
    logger.info(f"{name}: start")
    t0 = time.monotonic()
    try:
        rv = fn(*fargs, **fkw)
        dt = int((time.monotonic() - t0) * 1000)
        # Accept functions that return a path or (path, extra)
        path_like = rv[0] if isinstance(rv, (list, tuple)) and rv else rv
        logger.info(f"{name}: ok in {dt} ms → {path_like}")
        return Path(path_like) if path_like is not None else None
    except Exception as e:
        logger.error(f"{name}: FAIL → {e}")
        if stop_on_fail:
            raise
        return None


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Run extractor pipeline sequentially for debugging")
    p.add_argument("--pdf", required=True, type=Path)
    p.add_argument("--out", default=Path("data/results/pipeline"), type=Path)
    p.add_argument("--summary-only", action="store_true")
    p.add_argument("--skip-fig-descriptions", action="store_true")
    p.add_argument("--skip-export", action="store_true")
    p.add_argument("--stop-on-fail", action="store_true", default=True)
    args = p.parse_args(argv)

    # Load .env once (no import-time side effects in steps)
    try:
        load_dotenv(find_dotenv(), override=True)
    except Exception:
        pass

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

    def _write_artifacts_index(stage_dir: Path) -> None:
        try:
            json_dir = stage_dir / "json_output"
            img_dir = stage_dir / "image_output"
            txt_dir = stage_dir / "text_output"
            idx = {
                "images": [str(p.relative_to(out)) for p in (img_dir.rglob("*"))] if img_dir.exists() else [],
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
        s04_section_builder as s04,
        s05_table_extractor as s05,
        s06_figure_extractor as s06,
        s07_reflow_section as s07,
        s09_section_summarizer as s09,
        s10_arangodb_exporter as s10,
    )

    # 01
    a01 = _step("01_annotation_processor", s01.run, pdf, out, stop_on_fail=args.stop_on_fail)
    if not a01:
        return 1
    results["01"] = a01
    _write_artifacts_index((out / "01_annotation_processor"))
    manifest.record_stage("01_annotation_processor", "Completed", {"json": str(a01.relative_to(out))})

    # 02
    a02 = _step("02_marker_extractor", s02.run, pdf, out, stop_on_fail=args.stop_on_fail)
    if not a02:
        return 1
    results["02"] = a02
    _write_artifacts_index((out / "02_marker_extractor"))
    manifest.record_stage("02_marker_extractor", "Completed", {"json": str(a02.relative_to(out))})

    # 04
    pdf_dir = out / "01_annotation_processor"
    a04_path = _step("04_section_builder", s04.run, a02, pdf_dir, out, stop_on_fail=args.stop_on_fail)
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
        {"json": str(a04_path.relative_to(out))},
        counts={"sections": sec_count} if isinstance(sec_count, int) else None,
    )

    # 05
    a05 = _step("05_table_extractor", s05.run, a04_path, pdf_dir, out, stop_on_fail=args.stop_on_fail)
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
        {"json": str(a05.relative_to(out))},
        counts={"tables": tcount} if isinstance(tcount, int) else None,
    )

    # 05
    a05 = _step("05_table_extractor", s05.run, a04_path, pdf_dir, out, stop_on_fail=args.stop_on_fail)
    if not a05:
        return 1
    results["05"] = a05

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
        {"json": str(a06.relative_to(out))},
        counts={"figures": fcount} if isinstance(fcount, int) else None,
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
        stop_on_fail=args.stop_on_fail,
    )
    if not a07:
        return 1
    results["07"] = a07
    _write_artifacts_index((out / "07_reflow_section"))
    manifest.record_stage("07_reflow_section", "Completed", {"json": str(a07.relative_to(out))})

    # 09
    a09 = _step(
        "09_section_summarizer",
        s09._cmd_run,
        out / "07_reflow_section" / "json_output" / "07_reflowed.json",
        out,
        stop_on_fail=args.stop_on_fail,
    )
    if not a09:
        return 1
    results["09"] = a09
    _write_artifacts_index((out / "09_section_summarizer"))
    manifest.record_stage("09_section_summarizer", "Completed", {"json": str(a09.relative_to(out))})

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
        )
        _write_artifacts_index((out / "10_arangodb_exporter"))
        manifest.record_stage("10_arangodb_exporter", "Completed", {"json": str((out / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json").relative_to(out))})

    logger.info("pipeline: complete")
    for k, v in results.items():
        logger.info(f"  {k} → {v}")

    # Write manifests
    try:
        import json as _json
        manifest = {
            "input_pdf": str(pdf),
            "outputs": {k: str(v) for k, v in results.items()},
            "counts": {},
            "flags": {
                "summary_only": bool(args.summary_only),
                "skip_fig_descriptions": bool(args.skip_fig_descriptions),
            },
        }
        # Best-effort counts
        def _safe_load(p):
            try:
                return _json.loads(Path(p).read_text())
            except Exception:
                return {}
        try:
            d02 = _safe_load(out / "02_marker_extractor/json_output/02_marker_blocks.json")
            manifest["counts"]["blocks02"] = len(d02.get("blocks", []))
        except Exception:
            pass
        try:
            d04 = _safe_load(out / "04_section_builder/json_output/04_sections.json")
            manifest["counts"]["sections04"] = len(d04.get("sections", []))
        except Exception:
            pass
        try:
            d05 = _safe_load(out / "05_table_extractor/json_output/05_tables.json")
            manifest["counts"]["tables05"] = len(d05.get("tables", []))
        except Exception:
            pass
        try:
            d06 = _safe_load(out / "06_figure_extractor/json_output/06_figures.json")
            manifest["counts"]["figures06"] = len(d06.get("figures", [])) if isinstance(d06, dict) else 0
        except Exception:
            pass
        (out / "manifest.json").write_text(_json.dumps(manifest, indent=2))
    except Exception:
        pass
    try:
        manifest_obj_status = "Completed"
        manifest.finalize(manifest_obj_status)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
