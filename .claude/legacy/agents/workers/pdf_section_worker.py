#!/usr/bin/env python3
"""
PDF Section Header Validation Worker

Validates section headers and builds document structure using semantic understanding.
This is the CRITICAL component that must complete before any content processing.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="PDF Section Validation - Critical for >90% accuracy")
console = Console()

# Import the actual implementation
from extractor.core.subagents import PDFSectionHeaderValidator


class PDFSectionOrchestrator:
    """Orchestrates section validation using the sub-agent implementation."""
    
    def __init__(self):
        self.validator = PDFSectionHeaderValidator()
        
    async def validate_header(self, 
                            text: str,
                            context: Optional[Dict] = None) -> Dict:
        """Validate if text is a section header.
        
        Args:
            text: Text to validate
            context: Optional context (document type, etc.)
            
        Returns:
            Validation result with confidence and reasoning
        """
        block = {
            "type": "SectionHeader",
            "text": text,
            "metadata": {}
        }
        
        context = context or {"doc_type": "academic_paper"}
        
        result = await self.validator.validate_header(
            block=block,
            context=context,
            surrounding_blocks=[]
        )
        
        return result
    
    async def find_split_headers(self, blocks_file: Path) -> List[Dict]:
        """Find headers that were split across blocks.
        
        Args:
            blocks_file: JSON file containing extracted blocks
            
        Returns:
            List of split header candidates
        """
        with open(blocks_file) as f:
            data = json.load(f)
        
        blocks = data if isinstance(data, list) else data.get("blocks", [])
        
        splits = await self.validator.find_split_headers(blocks)
        
        return splits
    
    async def build_structure(self, 
                            blocks_file: Path,
                            output_file: Optional[Path] = None) -> Dict:
        """Build hierarchical section structure.
        
        Args:
            blocks_file: JSON file containing blocks
            output_file: Optional output path
            
        Returns:
            Section structure
        """
        with open(blocks_file) as f:
            data = json.load(f)
        
        blocks = data if isinstance(data, list) else data.get("blocks", [])
        
        # Validate all headers first
        validated_blocks = []
        for i, block in enumerate(blocks):
            if block.get("type") == "SectionHeader":
                # Get surrounding context
                surrounding = []
                if i > 0:
                    surrounding.append(blocks[i-1])
                if i < len(blocks) - 1:
                    surrounding.append(blocks[i+1])
                
                validation = await self.validator.validate_header(
                    block=block,
                    context={"doc_type": "document"},
                    surrounding_blocks=surrounding
                )
                
                # Update block type if not actually a header
                if not validation.get("is_header", True):
                    block["type"] = "Text"
                    block["metadata"] = block.get("metadata", {})
                    block["metadata"]["was_header"] = True
                    block["metadata"]["validation"] = validation
                else:
                    block["metadata"] = block.get("metadata", {})
                    block["metadata"]["header_level"] = validation.get("header_level", 1)
                    block["metadata"]["semantic_category"] = validation.get("semantic_category")
            
            validated_blocks.append(block)
        
        # Build structure from validated blocks
        structure = self._build_section_structure(validated_blocks)
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(structure, f, indent=2)
            logger.info(f"Saved structure to {output_file}")
        
        return structure
    
    def _build_section_structure(self, blocks: List[Dict]) -> Dict:
        """Build hierarchical structure from blocks."""
        sections = []
        current_section = None
        
        for block in blocks:
            if block.get("type") == "SectionHeader":
                if current_section:
                    sections.append(current_section)
                
                current_section = {
                    "type": "section",
                    "header": block.get("text", ""),
                    "level": block.get("metadata", {}).get("header_level", 1),
                    "semantic_category": block.get("metadata", {}).get("semantic_category"),
                    "content": []
                }
            elif current_section:
                current_section["content"].append(block)
            else:
                # Content before first section
                if not sections:
                    sections.append({
                        "type": "section", 
                        "header": "Document Start",
                        "level": 0,
                        "content": []
                    })
                sections[0]["content"].append(block)
        
        # Add final section
        if current_section:
            sections.append(current_section)
        
        return {
            "sections": sections,
            "total_sections": len(sections),
            "hierarchy": self._extract_hierarchy(sections)
        }
    
    def _extract_hierarchy(self, sections: List[Dict]) -> List[Dict]:
        """Extract section hierarchy for visualization."""
        hierarchy = []
        for section in sections:
            hierarchy.append({
                "header": section["header"],
                "level": section["level"],
                "content_blocks": len(section.get("content", []))
            })
        return hierarchy


# Initialize orchestrator
orchestrator = PDFSectionOrchestrator()


@app.command()
def validate(
    text: str = typer.Argument(..., help="Text to validate as header"),
    doc_type: str = typer.Option("academic_paper", "--doc-type", "-t", help="Document type")
):
    """Validate if text is a section header."""
    async def run():
        result = await orchestrator.validate_header(
            text=text,
            context={"doc_type": doc_type}
        )
        
        # Display result
        table = Table(title="Header Validation Result")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Is Header", str(result.get("is_header", False)))
        table.add_row("Confidence", f"{result.get('confidence', 0):.2%}")
        
        if result.get("is_header"):
            table.add_row("Header Level", str(result.get("header_level", "N/A")))
            table.add_row("Semantic Category", result.get("semantic_category", "N/A"))
        
        table.add_row("Reasoning", result.get("reasoning", "N/A"))
        
        console.print(table)
    
    asyncio.run(run())


@app.command("find-splits")
def find_splits(
    blocks_file: Path = typer.Argument(..., help="JSON file containing blocks")
):
    """Find headers that were split across blocks."""
    if not blocks_file.exists():
        console.print(f"[red]Error: File not found: {blocks_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        splits = await orchestrator.find_split_headers(blocks_file)
        
        if not splits:
            console.print("[green]No split headers detected![/green]")
            return
        
        table = Table(title=f"Split Headers Found ({len(splits)})")
        table.add_column("Index", style="cyan")
        table.add_column("First Part", style="yellow")
        table.add_column("Second Part", style="yellow")
        table.add_column("Combined", style="green")
        table.add_column("Confidence", style="magenta")
        
        for split in splits:
            table.add_row(
                f"{split['first_index']}-{split['second_index']}",
                split.get("first_text", ""),
                split.get("second_text", ""),
                split["combined_text"],
                f"{split['confidence']:.2%}"
            )
        
        console.print(table)
    
    asyncio.run(run())


@app.command("build-structure")
def build_structure(
    blocks_file: Path = typer.Argument(..., help="JSON file containing blocks"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for structure")
):
    """Build document structure from validated headers."""
    if not blocks_file.exists():
        console.print(f"[red]Error: File not found: {blocks_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        structure = await orchestrator.build_structure(blocks_file, output)
        
        # Display hierarchy
        console.print("\n[bold cyan]Document Structure:[/bold cyan]")
        
        for i, section in enumerate(structure["hierarchy"]):
            indent = "  " * section["level"]
            console.print(f"{indent}{i+1}. {section['header']} ({section['content_blocks']} blocks)")
        
        console.print(f"\n[green]Total sections: {structure['total_sections']}[/green]")
    
    asyncio.run(run())


@app.command("validate-gold")
def validate_gold(
    result_file: Path = typer.Argument(..., help="Extraction result JSON"),
    gold_file: Path = typer.Argument(..., help="Gold standard JSON")
):
    """Validate section structure against gold standard."""
    if not result_file.exists() or not gold_file.exists():
        console.print("[red]Error: Files not found[/red]")
        raise typer.Exit(1)
    
    async def run():
        with open(result_file) as f:
            result = json.load(f)
        
        with open(gold_file) as f:
            gold = json.load(f)
        
        validation = await orchestrator.validator.validate_against_gold_standard(
            result=result,
            gold_standard=gold
        )
        
        table = Table(title="Gold Standard Validation")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green" if validation["valid"] else "red")
        
        table.add_row("Valid", " PASS" if validation["valid"] else " FAIL")
        table.add_row("Score", f"{validation['score']:.2%}")
        
        details = validation.get("details", {})
        table.add_row("Correct Headers", str(details.get("correct", 0)))
        table.add_row("Total Headers", str(details.get("total", 0)))
        table.add_row("Missed Headers", str(details.get("missed", 0)))
        
        console.print(table)
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate section validation capabilities."""
    logger.info("Testing section header validation...")
    
    # Test various headers
    test_cases = [
        ("1. INTRODUCTION", True),
        ("As mentioned earlier,", False),
        ("TABLE I", True),
        ("For any configuration,", False),
        ("2.3 Implementation Details", True)
    ]
    
    for text, expected in test_cases:
        result = await orchestrator.validate_header(text)
        is_header = result.get("is_header", False)
        status = "" if is_header == expected else ""
        logger.info(f"{status} '{text}' -> Header: {is_header} ({result.get('confidence', 0):.2%})")
    
    # Test structure building
    logger.info("\nTesting structure building...")
    
    mock_blocks = [
        {"type": "SectionHeader", "text": "1. INTRODUCTION"},
        {"type": "Text", "text": "Introduction paragraph..."},
        {"type": "SectionHeader", "text": "2. METHODOLOGY"},
        {"type": "Text", "text": "Our approach..."},
        {"type": "SectionHeader", "text": "For testing,"},  # Should be invalidated
        {"type": "Text", "text": "continuation text"}
    ]
    
    # Save mock blocks
    mock_file = Path("/tmp/mock_blocks.json")
    with open(mock_file, 'w') as f:
        json.dump(mock_blocks, f)
    
    structure = await orchestrator.build_structure(mock_file)
    
    logger.info(f"\nBuilt structure with {structure['total_sections']} sections:")
    for section in structure["hierarchy"]:
        logger.info(f"  - {section['header']} (Level {section['level']})")


async def debug_function():
    """Debug edge cases in section validation."""
    logger.info("Testing edge cases...")
    
    # Edge case headers
    edge_cases = [
        "...",  # Too short
        "a. subsection",  # Lowercase start
        "ABSTRACT",  # All caps
        "References:",  # Ends with colon
        "3.1.2.4 Deep Subsection",  # Deep numbering
    ]
    
    for text in edge_cases:
        result = await orchestrator.validate_header(text)
        logger.info(f"\n'{text}':")
        logger.info(f"  Is Header: {result.get('is_header')}")
        logger.info(f"  Confidence: {result.get('confidence', 0):.2%}")
        logger.info(f"  Reasoning: {result.get('reasoning', 'N/A')}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()