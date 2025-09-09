#!/usr/bin/env python3
"""
Test marker extraction with LLMFormProcessor fix
"""

import sys
import subprocess
from pathlib import Path
import json
import shutil
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

# Set up paths
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root / 'src'))

# Setup working directory
working_dir = project_root / "tmp" / "test_marker_fix"
working_dir.mkdir(parents=True, exist_ok=True)

# Input PDF
input_pdf = project_root / "proof_of_concept" / "BHT_CV32A65X_marked.pdf"
test_pdf = working_dir / "test.pdf"

# Copy input PDF
logger.info(f"Copying input PDF to working directory")
shutil.copy(input_pdf, test_pdf)


def test_marker_with_fix():
    """Test marker extraction after fixing LLMFormProcessor"""
    logger.info("=" * 60)
    logger.info("Testing Marker Extraction with Fix")
    logger.info("=" * 60)
    
    # Run marker extraction
    cmd = f"cd {project_root} && python -m extractor.core.scripts.convert_single {test_pdf} --output_dir {working_dir} --output_format json --disable_multiprocessing"
    
    logger.info(f"Command: {cmd}")
    
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    logger.info(f"Exit code: {result.returncode}")
    
    if result.returncode != 0:
        logger.error("Marker extraction failed")
        logger.error(f"stderr: {result.stderr[-2000:]}")  # Last 2000 chars
    else:
        logger.success("✓ Marker extraction succeeded!")
    
    # Check for output
    test_json = working_dir / "test.json"
    if test_json.exists():
        logger.success(f"✓ Found output: {test_json}")
        
        # Analyze output
        with open(test_json) as f:
            data = json.load(f)
        
        if isinstance(data, dict) and 'blocks' in data:
            blocks = data['blocks']
            logger.info(f"Extracted {len(blocks)} blocks")
            
            # Count block types
            block_types = {}
            for block in blocks:
                btype = block.get('type', 'unknown')
                block_types[btype] = block_types.get(btype, 0) + 1
            
            logger.info("Block type distribution:")
            for btype, count in sorted(block_types.items()):
                logger.info(f"  {btype}: {count}")
            
            return True
        else:
            logger.warning("Output doesn't have expected structure")
            return False
    else:
        logger.error("No output file found")
        return False


def main():
    """Run test"""
    logger.info(f"Working directory: {working_dir}")
    logger.info(f"Test PDF: {test_pdf}")
    
    success = test_marker_with_fix()
    
    if success:
        logger.success("\n✓ Marker test with fix PASSED")
    else:
        logger.error("\n✗ Marker test with fix FAILED")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)