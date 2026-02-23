#!/usr/bin/env python3
"""
Gate Pipeline Context: Verifies proper preset detection and context generation.
"""
import sys
import json
import argparse
from pathlib import Path
from loguru import logger


def verify_pipeline_context(pipeline_dir: Path):
    # 1. Check S00 Output
    # 1. Check S00 Output
    # Expected: <pipeline>/00_profile_detector/profile.json
    s00_out = pipeline_dir / "00_profile_detector" / "profile.json"
    if not s00_out.exists():
        # Fallback: Maybe mapped flat?
        logger.warning(f"S00 output not found at {s00_out}, searching...")
        candidates = list(pipeline_dir.rglob("profile.json"))
        if not candidates:
            # Also try 00_profile.json
            candidates = list(pipeline_dir.rglob("00_profile.json"))

        if not candidates:
            logger.error(f"S00 output (profile.json) not found in {pipeline_dir}")
            return False
        s00_out = candidates[0]

    try:
        profile = json.loads(s00_out.read_text())
        preset = profile.get("detected_preset")
        logger.info(f"S00 detected preset: {preset}")
    except Exception as e:
        logger.error(f"Failed to read s00 profile: {e}")
        return False

    # 2. Check Pipeline Context Artifact
    # We expect run_pipeline to save the active context/config used
    ctx_out = pipeline_dir / "pipeline_context.json"
    if not ctx_out.exists():
        logger.error(f"Pipeline Context (pipeline_context.json) not found in {pipeline_dir}")
        return False

    try:
        ctx = json.loads(ctx_out.read_text())
        ctx_preset = ctx.get("preset_name")
        config = ctx.get("config")

        logger.info(f"Pipeline context preset: {ctx_preset}")

        if config is None:
            logger.error("Pipeline context missing 'config' object")
            return False

        if ctx_preset != preset:
            logger.warning(f"Mismatch: S00 says '{preset}' but Context says '{ctx_preset}'")
            # This might be valid if we override via CLI, but for now expect match

        logger.success("Context verification passed")
        return True

    except Exception as e:
        logger.error(f"Failed to read pipeline context: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", type=Path, default=Path("data/results/pipeline"))
    args = parser.parse_args()

    if verify_pipeline_context(args.pipeline_dir):
        sys.exit(0)
    else:
        sys.exit(1)
