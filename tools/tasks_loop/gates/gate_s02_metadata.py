#!/usr/bin/env python3
"""
Gate S02 Metadata: Verifies Stage 02 output format.
"""
import sys
import json
import argparse
from pathlib import Path
from loguru import logger

def verify_s02_output(pipeline_dir: Path):
    s02_dir = pipeline_dir / "02_marker_extractor" / "json_output"
    if not s02_dir.exists():
        logger.error(f"S02 output dir not found: {s02_dir}")
        return False

    json_files = list(s02_dir.glob("02_marker_blocks.json"))
    if not json_files:
        logger.error("02_marker_blocks.json not found")
        return False
        
    s02_file = json_files[0]
    try:
        data = json.loads(s02_file.read_text())
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return False

    # Check structure
    metadata = data.get("metadata")
    if not metadata:
        logger.error("Missing 'metadata' field in S02 output")
        return False
        
    llm_used = metadata.get("llm_used")
    if llm_used is None: # Can be False, but must exist
        logger.error("Missing 'metadata.llm_used'")
        return False
        
    page_count = metadata.get("page_count")
    if page_count is None:
        logger.error("Missing 'metadata.page_count'")
        return False
        
    logger.success(f"Verified metadata: llm_used={llm_used}, pages={page_count}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", type=Path, default=Path("data/results/pipeline"))
    args = parser.parse_args()
    
    if verify_s02_output(args.pipeline_dir):
        sys.exit(0)
    else:
        sys.exit(1)
