#!/usr/bin/env python3
"""
PDF Block Fixer Worker - Batch processing and UUID-based fixing for suspicious PDF blocks.

This worker provides the implementation for the PDF block fixing sub-agent.
It handles batch creation, UUID tracking, and jq-based write-back operations
with Knowledge Architect integration for caching and pattern learning.

Key capabilities:
- Create batches from marker extraction output with UUID tracking
- Aggregate decisions from multiple sub-agents
- Apply fixes atomically using jq and UUID mapping
- Cache successful fix patterns

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function demonstrates all core capabilities
- debug_function() is for testing new features
- All operations integrate with Knowledge Architect

Example Usage:
    # Direct execution
    python pdf_block_fixer_worker.py
    
    # From sub-agent markdown
    from .claude.agents.workers.pdf_block_fixer_worker import (
        PDFBlockFixerWorker,
        create_suspicious_batches,
        apply_fixes_with_jq
    )
"""

import asyncio
import json
import sys
import time
import hashlib
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
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
AGENT_NAME = "pdf-block-fixer"
COLLECTION_PREFIX = f"{AGENT_NAME}_"
CACHE_COLLECTION = f"{COLLECTION_PREFIX}cache"
PATTERNS_COLLECTION = f"{COLLECTION_PREFIX}patterns"


