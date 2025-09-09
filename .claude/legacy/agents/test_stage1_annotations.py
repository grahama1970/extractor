#!/usr/bin/env python3
"""
Test Stage 1: Annotation extraction
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
working_dir = project_root / "tmp" / "test_stage1"
working_dir.mkdir(parents=True, exist_ok=True)

# Input PDF
input_pdf = project_root / "proof_of_concept" / "BHT_CV32A65X_marked.pdf"
doc_pdf = working_dir / "doc.pdf"

# Copy input PDF
logger.info(f"Copying input PDF to working directory")
shutil.copy(input_pdf, doc_pdf)


def test_annotation_extraction():
    """Test annotation extraction with proper command"""
    logger.info("=" * 60)
    logger.info("Testing Stage 1: Annotation Extraction")
    logger.info("=" * 60)
    
    annotations_json = working_dir / "annotations.json"
    
    # Test 1: Basic command
    logger.info("Test 1: Basic annotation extraction")
    cmd = f"cd {project_root} && python -m extractor.core.processors.enhanced_annotation_extractor extract {doc_pdf} --output {annotations_json}"
    
    logger.info(f"Command: {cmd}")
    
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=60
    )
    
    logger.info(f"Exit code: {result.returncode}")
    if result.stdout:
        logger.info(f"stdout: {result.stdout[:500]}...")
    if result.stderr:
        logger.error(f"stderr: {result.stderr[:500]}...")
    
    # Check results
    if result.returncode == 0 and annotations_json.exists():
        logger.success("✓ Annotation extraction succeeded")
        
        # Analyze output
        with open(annotations_json) as f:
            data = json.load(f)
        
        annotations = data.get('annotations', [])
        logger.info(f"Found {len(annotations)} annotations")
        
        # Show annotation types
        ann_types = {}
        for ann in annotations:
            ann_type = ann.get('type', 'unknown')
            ann_types[ann_type] = ann_types.get(ann_type, 0) + 1
        
        logger.info("Annotation type distribution:")
        for ann_type, count in sorted(ann_types.items()):
            logger.info(f"  {ann_type}: {count}")
        
        # Show sample annotations
        logger.info("\nSample annotations:")
        for i, ann in enumerate(annotations[:3]):
            logger.info(f"  [{i}] Type: {ann.get('type')}")
            logger.info(f"       Content: {ann.get('content', '')[:100]}...")
            logger.info(f"       Page: {ann.get('page_num', '?')}")
            logger.info(f"       Color: {ann.get('color', '?')}")
        
        return True
    else:
        logger.error("✗ Annotation extraction failed")
        
        # Try to diagnose the issue
        if not doc_pdf.exists():
            logger.error(f"Input PDF not found: {doc_pdf}")
        
        # Try running with full path
        logger.info("\nTest 2: Trying with full Python path")
        cmd2 = f"{sys.executable} -m extractor.core.processors.enhanced_annotation_extractor extract {doc_pdf} --output {annotations_json}"
        
        result2 = subprocess.run(
            cmd2,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=60
        )
        
        if result2.returncode == 0:
            logger.success("✓ Succeeded with full Python path")
            return True
        else:
            logger.error("✗ Still failed with full Python path")
            return False


def main():
    """Run test"""
    logger.info(f"Working directory: {working_dir}")
    logger.info(f"Input PDF: {input_pdf}")
    logger.info(f"Doc PDF: {doc_pdf}")
    
    if not doc_pdf.exists():
        logger.error(f"Doc PDF not found: {doc_pdf}")
        return False
    
    success = test_annotation_extraction()
    
    if success:
        logger.success("\n✓ Stage 1 test PASSED")
    else:
        logger.error("\n✗ Stage 1 test FAILED")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)