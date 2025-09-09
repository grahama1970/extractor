#!/usr/bin/env python3
"""
Test Stage 5: Marker extraction
"""

import sys
import subprocess
from pathlib import Path
import json
import shutil
import os
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

# Set up paths
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root / 'src'))

# Setup working directory
working_dir = project_root / "tmp" / "test_stage5"
working_dir.mkdir(parents=True, exist_ok=True)

# Input PDF
input_pdf = project_root / "proof_of_concept" / "BHT_CV32A65X_marked.pdf"
test_pdf = working_dir / "test.pdf"

# Copy input PDF
logger.info(f"Copying input PDF to working directory")
shutil.copy(input_pdf, test_pdf)


def test_marker_extraction():
    """Test marker extraction step by step"""
    logger.info("=" * 60)
    logger.info("Testing Stage 5: Marker Extraction")
    logger.info("=" * 60)
    
    # Test 1: Check environment
    logger.info("\nTest 1: Environment check")
    logger.info(f"Python: {sys.executable}")
    logger.info(f"Working dir: {working_dir}")
    logger.info(f"Project root: {project_root}")
    logger.info(f"Test PDF exists: {test_pdf.exists()}")
    
    # Test 2: Try simplest command
    logger.info("\nTest 2: Simple marker extraction")
    cmd = f"{sys.executable} {project_root}/src/extractor/core/scripts/convert_single.py {test_pdf} --output_dir {working_dir}"
    
    logger.info(f"Command: {cmd}")
    
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=300
    )
    
    logger.info(f"Exit code: {result.returncode}")
    if result.returncode != 0:
        logger.error(f"stderr: {result.stderr[:1000]}...")
        
    # Check for output files
    logger.info("\nChecking for output files:")
    for f in working_dir.iterdir():
        if f.is_file():
            logger.info(f"  Found: {f.name} ({f.stat().st_size} bytes)")
    
    # Look for the output
    test_json = working_dir / "test.json"
    if test_json.exists():
        logger.success(f"✓ Found test.json")
        
        # Inspect content
        with open(test_json) as f:
            data = json.load(f)
        
        if isinstance(data, dict) and 'blocks' in data:
            blocks = data['blocks']
            logger.info(f"Found {len(blocks)} blocks")
            
            # Show block types
            block_types = {}
            for block in blocks:
                btype = block.get('type', 'unknown')
                block_types[btype] = block_types.get(btype, 0) + 1
            
            logger.info("Block types:")
            for btype, count in sorted(block_types.items()):
                logger.info(f"  {btype}: {count}")
                
            return True
        else:
            logger.warning("test.json doesn't have expected structure")
            logger.info(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
    
    # Test 3: Try with explicit Python module
    logger.info("\nTest 3: Try as Python module")
    cmd = f"cd {project_root} && {sys.executable} -m extractor.core.scripts.convert_single {test_pdf} --output_dir {working_dir} --output_format json"
    
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
        logger.error(f"stderr: {result.stderr[:500]}...")
    else:
        logger.success("✓ Module execution succeeded")
    
    # Check again for output
    for f in working_dir.iterdir():
        if f.suffix == '.json':
            logger.info(f"Found JSON: {f.name}")
            return True
    
    return False


def test_direct_import():
    """Test importing and using marker directly"""
    logger.info("\nTest 4: Direct import test")
    
    try:
        from extractor.core.converters.pdf import convert_single_pdf
        logger.success("✓ Imported convert_single_pdf")
        
        # Try conversion
        logger.info("Attempting direct conversion...")
        result = convert_single_pdf(
            str(test_pdf),
            max_pages=2,
            disable_multiprocessing=True
        )
        
        if result:
            logger.success(f"✓ Direct conversion succeeded, got {len(result)} chars")
            
            # Save to file
            output_file = working_dir / "direct_output.md"
            with open(output_file, 'w') as f:
                f.write(result)
            logger.info(f"Saved to {output_file}")
            
            return True
        else:
            logger.error("Direct conversion returned empty result")
            return False
            
    except Exception as e:
        logger.error(f"Direct import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    logger.info(f"Starting marker extraction tests")
    
    # Test marker extraction
    success1 = test_marker_extraction()
    
    # Test direct import
    success2 = test_direct_import()
    
    if success1 or success2:
        logger.success("\n✓ At least one marker test PASSED")
        return True
    else:
        logger.error("\n✗ All marker tests FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)