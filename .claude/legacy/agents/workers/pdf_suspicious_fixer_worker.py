#!/usr/bin/env python3
"""
PDF Suspicious Fixer Worker - Fixes remaining suspicious blocks after batch processing.

This worker provides the implementation for Stage 6 of the PDF extraction pipeline.
It handles suspicious blocks that weren't fixed by the batch processing in Stage 5.5.

Key capabilities:
- Find remaining suspicious blocks
- Apply pattern-based fixes
- Handle edge cases and orphaned blocks
- Clean up final output

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function demonstrates fixing remaining issues
- debug_function() is for testing fix patterns
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Third-party imports
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Constants
AGENT_NAME = "pdf-suspicious-fixer"


class PDFSuspiciousFixerWorker:
    """Worker for fixing remaining suspicious blocks."""
    
    def __init__(self):
        self.fix_patterns = {
            'orphaned_word': {
                'pattern': r'^[A-Z][a-z]+$',
                'max_length': 20,
                'action': 'merge_with_previous'
            },
            'incomplete_list_item': {
                'pattern': r'^[\d•\-]\.\s*$',
                'action': 'merge_with_next'
            },
            'floating_punctuation': {
                'pattern': r'^[,;:\.]+$',
                'action': 'merge_with_previous'
            },
            'continued_sentence': {
                'pattern': r'^[a-z]',  # Starts with lowercase
                'action': 'merge_with_previous'
            },
            'table_header_alone': {
                'pattern': r'^[\w\s]+\|[\w\s]+\|[\w\s]+$',
                'prev_not_table': True,
                'action': 'reclassify_as_table'
            }
        }
    
    async def fix_remaining_suspicious(
        self, 
        marker_json_path: str,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fix remaining suspicious blocks in marker output.
        
        Args:
            marker_json_path: Path to marker JSON with some fixes applied
            output_path: Output path for final fixed JSON
            
        Returns:
            Dict with fix results and statistics
        """
        logger.info(f"Fixing remaining suspicious blocks in: {marker_json_path}")
        
        # Load data
        with open(marker_json_path) as f:
            data = json.load(f)
        
        blocks = data.get('blocks', [])
        original_suspicious = sum(1 for b in blocks if b.get('suspicious'))
        
        if original_suspicious == 0:
            logger.info("No suspicious blocks found - nothing to fix")
            return {
                'success': True,
                'suspicious_before': 0,
                'suspicious_after': 0,
                'fixes_applied': 0
            }
        
        logger.info(f"Found {original_suspicious} suspicious blocks to fix")
        
        # Apply fixes
        fixed_blocks, fixes_applied = await self._apply_pattern_fixes(blocks)
        
        # Update data
        data['blocks'] = fixed_blocks
        data['metadata']['fixes_applied'] = data['metadata'].get('fixes_applied', 0) + fixes_applied
        data['metadata']['final_fix_timestamp'] = datetime.now().isoformat()
        
        # Count remaining suspicious
        final_suspicious = sum(1 for b in fixed_blocks if b.get('suspicious'))
        
        # Save output
        if output_path is None:
            output_path = Path(marker_json_path).parent / f"{Path(marker_json_path).stem}_final.json"
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.success(f"Fixed {fixes_applied} blocks, {final_suspicious} suspicious blocks remain")
        
        return {
            'success': True,
            'output_file': str(output_path),
            'suspicious_before': original_suspicious,
            'suspicious_after': final_suspicious,
            'fixes_applied': fixes_applied,
            'fix_summary': self._generate_fix_summary(fixes_applied, original_suspicious, final_suspicious)
        }
    
    async def _apply_pattern_fixes(self, blocks: List[Dict]) -> Tuple[List[Dict], int]:
        """Apply pattern-based fixes to suspicious blocks."""
        fixed_blocks = []
        fixes_applied = 0
        skip_next = False
        
        for i, block in enumerate(blocks):
            if skip_next:
                skip_next = False
                continue
            
            if not block.get('suspicious'):
                fixed_blocks.append(block)
                continue
            
            # Try to fix the block
            fix_applied = False
            text = block.get('text', '').strip()
            
            for fix_name, fix_config in self.fix_patterns.items():
                if self._matches_pattern(block, fix_config, blocks, i):
                    action = fix_config['action']
                    
                    if action == 'merge_with_previous' and i > 0:
                        # Merge with previous block
                        prev_block = fixed_blocks[-1]
                        prev_block['text'] = prev_block['text'].rstrip() + ' ' + text
                        prev_block['metadata'] = prev_block.get('metadata', {})
                        prev_block['metadata']['merged_from'] = block.get('uuid', block.get('block_id'))
                        fixes_applied += 1
                        fix_applied = True
                        logger.debug(f"Merged '{text[:30]}...' with previous")
                        break
                        
                    elif action == 'merge_with_next' and i < len(blocks) - 1:
                        # Merge with next block
                        next_block = blocks[i + 1]
                        block['text'] = text + ' ' + next_block.get('text', '').strip()
                        block['suspicious'] = False
                        block['issues'] = None
                        block['metadata'] = block.get('metadata', {})
                        block['metadata']['merged_with'] = next_block.get('uuid', next_block.get('block_id'))
                        fixed_blocks.append(block)
                        skip_next = True
                        fixes_applied += 1
                        fix_applied = True
                        logger.debug(f"Merged '{text[:30]}...' with next")
                        break
                        
                    elif action == 'reclassify_as_table':
                        # Change type to Table
                        block['type'] = 'Table'
                        block['block_type'] = 'Table'
                        block['suspicious'] = False
                        block['issues'] = None
                        block['metadata'] = block.get('metadata', {})
                        block['metadata']['reclassified'] = True
                        fixed_blocks.append(block)
                        fixes_applied += 1
                        fix_applied = True
                        logger.debug(f"Reclassified '{text[:30]}...' as Table")
                        break
            
            if not fix_applied:
                # Keep the suspicious block as-is
                fixed_blocks.append(block)
        
        return fixed_blocks, fixes_applied
    
    def _matches_pattern(self, block: Dict, fix_config: Dict, all_blocks: List[Dict], index: int) -> bool:
        """Check if a block matches a fix pattern."""
        text = block.get('text', '').strip()
        
        # Check text pattern
        if 'pattern' in fix_config:
            if not re.match(fix_config['pattern'], text):
                return False
        
        # Check length constraint
        if 'max_length' in fix_config:
            if len(text) > fix_config['max_length']:
                return False
        
        # Check previous block constraint
        if fix_config.get('prev_not_table') and index > 0:
            prev_block = all_blocks[index - 1]
            if prev_block.get('type') == 'Table' or prev_block.get('block_type') == 'Table':
                return False
        
        return True
    
    def _generate_fix_summary(self, fixes_applied: int, before: int, after: int) -> str:
        """Generate a human-readable fix summary."""
        if fixes_applied == 0:
            return "No fixes could be applied to remaining suspicious blocks"
        
        reduction = before - after
        percentage = (reduction / before * 100) if before > 0 else 0
        
        return (f"Applied {fixes_applied} fixes, reducing suspicious blocks "
                f"from {before} to {after} ({percentage:.1f}% reduction)")


