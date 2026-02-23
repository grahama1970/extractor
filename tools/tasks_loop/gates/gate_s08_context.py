#!/usr/bin/env python3
"""
Gate s08 Context: Verify s08 execution state based on preset.
"""
import sys
import json
import argparse
from pathlib import Path
from loguru import logger


def check_run(pipeline_dir: Path, expected_run: bool):
    manifest_path = pipeline_dir / "manifest.json"
    if not manifest_path.exists():
        logger.error(f"Manifest not found in {pipeline_dir}")
        return False

    try:
        manifest = json.loads(manifest_path.read_text())
        timings = manifest.get("timings_ms", {})

        ran_s08 = "08b_lean4_theorem_prover" in timings

        logger.info(f"Pipeline {pipeline_dir.name}: s08 ran? {ran_s08}")

        if expected_run and not ran_s08:
            logger.error(f"Expected s08 to run for {pipeline_dir.name}, but it didn't.")
            return False

        if not expected_run and ran_s08:
            logger.error(f"Expected s08 to SKIP for {pipeline_dir.name}, but it ran!")
            return False

        return True

    except Exception as e:
        logger.error(f"Failed to parse manifest: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arxiv-dir", type=Path)
    parser.add_argument("--boeing-dir", type=Path)
    args = parser.parse_args()

    ok = True
    if args.arxiv_dir:
        if not check_run(args.arxiv_dir, expected_run=True):
            ok = False

    if args.boeing_dir:
        # Boeing should NOT run s08
        if not check_run(args.boeing_dir, expected_run=False):
            ok = False

    if ok:
        logger.success("S08 Context Verification Passed")
        sys.exit(0)
    else:
        sys.exit(1)
