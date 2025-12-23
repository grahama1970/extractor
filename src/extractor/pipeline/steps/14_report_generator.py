#!/usr/bin/env python3
"""
Stage 14: Report Generator
==========================

Generates a comprehensive report (JSON and Markdown) summarizing the entire pipeline run.

This is a thin wrapper around the logic in `extractor.pipeline.utils.report_runner`.
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger

from extractor.pipeline.utils.report_runner import run_report
from extractor.pipeline.utils.step_sanity import run_step_sanity

STEP_NAME = "14_report_generator"

def sanity() -> int:
    return run_step_sanity(STEP_NAME)

def run(results_dir: Path, output_dir: Path) -> Optional[Path]:
    try:
        json_path, _ = run_report(results_dir, output_dir)
        return json_path
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m extractor.pipeline.steps.14_report_generator <pipeline_results_dir> [output_dir]", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "sanity":
        sys.exit(sanity())

    pipeline_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    try:
        json_path, _ = run_report(pipeline_dir, output_dir)
        print(str(json_path))
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
