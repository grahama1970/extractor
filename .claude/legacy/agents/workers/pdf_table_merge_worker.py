#!/usr/bin/env python3
"""
PDF Table Merge Worker

Merges split tables across pages and columns into complete structures.
Handles complex table continuations and reconstructs full tables.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
import re

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Merge split tables across pages into complete structures")
console = Console()


class PDFTableMerger:
    """Merges split tables into complete structures."""
    
    def __init__(self):
        # Continuation patterns
        self.continuation_patterns = [
            r"continued on next page",
            r"continued from previous page",
            r"table \d+ \(continued\)",
            r"\(cont'd\)",
            r"\.\.\.continued",
            r"continued",
            r"continued\s*&",
            r"&\s*continued",
            r"\.\.\.$",  # Ellipsis at end
            r"^\.\.\."   # Ellipsis at start
        ]
        
        # Header patterns
        self.header_patterns = [
            r"^(table|exhibit|figure)\s+\d+",
            r"^\d+\.\d+\s+\w+",  # Numbered sections
        ]
        
        # Statistics
        self.stats = {
            "tables_found": 0,
            "fragments_detected": 0,
            "successful_merges": 0,
            "failed_merges": 0
        }
    
    def detect_continuation(self, table_block: Dict) -> Dict:
        """Detect if a table is a continuation or has a continuation."""
        result = {
            "is_continuation": False,
            "has_continuation": False,
            "continuation_type": None,
            "confidence": 0.0
        }
        
        text = table_block.get("text", "").lower()
        caption = table_block.get("caption", "").lower()
        
        # Check for continuation markers
        for pattern in self.continuation_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                result["has_continuation"] = True
                result["continuation_type"] = "explicit"
                result["confidence"] = 0.95
                break
            if re.search(pattern, caption, re.IGNORECASE):
                result["is_continuation"] = True
                result["continuation_type"] = "explicit"
                result["confidence"] = 0.95
                break
        
        # Check for implicit continuation (no header on this table)
        if not result["is_continuation"] and table_block.get("missing_header"):
            result["is_continuation"] = True
            result["continuation_type"] = "implicit"
            result["confidence"] = 0.7
        
        # Check for ellipsis patterns
        if "..." in text[-10:] or "&" in text[-10:]:
            result["has_continuation"] = True
            result["continuation_type"] = "ellipsis"
            result["confidence"] = max(result["confidence"], 0.8)
        
        return result
    
    def match_table_structure(self, table1: Dict, table2: Dict) -> float:
        """Calculate similarity between two table structures."""
        score = 0.0
        
        # Get table dimensions
        cols1 = self._get_column_count(table1)
        cols2 = self._get_column_count(table2)
        
        # Column count match
        if cols1 == cols2:
            score += 0.4
        elif abs(cols1 - cols2) <= 1:  # Allow 1 column difference
            score += 0.2
        
        # Header similarity
        headers1 = self._extract_headers(table1)
        headers2 = self._extract_headers(table2)
        
        if headers1 and headers2:
            header_match = self._calculate_header_similarity(headers1, headers2)
            score += header_match * 0.3
        
        # Data pattern similarity
        pattern_match = self._compare_data_patterns(table1, table2)
        score += pattern_match * 0.3
        
        return score
    
    def _get_column_count(self, table: Dict) -> int:
        """Get number of columns in table."""
        if "cells" in table and table["cells"]:
            # Assume first row indicates column count
            return len(table["cells"][0]) if isinstance(table["cells"][0], list) else 1
        elif "columns" in table:
            return table["columns"]
        else:
            # Try to infer from text
            text = table.get("text", "")
            # Count pipes or tabs in first line
            first_line = text.split('\n')[0] if text else ""
            pipes = first_line.count('|')
            tabs = first_line.count('\t')
            return max(pipes - 1, tabs + 1, 1)
    
    def _extract_headers(self, table: Dict) -> List[str]:
        """Extract header row from table."""
        if "headers" in table:
            return table["headers"]
        
        if "cells" in table and table["cells"]:
            # First row might be headers
            first_row = table["cells"][0]
            if isinstance(first_row, list):
                return [str(cell) for cell in first_row]
        
        # Try to extract from text
        text = table.get("text", "")
        lines = text.split('\n')
        if lines:
            # Look for header-like first line
            first_line = lines[0]
            if '|' in first_line:
                headers = [h.strip() for h in first_line.split('|') if h.strip()]
                return headers
        
        return []
    
    def _calculate_header_similarity(self, headers1: List[str], headers2: List[str]) -> float:
        """Calculate similarity between two header lists."""
        if not headers1 or not headers2:
            return 0.0
        
        # Normalize headers
        h1_norm = [h.lower().strip() for h in headers1]
        h2_norm = [h.lower().strip() for h in headers2]
        
        # Calculate overlap
        matches = sum(1 for h in h1_norm if h in h2_norm)
        total = max(len(h1_norm), len(h2_norm))
        
        return matches / total if total > 0 else 0.0
    
    def _compare_data_patterns(self, table1: Dict, table2: Dict) -> float:
        """Compare data patterns between tables."""
        # This is simplified - in production would analyze actual data types
        # and patterns (numeric, text, dates, etc.)
        
        # For now, check if both have similar text patterns
        text1 = table1.get("text", "")
        text2 = table2.get("text", "")
        
        # Check for similar patterns
        has_numbers1 = bool(re.search(r'\d+', text1))
        has_numbers2 = bool(re.search(r'\d+', text2))
        
        has_currency1 = bool(re.search(r'[$£€]', text1))
        has_currency2 = bool(re.search(r'[$£€]', text2))
        
        score = 0.0
        if has_numbers1 == has_numbers2:
            score += 0.5
        if has_currency1 == has_currency2:
            score += 0.5
        
        return score
    
    async def find_table_fragments(self, blocks: List[Dict]) -> List[List[int]]:
        """Find groups of table fragments that should be merged."""
        fragments = []
        processed = set()
        
        for i, block in enumerate(blocks):
            if i in processed or block.get("type") != "Table":
                continue
            
            # Check if this table has continuation
            continuation = self.detect_continuation(block)
            
            if continuation["has_continuation"] or continuation["is_continuation"]:
                # Find related fragments
                fragment_group = [i]
                processed.add(i)
                
                # Look forward for continuations
                if continuation["has_continuation"]:
                    for j in range(i + 1, min(i + 10, len(blocks))):  # Check next 10 blocks
                        if blocks[j].get("type") == "Table":
                            match_score = self.match_table_structure(block, blocks[j])
                            if match_score > 0.6:
                                fragment_group.append(j)
                                processed.add(j)
                                # Check if this also continues
                                next_cont = self.detect_continuation(blocks[j])
                                if not next_cont["has_continuation"]:
                                    break
                
                # Look backward if this is a continuation
                if continuation["is_continuation"]:
                    for j in range(i - 1, max(i - 10, -1), -1):  # Check previous 10 blocks
                        if blocks[j].get("type") == "Table":
                            match_score = self.match_table_structure(blocks[j], block)
                            if match_score > 0.6:
                                fragment_group.insert(0, j)
                                processed.add(j)
                
                if len(fragment_group) > 1:
                    fragments.append(sorted(fragment_group))
                    self.stats["fragments_detected"] += len(fragment_group)
        
        return fragments
    
    async def merge_table_fragments(self, 
                                  blocks: List[Dict], 
                                  fragment_indices: List[int]) -> Dict:
        """Merge table fragments into a single table."""
        if not fragment_indices:
            return {}
        
        # Get fragments
        fragments = [blocks[i] for i in fragment_indices]
        
        # Start with first fragment as base
        merged = fragments[0].copy()
        merged["merged_from"] = fragment_indices
        merged["fragment_count"] = len(fragments)
        
        # Merge cells
        all_cells = []
        for frag in fragments:
            if "cells" in frag:
                # Skip duplicate headers in continuations
                cells = frag["cells"]
                if all_cells and self._is_header_row(cells[0]):
                    cells = cells[1:]  # Skip header
                all_cells.extend(cells)
        
        merged["cells"] = all_cells
        
        # Merge text
        all_text = []
        for i, frag in enumerate(fragments):
            text = frag.get("text", "")
            # Remove continuation markers
            for pattern in self.continuation_patterns:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            all_text.append(text.strip())
        
        merged["text"] = "\n".join(all_text)
        
        # Update metadata
        merged["page_range"] = [
            min(f.get("page", 0) for f in fragments),
            max(f.get("page", 0) for f in fragments)
        ]
        
        # Calculate merge confidence
        total_score = 0.0
        for i in range(len(fragments) - 1):
            score = self.match_table_structure(fragments[i], fragments[i + 1])
            total_score += score
        
        merged["merge_confidence"] = total_score / (len(fragments) - 1) if len(fragments) > 1 else 1.0
        
        self.stats["successful_merges"] += 1
        
        return merged
    
    def _is_header_row(self, row: List) -> bool:
        """Check if a row is likely a header row."""
        if not row:
            return False
        
        # Headers are often short text
        text_cells = [str(cell) for cell in row if cell]
        if not text_cells:
            return False
        
        # Check if all cells are short and text-like
        all_short = all(len(cell) < 30 for cell in text_cells)
        no_numbers = not any(re.search(r'^\d+\.?\d*$', cell) for cell in text_cells)
        
        return all_short and no_numbers
    
    async def merge_all_tables(self, blocks: List[Dict]) -> List[Dict]:
        """Process all blocks and merge table fragments."""
        # Find fragments
        fragment_groups = await self.find_table_fragments(blocks)
        
        if not fragment_groups:
            logger.info("No table fragments found to merge")
            return blocks
        
        # Create mapping of indices to skip
        skip_indices = set()
        for group in fragment_groups:
            skip_indices.update(group[1:])  # Skip all but first
        
        # Build result with merged tables
        result = []
        merged_tables = {}
        
        # Merge fragments
        for group in fragment_groups:
            merged = await self.merge_table_fragments(blocks, group)
            merged_tables[group[0]] = merged
        
        # Build final block list
        for i, block in enumerate(blocks):
            if i in skip_indices:
                continue  # Skip fragments that were merged
            elif i in merged_tables:
                result.append(merged_tables[i])  # Add merged table
            else:
                result.append(block)  # Keep original block
        
        return result
    
    def generate_merge_report(self) -> Dict:
        """Generate report of merge operations."""
        return {
            "statistics": self.stats,
            "success_rate": (
                self.stats["successful_merges"] / 
                (self.stats["successful_merges"] + self.stats["failed_merges"])
                if (self.stats["successful_merges"] + self.stats["failed_merges"]) > 0
                else 0.0
            ),
            "timestamp": datetime.utcnow().isoformat()
        }


# Initialize merger
merger = PDFTableMerger()


@app.command("merge")
def merge(
    input_file: Path = typer.Argument(..., help="JSON file with document blocks"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be merged without merging")
):
    """Merge split tables in document blocks."""
    if not input_file.exists():
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load blocks
        with open(input_file) as f:
            data = json.load(f)
        
        blocks = data if isinstance(data, list) else data.get("blocks", [])
        
        # Reset stats
        merger.stats = {
            "tables_found": sum(1 for b in blocks if b.get("type") == "Table"),
            "fragments_detected": 0,
            "successful_merges": 0,
            "failed_merges": 0
        }
        
        console.print(f"Found [cyan]{merger.stats['tables_found']}[/cyan] tables to analyze...")
        
        if dry_run:
            # Just find fragments
            fragments = await merger.find_table_fragments(blocks)
            
            if fragments:
                console.print(f"\n[bold]Would merge {len(fragments)} table groups:[/bold]")
                for i, group in enumerate(fragments):
                    pages = [blocks[idx].get("page", "?") for idx in group]
                    console.print(f"  Group {i + 1}: {len(group)} fragments on pages {pages}")
            else:
                console.print("[yellow]No table fragments found to merge[/yellow]")
            return
        
        # Perform merging
        with console.status("Merging table fragments..."):
            merged_blocks = await merger.merge_all_tables(blocks)
        
        # Show results
        report = merger.generate_merge_report()
        
        table = RichTable(title="Merge Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Tables Found", str(report["statistics"]["tables_found"]))
        table.add_row("Fragments Detected", str(report["statistics"]["fragments_detected"]))
        table.add_row("Successful Merges", str(report["statistics"]["successful_merges"]))
        table.add_row("Success Rate", f"{report['success_rate']:.1%}")
        
        console.print(table)
        
        # Save output
        if output:
            output_data = {
                "blocks": merged_blocks,
                "merge_report": report,
                "original_block_count": len(blocks),
                "merged_block_count": len(merged_blocks)
            }
            
            with open(output, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            console.print(f"\n[green] Saved merged document to {output}[/green]")
            console.print(f"Blocks: {len(blocks)} � {len(merged_blocks)}")
    
    asyncio.run(run())


@app.command("analyze")
def analyze(
    input_file: Path = typer.Argument(..., help="JSON file with document blocks")
):
    """Analyze tables for potential merging."""
    if not input_file.exists():
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load blocks
        with open(input_file) as f:
            data = json.load(f)
        
        blocks = data if isinstance(data, list) else data.get("blocks", [])
        
        # Analyze each table
        tables = [(i, b) for i, b in enumerate(blocks) if b.get("type") == "Table"]
        
        console.print(f"Analyzing [cyan]{len(tables)}[/cyan] tables...\n")
        
        for idx, (block_idx, table) in enumerate(tables):
            continuation = merger.detect_continuation(table)
            
            panel_content = f"Block Index: {block_idx}\n"
            panel_content += f"Page: {table.get('page', '?')}\n"
            
            if continuation["is_continuation"] or continuation["has_continuation"]:
                panel_content += f"[yellow]Continuation Detected![/yellow]\n"
                panel_content += f"Type: {continuation['continuation_type']}\n"
                panel_content += f"Confidence: {continuation['confidence']:.2%}\n"
                
                if continuation["is_continuation"]:
                    panel_content += "� This is a continuation from previous table\n"
                if continuation["has_continuation"]:
                    panel_content += "� This table continues on next page\n"
            else:
                panel_content += "[green]Standalone table[/green]\n"
            
            # Show snippet
            text_snippet = table.get("text", "")[:100]
            if text_snippet:
                panel_content += f"\nSnippet: {text_snippet}..."
            
            console.print(Panel(panel_content, title=f"Table {idx + 1}"))
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate table merging capabilities."""
    logger.info("Testing table fragment merging...")
    
    # Create sample fragmented table
    test_blocks = [
        {
            "type": "Text",
            "text": "Results are shown below:",
            "page": 1
        },
        {
            "type": "Table",
            "text": "Year | Revenue | Profit\n2021 | $100M | $20M\n2022 | $150M | $30M\n...continued on next page",
            "cells": [
                ["Year", "Revenue", "Profit"],
                ["2021", "$100M", "$20M"],
                ["2022", "$150M", "$30M"]
            ],
            "page": 1
        },
        {
            "type": "Text", 
            "text": "Some intervening text",
            "page": 2
        },
        {
            "type": "Table",
            "text": "Year | Revenue | Profit\n2023 | $200M | $45M\n2024 | $250M | $60M",
            "cells": [
                ["Year", "Revenue", "Profit"],  # Repeated header
                ["2023", "$200M", "$45M"],
                ["2024", "$250M", "$60M"]
            ],
            "page": 2,
            "caption": "Table 1 (continued)"
        }
    ]
    
    # Find fragments
    fragments = await merger.find_table_fragments(test_blocks)
    logger.info(f"\nFound {len(fragments)} fragment groups")
    
    if fragments:
        # Merge first group
        merged = await merger.merge_table_fragments(test_blocks, fragments[0])
        
        logger.info(f"\nMerged table:")
        logger.info(f"  Pages: {merged['page_range']}")
        logger.info(f"  Rows: {len(merged.get('cells', []))}")
        logger.info(f"  Confidence: {merged['merge_confidence']:.2%}")


async def debug_function():
    """Test edge cases in table merging."""
    logger.info("Testing table merge edge cases...")
    
    # Test 1: Tables with different column counts
    table1 = {"type": "Table", "cells": [["A", "B", "C"]], "text": "A | B | C"}
    table2 = {"type": "Table", "cells": [["A", "B", "C", "D"]], "text": "A | B | C | D"}
    
    score = merger.match_table_structure(table1, table2)
    logger.info(f"\nDifferent columns score: {score:.2f}")
    
    # Test 2: Implicit continuation detection
    implicit_table = {
        "type": "Table",
        "text": "100 | Data | Value",
        "missing_header": True
    }
    
    cont = merger.detect_continuation(implicit_table)
    logger.info(f"\nImplicit continuation: {cont}")
    
    # Test 3: Complex continuation pattern
    complex_table = {
        "type": "Table",
        "text": "Data table contents",
        "caption": "Exhibit A-1 (cont'd from previous page)"
    }
    
    cont2 = merger.detect_continuation(complex_table)
    logger.info(f"\nComplex pattern: {cont2}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()