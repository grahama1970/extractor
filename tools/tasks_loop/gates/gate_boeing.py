#!/usr/bin/env python3
"""
Gate Boeing: Verifies requirements_spec preset execution.
"""
import sys
import json
import argparse
from pathlib import Path
from loguru import logger

def verify_boeing(pipeline_dir: Path):
    # 1. Check Context
    ctx_out = pipeline_dir / "pipeline_context.json"
    if not ctx_out.exists():
        logger.error("pipeline_context.json missing")
        return False
        
    try:
        ctx = json.loads(ctx_out.read_text())
        preset = ctx.get("preset_name")
        config = ctx.get("config", {})
        
        logger.info(f"Detected Preset: {preset}")
        
        if preset != "requirements_spec":
            logger.error(f"Expected 'requirements_spec', got '{preset}'")
            # Fail unless we allow partial matches? No, we demand exact detection here.
            return False
            
        if not config:
            logger.error("Config missing in context")
            return False
            
        # Verify regex passed
        pat = config.get("detection", {}).get("section_pattern")
        logger.info(f"Active Regex: {pat}")
        if not pat:
            logger.warning("No section_pattern in context config!")
            
    except Exception as e:
        logger.error(f"Context check failed: {e}")
        return False

    # 2. Check Sections
    sections_out = pipeline_dir / "04_section_builder/json_output/04_sections.json"
    if not sections_out.exists():
        logger.error("04_sections.json missing")
        return False
        
    try:
        data = json.loads(sections_out.read_text())
        sections = data.get("sections", [])
        count = len(sections)
        logger.info(f"Sections built: {count}")
        
        if count == 0:
            logger.error("No sections built! Regex might be failing or PDF is empty.")
            return False
            
        # Optional: Check if titles look right
        titles = [s.get("title") for s in sections[:3]]
        logger.info(f"First 3 sections: {titles}")
        
        return True
    except Exception as e:
        logger.error(f"Section check failed: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", type=Path, default=Path("data/results/pipeline"))
    args = parser.parse_args()
    
    if verify_boeing(args.pipeline_dir):
        sys.exit(0)
    else:
        sys.exit(1)
