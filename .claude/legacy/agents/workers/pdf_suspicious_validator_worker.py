#!/usr/bin/env python3
"""
PDF Suspicious Block Validator Worker

Uses Claude's semantic understanding to validate suspicious blocks and achieve >90% accuracy.
This is the key component that differentiates us from pattern-based approaches.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import os

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from anthropic import AsyncAnthropic

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Semantic validation of suspicious PDF blocks using Claude")
console = Console()


class PDFSuspiciousValidator:
    """Validates suspicious blocks using Claude's semantic understanding."""
    
    def __init__(self):
        # Initialize Claude client
        api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("CLAUDE_API_KEY or ANTHROPIC_API_KEY environment variable required")
        
        # Validate API key format for security
        if not api_key.startswith("sk-ant-"):
            raise ValueError("Invalid Claude API key format - must start with 'sk-ant-'")
        
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-3-haiku-20240307"  # Fast and cost-effective
        
        # Cache for similar validations
        self.cache = {}
        self.cache_hits = 0
        self.total_calls = 0
        
    async def validate_block(self,
                           text: str,
                           block_type: str,
                           context_before: Optional[str] = None,
                           context_after: Optional[str] = None,
                           metadata: Optional[Dict] = None) -> Dict:
        """Validate a suspicious block using semantic understanding.
        
        Args:
            text: The block text to validate
            block_type: Current classification (e.g., "SectionHeader")
            context_before: Text from previous block
            context_after: Text from next block
            metadata: Additional metadata (font size, position, etc.)
            
        Returns:
            Validation result with corrections and reasoning
        """
        self.total_calls += 1
        
        # Check cache first
        cache_key = f"{text}:{block_type}:{context_before}:{context_after}"
        if cache_key in self.cache:
            self.cache_hits += 1
            logger.debug(f"Cache hit ({self.cache_hits}/{self.total_calls})")
            return self.cache[cache_key]
        
        # Build context for Claude
        prompt = self._build_validation_prompt(
            text=text,
            block_type=block_type,
            context_before=context_before,
            context_after=context_after,
            metadata=metadata
        )
        
        try:
            # Call Claude
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistency
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Parse response
            result = self._parse_claude_response(response.content[0].text)
            
            # Add original info
            result["original_type"] = block_type
            result["text"] = text
            
            # Cache result
            self.cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            # Fallback to heuristic
            return self._heuristic_validation(text, block_type)
    
    def _build_validation_prompt(self, 
                               text: str,
                               block_type: str,
                               context_before: Optional[str],
                               context_after: Optional[str],
                               metadata: Optional[Dict]) -> str:
        """Build prompt for Claude validation."""
        
        # Include metadata if available
        meta_info = ""
        if metadata:
            if "font_size" in metadata:
                meta_info += f"\nFont size: {metadata['font_size']}"
            if "font_weight" in metadata:
                meta_info += f"\nFont weight: {metadata['font_weight']}"
            if "position" in metadata:
                meta_info += f"\nPosition on page: {metadata['position']}"
        
        prompt = f"""You are analyzing a PDF extraction where a block of text was classified as "{block_type}".
Your task is to determine if this classification is correct based on semantic understanding.

Text to analyze: "{text}"

Context before: {f'"{context_before}"' if context_before else "None"}
Context after: {f'"{context_after}"' if context_after else "None"}
{meta_info}

Analyze this text and provide a JSON response with:
1. "corrected_type": The correct type (SectionHeader, Text, Table, ListItem, etc.)
2. "confidence": Your confidence level (0.0 to 1.0)
3. "reasoning": Brief explanation of your decision
4. "semantic_role": What role this text plays (e.g., "transitional_phrase", "section_title", "continuation")
5. "should_merge": true/false - should this be merged with adjacent blocks?
6. "merge_direction": "previous", "next", or null

Common patterns to consider:
- Headers ending with commas are usually sentence fragments
- Text starting with "As", "For", "But" often continues from previous
- All caps doesn't always mean header
- Tables can be misidentified if they have irregular structure

Respond with valid JSON only."""

        return prompt
    
    def _parse_claude_response(self, response: str) -> Dict:
        """Parse Claude's response into structured data."""
        try:
            # Extract JSON from response
            # Claude sometimes adds explanation before/after JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response)
            
            # Validate required fields
            required = ["corrected_type", "confidence", "reasoning"]
            for field in required:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            # Set defaults for optional fields
            result.setdefault("semantic_role", "unknown")
            result.setdefault("should_merge", False)
            result.setdefault("merge_direction", None)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse Claude response: {e}")
            logger.debug(f"Response was: {response}")
            
            # Return a safe default
            return {
                "corrected_type": "Text",
                "confidence": 0.5,
                "reasoning": "Failed to parse LLM response",
                "semantic_role": "unknown",
                "should_merge": False,
                "merge_direction": None
            }
    
    def _heuristic_validation(self, text: str, block_type: str) -> Dict:
        """Fallback heuristic validation when Claude is unavailable."""
        result = {
            "corrected_type": block_type,
            "confidence": 0.6,
            "reasoning": "Heuristic validation (Claude unavailable)",
            "semantic_role": "unknown",
            "should_merge": False,
            "merge_direction": None
        }
        
        # Simple heuristics
        if block_type == "SectionHeader":
            if text.endswith(','):
                result["corrected_type"] = "Text"
                result["reasoning"] = "Headers typically don't end with commas"
                result["should_merge"] = True
                result["merge_direction"] = "next"
            elif text.startswith(('As ', 'For ', 'But ', 'And ')):
                result["corrected_type"] = "Text"
                result["reasoning"] = "Appears to be continuation of sentence"
                result["should_merge"] = True
                result["merge_direction"] = "previous"
        
        return result
    
    async def validate_batch(self, blocks: List[Dict]) -> List[Dict]:
        """Validate multiple blocks efficiently."""
        validated = []
        
        for i, block in enumerate(blocks):
            # Get context
            context_before = blocks[i-1]["text"] if i > 0 else None
            context_after = blocks[i+1]["text"] if i < len(blocks)-1 else None
            
            # Only validate suspicious blocks
            if block.get("suspicious", False) or block.get("suspicion_score", 0) > 0:
                result = await self.validate_block(
                    text=block["text"],
                    block_type=block["type"],
                    context_before=context_before,
                    context_after=context_after,
                    metadata=block.get("metadata", {})
                )
                
                # Apply corrections
                block["original_type"] = block["type"]
                block["type"] = result["corrected_type"]
                block["validation"] = result
            
            validated.append(block)
        
        return validated
    
    def get_statistics(self) -> Dict:
        """Get validation statistics."""
        return {
            "total_validations": self.total_calls,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hits / self.total_calls if self.total_calls > 0 else 0,
            "unique_validations": len(self.cache)
        }


