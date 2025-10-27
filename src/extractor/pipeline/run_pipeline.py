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


def _step(name: str, fn, *fargs, stop_on_fail: bool = True, **fkw) -> Optional[Path]:
    logger.info(f"{name}: start")
    t0 = time.monotonic()
    try:
        path = fn(*fargs, **fkw)
        dt = int((time.monotonic() - t0) * 1000)
        logger.info(f"{name}: ok in {dt} ms → {path}")
        return Path(path)
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

    # 02
    a02 = _step("02_marker_extractor", s02.run, pdf, out, stop_on_fail=args.stop_on_fail)
    if not a02:
        return 1
    results["02"] = a02

    # 04
    pdf_dir = out / "01_annotation_processor"
    a04_path = _step("04_section_builder", s04.run, a02, pdf_dir, out, stop_on_fail=args.stop_on_fail)
    if not a04_path:
        return 1
    results["04"] = a04_path

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

    logger.info("pipeline: complete")
    for k, v in results.items():
        logger.info(f"  {k} → {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

