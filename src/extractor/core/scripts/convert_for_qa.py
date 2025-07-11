"""
Marker conversion script optimized for Q&A generation.
Module: convert_for_qa.py

This script converts PDFs with maximum accuracy, ensuring complete
corpus extraction for downstream Q&A generation.
"""

import json
from pathlib import Path
from typing import Optional
from enum import Enum

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from extractor.core.converters.pdf import PdfConverter
from extractor.core.config.qa_optimized import get_qa_optimized_config
from extractor.core.models import create_model_dict
from extractor.core.output import save_output


# Initialize rich console
console = Console()

# Create typer app
app = typer.Typer(
    name="marker-qa",
    help="Convert PDFs optimized for Q&A generation with complete corpus validation",
    add_completion=False,
)


class OutputFormat(str, Enum):
    """Supported output formats."""
    JSON = "json"
    MARKDOWN = "markdown"


def convert_for_qa(
    pdf_path: Path,
    output_dir: Path,
    output_format: OutputFormat = OutputFormat.JSON
) -> Path:
    """
    Convert PDF optimized for Q&A generation.
    
    Args:
        pdf_path: Path to input PDF
        output_dir: Directory for output
        output_format: Output format (json/markdown)
        
    Returns:
        Path to output file
    """
    logger.info(f"Converting {pdf_path} for Q&A generation")
    
    # Get Q&A-optimized configuration
    config = get_qa_optimized_config()
    
    # Create converter with enhanced configuration
    converter = PdfConverter(
        artifact_dict=create_model_dict(),
        config=config
    )
    
    # Convert document
    result = converter(str(pdf_path))
    
    # Save output with validation data
    output_path = output_dir / f"{pdf_path.stem}.{output_format.value}"
    
    if output_format == OutputFormat.JSON:
        # Include all validation data in JSON output
        output_data = {
            "document": result.document.to_dict(),
            "metadata": result.metadata,
            "validation": {
                "corpus_validation": result.document.metadata.get("corpus_validation", {}),
                "table_validation": result.document.metadata.get("table_validation", {}),
                "validation_issues": result.document.metadata.get("validation_issues", [])
            },
            "raw_corpus": getattr(result.document, "raw_corpus", None)
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
    else:
        # Save standard output
        save_output(output_path, result, output_format.value)
    
    logger.info(f"Conversion complete. Output: {output_path}")
    
    # Display validation results
    display_validation_results(result.document.metadata)
    
    return output_path


def display_validation_results(metadata: dict):
    """Display validation results in a formatted table."""
    table = Table(title="Validation Results", show_header=True)
    table.add_column("Validation Type", style="cyan")
    table.add_column("Result", style="green")
    
    # Corpus validation
    if "corpus_validation" in metadata:
        validation = metadata["corpus_validation"]
        table.add_row(
            "Corpus Validation",
            f" Performed (threshold: {validation.get('threshold', 'N/A')}%)"
        )
        table.add_row(
            "Raw Corpus Length",
            f"{validation.get('raw_corpus_length', 0):,} characters"
        )
    
    # Table validation  
    if "table_validation" in metadata:
        table_val = metadata["table_validation"]
        table.add_row(
            "Table Validation",
            f" Performed"
        )
        table.add_row(
            "PyMuPDF Tables",
            str(table_val.get('pymupdf_tables', 0))
        )
        table.add_row(
            "Marker Tables",
            str(table_val.get('marker_tables', 0))
        )
        table.add_row(
            "Enhanced Tables",
            str(table_val.get('enhanced_tables', 0))
        )
    
    # Validation issues
    if "validation_issues" in metadata:
        issues = metadata["validation_issues"]
        table.add_row(
            "Validation Issues",
            f"{len(issues)} found"
        )
    
    console.print(table)


@app.command()
def convert(
    pdf_path: Path = typer.Argument(
        ...,
        help="Path to input PDF file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True
    ),
    output_dir: Path = typer.Option(
        Path("./qa_output"),
        "--output-dir", "-o",
        help="Output directory for converted files"
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.JSON,
        "--format", "-f",
        help="Output format"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose logging"
    )
):
    """
    Convert a PDF with Q&A-optimized settings and validation.
    
    This command uses:
    - PyMuPDF for corpus validation
    - Enhanced table extraction with Camelot fallback
    - Complete text validation against raw PDF
    - Comprehensive metadata for downstream Q&A
    """
    # Set logging level
    if verbose:
        logger.remove()
        logger.add(lambda msg: console.print(msg), level="DEBUG")
    
    # Create output directory
    output_dir.mkdir(exist_ok=True, parents=True)
    
    try:
        # Show processing status
        with console.status(f"Converting {pdf_path.name}..."):
            output_path = convert_for_qa(pdf_path, output_dir, output_format)
        
        # Success message
        console.print(f"[green][/green] Converted to: {output_path}")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def batch(
    input_dir: Path = typer.Argument(
        ...,
        help="Directory containing PDF files",
        exists=True,
        file_okay=False,
        dir_okay=True
    ),
    output_dir: Path = typer.Option(
        Path("./qa_output"),
        "--output-dir", "-o",
        help="Output directory for converted files"
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.JSON,
        "--format", "-f",
        help="Output format"
    ),
    pattern: str = typer.Option(
        "*.pdf",
        "--pattern", "-p",
        help="File pattern to match"
    )
):
    """
    Batch convert PDFs in a directory.
    """
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Find all PDFs
    pdf_files = list(input_dir.glob(pattern))
    
    if not pdf_files:
        console.print(f"[yellow]No files found matching pattern: {pattern}[/yellow]")
        raise typer.Exit(0)
    
    console.print(f"Found {len(pdf_files)} PDFs to convert")
    
    # Process each file
    successful = 0
    failed = 0
    
    for pdf_path in pdf_files:
        try:
            console.print(f"\nProcessing: {pdf_path.name}")
            with console.status("Converting..."):
                output_path = convert_for_qa(pdf_path, output_dir, output_format)
            console.print(f"[green][/green] {output_path}")
            successful += 1
        except Exception as e:
            console.print(f"[red][/red] Failed: {e}")
            failed += 1
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Successful: {successful}")
    console.print(f"  Failed: {failed}")


@app.command()
def validate(
    json_path: Path = typer.Argument(
        ...,
        help="Path to converted JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False
    )
):
    """
    Validate a converted JSON file and display detailed results.
    """
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Display validation information
        if "validation" in data:
            console.print("[bold]Validation Report[/bold]\n")
            
            validation = data["validation"]
            
            # Corpus validation
            if "corpus_validation" in validation:
                corpus_val = validation["corpus_validation"]
                console.print("[cyan]Corpus Validation:[/cyan]")
                console.print(f"  Performed: {corpus_val.get('performed', False)}")
                console.print(f"  Threshold: {corpus_val.get('threshold', 'N/A')}%")
                console.print(f"  Raw corpus: {corpus_val.get('raw_corpus_length', 0):,} chars\n")
            
            # Table validation
            if "table_validation" in validation:
                table_val = validation["table_validation"]
                console.print("[cyan]Table Validation:[/cyan]")
                for key, value in table_val.items():
                    console.print(f"  {key}: {value}")
                console.print()
            
            # Issues
            if "validation_issues" in validation:
                issues = validation["validation_issues"]
                console.print(f"[yellow]Issues Found: {len(issues)}[/yellow]")
                for issue in issues[:5]:  # Show first 5
                    console.print(f"  - {issue}")
        
        # Check raw corpus
        if "raw_corpus" in data and data["raw_corpus"]:
            console.print(f"\n[green][/green] Raw corpus included")
        else:
            console.print(f"\n[red][/red] Raw corpus missing")
        
    except Exception as e:
        console.print(f"[red]Error reading file:[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()