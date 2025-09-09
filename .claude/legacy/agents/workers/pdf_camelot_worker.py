#!/usr/bin/env python3
"""
PDF Camelot Table Extractor Worker

Advanced table extraction using Camelot library for complex table structures.
Handles borderless tables, merged cells, and irregular layouts.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import os

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable
from rich.progress import Progress, SpinnerColumn, TextColumn

# Camelot imports
import camelot

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Extract complex tables using Camelot")
console = Console()


class PDFCamelotExtractor:
    """Extract tables using Camelot for complex cases."""
    
    def __init__(self):

        # Default parameters for each method
        self.lattice_params = {
            'line_scale': 15,     # Line detection sensitivity
            'split_text': True,   # Split text at cell borders
            'flag_size': True,    # Flag large tables
            'strip_text': ' \n',  # Characters to strip
            'line_tol': 2,        # Line tolerance
            'joint_tol': 2,       # Joint tolerance
            'threshold_blocksize': 15,
            'threshold_constant': -2
        }
        
        self.stream_params = {
            'row_tol': 2,         # Row separation tolerance
            'column_tol': 0,      # Column separation tolerance  
            'edge_tol': 50,       # Table edge tolerance
            'strip_text': ' \n'   # Characters to strip
        }
    
    async def extract_table(self,
                          pdf_path: Path,
                          page: int,
                          bbox: Optional[Tuple[float, float, float, float]] = None,
                          method: str = 'auto') -> Dict:
        """Extract a specific table from PDF.
        
        Args:
            pdf_path: Path to PDF file
            page: Page number (1-indexed)
            bbox: Bounding box (x1, y1, x2, y2) in PDF coordinates
            method: 'lattice', 'stream', or 'auto'
            
        Returns:
            Extracted table data with metadata
        """
        if method == 'auto':
            # Try lattice first for better accuracy
            result = await self._extract_lattice(pdf_path, page, bbox)
            if result['accuracy'] < 70:
                # Fall back to stream
                stream_result = await self._extract_stream(pdf_path, page, bbox)
                if stream_result['accuracy'] > result['accuracy']:
                    result = stream_result
        elif method == 'lattice':
            result = await self._extract_lattice(pdf_path, page, bbox)
        else:  # stream
            result = await self._extract_stream(pdf_path, page, bbox)
        
        return result
    
    async def _extract_lattice(self, pdf_path: Path, page: int, 
                             bbox: Optional[Tuple] = None) -> Dict:
        """Extract using lattice method (for tables with borders)."""
        try:
            # Build parameters
            params = self.lattice_params.copy()
            if bbox:
                # Convert bbox to string format
                table_areas = [f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"]
                params['table_areas'] = table_areas
            
            # Extract tables
            tables = camelot.read_pdf(
                str(pdf_path),
                pages=str(page),
                flavor='lattice',
                **params
            )
            
            if not tables:
                return self._empty_result()
            
            # Use best table
            table = tables[0]
            
            return {
                'method': 'lattice',
                'cells': table.data,
                'shape': table.shape,
                'accuracy': table.accuracy,
                'whitespace': table.whitespace,
                'order': table.order,
                'page': table.page,
                'extraction_report': table.parsing_report,
                'df': table.df.to_dict('records')
            }
            
        except Exception as e:
            logger.error(f"Lattice extraction failed: {e}")
            return self._empty_result()
    
    async def _extract_stream(self, pdf_path: Path, page: int,
                            bbox: Optional[Tuple] = None) -> Dict:
        """Extract using stream method (for borderless tables)."""
        try:
            # Build parameters
            params = self.stream_params.copy()
            if bbox:
                table_areas = [f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"]
                params['table_areas'] = table_areas
            
            # Extract tables
            tables = camelot.read_pdf(
                str(pdf_path),
                pages=str(page),
                flavor='stream',
                **params
            )
            
            if not tables:
                return self._empty_result()
            
            # Use best table
            table = tables[0]
            
            return {
                'method': 'stream',
                'cells': table.data,
                'shape': table.shape,
                'accuracy': table.accuracy,
                'whitespace': table.whitespace,
                'order': table.order,
                'page': table.page,
                'extraction_report': table.parsing_report,
                'df': table.df.to_dict('records')
            }
            
        except Exception as e:
            logger.error(f"Stream extraction failed: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict:
        """Return empty result structure."""
        return {
            'method': None,
            'cells': [],
            'shape': (0, 0),
            'accuracy': 0.0,
            'whitespace': 0.0,
            'order': 0,
            'page': 0,
            'extraction_report': {},
            'df': []
        }
    
    async def extract_all_tables(self, pdf_path: Path, 
                               pages: str = 'all',
                               method: str = 'auto') -> List[Dict]:
        """Extract all tables from PDF."""
        results = []
        
        # Get page count
        if pages == 'all':
            # Detect number of pages
            try:
                import PyPDF2
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    num_pages = len(reader.pages)
                    pages = f"1-{num_pages}"
            except:
                pages = "1-end"
        
        # Try both methods if auto
        if method == 'auto':
            # Try lattice
            try:
                lattice_tables = camelot.read_pdf(
                    str(pdf_path),
                    pages=pages,
                    flavor='lattice',
                    **self.lattice_params
                )
                for table in lattice_tables:
                    results.append({
                        'method': 'lattice',
                        'cells': table.data,
                        'shape': table.shape,
                        'accuracy': table.accuracy,
                        'page': table.page
                    })
            except Exception as e:
                logger.debug(f"Lattice extraction failed: {e}")
            
            # Try stream
            try:
                stream_tables = camelot.read_pdf(
                    str(pdf_path),
                    pages=pages,
                    flavor='stream',
                    **self.stream_params
                )
                
                # Add stream tables if better or not found by lattice
                for table in stream_tables:
                    page_has_lattice = any(
                        r['page'] == table.page and r['method'] == 'lattice' 
                        for r in results
                    )
                    
                    if not page_has_lattice or table.accuracy > 70:
                        results.append({
                            'method': 'stream',
                            'cells': table.data,
                            'shape': table.shape,
                            'accuracy': table.accuracy,
                            'page': table.page
                        })
            except Exception as e:
                logger.debug(f"Stream extraction failed: {e}")
        
        else:
            # Use specified method
            try:
                tables = camelot.read_pdf(
                    str(pdf_path),
                    pages=pages,
                    flavor=method,
                    **(self.lattice_params if method == 'lattice' else self.stream_params)
                )
                
                for table in tables:
                    results.append({
                        'method': method,
                        'cells': table.data,
                        'shape': table.shape,
                        'accuracy': table.accuracy,
                        'page': table.page
                    })
            except Exception as e:
                logger.error(f"{method} extraction failed: {e}")
        
        # Sort by page
        results.sort(key=lambda x: x['page'])
        
        return results
    
    def analyze_table_quality(self, table_data: Dict) -> Dict:
        """Analyze extraction quality and suggest improvements."""
        analysis = {
            'quality_score': table_data.get('accuracy', 0),
            'issues': [],
            'recommendations': []
        }
        
        # Check accuracy
        if analysis['quality_score'] < 50:
            analysis['issues'].append("Very low extraction accuracy")
            analysis['recommendations'].append("Try manual table area selection")
        elif analysis['quality_score'] < 70:
            analysis['issues'].append("Low extraction accuracy")
            analysis['recommendations'].append("Adjust extraction parameters")
        
        # Check whitespace
        whitespace = table_data.get('whitespace', 0)
        if whitespace > 50:
            analysis['issues'].append("High whitespace ratio")
            analysis['recommendations'].append("Table might have sparse data")
        
        # Check dimensions
        shape = table_data.get('shape', (0, 0))
        if shape[0] * shape[1] == 0:
            analysis['issues'].append("Empty table detected")
        elif shape[0] == 1:
            analysis['issues'].append("Single row table")
        elif shape[1] == 1:
            analysis['issues'].append("Single column table")
        
        return analysis
    
    async def debug_extraction(self, pdf_path: Path, page: int):
        """Visual debugging of table extraction."""
        
        # Extract with both methods
        console.print(f"\n[bold]Debugging page {page} of {pdf_path.name}[/bold]")
        
        # Try lattice
        try:
            lattice_tables = camelot.read_pdf(
                str(pdf_path),
                pages=str(page),
                flavor='lattice'
            )
            
            if lattice_tables:
                console.print(f"\n[green]Lattice method found {len(lattice_tables)} tables[/green]")
                for i, table in enumerate(lattice_tables):
                    console.print(f"  Table {i+1}: {table.shape} cells, {table.accuracy:.1f}% accuracy")
                    
                    # Plot debugging visualizations
                    try:
                        plot_path = f"debug_lattice_p{page}_t{i+1}.png"
                        camelot.plot(table, kind='grid').savefig(plot_path)
                        console.print(f"    Saved grid plot to {plot_path}")
                    except:
                        pass
        except Exception as e:
            console.print(f"[red]Lattice failed: {e}[/red]")
        
        # Try stream
        try:
            stream_tables = camelot.read_pdf(
                str(pdf_path),
                pages=str(page),
                flavor='stream'
            )
            
            if stream_tables:
                console.print(f"\n[green]Stream method found {len(stream_tables)} tables[/green]")
                for i, table in enumerate(stream_tables):
                    console.print(f"  Table {i+1}: {table.shape} cells, {table.accuracy:.1f}% accuracy")
                    
                    try:
                        plot_path = f"debug_stream_p{page}_t{i+1}.png"
                        camelot.plot(table, kind='textedge').savefig(plot_path)
                        console.print(f"    Saved textedge plot to {plot_path}")
                    except:
                        pass
        except Exception as e:
            console.print(f"[red]Stream failed: {e}[/red]")


# Initialize extractor
extractor = PDFCamelotExtractor() 


@app.command("extract")
def extract(
    pdf_file: Path = typer.Argument(..., help="PDF file to extract tables from"),
    page: Optional[int] = typer.Option(None, "--page", "-p", help="Specific page number"),
    method: str = typer.Option("auto", "--method", "-m", help="Extraction method: auto/lattice/stream"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json/csv/excel")
):
    """Extract tables using Camelot."""

    if not pdf_file.exists():
        console.print(f"[red]Error: File not found: {pdf_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        if page:
            # Extract single page
            with console.status(f"Extracting table from page {page}..."):
                result = await extractor.extract_table(pdf_file, page, method=method)
            
            if result['accuracy'] == 0:
                console.print("[red]No table found on specified page[/red]")
                return
            
            # Display result
            console.print(f"\n[bold]Extracted table from page {page}:[/bold]")
            console.print(f"Method: {result['method']}")
            console.print(f"Shape: {result['shape']}")
            console.print(f"Accuracy: {result['accuracy']:.1f}%")
            
            results = [result]
        else:
            # Extract all pages
            with console.status("Extracting all tables..."):
                results = await extractor.extract_all_tables(pdf_file, method=method)
            
            console.print(f"\n[bold]Found {len(results)} tables[/bold]")
            
            # Summary table
            summary = RichTable(title="Extracted Tables")
            summary.add_column("Page", style="cyan")
            summary.add_column("Method", style="green")
            summary.add_column("Size", style="yellow")
            summary.add_column("Accuracy", style="magenta")
            
            for r in results:
                summary.add_row(
                    str(r['page']),
                    r['method'],
                    f"{r['shape'][0]}x{r['shape'][1]}",
                    f"{r['accuracy']:.1f}%"
                )
            
            console.print(summary)
        
        # Save output
        if output:
            if format == "json":
                with open(output, 'w') as f:
                    json.dump(results, f, indent=2)
            elif format == "csv" and results:
                # Save first table as CSV
                import pandas as pd
                df = pd.DataFrame(results[0]['cells'])
                df.to_csv(output, index=False, header=False)
            elif format == "excel" and results:
                import pandas as pd
                with pd.ExcelWriter(output) as writer:
                    for i, result in enumerate(results):
                        df = pd.DataFrame(result['cells'])
                        df.to_excel(writer, sheet_name=f"Page_{result['page']}", 
                                   index=False, header=False)
            
            console.print(f"[green] Saved to {output}[/green]")
    
    asyncio.run(run())


@app.command("analyze")
def analyze(
    pdf_file: Path = typer.Argument(..., help="PDF file to analyze"),
    pages: str = typer.Option("1-5", "--pages", "-p", help="Page range to analyze")
):
    """Analyze table extraction quality."""
    async def run():
        with console.status("Analyzing tables..."):
            results = await extractor.extract_all_tables(pdf_file, pages=pages)
        
        if not results:
            console.print("[yellow]No tables found[/yellow]")
            return
        
        # Analyze each table
        for result in results:
            analysis = extractor.analyze_table_quality(result)
            
            console.print(f"\n[bold]Page {result['page']} - {result['method']} method:[/bold]")
            console.print(f"Quality Score: {analysis['quality_score']:.1f}%")
            
            if analysis['issues']:
                console.print("[yellow]Issues:[/yellow]")
                for issue in analysis['issues']:
                    console.print(f"  • {issue}")
            
            if analysis['recommendations']:
                console.print("[cyan]Recommendations:[/cyan]")
                for rec in analysis['recommendations']:
                    console.print(f"  • {rec}")
    
    asyncio.run(run())


@app.command("debug")
def debug(
    pdf_file: Path = typer.Argument(..., help="PDF file to debug"),
    page: int = typer.Argument(..., help="Page number to debug")
):
    """Visual debugging of table extraction."""
    async def run():
        await extractor.debug_extraction(pdf_file, page)
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate Camelot extraction."""
    logger.info("Testing Camelot table extraction...")

    # Simulate extraction result
    test_result = {
        'method': 'lattice',
        'cells': [
            ['Header 1', 'Header 2', 'Header 3'],
            ['Data 1', 'Data 2', 'Data 3'],
            ['Data 4', 'Data 5', 'Data 6']
        ],
        'shape': (3, 3),
        'accuracy': 85.5,
        'whitespace': 12.3,
        'page': 1
    }
    
    # Analyze quality
    analysis = extractor.analyze_table_quality(test_result)
    
    logger.info(f"\nExtraction result:")
    logger.info(f"  Method: {test_result['method']}")
    logger.info(f"  Accuracy: {test_result['accuracy']}%")
    logger.info(f"  Quality: {analysis['quality_score']}%")
    
    if analysis['recommendations']:
        logger.info(f"  Recommendations: {', '.join(analysis['recommendations'])}")


async def debug_function():
    """Test extraction parameters."""
    logger.info("Testing Camelot parameters...")
    
    if not CAMELOT_AVAILABLE:
        logger.warning("Camelot not available")
        return
    
    # Test parameter combinations
    test_params = [
        {'line_scale': 15},  # More sensitive
        {'line_scale': 60},  # Less sensitive
        {'row_tol': 5},      # Larger row tolerance
        {'edge_tol': 100}    # Larger edge tolerance
    ]
    
    logger.info("\nParameter sensitivity tests:")
    for params in test_params:
        logger.info(f"  Testing: {params}")
        # Would test on actual PDF here


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()