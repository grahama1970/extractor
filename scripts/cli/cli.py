#!/usr/bin/env python3
"""
Marker Typer-based CLI

This module provides a robust command-line interface for the Marker PDF conversion tool.
It offers multiple output formats and follows the patterns established in the ArangoDB CLI.

Command Groups:
- convert: PDF conversion operations
- version: Version information

Output Formats:
- markdown: Standard markdown output (default)
- json: JSON output with document structure
- html: HTML output
- dict: Python dictionary format (for programmatic use)
- table: Rich table format showing document structure

Sample Input:
- marker convert single test.pdf --output-format json
- marker convert batch ./pdfs/ --workers 5 --output-format markdown
- marker version

Expected Output:
- Console-formatted tables, JSON, markdown, or HTML based on the --output-format parameter
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from enum import Enum

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON
from rich.progress import Progress
import json

# Initialize rich console
console = Console()

# Define output formats
class OutputFormat(str, Enum):
    """Supported output formats for CLI commands."""
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"
    DICT = "dict"
    TABLE = "table"
    SUMMARY = "summary"
    METRICS = "metrics"
    MERGED_JSON = "merged-json"


def format_output(
    data: Any,
    output_format: OutputFormat = OutputFormat.TABLE,
    title: Optional[str] = None,
    headers: Optional[List[str]] = None,
    fields: Optional[List[str]] = None,
) -> Any:
    """
    Format output data according to the specified format.
    
    Args:
        data: Data to format
        output_format: Output format to use
        title: Optional title for the output
        headers: Optional headers for table format
        fields: Optional fields to extract from data
        
    Returns:
        Formatted data ready for output
    """
    if output_format == OutputFormat.JSON:
        return json.dumps(data, indent=2)
    
    elif output_format == OutputFormat.DICT:
        return data
    
    elif output_format == OutputFormat.TABLE:
        if not headers:
            headers = ["Property", "Value"]
            
        table = Table(title=title or "Marker Output", show_header=True)
        for header in headers:
            table.add_column(header)
            
        if isinstance(data, dict):
            for key, value in data.items():
                table.add_row(str(key), str(value))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    row = [str(item.get(field, "")) for field in fields] if fields else list(map(str, item.values()))
                    table.add_row(*row)
                else:
                    table.add_row(str(item))
        
        return table
    
    elif output_format == OutputFormat.SUMMARY:
        # Create a summary panel with key information
        if isinstance(data, dict):
            summary_lines = []
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    summary_lines.append(f"[bold]{key}:[/bold] {type(value).__name__} with {len(value)} items")
                else:
                    summary_lines.append(f"[bold]{key}:[/bold] {value}")
            
            return Panel("\n".join(summary_lines), title=title or "Summary", border_style="cyan")
        else:
            return Panel(str(data), title=title or "Summary", border_style="cyan")
    
    else:
        # For markdown and html, return as-is
        return data


def error_handler(func):
    """Decorator to handle errors in CLI commands."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            console.print(f"[red]Error:[/red] {e}")
            if kwargs.get("debug", False):
                console.print_exception()
            raise typer.Exit(1)
    return wrapper


# Create the main app
app = typer.Typer(
    name="marker",
    help="Marker PDF conversion tool - Convert PDFs to various formats with AI assistance",
    add_completion=False,
    rich_markup_mode="markdown",
)

# Create search subcommand
search_app = typer.Typer(
    name="search", 
    help="Search and debug document models",
    rich_markup_mode="markdown",
)

# Create convert subcommand group
convert_app = typer.Typer(
    name="convert",
    help="PDF conversion commands",
    rich_markup_mode="markdown",
)


