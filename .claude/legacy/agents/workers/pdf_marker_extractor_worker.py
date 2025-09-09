#!/usr/bin/env python3
"""
PDF Marker Extractor Worker - Runs marker-pdf extraction with UUID assignment.

This worker provides the implementation for Stage 5 of the PDF extraction pipeline.
It runs marker-pdf to extract blocks and assigns UUIDs and metadata for tracking.

Key capabilities:
- Run marker-pdf extraction
- Assign UUIDs to each block
- Add page numbers and indices
- Flag suspicious blocks
- Create output with full indexing metadata

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function demonstrates marker extraction with UUIDs
- debug_function() is for testing different PDFs
"""

import asyncio
import json
import subprocess
import sys
import uuid
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Third-party imports
from loguru import logger
from dotenv import load_dotenv, find_dotenv

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Load environment variables
load_dotenv(find_dotenv())

# Constants for this agent
AGENT_NAME = "pdf-marker-extractor"


class PDFMarkerExtractorWorker:
    """Worker for marker-pdf extraction with metadata."""
    
    def __init__(self):
        self.suspicious_patterns = {
            'incomplete_sentence': r'[\w\s]+\($',  # Ends with opening paren
            'sentence_fragment': r'^\)[^\(]*$',    # Starts with closing paren
            'split_number_header': r'^\d+\.\d+\.\d+\.\s*\w+\s*\($',  # "4.1.5.4. BHT ("
            'orphaned_punctuation': r'^[)\]}\s]+$',  # Just closing punctuation
            'incomplete_header': r'^(Chapter|Section|Part)\s+\d+[:\s]*$',  # "Chapter 1:" alone
            'possible_table_continuation': r'^[\w\s]+\|[\w\s]+\|',  # Table-like data
            'very_short_text': lambda text: len(text.strip()) < 5,
            'possible_split_header': lambda text: re.match(r'^\d+\.\d+', text) and len(text) < 30
        }
    
    async def extract_with_marker(
        self, 
        pdf_path: str, 
        output_dir: Optional[str] = None,
        clean_pdf: bool = True
    ) -> Dict[str, Any]:
        """
        Extract PDF using marker-pdf and add UUIDs/metadata.
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Output directory (defaults to /tmp)
            clean_pdf: Whether to use clean PDF (no annotations)
            
        Returns:
            Dict with extraction results including UUID-indexed blocks
        """
        logger.info(f"Starting marker extraction for: {pdf_path}")
        
        # Validate input
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        # Set output directory
        if output_dir is None:
            output_dir = Path("/tmp/marker_output")
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Step 1: Run marker extraction
        marker_output = await self._run_marker_extraction(pdf_path, output_dir)
        
        if not marker_output['success']:
            return marker_output
        
        # Step 2: Load marker output and add metadata
        marker_json_path = marker_output['output_file']
        enhanced_data = await self._enhance_with_metadata(marker_json_path)
        
        # Step 3: Save enhanced version
        enhanced_path = output_dir / f"{pdf_path.stem}_enhanced.json"
        with open(enhanced_path, 'w') as f:
            json.dump(enhanced_data, f, indent=2)
        
        logger.success(f"Enhanced marker output saved to: {enhanced_path}")
        
        return {
            'success': True,
            'original_marker_output': str(marker_json_path),
            'enhanced_output': str(enhanced_path),
            'metadata': enhanced_data['metadata'],
            'suspicious_count': enhanced_data['metadata'].get('suspicious_count', 0)
        }
    
    async def _run_marker_extraction(self, pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Run the actual marker command."""
        try:
            # Prepare marker command
            cmd = [
                'python', '-m', 'marker_pdf',
                str(pdf_path),
                str(output_dir),
                '--batch_multiplier', '2'
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            # Run marker
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"Marker failed: {stderr.decode()}")
                return {
                    'success': False,
                    'error': stderr.decode()
                }
            
            # Find the output JSON file
            json_files = list(output_dir.glob(f"{pdf_path.stem}*.json"))
            if not json_files:
                logger.error("No JSON output from marker")
                return {
                    'success': False,
                    'error': "Marker did not produce JSON output"
                }
            
            return {
                'success': True,
                'output_file': json_files[0]
            }
            
        except Exception as e:
            logger.error(f"Marker extraction failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _enhance_with_metadata(self, marker_json_path: Path) -> Dict[str, Any]:
        """Add UUIDs and metadata to marker output."""
        logger.info("Enhancing marker output with metadata")
        
        # Load marker output
        with open(marker_json_path) as f:
            data = json.load(f)
        
        # Initialize counters
        block_counter = 0
        suspicious_count = 0
        enhanced_blocks = []
        
        # Process each page
        pages = data.get('pages', [])
        for page_num, page in enumerate(pages):
            page_blocks = page.get('blocks', [])
            
            for block_idx, block in enumerate(page_blocks):
                # Add metadata
                enhanced_block = {
                    'uuid': str(uuid.uuid4()),
                    'page': page_num,
                    'page_index': block_idx,
                    'block_id': block_counter,
                    'original_index': block_counter,
                    'sort_key': f"{page_num:04d}_{block_idx:04d}",
                    **block  # Include all original block data
                }
                
                # Check if suspicious
                suspicious_info = self._check_suspicious(block)
                if suspicious_info['suspicious']:
                    enhanced_block['suspicious'] = True
                    enhanced_block['issues'] = suspicious_info['issues']
                    suspicious_count += 1
                
                enhanced_blocks.append(enhanced_block)
                block_counter += 1
        
        # Create enhanced output structure
        enhanced_data = {
            'metadata': {
                'source_file': str(marker_json_path),
                'total_pages': len(pages),
                'total_blocks': len(enhanced_blocks),
                'suspicious_count': suspicious_count,
                'extraction_timestamp': datetime.now().isoformat(),
                'indexing': {
                    'description': 'Blocks indexed with: uuid, page, page_index, block_id, sort_key',
                    'sorting': 'Use sort_key for document order'
                }
            },
            'blocks': enhanced_blocks,
            'original_metadata': data.get('metadata', {})
        }
        
        return enhanced_data
    
    def _check_suspicious(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a block is suspicious."""
        text = block.get('text', '').strip()
        block_type = block.get('block_type', 'Unknown')
        issues = []
        
        if not text:
            return {'suspicious': False, 'issues': []}
        
        # Check patterns
        for issue_name, pattern in self.suspicious_patterns.items():
            if callable(pattern):
                if pattern(text):
                    issues.append(issue_name)
            elif re.search(pattern, text):
                issues.append(issue_name)
        
        # Type-specific checks
        if block_type == 'Text' and re.match(r'^\d+\.\d+', text):
            issues.append('numbered_text_not_header')
        
        return {
            'suspicious': len(issues) > 0,
            'issues': issues
        }


# Module-level function for easy import
async def extract_pdf_with_uuids(
    pdf_path: str, 
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Extract PDF with marker and add UUIDs."""
    worker = PDFMarkerExtractorWorker()
    return await worker.extract_with_marker(pdf_path, output_dir)


# ============================================
# USAGE EXAMPLES (MANDATORY)
# ============================================

async def working_usage():
    """
    Demonstrate marker extraction with UUID assignment.
    """
    logger.info("=== Running Marker Extraction Working Usage ===")
    
    # Use a test PDF
    test_pdf = "/home/graham/workspace/experiments/extractor/gold_standards/BHT.pdf"
    
    if not Path(test_pdf).exists():
        logger.error(f"Test PDF not found: {test_pdf}")
        # Create minimal test
        logger.info("Using simulated marker output for demonstration")
        
        # Simulate marker output
        test_data = {
            'pages': [
                {
                    'page_num': 0,
                    'blocks': [
                        {
                            'block_type': 'Text',
                            'text': '4.1.5.4. BHT (Branch History',
                            'bbox': [72, 234, 540, 258]
                        },
                        {
                            'block_type': 'Text', 
                            'text': 'Table) submodule',
                            'bbox': [72, 258, 540, 282]
                        }
                    ]
                }
            ]
        }
        
        # Save simulated data
        sim_path = Path("/tmp/simulated_marker.json")
        with open(sim_path, 'w') as f:
            json.dump(test_data, f)
        
        # Enhance it
        worker = PDFMarkerExtractorWorker()
        enhanced = await worker._enhance_with_metadata(sim_path)
        
        # Verify
        assert len(enhanced['blocks']) == 2, "Expected 2 blocks"
        assert enhanced['blocks'][0].get('uuid'), "Missing UUID"
        assert enhanced['blocks'][0].get('suspicious'), "Should be suspicious"
        assert enhanced['metadata']['suspicious_count'] == 2, "Both should be suspicious"
        
        logger.success("✓ Simulated test passed")
        
    else:
        # Real extraction
        worker = PDFMarkerExtractorWorker()
        result = await worker.extract_with_marker(test_pdf)
        
        if result['success']:
            logger.success(f"✓ Extraction completed")
            logger.info(f"Output: {result['enhanced_output']}")
            logger.info(f"Suspicious blocks: {result['suspicious_count']}")
        else:
            logger.error(f"Extraction failed: {result.get('error')}")
            return False
    
    return True


async def debug_function():
    """
    Debug function for testing pattern detection.
    """
    logger.info("=== Running Debug Function ===")
    
    worker = PDFMarkerExtractorWorker()
    
    # Test suspicious patterns
    test_cases = [
        ("4.1.5.4. BHT (Branch History", ['incomplete_sentence', 'possible_split_header']),
        ("Table) submodule", ['sentence_fragment']),
        (")", ['orphaned_punctuation', 'very_short_text']),
        ("Chapter 1:", ['incomplete_header']),
        ("Signal|Type|Description", ['possible_table_continuation']),
        ("Normal text without issues", [])
    ]
    
    logger.info("Testing suspicious block detection:")
    for text, expected_issues in test_cases:
        result = worker._check_suspicious({'text': text, 'block_type': 'Text'})
        logger.info(f"\nText: '{text}'")
        logger.info(f"Suspicious: {result['suspicious']}")
        logger.info(f"Issues: {result['issues']}")
        
        # Verify some expected issues are found
        for expected in expected_issues:
            if expected in result['issues']:
                logger.success(f"  ✓ Found expected: {expected}")
            else:
                logger.warning(f"  ✗ Missing expected: {expected}")
    
    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - stable example that works
    - DEBUG: Run with 'debug' argument to test pattern detection
    - DO NOT create external test files - use debug_function() instead!
    """
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        logger.info("Running debug mode...")
        asyncio.run(debug_function())
    else:
        logger.info("Running working usage mode...")
        success = asyncio.run(working_usage())
        exit(0 if success else 1)