#!/usr/bin/env python3
"""
Claude API integration for PDF block analysis.
This module provides a way to analyze suspicious PDF blocks using Claude's API.
"""

import os
import json
from typing import List, Dict, Any, Optional
from loguru import logger

# Check if we have Claude API access
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_AVAILABLE = bool(ANTHROPIC_API_KEY)

if CLAUDE_AVAILABLE:
    try:
        from anthropic import Anthropic
        logger.info("Anthropic SDK available")
    except ImportError:
        CLAUDE_AVAILABLE = False
        logger.warning("Anthropic SDK not installed. Install with: pip install anthropic")


async def analyze_blocks_with_api(
    blocks: List[Dict[str, Any]], 
    valid_block_types: List[str]
) -> List[Dict[str, Any]]:
    """Analyze suspicious blocks using Claude API."""
    
    if not CLAUDE_AVAILABLE:
        logger.error("Claude API not available. Using fallback analysis.")
        return []
    
    # Prepare the prompt
    blocks_for_prompt = []
    for block in blocks:
        blocks_for_prompt.append({
            "uuid": block.get("uuid"),
            "block_type": block.get("block_type"),
            "text": block.get("text", "")[:200],  # Limit text length
            "page": block.get("page", 0),
            "suspicion_reasons": block.get("suspicion_reasons", []),
            "suspicion_score": block.get("suspicion_score", 0)
        })
    
    prompt = f"""Analyze these suspicious blocks from a PDF extraction and determine their correct block types.

Context: These blocks were flagged as suspicious during PDF processing. Common issues:
- Headers misclassified as TableCells when inside tables
- Tables containing full sentences misclassified (should be Text)
- Garbled text from OCR errors
- Fragment words that are actually table cells

For each block, provide:
1. The correct block_type (one of: {', '.join(valid_block_types)})
2. A confidence score (0.0-1.0)
3. Brief reasoning

Blocks to analyze:
{json.dumps(blocks_for_prompt, indent=2)}

Respond ONLY with a JSON array like this:
[
  {{
    "uuid": "block-uuid-here",
    "correct_type": "Text",
    "confidence": 0.95,
    "reasoning": "Brief explanation"
  }}
]"""
    
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Use Haiku for cost efficiency
            max_tokens=1000,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract the response text
        response_text = response.content[0].text
        logger.info(f"Claude API response received ({len(response_text)} chars)")
        
        # Parse the JSON response
        return parse_api_response(response_text, blocks)
        
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return []


def parse_api_response(response: str, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse Claude API response."""
    results = []
    
    try:
        # Extract JSON from response
        import re
        json_match = re.search(r'\[\s*\{.*?\}\s*\]', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            parsed = json.loads(json_str)
            
            # Extract results
            for item in parsed:
                if isinstance(item, dict) and "uuid" in item:
                    results.append({
                        "uuid": item.get("uuid"),
                        "correct_type": item.get("correct_type", "Text"),
                        "confidence": float(item.get("confidence", 0.5)),
                        "reasoning": item.get("reasoning", "Claude API analysis")
                    })
                    
    except Exception as e:
        logger.error(f"Failed to parse Claude API response: {e}")
    
    return results


def check_claude_availability():
    """Check if Claude is available via API."""
    return {
        "api_available": CLAUDE_AVAILABLE,
        "api_key_set": bool(ANTHROPIC_API_KEY),
        "sdk_installed": 'anthropic' in globals()
    }


if __name__ == "__main__":
    """Test Claude availability."""
    import asyncio
    
    async def test():
        status = check_claude_availability()
        print(f"Claude API Status: {json.dumps(status, indent=2)}")
        
        if status["api_available"]:
            # Test with sample blocks
            test_blocks = [
                {
                    "uuid": "test-001",
                    "block_type": "Table",
                    "text": "This is a complete sentence that should not be in a table.",
                    "suspicion_reasons": ["table_is_actually_text"],
                    "suspicion_score": 0.9
                }
            ]
            
            results = await analyze_blocks_with_api(
                test_blocks, 
                ["Text", "Table", "SectionHeader", "TableCell", "Figure", "ListItem"]
            )
            print(f"\nAnalysis results: {json.dumps(results, indent=2)}")
    
    asyncio.run(test())