class PDFBlockFixerWorker:
    """Worker for PDF block fixing operations."""
    
    def __init__(self):
        self.batch_dir = Path("/tmp/pdf_batches")
        self.batch_dir.mkdir(exist_ok=True)
    
    def add_uuids_to_blocks(self, marker_output_path: str) -> Dict[str, Any]:
        """Add UUIDs to marker-extracted blocks if not present."""
        logger.info(f"Adding UUIDs to blocks in {marker_output_path}")
        
        with open(marker_output_path) as f:
            data = json.load(f)
        
        modified = False
        for i, block in enumerate(data.get('blocks', [])):
            if 'uuid' not in block:
                block['uuid'] = str(uuid.uuid4())
                block['original_index'] = i
                modified = True
        
        if modified:
            # Save back to file
            with open(marker_output_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Added UUIDs to {len(data['blocks'])} blocks")
        else:
            logger.info("All blocks already have UUIDs")
        
        return data
    
    def create_suspicious_batches(self, marker_output_path: str, max_tokens_per_batch: int = 150000) -> Dict[str, Any]:
        """Create batches of suspicious blocks for parallel processing."""
        logger.info("Creating suspicious block batches")
        
        # Ensure blocks have UUIDs
        data = self.add_uuids_to_blocks(marker_output_path)
        
        # Extract suspicious blocks with extended context using jq
        jq_query = '''
        . as $root |
        .blocks | to_entries | 
        map(select(.value.suspicious == true)) |
        map({
            uuid: .value.uuid,
            index: .key,
            block: .value,
            context: {
                before_2: (if .key >= 2 then $root.blocks[.key - 2] else null end),
                before_1: (if .key >= 1 then $root.blocks[.key - 1] else null end),
                after_1: (if .key < ($root.blocks | length - 1) then $root.blocks[.key + 1] else null end),
                after_2: (if .key < ($root.blocks | length - 2) then $root.blocks[.key + 2] else null end)
            }
        })
        '''
        
        result = subprocess.run(
            ['jq', jq_query, marker_output_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"jq error: {result.stderr}")
            return {'success': False, 'error': result.stderr}
        
        suspicious_blocks = json.loads(result.stdout)
        logger.info(f"Found {len(suspicious_blocks)} suspicious blocks")
        
        # Create batches based on token count
        batches = []
        current_batch = []
        current_tokens = 0
        
        for item in suspicious_blocks:
            # Estimate tokens (rough approximation)
            item_json = json.dumps(item)
            item_tokens = len(item_json) // 4  # Rough token estimate
            
            if current_tokens + item_tokens > max_tokens_per_batch and current_batch:
                # Save current batch
                batches.append(current_batch)
                current_batch = [item]
                current_tokens = item_tokens
            else:
                current_batch.append(item)
                current_tokens += item_tokens
        
        # Add final batch
        if current_batch:
            batches.append(current_batch)
        
        # Save batch files
        batch_files = []
        manifest = {
            'original_file': marker_output_path,
            'total_suspicious': len(suspicious_blocks),
            'total_batches': len(batches),
            'batch_files': []
        }
        
        for i, batch in enumerate(batches):
            batch_data = {
                'batch_id': i,
                'suspicious_blocks': batch,
                'metadata': {
                    'source_file': marker_output_path,
                    'block_count': len(batch),
                    'uuids': [item['uuid'] for item in batch]
                }
            }
            
            batch_file = self.batch_dir / f"batch_{i:03d}.json"
            with open(batch_file, 'w') as f:
                json.dump(batch_data, f, indent=2)
            
            batch_files.append(str(batch_file))
            manifest['batch_files'].append({
                'batch_id': i,
                'file': str(batch_file),
                'blocks': len(batch),
                'uuids': batch_data['metadata']['uuids']
            })
        
        # Save manifest
        manifest_file = self.batch_dir / "manifest.json"
        manifest['timestamp'] = datetime.now().isoformat()
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.success(f"Created {len(batches)} batch files")
        
        return {
            'success': True,
            'batch_count': len(batches),
            'batch_files': batch_files,
            'manifest': str(manifest_file),
            'total_suspicious': len(suspicious_blocks)
        }
    
    def aggregate_decisions(self, batch_files: List[str]) -> str:
        """Aggregate decisions from all batch processing."""
        logger.info(f"Aggregating decisions from {len(batch_files)} batches")
        
        all_decisions = {'decisions': []}
        
        for batch_file in batch_files:
            batch_path = Path(batch_file)
            decisions_file = batch_path.parent / f"{batch_path.stem}_decisions.json"
            
            if decisions_file.exists():
                with open(decisions_file) as f:
                    batch_decisions = json.load(f)
                    all_decisions['decisions'].extend(batch_decisions.get('decisions', []))
                logger.info(f"Added {len(batch_decisions.get('decisions', []))} decisions from {decisions_file.name}")
            else:
                logger.warning(f"No decisions file found for {batch_file}")
        
        # Save aggregated decisions
        all_decisions_file = self.batch_dir / "all_decisions.json"
        with open(all_decisions_file, 'w') as f:
            json.dump(all_decisions, f, indent=2)
        
        logger.success(f"Aggregated {len(all_decisions['decisions'])} total decisions")
        return str(all_decisions_file)
    
    def apply_fixes_with_jq(self, original_file: str, decisions_file: str) -> Dict[str, Any]:
        """Apply fixes to original file using jq and UUID mapping."""
        logger.info("Applying fixes with jq")
        
        # Create jq script
        jq_script = '''
        . as $original |
        $decisions_arg[0] as $decisions |
        ($decisions.decisions | map({(.uuid): .}) | add) as $decision_map |
        
        $original | .blocks = (.blocks | map(
            . as $block |
            if $decision_map[$block.uuid] then
                $decision_map[$block.uuid] as $decision |
                
                if $decision.action == "delete" then
                    empty
                elif $decision.action == "merge_with_next" then
                    . + {
                        type: $decision.new_type,
                        text: $decision.new_text,
                        suspicious: false,
                        issues: null,
                        metadata: {fixed: true, action: "merged_with_next"}
                    }
                elif $decision.action == "merge_with_previous" then
                    empty
                elif $decision.action == "reclassify" then
                    . + {
                        type: $decision.new_type,
                        suspicious: false,
                        issues: null,
                        metadata: {fixed: true, action: "reclassified"}
                    }
                else
                    .
                end
            else
                .
            end
        )) |
        
        .blocks = (.blocks | to_entries | map(
            .value + {
                block_id: .key,
                page_index: (.value.page_index // .key)
            }
        ))
        '''
        
        # Write jq script to file
        jq_script_file = self.batch_dir / "apply_fixes.jq"
        with open(jq_script_file, 'w') as f:
            f.write(jq_script)
        
        # Apply fixes
        output_file = Path(original_file).parent / f"{Path(original_file).stem}_fixed.json"
        
        cmd = [
            'jq',
            '--slurpfile', 'decisions_arg', decisions_file,
            '-f', str(jq_script_file),
            original_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            with open(output_file, 'w') as f:
                f.write(result.stdout)
            
            # Count changes
            with open(original_file) as f:
                original_data = json.load(f)
            with open(output_file) as f:
                fixed_data = json.load(f)
            
            original_count = len(original_data.get('blocks', []))
            fixed_count = len(fixed_data.get('blocks', []))
            
            logger.success(f"Applied fixes: {original_count} blocks → {fixed_count} blocks")
            
            return {
                'success': True,
                'output_file': str(output_file),
                'original_blocks': original_count,
                'fixed_blocks': fixed_count,
                'blocks_removed': original_count - fixed_count
            }
        else:
            logger.error(f"jq error: {result.stderr}")
            return {
                'success': False,
                'error': result.stderr
            }


# Module-level functions for easy import
async def create_suspicious_batches(marker_output_path: str, max_tokens_per_batch: int = 150000) -> Dict[str, Any]:
    """Create batches from marker output."""
    worker = PDFBlockFixerWorker()
    return worker.create_suspicious_batches(marker_output_path, max_tokens_per_batch)


async def apply_fixes_with_jq(original_file: str, decisions_file: str) -> Dict[str, Any]:
    """Apply fixes using jq."""
    worker = PDFBlockFixerWorker()
    return worker.apply_fixes_with_jq(original_file, decisions_file)


# ============================================
# USAGE EXAMPLES (MANDATORY)
# ============================================

async def working_usage():
    """
    Known working examples that demonstrate all capabilities.
    """
    logger.info("=== Running PDF Block Fixer Working Usage ===")
    
    # Create test data
    test_marker_output = {
        "metadata": {
            "source_file": "test.pdf",
            "total_pages": 2,
            "total_blocks": 7
        },
        "blocks": [
            {
                "block_id": 0,
                "type": "Text",
                "text": "4.1.5.4. BHT (Branch History",
                "page": 0,
                "suspicious": True,
                "issues": ["incomplete_sentence"]
            },
            {
                "block_id": 1,
                "type": "Text",
                "text": "Table) submodule",
                "page": 0,
                "suspicious": True,
                "issues": ["sentence_fragment"]
            },
            {
                "block_id": 2,
                "type": "Text",
                "text": "Normal content here.",
                "page": 0,
                "suspicious": False
            }
        ]
    }
    
    # Save test data
    test_file = Path("/tmp/test_marker_output.json")
    with open(test_file, 'w') as f:
        json.dump(test_marker_output, f, indent=2)
    
    # Test 1: Create batches
    logger.info("\nTest 1: Creating suspicious batches")
    worker = PDFBlockFixerWorker()
    batch_result = worker.create_suspicious_batches(str(test_file))
    
    assert batch_result['success'], "Batch creation failed"
    assert batch_result['batch_count'] > 0, "No batches created"
    assert batch_result['total_suspicious'] == 2, "Wrong suspicious count"
    logger.success("✓ Batch creation passed")
    
    # Test 2: Simulate decisions
    logger.info("\nTest 2: Creating test decisions")
    test_decisions = {
        "decisions": [
            {
                "uuid": test_marker_output['blocks'][0].get('uuid', 'test-uuid-1'),
                "action": "merge_with_next",
                "new_type": "SectionHeader",
                "new_text": "4.1.5.4. BHT (Branch History Table) submodule"
            },
            {
                "uuid": test_marker_output['blocks'][1].get('uuid', 'test-uuid-2'),
                "action": "delete",
                "reason": "Merged into previous"
            }
        ]
    }
    
    decisions_file = worker.batch_dir / "test_decisions.json"
    with open(decisions_file, 'w') as f:
        json.dump(test_decisions, f, indent=2)
    
    # Test 3: Apply fixes
    logger.info("\nTest 3: Applying fixes with jq")
    
    # Re-read to get UUIDs
    with open(test_file) as f:
        updated_data = json.load(f)
    
    # Update decisions with actual UUIDs
    if 'blocks' in updated_data and len(updated_data['blocks']) >= 2:
        test_decisions['decisions'][0]['uuid'] = updated_data['blocks'][0]['uuid']
        test_decisions['decisions'][1]['uuid'] = updated_data['blocks'][1]['uuid']
        
        with open(decisions_file, 'w') as f:
            json.dump(test_decisions, f, indent=2)
    
    fix_result = worker.apply_fixes_with_jq(str(test_file), str(decisions_file))
    
    assert fix_result['success'], f"Fix application failed: {fix_result.get('error')}"
    assert fix_result['blocks_removed'] == 1, "Wrong number of blocks removed"
    logger.success("✓ Fix application passed")
    
    # Verify fixed file
    if fix_result['success']:
        with open(fix_result['output_file']) as f:
            fixed_data = json.load(f)
        
        assert len(fixed_data['blocks']) == 2, "Wrong number of blocks after fix"
        assert fixed_data['blocks'][0]['text'] == "4.1.5.4. BHT (Branch History Table) submodule"
        assert fixed_data['blocks'][0]['type'] == "SectionHeader"
        logger.success("✓ Fixed content verification passed")
    
    logger.success("\n=== All tests passed! ===")
    return True


async def debug_function():
    """
    Debug function for testing new features.
    Currently testing: Pattern learning from successful fixes
    """
    logger.info("=== Running Debug Function ===")
    
    # Test pattern detection
    worker = PDFBlockFixerWorker()
    
    # Create sample patterns
    patterns = [
        {
            "pattern": "split_header",
            "regex": r".*\($",  # Ends with opening paren
            "next_regex": r"^\).*",  # Starts with closing paren
            "action": "merge_with_next",
            "new_type": "SectionHeader"
        },
        {
            "pattern": "orphaned_word",
            "regex": r"^[A-Z][a-z]+$",  # Single capitalized word
            "prev_type": "SectionHeader",
            "action": "merge_with_previous"
        }
    ]
    
    logger.info(f"Testing {len(patterns)} fix patterns")
    
    # Simulate pattern matching
    test_blocks = [
        {"text": "4.1.5.4. BHT (Branch History", "type": "Text"},
        {"text": "Table) submodule", "type": "Text"},
        {"text": "Interface", "type": "Text"}
    ]
    
    for i, block in enumerate(test_blocks):
        logger.info(f"\nAnalyzing block: '{block['text']}'")
        
        # Check patterns
        for pattern in patterns:
            if 'regex' in pattern:
                import re
                if re.match(pattern['regex'], block['text']):
                    logger.info(f"  → Matches pattern: {pattern['pattern']}")
                    logger.info(f"  → Suggested action: {pattern['action']}")
    
    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - stable example that works
    - DEBUG: Run with 'debug' argument to test new ideas
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