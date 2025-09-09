#!/usr/bin/env python3
"""
Test script for PDF extraction pipeline with sub-agents.

Tests the complete workflow with the BHT PDF.
"""

import asyncio
import sys
from pathlib import Path
import json
from datetime import datetime

# Add parent directories to path
current_dir = Path(__file__).parent
extractor_root = current_dir.parent.parent.parent.parent / "src"
sys.path.insert(0, str(extractor_root))

from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")


async def test_pdf_extraction():
    """Test the PDF extraction pipeline."""
    
    # Import the orchestrator
    from extract_pdf_worker import PDFExtractionOrchestrator
    
    # Path to test PDF
    pdf_path = Path("/home/graham/workspace/experiments/extractor/proof_of_concept/BHT_CV32A65X_marked.pdf")
    if not pdf_path.exists():
        logger.error(f"Test PDF not found: {pdf_path}")
        return False
    
    # Create orchestrator
    orchestrator = PDFExtractionOrchestrator()
    
    try:
        logger.info(f"Starting extraction of {pdf_path.name}")
        start_time = datetime.now()
        
        # Extract PDF
        result = await orchestrator.extract_pdf(
            pdf_path=pdf_path,
            output_path=Path("/tmp/bht_extraction_result.json"),
            validate_gold=False  # No gold standard yet
        )
        
        # Show results
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.success(f"Extraction completed in {elapsed:.2f} seconds")
        
        # Summary
        if "blocks" in result:
            logger.info(f"Total blocks extracted: {len(result['blocks'])}")
            
        if "sections" in result:
            logger.info(f"Sections identified: {len(result['sections'])}")
            for i, section in enumerate(result['sections'][:5]):
                logger.info(f"  Section {i+1}: {section.get('title', 'Untitled')}")
            
        if "metadata" in result:
            logger.info(f"Metadata: {json.dumps(result['metadata'], indent=2)}")
            
        # Check suspicious blocks
        if "suspicious_analysis" in result:
            sus = result["suspicious_analysis"]
            logger.info(f"Suspicious blocks: {sus.get('total_suspicious', 0)}/{sus.get('total_blocks', 0)}")
            
        return True
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integration():
    """Test integration with existing pipeline."""
    
    # Test direct subagent integration
    from extractor.core.subagent_pipeline_integration import SubAgentPipelineIntegration
    
    integration = SubAgentPipelineIntegration(enable_sub_agents=True)
    
    # Use the same PDF path that works in test 1
    pdf_path = "/home/graham/workspace/experiments/extractor/proof_of_concept/BHT_CV32A65X_marked.pdf"
    
    try:
        logger.info("Testing sub-agent integration...")
        
        # Process with sub-agents
        result = await integration.process_stage2_with_sub_agents(
            pdf_path=pdf_path
        )
        
        logger.success(f"Integration test passed - extracted {len(result.get('blocks', []))} blocks")
        
        # Show metrics
        metrics = integration.get_metrics()
        logger.info(f"Metrics: {json.dumps(metrics, indent=2)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("PDF Sub-Agent Pipeline Test")
    logger.info("=" * 60)
    
    # Test 1: Full extraction
    logger.info("\nTest 1: Full PDF extraction with orchestrator")
    test1_passed = await test_pdf_extraction()
    
    # Test 2: Integration
    logger.info("\nTest 2: Direct sub-agent integration")
    test2_passed = await test_integration()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary:")
    logger.info(f"  Test 1 (Full extraction): {'✓ PASSED' if test1_passed else '✗ FAILED'}")
    logger.info(f"  Test 2 (Integration): {'✓ PASSED' if test2_passed else '✗ FAILED'}")
    logger.info("=" * 60)
    
    return test1_passed and test2_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)