@convert_app.command("single", help="Convert a single PDF file to the specified format")
def convert_single(
    filepath: Path = typer.Argument(..., help="Path to the PDF file to convert"),
    output_format: OutputFormat = typer.Option(
        OutputFormat.MARKDOWN,
        "--output-format",
        "-f",
        help="Output format for the conversion results",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to save output files (default: settings.OUTPUT_DIR)",
    ),
    renderer_format: str = typer.Option(
        "markdown",
        "--renderer",
        "-r",
        help="Renderer format to use (markdown, json, html)",
    ),
    use_llm: bool = typer.Option(
        False,
        "--use-llm",
        help="Enable LLM-enhanced processing for better quality",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug mode with verbose output",
    ),
    extract_images: bool = typer.Option(
        True,
        "--extract-images/--no-extract-images",
        help="Extract images from the PDF",
    ),
    page_range: Optional[str] = typer.Option(
        None,
        "--page-range",
        help="Page range to convert (e.g., '1-5,10,15-20')",
    ),
    languages: Optional[str] = typer.Option(
        None,
        "--languages",
        help="Comma-separated list of languages for OCR",
    ),
    skip_table_merge: bool = typer.Option(
        False,
        "--skip-table-merge",
        help="Skip table merging step",
    ),
    add_summaries: bool = typer.Option(
        False,
        "--add-summaries",
        help="Add LLM-generated summaries to sections and document",
    ),
    json_indent: int = typer.Option(
        2,
        "--json-indent",
        help="JSON indentation level",
    ),
):
    """Convert a single PDF file to the specified format."""
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    from marker.output import save_output
    from marker.logger import configure_logging
    
    configure_logging()
    
    # Prepare configuration
    config_dict = {
        "output_format": renderer_format,
        "output_dir": str(output_dir) if output_dir else None,
        "use_llm": use_llm,
        "debug": debug,
        "extract_images": extract_images,
        "page_range": page_range,
        "languages": languages,
        "skip_table_merge": skip_table_merge,
        "add_summaries": add_summaries,
    }
    
    # Remove None values
    config_dict = {k: v for k, v in config_dict.items() if v is not None}
    
    try:
        # Create model dictionary
        models = create_model_dict()
        
        # Set up configuration parser
        config_parser = ConfigParser(config_dict)
        
        # Get converter class and create converter
        converter_cls = config_parser.get_converter_cls()
        
        # Override renderer for merged JSON
        if output_format == OutputFormat.MERGED_JSON:
            # Update config to use merged JSON renderer
            config_dict["output_format"] = "json"  # Still produces JSON
            config_parser = ConfigParser(config_dict)
            renderer = "marker.renderers.merged_json.MergedJSONRenderer"
        else:
            renderer = config_parser.get_renderer()
        
        converter = converter_cls(
            config=config_parser.generate_config_dict(),
            artifact_dict=models,
            processor_list=config_parser.get_processors(),
            renderer=renderer,
            llm_service=config_parser.get_llm_service()
        )
        
        # Convert the PDF
        console.print(f"[cyan]Converting[/cyan] {filepath}...")
        start_time = time.time()
        
        rendered = converter(str(filepath))
        
        # Prepare output based on format
        if output_format == OutputFormat.DICT:
            # Return the document model as a dict
            output_data = rendered.model_dump(exclude=["metadata"]) if hasattr(rendered, "model_dump") else rendered
            console.print(output_data)
        
        elif output_format == OutputFormat.TABLE:
            # Create a table view of the document structure
            table = Table(title=f"Document Structure: {filepath.name}")
            table.add_column("Type", style="cyan")
            table.add_column("Content", style="white", overflow="fold")
            table.add_column("Properties", style="green")
            
            # Add metadata row
            if hasattr(rendered, "metadata"):
                meta_str = json.dumps(rendered.metadata, indent=None)[:100] + "..."
                table.add_row("Metadata", meta_str, "")
            
            # Add content structure (simplified view)
            if hasattr(rendered, "children"):
                for idx, child in enumerate(rendered.children[:10]):  # Show first 10 items
                    child_type = getattr(child, "block_type", "unknown")
                    child_content = str(getattr(child, "text", ""))[:50] + "..."
                    child_props = f"ID: {getattr(child, 'id', 'N/A')}"
                    table.add_row(child_type, child_content, child_props)
                
                if len(rendered.children) > 10:
                    table.add_row("...", f"({len(rendered.children) - 10} more items)", "...")
            
            console.print(table)
        
        elif output_format == OutputFormat.SUMMARY:
            # Create a summary view
            summary_data = {
                "File": filepath.name,
                "Renderer": renderer_format,
                "Processing Time": f"{time.time() - start_time:.2f}s",
                "Used LLM": use_llm,
            }
            
            if hasattr(rendered, "metadata"):
                summary_data["Page Count"] = rendered.metadata.get("page_count", "N/A")
                summary_data["Language"] = rendered.metadata.get("language", "N/A")
            
            if hasattr(rendered, "children"):
                summary_data["Block Count"] = len(rendered.children)
            
            panel = format_output(
                summary_data,
                output_format=OutputFormat.SUMMARY,
                title="Conversion Summary"
            )
            console.print(panel)
        
        elif output_format == OutputFormat.JSON or output_format == OutputFormat.MERGED_JSON:
            # Output as JSON with proper formatting
            if hasattr(rendered, "model_dump_json"):
                json_output = rendered.model_dump_json(exclude=["metadata"], indent=json_indent)
            else:
                json_output = json.dumps(rendered, indent=json_indent)
            
            console.print(JSON(json_output))
        
        elif output_format == OutputFormat.METRICS:
            # Create metrics table for extraction statistics
            metrics_table = Table(title=f"PDF Extraction Metrics: {filepath.name}")
            metrics_table.add_column("Metric", style="cyan", no_wrap=True)
            metrics_table.add_column("Value", style="white")
            metrics_table.add_column("Details", style="green")
            
            # Add processing time
            processing_time = time.time() - start_time
            metrics_table.add_row("Processing Time", f"{processing_time:.2f}s", "")
            
            # Initialize counts
            block_counts = {}
            total_block_count = 0
            page_count = 0
            
            # Extract metadata if available
            if hasattr(rendered, "metadata"):
                metadata = rendered.metadata
                
                # Get page count from metadata
                if "page_stats" in metadata:
                    page_count = len(metadata["page_stats"])
                    
                    # Aggregate block counts from all pages
                    for page_stat in metadata["page_stats"]:
                        if "block_counts" in page_stat:
                            for block_type, count in page_stat["block_counts"]:
                                block_counts[block_type] = block_counts.get(block_type, 0) + count
                                total_block_count += count
                
                # Document information
                metrics_table.add_row("[bold]Document Info[/bold]", "", "")
                metrics_table.add_row("  Pages", str(page_count), "")
                
                # Text extraction method
                if "page_stats" in metadata and metadata["page_stats"]:
                    extraction_methods = set()
                    for page in metadata["page_stats"]:
                        if "text_extraction_method" in page:
                            extraction_methods.add(page["text_extraction_method"])
                    if extraction_methods:
                        metrics_table.add_row("  Text Extraction", ", ".join(extraction_methods), "")
                
                # LLM usage stats
                total_llm_requests = 0
                total_llm_errors = 0
                total_llm_tokens = 0
                
                if "page_stats" in metadata:
                    for page in metadata["page_stats"]:
                        if "block_metadata" in page:
                            block_meta = page["block_metadata"]
                            total_llm_requests += block_meta.get("llm_request_count", 0)
                            total_llm_errors += block_meta.get("llm_error_count", 0)
                            total_llm_tokens += block_meta.get("llm_tokens_used", 0)
                
                if total_llm_requests > 0:
                    metrics_table.add_row("  LLM Requests", str(total_llm_requests), 
                                        f"Errors: {total_llm_errors}, Tokens: {total_llm_tokens}")
                
                # Extraction metrics
                metrics_table.add_row("", "", "")  # Empty row
                metrics_table.add_row("[bold]Extraction Metrics[/bold]", "", "")
                
                # Count specific block types
                table_count = block_counts.get("Table", 0)
                figure_count = block_counts.get("Figure", 0) + block_counts.get("Picture", 0)
                section_count = block_counts.get("SectionHeader", 0) + block_counts.get("Section", 0)
                code_count = block_counts.get("Code", 0)
                equation_count = block_counts.get("Equation", 0)
                
                metrics_table.add_row("  Tables", str(table_count), "")
                if figure_count > 0:
                    metrics_table.add_row("  Figures/Images", str(figure_count), "")
                if section_count > 0:
                    metrics_table.add_row("  Sections", str(section_count), "")
                if code_count > 0:
                    metrics_table.add_row("  Code Blocks", str(code_count), "")
                if equation_count > 0:
                    metrics_table.add_row("  Equations", str(equation_count), "")
                
                # Debug path if available
                if "debug_data_path" in metadata:
                    metrics_table.add_row("  Debug Data", metadata["debug_data_path"], "")
            
            # Count direct children block types
            if hasattr(rendered, "children"):
                direct_child_types = {}
                for child in rendered.children:
                    child_type = getattr(child, "block_type", "unknown")
                    direct_child_types[child_type] = direct_child_types.get(child_type, 0) + 1
                
                # Show direct children summary
                if direct_child_types:
                    metrics_table.add_row("", "", "")  # Empty row
                    metrics_table.add_row("[bold]Document Structure[/bold]", "", "")
                    for block_type, count in sorted(direct_child_types.items()):
                        metrics_table.add_row(f"  {block_type}", str(count), "")
            
            # Block type distribution from metadata
            if block_counts:
                metrics_table.add_row("", "", "")  # Empty row
                metrics_table.add_row("[bold]Block Types (All Pages)[/bold]", "", "")
                
                # Sort by count descending
                sorted_blocks = sorted(block_counts.items(), key=lambda x: x[1], reverse=True)
                
                # Show top block types
                for block_type, count in sorted_blocks[:10]:  # Show top 10
                    percentage = (count / total_block_count) * 100 if total_block_count > 0 else 0
                    metrics_table.add_row(f"  {block_type}", str(count), f"{percentage:.1f}%")
                
                if len(sorted_blocks) > 10:
                    remaining = len(sorted_blocks) - 10
                    metrics_table.add_row(f"  ... ({remaining} more types)", "", "")
            
            # Processing settings
            metrics_table.add_row("", "", "")  # Empty row
            metrics_table.add_row("[bold]Processing Settings[/bold]", "", "")
            metrics_table.add_row("  LLM Enhancement", str(use_llm), "")
            metrics_table.add_row("  Image Extraction", str(extract_images), "")
            metrics_table.add_row("  Renderer Format", renderer_format, "")
            metrics_table.add_row("  Debug Mode", str(debug), "")
            
            console.print(metrics_table)
        
        else:
            # Default: save to file and show file location
            out_folder = config_parser.get_output_folder(str(filepath))
            base_name = config_parser.get_base_filename(str(filepath))
            save_output(rendered, out_folder, base_name)
            
            console.print(f"[green]✓[/green] Saved output to {out_folder}")
            console.print(f"[green]✓[/green] Base filename: {base_name}")
            console.print(f"[green]✓[/green] Format: {renderer_format}")
            console.print(f"[green]✓[/green] Processing time: {time.time() - start_time:.2f}s")
        
    except Exception as e:
        if debug:
            logger.exception("Error during conversion")
        raise


