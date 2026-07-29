#!/usr/bin/env python3
"""
MARKER FORK ADDITION - Suspicious Header Detection Enhancement

Stage 4: Suspicious Block Analysis with jq and Prompts

This stage:
1. Uses jq to extract all suspicious blocks from marker output
2. Batches them for efficient processing
3. Analyzes each batch with prompts to determine fixes

Uses the simple claude_p_with_timeout function from extract_pdf_pipeline.py
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any
from loguru import logger
import sys


class SuspiciousBlockAnalyzer:
    """Analyze suspicious blocks using jq extraction and prompt-based analysis."""

    def __init__(self):
        self.batch_size = 5  # Analyze 5 suspicious blocks at a time

    def extract_suspicious_with_jq(self, blocks_file: str) -> List[Dict[str, Any]]:
        """Use jq to extract all suspicious blocks with their context."""

        logger.info("=== Using jq to extract suspicious blocks ===")

        # jq query to extract suspicious blocks with context
        jq_query = """
        . as $root |
        .blocks | to_entries | 
        map(select(.value.suspicious == true)) |
        map({
            index: .key,
            block: .value,
            prev: (if .key > 0 then $root.blocks[.key - 1] else null end),
            next: (if .key < ($root.blocks | length - 1) then $root.blocks[.key + 1] else null end)
        })
        """

        try:
            # Run jq command
            result = subprocess.run(
                ["jq", jq_query, blocks_file], capture_output=True, text=True, check=True
            )

            suspicious_blocks = json.loads(result.stdout)
            logger.info(f"Found {len(suspicious_blocks)} suspicious blocks with jq")

            return suspicious_blocks

        except subprocess.CalledProcessError as e:
            logger.error(f"jq command failed: {e.stderr}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse jq output: {e}")
            return []

    def create_analysis_prompt(
        self, batch: List[Dict[str, Any]], annotations: List[Dict[str, Any]]
    ) -> str:
        """Create a prompt for analyzing a batch of suspicious blocks."""

        prompt = """Analyze these suspicious PDF blocks and determine the correct fixes.

CONTEXT: These blocks were marked as suspicious by the marker-pdf extraction process.
Your task is to analyze each block with its surrounding context and determine:
1. The correct block type (Text, SectionHeader, Table, etc.)
2. Whether it should be merged with adjacent blocks
3. The confidence level of your decision

ANNOTATIONS FROM THE PDF:
"""

        # Add relevant annotations
        for ann in annotations:
            if ann.get("type") and ann.get("content"):
                prompt += (
                    f"- {ann['type']}: \"{ann['content']}\" on page {ann.get('page', 'unknown')}\n"
                )

        prompt += "\nSUSPICIOUS BLOCKS TO ANALYZE:\n\n"

        # Add each suspicious block with context
        for item in batch:
            idx = item["index"]
            block = item["block"]
            prev_block = item.get("prev")
            next_block = item.get("next")

            prompt += f"=== Block {idx} ===\n"
            prompt += f"Current Type: {block.get('type', 'Unknown')}\n"
            prompt += f"Text: \"{block.get('text', '')}\"\n"
            prompt += f"Page: {block.get('page', 'unknown')}\n"
            prompt += f"Issues: {', '.join(block.get('issues', []))}\n"

            if prev_block:
                prompt += f"\nPrevious Block ({idx-1}):\n"
                prompt += f"  Type: {prev_block.get('type', 'Unknown')}\n"
                prompt += f"  Text: \"{prev_block.get('text', '')[:50]}...\"\n"

            if next_block:
                prompt += f"\nNext Block ({idx+1}):\n"
                prompt += f"  Type: {next_block.get('type', 'Unknown')}\n"
                prompt += f"  Text: \"{next_block.get('text', '')[:50]}...\"\n"

            prompt += "\n"

        prompt += """
For each block, provide your analysis in this JSON format:
{
  "block_<index>": {
    "action": "merge_with_next|merge_with_previous|reclassify|none",
    "new_type": "SectionHeader|Text|Table|Figure|List|ListItem",
    "reason": "Brief explanation",
    "confidence": 0.0-1.0
  }
}

