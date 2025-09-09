#!/usr/bin/env python3
"""
Debug script to test each pipeline stage individually
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
working_dir = project_root / "tmp" / "debug_pipeline"
working_dir.mkdir(parents=True, exist_ok=True)

# Input PDF
input_pdf = project_root / "proof_of_concept" / "BHT_CV32A65X_marked.pdf"
doc_pdf = working_dir / "doc.pdf"

# Copy input PDF
logger.info(f"Copying input PDF to working directory")
shutil.copy(input_pdf, doc_pdf)


def run_command(cmd: str, description: str = "", timeout: int = 120) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr"""
    logger.info(f"Running: {description}")
    logger.info(f"Command: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Failed with code {result.returncode}")
            logger.error(f"stderr: {result.stderr}")
        else:
            logger.success(f"Success!")
            
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout after {timeout}s")
        return -1, "", f"Timeout after {timeout}s"


def test_stage1_annotation_extraction():
    """Test Stage 1: Extract annotations"""
    logger.info("=" * 60)
    logger.info("STAGE 1: Extract annotations")
    logger.info("=" * 60)
    
    annotations_json = working_dir / "annotations.json"
    
    # Test direct module import first
    logger.info("Testing direct module import...")
    try:
        from extractor.core.processors.enhanced_annotation_extractor import extract_annotations
        logger.success("✓ Module imported successfully")
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False
    
    # Test command line execution
    cmd = f"python -m extractor.core.processors.enhanced_annotation_extractor extract {doc_pdf} --output {annotations_json}"
    exit_code, stdout, stderr = run_command(cmd, "Extract annotations")
    
    if exit_code == 0 and annotations_json.exists():
        logger.success(f"✓ Annotations extracted to {annotations_json}")
        
        # Load and inspect
        with open(annotations_json) as f:
            data = json.load(f)
        
        logger.info(f"Found {len(data.get('annotations', []))} annotations")
        for i, ann in enumerate(data.get('annotations', [])[:3]):
            logger.info(f"  Annotation {i}: {ann.get('type', 'unknown')} - {ann.get('content', '')[:50]}...")
        
        return True
    else:
        logger.error("✗ Annotation extraction failed")
        return False


def test_stage3_pdf_cleaner():
    """Test Stage 3: Clean PDF"""
    logger.info("=" * 60)
    logger.info("STAGE 3: Clean PDF")
    logger.info("=" * 60)
    
    clean_pdf = working_dir / "clean.pdf"
    
    # Test direct module import
    logger.info("Testing direct module import...")
    try:
        from extractor.core.processors.pdf_cleaner import PDFCleaner
        logger.success("✓ Module imported successfully")
        
        # Try direct usage
        cleaner = PDFCleaner()
        logger.info("✓ PDFCleaner instantiated")
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False
    
    # Test command line execution
    cmd = f"python -m extractor.core.processors.pdf_cleaner clean {doc_pdf} --output {clean_pdf}"
    exit_code, stdout, stderr = run_command(cmd, "Clean PDF")
    
    if exit_code == 0 and clean_pdf.exists():
        logger.success(f"✓ Clean PDF created at {clean_pdf}")
        logger.info(f"  Size: {clean_pdf.stat().st_size} bytes")
        return True
    else:
        logger.error("✗ PDF cleaning failed")
        # Create a copy as fallback
        shutil.copy(doc_pdf, clean_pdf)
        logger.info("Created fallback clean.pdf")
        return False


def test_stage5_marker_extraction():
    """Test Stage 5: Marker extraction"""
    logger.info("=" * 60)
    logger.info("STAGE 5: Marker extraction")
    logger.info("=" * 60)
    
    clean_pdf = working_dir / "clean.pdf"
    blocks_json = working_dir / "blocks.json"
    
    # Ensure clean.pdf exists
    if not clean_pdf.exists():
        logger.warning("clean.pdf not found, using doc.pdf")
        shutil.copy(doc_pdf, clean_pdf)
    
    # Test 1: Check if convert_single.py exists
    convert_script = project_root / "src" / "extractor" / "core" / "scripts" / "convert_single.py"
    if convert_script.exists():
        logger.success(f"✓ convert_single.py found at {convert_script}")
    else:
        logger.error(f"✗ convert_single.py not found at {convert_script}")
        return False
    
    # Test 2: Try direct Python execution
    logger.info("Testing direct Python execution...")
    cmd = f"cd {project_root} && python {convert_script} {clean_pdf} --output_dir {working_dir} --output_format json --disable_tqdm"
    exit_code, stdout, stderr = run_command(cmd, "Direct Python execution", timeout=300)
    
    if exit_code == 0:
        logger.success("✓ Direct execution succeeded")
    else:
        logger.warning("Direct execution failed, trying with activated venv...")
        
        # Test 3: Try with activated venv
        cmd = f"cd {project_root} && source .venv/bin/activate && python -m extractor.core.scripts.convert_single {clean_pdf} --output_dir {working_dir} --output_format json --disable_tqdm"
        exit_code, stdout, stderr = run_command(cmd, "Venv execution", timeout=300)
    
    # Check for output
    clean_json = working_dir / "clean.json"
    if clean_json.exists():
        logger.info("Found clean.json, moving to blocks.json")
        shutil.move(clean_json, blocks_json)
    
    if blocks_json.exists():
        logger.success(f"✓ Marker extraction succeeded, blocks.json created")
        
        # Inspect content
        with open(blocks_json) as f:
            data = json.load(f)
        
        blocks = data.get('blocks', [])
        logger.info(f"Found {len(blocks)} blocks")
        
        # Count block types
        block_types = {}
        for block in blocks:
            block_type = block.get('type', 'unknown')
            block_types[block_type] = block_types.get(block_type, 0) + 1
        
        logger.info("Block type distribution:")
        for block_type, count in sorted(block_types.items()):
            logger.info(f"  {block_type}: {count}")
        
        return True
    else:
        logger.error("✗ Marker extraction failed")
        return False


def main():
    """Run all tests"""
    logger.info("Starting pipeline stage debugging")
    logger.info(f"Working directory: {working_dir}")
    logger.info(f"Input PDF: {input_pdf}")
    
    results = {}
    
    # Test each stage
    results['stage1'] = test_stage1_annotation_extraction()
    results['stage3'] = test_stage3_pdf_cleaner()
    results['stage5'] = test_stage5_marker_extraction()
    
    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    for stage, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"{stage}: {status}")
    
    if all(results.values()):
        logger.success("All stages passed!")
    else:
        logger.error("Some stages failed")


if __name__ == "__main__":
    main()