@convert_app.command("batch", help="Convert multiple PDF files in batch mode")
def convert_batch(
    input_dir: Path = typer.Argument(..., help="Directory containing PDF files to convert"),
    output_format: OutputFormat = typer.Option(
        OutputFormat.SUMMARY,
        "--output-format",
        "-f",
        help="Output format for the results",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to save output files",
    ),
    workers: int = typer.Option(
        5,
        "--workers",
        "-w",
        help="Number of worker processes to use",
    ),
    max_files: Optional[int] = typer.Option(
        None,
        "--max-files",
        help="Maximum number of files to process",
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        help="Skip files that have already been converted",
    ),
    renderer_format: str = typer.Option(
        "markdown",
        "--renderer",
        "-r",
        help="Renderer format to use (markdown, json, html)",
    ),
    use_llm: bool = typer.Option(
        False,
        "--use-llm",
        help="Enable LLM-enhanced processing",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug mode",
    ),
    chunk_idx: int = typer.Option(
        0,
        "--chunk-idx",
        help="Chunk index for parallel processing",
    ),
    num_chunks: int = typer.Option(
        1,
        "--num-chunks",
        help="Total number of chunks for parallel processing",
    ),
):
    """Convert multiple PDF files in batch mode."""
    from marker.scripts.convert import convert_cli as original_convert_cli
    
    # Prepare arguments for the original CLI
    args = {
        "in_folder": str(input_dir),
        "output_dir": str(output_dir) if output_dir else None,
        "output_format": renderer_format,
        "workers": workers,
        "max_files": max_files,
        "skip_existing": skip_existing,
        "use_llm": use_llm,
        "debug": debug,
        "chunk_idx": chunk_idx,
        "num_chunks": num_chunks,
    }
    
    # Remove None values
    args = {k: v for k, v in args.items() if v is not None}
    
    # If output format is summary or table, capture results for custom display
    if output_format in [OutputFormat.SUMMARY, OutputFormat.TABLE]:
        start_time = time.time()
        
        # Find PDF files
        pdf_files = list(input_dir.glob("*.pdf"))
        if max_files:
            pdf_files = pdf_files[:max_files]
        
        console.print(f"[cyan]Processing {len(pdf_files)} PDF files[/cyan]")
        
        # Run the conversion
        original_convert_cli(**args)
        
        # Display summary
        end_time = time.time()
        summary_data = {
            "Input Directory": str(input_dir),
            "Output Directory": args.get("output_dir", "Default"),
            "Files Processed": len(pdf_files),
            "Workers": workers,
            "Renderer": renderer_format,
            "LLM Enabled": use_llm,
            "Total Time": f"{end_time - start_time:.2f}s",
            "Skip Existing": skip_existing,
        }
        
        if output_format == OutputFormat.SUMMARY:
            panel = format_output(
                summary_data,
                output_format=OutputFormat.SUMMARY,
                title="Batch Conversion Summary"
            )
            console.print(panel)
        else:
            table = format_output(
                summary_data,
                output_format=OutputFormat.TABLE,
                title="Batch Conversion Results"
            )
            console.print(table)
    else:
        # For other formats, just run the original CLI
        original_convert_cli(**args)


