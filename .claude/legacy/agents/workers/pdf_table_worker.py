#!/usr/bin/env python3
"""
PDF Table Analysis Worker

Provides deep semantic understanding of table structures using Claude.
Goes beyond cell extraction to understand relationships, headers, and data meaning.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import os

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable
from anthropic import AsyncAnthropic
import pandas as pd

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Semantic table analysis for PDF extraction")
console = Console()


class PDFTableAnalyzer:
    """Analyzes table structures using Claude's understanding."""
    
    def __init__(self):
        # Initialize Claude client
        api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("CLAUDE_API_KEY or ANTHROPIC_API_KEY environment variable required")
        
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-3-haiku-20240307"
        
        # Cache for similar tables
        self.cache = {}
        
    async def analyze_table(self,
                          cells: List[List[str]],
                          caption: Optional[str] = None,
                          context: Optional[Dict] = None) -> Dict:
        """Analyze table structure and extract semantic meaning.
        
        Args:
            cells: 2D array of cell contents
            caption: Table caption if available
            context: Document context (section, type, etc.)
            
        Returns:
            Analysis result with structure and meaning
        """
        # Check cache
        cache_key = f"{str(cells)}:{caption}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Build prompt
        prompt = self._build_analysis_prompt(cells, caption, context)
        
        try:
            # Call Claude
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Parse response
            result = self._parse_claude_response(response.content[0].text)
            
            # Add extracted data
            result["cells"] = cells
            result["caption"] = caption
            result["extracted_data"] = self._extract_structured_data(cells, result)
            
            # Cache result
            self.cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return self._heuristic_analysis(cells, caption)
    
    def _build_analysis_prompt(self, 
                             cells: List[List[str]], 
                             caption: Optional[str],
                             context: Optional[Dict]) -> str:
        """Build prompt for table analysis."""
        
        # Convert cells to readable format
        table_text = self._cells_to_text(cells)
        
        # Context info
        context_info = ""
        if context:
            if "section" in context:
                context_info += f"\nCurrent section: {context['section']}"
            if "doc_type" in context:
                context_info += f"\nDocument type: {context['doc_type']}"
        
        prompt = f"""Analyze this table extracted from a PDF document.

Table caption: {caption or "None"}
{context_info}

Table content:
{table_text}

Analyze this table and provide a JSON response with:
1. "is_valid_table": true/false - is this actually a table (not just formatted text)?
2. "confidence": 0.0 to 1.0
3. "table_type": Classification (data_table, comparison, matrix, schedule, etc.)
4. "headers": {{
     "column_headers": [list of column headers if identified],
     "row_headers": [list of row headers if applicable]
   }}
5. "structure_type": "simple", "nested", or "multi_header"
6. "key_insights": [list of 2-3 important data points or relationships]
7. "data_types": {{column_name: data_type}} for each column
8. "interpretation": Brief description of what the table shows
9. "quality_issues": [list of any problems like missing data, alignment issues]

Consider:
- Tables in academic papers often show experimental results
- Financial tables have specific patterns (currency, percentages)
- Some "tables" are actually formatted lists or equations
- Headers might be in first row, first column, or both

Respond with valid JSON only."""

        return prompt
    
    def _cells_to_text(self, cells: List[List[str]]) -> str:
        """Convert cells to readable text format."""
        if not cells:
            return "Empty table"
        
        # Simple text representation
        lines = []
        for row in cells:
            if isinstance(row, list):
                lines.append(" | ".join(str(cell) for cell in row))
        
        return "\n".join(lines)
    
    def _parse_claude_response(self, response: str) -> Dict:
        """Parse Claude's response."""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response)
            
            # Set defaults
            result.setdefault("is_valid_table", True)
            result.setdefault("confidence", 0.8)
            result.setdefault("table_type", "data_table")
            result.setdefault("headers", {"column_headers": [], "row_headers": []})
            result.setdefault("structure_type", "simple")
            result.setdefault("key_insights", [])
            result.setdefault("data_types", {})
            result.setdefault("interpretation", "Table analysis")
            result.setdefault("quality_issues", [])
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse Claude response: {e}")
            return self._default_result()
    
    def _default_result(self) -> Dict:
        """Default result when parsing fails."""
        return {
            "is_valid_table": True,
            "confidence": 0.5,
            "table_type": "data_table",
            "headers": {"column_headers": [], "row_headers": []},
            "structure_type": "simple",
            "key_insights": [],
            "data_types": {},
            "interpretation": "Unable to analyze",
            "quality_issues": ["Analysis failed"]
        }
    
    def _heuristic_analysis(self, cells: List[List[str]], caption: Optional[str]) -> Dict:
        """Fallback heuristic analysis."""
        if not cells:
            return self._default_result()
        
        result = self._default_result()
        
        # Simple heuristics
        num_rows = len(cells)
        num_cols = len(cells[0]) if cells else 0
        
        # Guess headers
        if num_rows > 0 and cells[0]:
            # First row might be headers
            first_row = cells[0]
            if all(isinstance(cell, str) and len(cell) < 50 for cell in first_row):
                result["headers"]["column_headers"] = first_row
        
        # Table type based on size
        if num_rows * num_cols < 10:
            result["table_type"] = "summary"
        elif num_cols == 2:
            result["table_type"] = "key_value"
        elif num_rows > 10:
            result["table_type"] = "data_table"
        
        result["interpretation"] = f"Table with {num_rows} rows and {num_cols} columns"
        
        return result
    
    def _extract_structured_data(self, cells: List[List[str]], analysis: Dict) -> List[Dict]:
        """Extract structured data based on analysis."""
        if not cells or not analysis.get("is_valid_table"):
            return []
        
        headers = analysis.get("headers", {})
        col_headers = headers.get("column_headers", [])
        
        # Skip header row if identified
        data_start = 1 if col_headers and len(cells) > 1 else 0
        
        structured = []
        for row_idx in range(data_start, len(cells)):
            if row_idx >= len(cells):
                break
                
            row = cells[row_idx]
            row_data = {}
            
            for col_idx, value in enumerate(row):
                # Use header as key if available
                if col_idx < len(col_headers):
                    key = col_headers[col_idx]
                else:
                    key = f"column_{col_idx}"
                
                row_data[key] = value
            
            if row_data:
                structured.append(row_data)
        
        return structured
    
    async def find_caption(self, 
                         table_index: int,
                         blocks: List[Dict]) -> Optional[str]:
        """Find caption for a table from surrounding blocks."""
        # Look for caption patterns before and after
        search_range = 3  # Look 3 blocks before/after
        
        for offset in range(-search_range, search_range + 1):
            if offset == 0:
                continue
                
            idx = table_index + offset
            if 0 <= idx < len(blocks):
                block = blocks[idx]
                text = block.get("text", "").strip()
                
                # Caption patterns
                if any(pattern in text.upper() for pattern in ["TABLE", "FIGURE", "EXHIBIT"]):
                    if any(char.isdigit() for char in text):  # Has a number
                        return text
        
        return None
    
    async def validate_extraction(self, 
                                extracted_table: Dict,
                                gold_standard: Dict) -> Dict:
        """Validate extracted table against gold standard."""
        # Compare structure
        extracted_rows = len(extracted_table.get("cells", []))
        gold_rows = len(gold_standard.get("cells", []))
        
        extracted_cols = len(extracted_table.get("cells", [[]])[0]) if extracted_table.get("cells") else 0
        gold_cols = len(gold_standard.get("cells", [[]])[0]) if gold_standard.get("cells") else 0
        
        structure_match = (extracted_rows == gold_rows and extracted_cols == gold_cols)
        
        # Compare headers
        extracted_headers = extracted_table.get("headers", {}).get("column_headers", [])
        gold_headers = gold_standard.get("headers", {}).get("column_headers", [])
        
        header_match = extracted_headers == gold_headers
        
        # Calculate score
        score = 0.0
        if structure_match:
            score += 0.5
        if header_match:
            score += 0.3
        
        # Content similarity would add remaining 0.2
        
        return {
            "valid": score >= 0.8,
            "score": score,
            "structure_match": structure_match,
            "header_match": header_match,
            "details": {
                "extracted_shape": f"{extracted_rows}x{extracted_cols}",
                "gold_shape": f"{gold_rows}x{gold_cols}"
            }
        }