# Initialize validator
validator = PDFSuspiciousValidator()


@app.command("validate-block")
def validate_block(
    text: str = typer.Argument(..., help="Text to validate"),
    block_type: str = typer.Option("SectionHeader", "--type", "-t", help="Current block type"),
    context_before: Optional[str] = typer.Option(None, "--context-before", help="Previous block text"),
    context_after: Optional[str] = typer.Option(None, "--context-after", help="Next block text")
):
    """Validate a single suspicious block."""
    async def run():
        result = await validator.validate_block(
            text=text,
            block_type=block_type,
            context_before=context_before,
            context_after=context_after
        )
        
        # Display result
        table = Table(title="Validation Result")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Original Type", block_type)
        table.add_row("Corrected Type", result["corrected_type"])
        table.add_row("Confidence", f"{result['confidence']:.2%}")
        table.add_row("Semantic Role", result["semantic_role"])
        table.add_row("Should Merge", str(result["should_merge"]))
        
        if result["should_merge"]:
            table.add_row("Merge Direction", result["merge_direction"])
        
        console.print(table)
        console.print(f"\n[bold]Reasoning:[/bold] {result['reasoning']}")
    
    asyncio.run(run())


@app.command("validate-batch")
def validate_batch(
    input_file: Path = typer.Argument(..., help="JSON file with blocks to validate"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file")
):
    """Validate multiple suspicious blocks from a file."""
    if not input_file.exists():
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load blocks
        with open(input_file) as f:
            data = json.load(f)
        
        blocks = data if isinstance(data, list) else data.get("blocks", [])
        
        # Count suspicious blocks
        suspicious_count = sum(1 for b in blocks 
                             if b.get("suspicious", False) or b.get("suspicion_score", 0) > 0)
        
        console.print(f"Found [yellow]{suspicious_count}[/yellow] suspicious blocks to validate...")
        
        # Validate
        with console.status("Validating blocks..."):
            validated = await validator.validate_batch(blocks)
        
        # Count corrections
        corrections = sum(1 for b in validated 
                        if b.get("validation") and 
                        b["validation"]["corrected_type"] != b.get("original_type"))
        
        console.print(f"[green]✓ Validated {suspicious_count} blocks[/green]")
        console.print(f"[yellow]↻ Made {corrections} corrections[/yellow]")
        
        # Save results
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(validated, f, indent=2)
            console.print(f"[green]✓ Saved to {output_file}[/green]")
        
        # Show statistics
        stats = validator.get_statistics()
        console.print(f"\nCache hit rate: {stats['cache_hit_rate']:.1%}")
    
    asyncio.run(run())


@app.command("explain-correction")
def explain_correction(
    original: str = typer.Argument(..., help="Original classification"),
    corrected: str = typer.Argument(..., help="Corrected classification"),
    text: str = typer.Argument(..., help="The text that was corrected")
):
    """Explain why a correction was made."""
    explanations = {
        ("SectionHeader", "Text"): [
            "Headers typically don't end with punctuation like commas or periods",
            "The text appears to be a sentence fragment or continuation",
            "Context suggests this is narrative text, not a structural element"
        ],
        ("Table", "Text"): [
            "The structure doesn't match typical table patterns",
            "Low confidence score from table detection algorithm",
            "Content appears to be formatted text, not tabular data"
        ],
        ("Text", "ListItem"): [
            "The text starts with a list marker (bullet, number, letter)",
            "Indentation suggests list structure",
            "Part of a sequence of similar items"
        ]
    }
    
    key = (original, corrected)
    if key in explanations:
        console.print(f"[bold]Why '{text}' was changed from {original} to {corrected}:[/bold]\n")
        for reason in explanations[key]:
            console.print(f"  • {reason}")
    else:
        console.print(f"[yellow]No specific explanation for {original} → {corrected}[/yellow]")


@app.command("stats")
def stats():
    """Show validation statistics."""
    stats = validator.get_statistics()
    
    table = Table(title="Validation Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Validations", str(stats["total_validations"]))
    table.add_row("Cache Hits", str(stats["cache_hits"]))
    table.add_row("Cache Hit Rate", f"{stats['cache_hit_rate']:.1%}")
    table.add_row("Unique Patterns", str(stats["unique_validations"]))
    
    console.print(table)


# Worker functions for testing
async def working_usage():
    """Demonstrate validation capabilities."""
    logger.info("Testing suspicious block validation...")
    
    # Test cases that pattern matching gets wrong
    test_cases = [
        {
            "text": "As mentioned earlier,",
            "type": "SectionHeader",
            "context_before": "1. INTRODUCTION",
            "context_after": "the design must consider"
        },
        {
            "text": "TABLE I,",
            "type": "SectionHeader",
            "context_before": "Results are shown in",
            "context_after": "which presents the data"
        },
        {
            "text": "appendix a: supplementary data",
            "type": "Text",  # Pattern matcher wrongly thinks lowercase = not header
            "context_before": "REFERENCES",
            "context_after": "This section contains"
        }
    ]
    
    for test in test_cases:
        result = await validator.validate_block(
            text=test["text"],
            block_type=test["type"],
            context_before=test["context_before"],
            context_after=test["context_after"]
        )
        
        status = "✓" if result["corrected_type"] != test["type"] else "✗"
        logger.info(f"\n{status} '{test['text']}'")
        logger.info(f"  Original: {test['type']} → Corrected: {result['corrected_type']}")
        logger.info(f"  Confidence: {result['confidence']:.2%}")
        logger.info(f"  Reasoning: {result['reasoning']}")


async def debug_function():
    """Debug edge cases and error handling."""
    logger.info("Testing edge cases...")
    
    # Test with no API key
    original_key = os.environ.get("CLAUDE_API_KEY")
    try:
        if original_key:
            del os.environ["CLAUDE_API_KEY"]
        
        # This should use heuristic fallback
        result = await validator.validate_block(
            text="Testing, without API",
            block_type="SectionHeader"
        )
        logger.info(f"Fallback result: {result['reasoning']}")
        
    finally:
        if original_key:
            os.environ["CLAUDE_API_KEY"] = original_key
    
    # Test cache efficiency
    logger.info("\nTesting cache...")
    
    # Make same request 3 times
    for i in range(3):
        await validator.validate_block(
            text="Repeated validation test",
            block_type="Text"
        )
    
    stats = validator.get_statistics()
    logger.info(f"Cache hit rate after repeats: {stats['cache_hit_rate']:.1%}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()