Focus on:
- Headers split across lines (missing closing parentheses, sentence fragments)
- Table rows that should be merged
- Text incorrectly classified as headers or vice versa
- Annotations that provide guidance (e.g., "Split header - fix this")
"""

        return prompt

    def batch_suspicious_blocks(
        self, suspicious_blocks: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Batch suspicious blocks for efficient processing."""

        batches = []
        for i in range(0, len(suspicious_blocks), self.batch_size):
            batch = suspicious_blocks[i : i + self.batch_size]
            batches.append(batch)

        logger.info(f"Created {len(batches)} batches of suspicious blocks")
        return batches

    async def analyze_suspicious_blocks(
        self, blocks_file: str, annotations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Main entry point: analyze all suspicious blocks."""

        # Step 1: Extract suspicious blocks with jq
        suspicious_blocks = self.extract_suspicious_with_jq(blocks_file)

        if not suspicious_blocks:
            logger.info("No suspicious blocks found")
            return []

        # Show what jq found
        logger.info("\n=== Suspicious blocks found by jq ===")
        for item in suspicious_blocks[:3]:  # Show first 3
            block = item["block"]
            logger.info(
                f"Block {item['index']}: {block.get('type')} - \"{block.get('text', '')[:40]}...\""
            )

        # Step 2: Batch the blocks
        batches = self.batch_suspicious_blocks(suspicious_blocks)

        # Step 3: Create prompts for each batch
        all_decisions = []

        for i, batch in enumerate(batches):
            logger.info(f"\n=== Analyzing batch {i+1}/{len(batches)} ===")

            # Create prompt
            prompt = self.create_analysis_prompt(batch, annotations)

            # Save prompt for inspection
            prompt_file = Path("tmp") / f"suspicious_batch_{i+1}_prompt.txt"
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            with open(prompt_file, "w") as f:
                f.write(prompt)

            logger.info(f"Created analysis prompt: {prompt_file}")

            # Use claude -p for analysis
            decisions = await self.analyze_with_claude(prompt)
            all_decisions.extend(decisions)

        return all_decisions


def main():
    """Demonstrate suspicious block analysis with jq."""

    # Create test data
    test_blocks = {
        "blocks": [
            {
                "block_id": 0,
                "type": "Text",
                "text": "4.1.5.4. BHT (Branch History",
                "page": 0,
                "suspicious": True,
                "issues": ["incomplete_sentence", "possible_header"],
            },
            {
                "block_id": 1,
                "type": "Text",
                "text": "Table) submodule",
                "page": 0,
                "suspicious": True,
                "issues": ["sentence_fragment"],
            },
            {
                "block_id": 2,
                "type": "Text",
                "text": "BHT is implemented as a memory which is composed of BHTDepth configuration parameter entries.",
                "page": 0,
                "suspicious": False,
            },
            {
                "block_id": 3,
                "type": "Table",
                "text": "Signal|IO|Description|Connection|Type",
                "page": 0,
                "suspicious": False,
            },
            {
                "block_id": 4,
                "type": "Table",
                "text": "clk_i|I|Clock signal|core|logic",
                "page": 0,
                "suspicious": True,
                "issues": ["possible_table_continuation"],
            },
        ]
    }

    # Save test data
    test_file = Path("tmp") / "test_blocks_for_jq.json"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    with open(test_file, "w") as f:
        json.dump(test_blocks, f, indent=2)

    # Test annotations
    annotations = [
        {"page": 0, "type": "Highlight", "content": "Split header - fix this"},
        {"page": 0, "type": "FreeText", "content": "Merge Table"},
    ]

    # Run analysis
    analyzer = SuspiciousBlockAnalyzer()
    import asyncio

    decisions = asyncio.run(analyzer.analyze_suspicious_blocks(str(test_file), annotations))

    # Show results
    logger.info("\n=== Analysis Decisions ===")
    for decision in decisions:
        logger.info(
            f"Block {decision['block_index']}: {decision['action']} → {decision['new_type']}"
        )
        logger.info(f"  Reason: {decision['reason']} (confidence: {decision['confidence']})")


def debug_function():
    """Test jq extraction directly."""

    # Test jq command
    test_file = Path("tmp") / "test_blocks_for_jq.json"

    # Direct jq test
    jq_command = """
    .blocks | to_entries | 
    map(select(.value.suspicious == true)) |
    map({
        index: .key,
        type: .value.type,
        text: .value.text,
        issues: .value.issues
    })
    """

    try:
        result = subprocess.run(["jq", jq_command, test_file], capture_output=True, text=True)

        logger.info("jq output:")
        logger.info(result.stdout)

    except Exception as e:
        logger.error(f"jq test failed: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        debug_function()
    else:
        main()