# Module-level functions
async def fix_remaining_suspicious_blocks(
    marker_json_path: str,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """Fix remaining suspicious blocks."""
    worker = PDFSuspiciousFixerWorker()
    return await worker.fix_remaining_suspicious(marker_json_path, output_path)


# ============================================
# USAGE EXAMPLES (MANDATORY)
# ============================================

async def working_usage():
    """
    Demonstrate fixing remaining suspicious blocks.
    """
    logger.info("=== Running Suspicious Fixer Working Usage ===")
    
    # Create test data with suspicious blocks
    test_data = {
        'metadata': {
            'source': 'test.pdf',
            'total_blocks': 7
        },
        'blocks': [
            {
                'block_id': 0,
                'type': 'SectionHeader',
                'text': '4.1.5.4. Cache',
                'suspicious': False
            },
            {
                'block_id': 1,
                'type': 'Text',
                'text': 'Interface',  # Orphaned word
                'suspicious': True,
                'issues': ['orphaned_word']
            },
            {
                'block_id': 2,
                'type': 'Text',
                'text': 'The cache provides fast access.',
                'suspicious': False
            },
            {
                'block_id': 3,
                'type': 'Text',
                'text': ',',  # Floating punctuation
                'suspicious': True,
                'issues': ['floating_punctuation']
            },
            {
                'block_id': 4,
                'type': 'Text',
                'text': 'which improves performance.',  # Continued sentence
                'suspicious': True,
                'issues': ['continued_sentence']
            },
            {
                'block_id': 5,
                'type': 'Text',
                'text': 'Signal|Type|Description',  # Table header alone
                'suspicious': True,
                'issues': ['possible_table']
            }
        ]
    }
    
    # Save test data
    test_file = Path("/tmp/test_suspicious_blocks.json")
    with open(test_file, 'w') as f:
        json.dump(test_data, f, indent=2)
    
    # Fix suspicious blocks
    worker = PDFSuspiciousFixerWorker()
    result = await worker.fix_remaining_suspicious(str(test_file))
    
    # Verify results
    assert result['success'], "Fix operation failed"
    assert result['suspicious_before'] == 4, "Expected 4 suspicious blocks"
    assert result['fixes_applied'] >= 3, "Expected at least 3 fixes"
    assert result['suspicious_after'] <= 1, "Expected at most 1 remaining suspicious"
    
    logger.success("✓ All tests passed")
    
    # Show results
    with open(result['output_file']) as f:
        fixed_data = json.load(f)
    
    logger.info("\nFixed blocks:")
    for block in fixed_data['blocks']:
        text = block['text'][:50] + '...' if len(block['text']) > 50 else block['text']
        suspicious = '⚠️' if block.get('suspicious') else '✓'
        logger.info(f"{suspicious} [{block['type']}] {text}")
    
    return True


async def debug_function():
    """
    Debug pattern matching logic.
    """
    logger.info("=== Running Debug Function ===")
    
    worker = PDFSuspiciousFixerWorker()
    
    # Test pattern matching
    test_cases = [
        {'text': 'Interface', 'expected': 'orphaned_word'},
        {'text': 'computational', 'expected': 'orphaned_word'},
        {'text': ',', 'expected': 'floating_punctuation'},
        {'text': 'which continues', 'expected': 'continued_sentence'},
        {'text': 'Signal|Type|Desc', 'expected': 'table_header_alone'},
        {'text': 'Normal text here', 'expected': None}
    ]
    
    logger.info("Testing pattern detection:")
    for case in test_cases:
        block = {'text': case['text'], 'suspicious': True}
        
        matched = None
        for pattern_name, config in worker.fix_patterns.items():
            if worker._matches_pattern(block, config, [], 0):
                matched = pattern_name
                break
        
        logger.info(f"\nText: '{case['text']}'")
        logger.info(f"Expected: {case['expected']}")
        logger.info(f"Matched: {matched}")
        
        if matched == case['expected']:
            logger.success("✓ Correct match")
        else:
            logger.warning("✗ Mismatch")
    
    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - demonstrates fixing suspicious blocks
    - DEBUG: Run with 'debug' argument to test pattern matching
    - DO NOT create external test files - use debug_function() instead!
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        logger.info("Running debug mode...")
        asyncio.run(debug_function())
    else:
        logger.info("Running working usage mode...")
        success = asyncio.run(working_usage())
        exit(0 if success else 1)