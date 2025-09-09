#!/usr/bin/env python3
"""Test script to verify Claude CLI integration."""

import asyncio
import json
import sys
from pathlib import Path
from loguru import logger

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from poc_07_final_secure_pipeline import call_claude_cli, sanitize_prompt, parse_claude_response

logger.remove()
logger.add(sys.stderr, level="INFO")


async def test_claude_cli():
    """Test the Claude CLI integration."""
    logger.info("Testing Claude CLI integration...")
    
    # Test 1: Simple prompt
    prompt = """Please respond with ONLY this JSON array:
[
  {
    "uuid": "test-123",
    "correct_type": "Text",
    "confidence": 0.95,
    "reasoning": "Test response"
  }
]"""
    
    sanitized = sanitize_prompt(prompt)
    logger.info(f"Sanitized prompt: {sanitized[:100]}...")
    
    result = await call_claude_cli(sanitized)
    
    if result:
        logger.success(f"Claude responded with {len(result)} characters")
        logger.info(f"Response: {result[:200]}...")
        
        # Test parsing
        test_blocks = [{"uuid": "test-123"}]
        parsed = parse_claude_response(result, test_blocks)
        logger.info(f"Parsed results: {json.dumps(parsed, indent=2)}")
    else:
        logger.error("Claude CLI call failed")
        return False
    
    return True


async def test_batch_analysis():
    """Test analyzing suspicious blocks."""
    from poc_07_final_secure_pipeline import analyze_with_claude_batch
    
    # Create mock suspicious blocks
    suspicious_blocks = [
        {
            "uuid": "block-001",
            "block_type": "Table",
            "text": "This is actually a regular paragraph of text, not a table.",
            "page": 0,
            "suspicion_reasons": ["table_is_actually_text"],
            "suspicion_score": 0.9
        },
        {
            "uuid": "block-002", 
            "block_type": "SectionHeader",
            "text": "EXECU",
            "page": 1,
            "suspicion_reasons": ["known_fragment", "inside_camelot_table"],
            "suspicion_score": 0.95
        }
    ]
    
    logger.info("Testing batch analysis with Claude...")
    results = await analyze_with_claude_batch(suspicious_blocks, Path("test.pdf"), batch_size=2)
    
    logger.info(f"Analysis results: {json.dumps(results, indent=2)}")
    return True


async def main():
    """Run all tests."""
    # Test basic CLI call
    success = await test_claude_cli()
    if not success:
        logger.warning("Basic CLI test failed, will use fallback")
    
    # Test batch analysis
    await test_batch_analysis()


if __name__ == "__main__":
    asyncio.run(main())