@search_app.command("json", help="Search within a JSON document model")
def search_json(
    filepath: Path = typer.Argument(..., help="Path to the JSON file to search"),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Text to search for (case-insensitive)"),
    block_type: Optional[str] = typer.Option(None, "--block-type", "-b", help="Filter by block type"),
    section_id: Optional[str] = typer.Option(None, "--section", "-s", help="Search within specific section ID"),
    has_images: Optional[bool] = typer.Option(None, "--has-images/--no-images", help="Filter blocks with/without images"),
    get_node: Optional[str] = typer.Option(None, "--get-node", "-n", help="Get specific node by ID"),
    structure: bool = typer.Option(False, "--structure", help="Show document structure summary"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format", "-f", help="Output format"),
):
    """Search and debug document models."""
    try:
        # Import here to avoid circular imports
        from marker.cli.search import DocumentSearcher, SearchCriteria
        import json
        
        # Load document
        with open(filepath, 'r') as f:
            doc_data = json.load(f)
        
        # Create a simple document structure for searching
        class SimpleDoc:
            def __init__(self, data):
                self.children = []
                self._parse_dict(data)
            
            def _parse_dict(self, data):
                for key, value in data.items():
                    if key == "children" and isinstance(value, list):
                        for child in value:
                            self.children.append(SimpleDoc(child))
                    else:
                        setattr(self, key, value)
        
        doc = SimpleDoc(doc_data)
        searcher = DocumentSearcher(doc)
        
        # Handle different operations
        if structure:
            result = searcher.get_structure_summary()
            if output_format == OutputFormat.JSON:
                console.print(JSON(json.dumps(result, indent=2)))
            else:
                # Pretty print structure
                table = Table(title="Document Structure Summary")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="white")
                
                table.add_row("Total Blocks", str(result['total_blocks']))
                table.add_row("Max Depth", str(result['max_depth']))
                table.add_row("Pages", str(len(result['pages'])))
                table.add_row("Sections", str(len(result['sections'])))
                table.add_row("Images", str(result['images_count']))
                table.add_row("Tables", str(result['tables_count']))
                
                console.print(table)
                
                # Block types table
                bt_table = Table(title="Block Type Distribution")
                bt_table.add_column("Block Type", style="cyan")
                bt_table.add_column("Count", style="white")
                
                for block_type, count in sorted(result['block_types'].items()):
                    bt_table.add_row(block_type, str(count))
                
                console.print(bt_table)
        
        elif get_node:
            result = searcher.get_node_by_id(get_node)
            if result:
                if output_format == OutputFormat.JSON:
                    console.print(JSON(json.dumps(result, indent=2)))
                else:
                    # Pretty print node
                    console.print(Panel(f"Node: {result.get('id', 'Unknown')}", style="cyan"))
                    for key, value in result.items():
                        if key == 'children':
                            console.print(f"[bold]{key}:[/bold] {len(value)} items")
                        else:
                            console.print(f"[bold]{key}:[/bold] {value}")
            else:
                console.print(f"[red]Node not found:[/red] {get_node}")
        
        else:
            # Search with criteria
            criteria = SearchCriteria(
                text=text,
                block_type=block_type,
                section_id=section_id,
                has_images=has_images
            )
            
            results = searcher.search(criteria)
            
            if output_format == OutputFormat.JSON:
                console.print(JSON(json.dumps([r.model_dump() for r in results], indent=2)))
            else:
                # Pretty print results
                if not results:
                    console.print("[yellow]No results found[/yellow]")
                else:
                    console.print(f"[green]Found {len(results)} results[/green]\n")
                    
                    for i, result in enumerate(results[:10], 1):
                        console.print(f"[bold cyan]Result {i}:[/bold cyan]")
                        console.print(f"  ID: {result.id}")
                        console.print(f"  Type: {result.block_type}")
                        console.print(f"  Path: {' > '.join(result.path)}")
                        console.print(f"  Match: {result.match_reason}")
                        if result.content:
                            console.print(f"  Content: {result.content}")
                        console.print()
                    
                    if len(results) > 10:
                        console.print(f"[dim]... and {len(results) - 10} more results[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("version")
def version_command():
    """Display version information for Marker."""
    try:
        from marker import __version__
        version_info = {
            "Marker Version": getattr(marker, "__version__", "Unknown"),
            "Python Version": sys.version.split()[0],
            "Platform": sys.platform,
        }
    except:
        version_info = {
            "Marker Version": "Unknown",
            "Python Version": sys.version.split()[0],
            "Platform": sys.platform,
        }
    
    panel = format_output(
        version_info,
        output_format=OutputFormat.SUMMARY,
        title="Marker Version Information"
    )
    console.print(panel)


# Add subcommand groups to main app
app.add_typer(convert_app, name="convert")
app.add_typer(search_app, name="search")


# Global callback for common options
@app.callback()
def main_callback(
    log_level: str = typer.Option(
        os.environ.get("LOG_LEVEL", "INFO").upper(),
        "--log-level",
        "-l",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR)",
        envvar="LOG_LEVEL",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug mode",
    ),
):
    """Main callback to configure logging and global settings."""
    # Configure logging
    log_level = log_level.upper()
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        console.print(
            f"[yellow]Warning:[/yellow] Invalid log level '{log_level}'. Defaulting to INFO.",
            file=sys.stderr,
        )
        log_level = "INFO"
    
    if debug:
        log_level = "DEBUG"
    
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        level=log_level,
        format="{time:HH:mm:ss} | {level: <7} | {message}",
        backtrace=debug,
        diagnose=debug,
    )
    
    logger.debug("Marker CLI initialized")


if __name__ == "__main__":
    app()