# Initialize analyzer
analyzer = PDFTableAnalyzer()


@app.command("analyze")
def analyze(
    table_file: Path = typer.Argument(..., help="JSON file containing table cells"),
    caption: Optional[str] = typer.Option(None, "--caption", "-c", help="Table caption"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file")
):
    """Analyze a table's structure and meaning."""
    if not table_file.exists():
        console.print(f"[red]Error: File not found: {table_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load table
        with open(table_file) as f:
            data = json.load(f)
        
        # Extract cells
        if isinstance(data, list):
            cells = data
        else:
            cells = data.get("cells", data.get("data", []))
        
        if not cells:
            console.print("[red]No table data found[/red]")
            return
        
        # Analyze
        with console.status("Analyzing table with Claude..."):
            result = await analyzer.analyze_table(cells, caption)
        
        # Display results
        display_table = RichTable(title="Table Analysis")
        display_table.add_column("Property", style="cyan")
        display_table.add_column("Value", style="green")
        
        display_table.add_row("Valid Table", str(result["is_valid_table"]))
        display_table.add_row("Confidence", f"{result['confidence']:.2%}")
        display_table.add_row("Table Type", result["table_type"])
        display_table.add_row("Structure", result["structure_type"])
        
        if result["headers"]["column_headers"]:
            display_table.add_row("Column Headers", ", ".join(result["headers"]["column_headers"]))
        
        console.print(display_table)
        
        if result["key_insights"]:
            console.print("\n[bold]Key Insights:[/bold]")
            for insight in result["key_insights"]:
                console.print(f"  " {insight}")
        
        console.print(f"\n[bold]Interpretation:[/bold] {result['interpretation']}")
        
        if result["quality_issues"]:
            console.print("\n[yellow]Quality Issues:[/yellow]")
            for issue in result["quality_issues"]:
                console.print(f"    {issue}")
        
        # Save if requested
        if output:
            with open(output, 'w') as f:
                json.dump(result, f, indent=2)
            console.print(f"\n[green] Saved analysis to {output}[/green]")
    
    asyncio.run(run())


@app.command("extract-data")
def extract_data(
    analysis_file: Path = typer.Argument(..., help="Table analysis JSON file"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json/csv)")
):
    """Extract structured data from analyzed table."""
    if not analysis_file.exists():
        console.print(f"[red]Error: File not found: {analysis_file}[/red]")
        raise typer.Exit(1)
    
    with open(analysis_file) as f:
        analysis = json.load(f)
    
    data = analysis.get("extracted_data", [])
    
    if not data:
        console.print("[yellow]No structured data found[/yellow]")
        return
    
    if format == "csv":
        # Convert to DataFrame and display
        df = pd.DataFrame(data)
        console.print(df.to_string())
        
        # Save option
        save = typer.confirm("Save as CSV?")
        if save:
            output_path = analysis_file.with_suffix(".csv")
            df.to_csv(output_path, index=False)
            console.print(f"[green] Saved to {output_path}[/green]")
    else:
        # Display JSON
        console.print(json.dumps(data, indent=2))


@app.command("batch-analyze")
def batch_analyze(
    blocks_file: Path = typer.Argument(..., help="JSON file with all blocks"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory")
):
    """Analyze all tables in a document."""
    if not blocks_file.exists():
        console.print(f"[red]Error: File not found: {blocks_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load blocks
        with open(blocks_file) as f:
            data = json.load(f)
        
        blocks = data if isinstance(data, list) else data.get("blocks", [])
        
        # Find tables
        tables = [(i, b) for i, b in enumerate(blocks) if b.get("type") == "Table"]
        
        console.print(f"Found [cyan]{len(tables)}[/cyan] tables to analyze")
        
        results = []
        for idx, (block_idx, table_block) in enumerate(tables):
            # Find caption
            caption = await analyzer.find_caption(block_idx, blocks)
            
            # Get cells
            cells = table_block.get("cells", [])
            if not cells and "text" in table_block:
                # Try to parse from text
                lines = table_block["text"].split("\n")
                cells = [line.split() for line in lines if line.strip()]
            
            if cells:
                with console.status(f"Analyzing table {idx + 1}/{len(tables)}..."):
                    result = await analyzer.analyze_table(cells, caption)
                
                result["block_index"] = block_idx
                results.append(result)
                
                # Show summary
                console.print(f"[green][/green] Table {idx + 1}: {result['table_type']} "
                            f"({result['confidence']:.0%} confidence)")
        
        # Save results
        if output_dir:
            output_dir.mkdir(exist_ok=True)
            for i, result in enumerate(results):
                output_path = output_dir / f"table_{i+1}_analysis.json"
                with open(output_path, 'w') as f:
                    json.dump(result, f, indent=2)
            
            console.print(f"\n[green] Saved {len(results)} analyses to {output_dir}[/green]")
        
        # Summary
        console.print("\n[bold]Summary:[/bold]")
        valid_tables = sum(1 for r in results if r["is_valid_table"])
        console.print(f"  Valid tables: {valid_tables}/{len(results)}")
        
        table_types = {}
        for r in results:
            t = r["table_type"]
            table_types[t] = table_types.get(t, 0) + 1
        
        console.print("  Types found:")
        for t, count in table_types.items():
            console.print(f"    - {t}: {count}")
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate table analysis capabilities."""
    logger.info("Testing table analysis...")
    
    # Example table from BHT PDF
    test_table = [
        ["Parameter", "Value", "Unit"],
        ["Frequency", "10", "GHz"],
        ["Power", "100", "W"],
        ["Efficiency", "85", "%"]
    ]
    
    result = await analyzer.analyze_table(
        cells=test_table,
        caption="TABLE I. System Parameters",
        context={"section": "Results", "doc_type": "technical_paper"}
    )
    
    logger.info("\nTable Analysis Result:")
    logger.info(f"Type: {result['table_type']}")
    logger.info(f"Confidence: {result['confidence']:.2%}")
    logger.info(f"Headers: {result['headers']['column_headers']}")
    logger.info(f"Interpretation: {result['interpretation']}")
    
    # Extract data
    data = result["extracted_data"]
    if data:
        logger.info("\nExtracted Data:")
        for row in data:
            logger.info(f"  {row}")


async def debug_function():
    """Test edge cases."""
    logger.info("Testing edge cases...")
    
    # Test 1: Not really a table
    fake_table = [
        ["This is just"],
        ["formatted text"],
        ["not a table"]
    ]
    
    result1 = await analyzer.analyze_table(fake_table)
    logger.info(f"\nFake table detected: {not result1['is_valid_table']}")
    
    # Test 2: Complex multi-header table
    complex_table = [
        ["", "2023", "2023", "2024", "2024"],
        ["", "Q1", "Q2", "Q1", "Q2"],
        ["Revenue", "100", "120", "130", "140"],
        ["Costs", "80", "90", "95", "100"]
    ]
    
    result2 = await analyzer.analyze_table(complex_table)
    logger.info(f"\nComplex table structure: {result2['structure_type']}")
    
    # Test 3: Table with quality issues
    bad_table = [
        ["Col1", "Col2", "Col3"],
        ["A", "B"],  # Missing column
        ["X", "Y", "Z", "Extra"],  # Extra column
    ]
    
    result3 = await analyzer.analyze_table(bad_table)
    logger.info(f"\nQuality issues detected: {len(result3['quality_issues'])}")
    for issue in result3["quality_issues"]:
        logger.info(f"  - {issue}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()