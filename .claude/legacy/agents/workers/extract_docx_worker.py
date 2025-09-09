#!/usr/bin/env python3
"""
DOCX Extraction Worker

Provides sub-agent capabilities for extracting content from Microsoft Word documents.
Leverages the DOCXProvider for native extraction without lossy PDF conversion.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="DOCX Extraction Worker - Native extraction preserving all document features")
console = Console()

# Import the DOCX provider
from extractor.core.providers.docx import DOCXProvider
from extractor.core.schema.unified_document import BlockType


class DOCXExtractionWorker:
    """Worker for extracting content from DOCX files."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "extractor" / "docx"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    async def extract_docx(self, 
                          docx_path: Path,
                          output_path: Optional[Path] = None,
                          config: Optional[Dict] = None) -> Dict:
        """Extract DOCX with native extraction.
        
        Args:
            docx_path: Path to DOCX file
            output_path: Optional output path for results
            config: Optional configuration dict
            
        Returns:
            Extraction results with metadata
        """
        start_time = datetime.now()
        
        # Check cache first (knowledge-first pattern)
        cache_key = self._get_cache_key(docx_path)
        cached_result = await self._check_cache(cache_key)
        if cached_result:
            logger.info(f"Found cached extraction for {docx_path.name}")
            return cached_result
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            task = progress.add_task("Extracting DOCX content...", total=None)
            
            try:
                # Initialize provider with config
                provider = DOCXProvider(config or {})
                
                # Extract document
                doc = provider.extract_document(docx_path)
                
                # Convert to result format
                result = {
                    "success": True,
                    "data": {
                        "blocks": [self._serialize_block(b) for b in doc.blocks],
                        "metadata": {
                            "title": doc.metadata.title,
                            "author": doc.metadata.author,
                            "created_date": doc.metadata.created_date.isoformat() if doc.metadata.created_date else None,
                            "modified_date": doc.metadata.modified_date.isoformat() if doc.metadata.modified_date else None,
                            "language": doc.metadata.language,
                            "format_metadata": doc.metadata.format_metadata
                        },
                        "hierarchy": self._serialize_hierarchy(doc.hierarchy) if doc.hierarchy else None,
                        "statistics": self._calculate_statistics(doc.blocks)
                    },
                    "extraction_metadata": {
                        "source_path": str(docx_path),
                        "extraction_time": (datetime.now() - start_time).total_seconds(),
                        "extractor_version": "1.0",
                        "method": "native_docx_extraction"
                    }
                }
                
                progress.update(task, completed=True)
                
                # Cache result
                await self._cache_result(cache_key, result)
                
                # Save if output path provided
                if output_path:
                    await self._save_result(result, output_path)
                
                return result
                
            except Exception as e:
                logger.error(f"DOCX extraction failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "source_path": str(docx_path)
                }
    
    async def analyze_docx_structure(self, docx_path: Path) -> Dict:
        """Analyze DOCX structure and features.
        
        Args:
            docx_path: Path to DOCX file
            
        Returns:
            Structure analysis
        """
        try:
            provider = DOCXProvider()
            doc = provider.extract_document(docx_path)
            
            # Analyze block types
            block_types = {}
            for block in doc.blocks:
                block_type = block.type.value if hasattr(block.type, 'value') else str(block.type)
                block_types[block_type] = block_types.get(block_type, 0) + 1
            
            # Analyze special features
            features = {
                "has_comments": any(b.type == BlockType.COMMENT for b in doc.blocks),
                "has_footnotes": any(b.type == BlockType.FOOTNOTE for b in doc.blocks),
                "has_images": any(b.type == BlockType.IMAGE for b in doc.blocks),
                "has_tables": any(b.type == BlockType.TABLE for b in doc.blocks),
                "has_headers": any(b.type == BlockType.PAGEHEADER for b in doc.blocks),
                "has_footers": any(b.type == BlockType.PAGEFOOTER for b in doc.blocks)
            }
            
            # Analyze hierarchy
            hierarchy_depth = 0
            if doc.hierarchy:
                hierarchy_depth = self._calculate_hierarchy_depth(doc.hierarchy)
            
            return {
                "success": True,
                "analysis": {
                    "total_blocks": len(doc.blocks),
                    "block_types": block_types,
                    "features": features,
                    "hierarchy_depth": hierarchy_depth,
                    "has_hierarchy": doc.hierarchy is not None,
                    "metadata": {
                        "title": doc.metadata.title,
                        "author": doc.metadata.author
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Structure analysis failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def extract_tables(self, docx_path: Path) -> Dict:
        """Extract only tables from DOCX.
        
        Args:
            docx_path: Path to DOCX file
            
        Returns:
            Table extraction results
        """
        try:
            provider = DOCXProvider()
            doc = provider.extract_document(docx_path)
            
            # Filter table blocks
            tables = [b for b in doc.blocks if b.type == BlockType.TABLE]
            
            # Convert tables to structured format
            table_data = []
            for table in tables:
                # Convert cells to 2D array
                rows_data = {}
                for cell in table.cells:
                    if cell.row not in rows_data:
                        rows_data[cell.row] = {}
                    rows_data[cell.row][cell.col] = cell.content
                
                # Convert to list format
                table_array = []
                for row_idx in range(table.rows):
                    row = []
                    for col_idx in range(table.cols):
                        row.append(rows_data.get(row_idx, {}).get(col_idx, ""))
                    table_array.append(row)
                
                table_data.append({
                    "id": table.id,
                    "rows": table.rows,
                    "cols": table.cols,
                    "data": table_array,
                    "headers": table.headers,
                    "metadata": table.metadata.attributes if table.metadata else {}
                })
            
            return {
                "success": True,
                "tables": table_data,
                "total_tables": len(tables)
            }
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _serialize_block(self, block: Any) -> Dict:
        """Serialize a block to JSON-compatible format."""
        result = {
            "id": block.id,
            "type": block.type.value if hasattr(block.type, 'value') else str(block.type),
            "content": block.content
        }
        
        # Add metadata if present
        if hasattr(block, 'metadata') and block.metadata:
            result["metadata"] = {
                "attributes": block.metadata.attributes,
                "confidence": block.metadata.confidence
            }
        
        # Handle table-specific fields
        if block.type == BlockType.TABLE:
            result["rows"] = block.rows
            result["cols"] = block.cols
            result["cells"] = [
                {"row": c.row, "col": c.col, "content": c.content}
                for c in block.cells
            ]
            result["headers"] = block.headers
        
        # Handle image-specific fields
        if block.type == BlockType.IMAGE:
            result["src"] = block.src
            result["alt"] = block.alt
            result["format"] = block.format
        
        return result
    
    def _serialize_hierarchy(self, hierarchy: Any) -> Dict:
        """Serialize hierarchy to JSON-compatible format."""
        if not hierarchy:
            return None
        
        def serialize_node(node):
            return {
                "id": node.id,
                "title": node.title,
                "level": node.level,
                "block_id": node.block_id,
                "parent_id": node.parent_id,
                "breadcrumb": node.breadcrumb if hasattr(node, 'breadcrumb') else [],
                "children": [serialize_node(child) for child in node.children]
            }
        
        return serialize_node(hierarchy)
    
    def _calculate_statistics(self, blocks: List[Any]) -> Dict:
        """Calculate extraction statistics."""
        stats = {
            "total_blocks": len(blocks),
            "block_types": {},
            "total_text_length": 0,
            "table_count": 0,
            "image_count": 0,
            "heading_count": 0
        }
        
        for block in blocks:
            block_type = block.type.value if hasattr(block.type, 'value') else str(block.type)
            stats["block_types"][block_type] = stats["block_types"].get(block_type, 0) + 1
            
            if hasattr(block, 'content') and isinstance(block.content, str):
                stats["total_text_length"] += len(block.content)
            
            if block.type == BlockType.TABLE:
                stats["table_count"] += 1
            elif block.type == BlockType.IMAGE:
                stats["image_count"] += 1
            elif block.type == BlockType.HEADING:
                stats["heading_count"] += 1
        
        return stats
    
    def _calculate_hierarchy_depth(self, hierarchy: Any, depth: int = 0) -> int:
        """Calculate maximum hierarchy depth."""
        if not hierarchy or not hasattr(hierarchy, 'children'):
            return depth
        
        max_depth = depth
        for child in hierarchy.children:
            child_depth = self._calculate_hierarchy_depth(child, depth + 1)
            max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def _get_cache_key(self, docx_path: Path) -> str:
        """Generate cache key for DOCX file."""
        stat = docx_path.stat()
        data = f"{docx_path.absolute()}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def _check_cache(self, cache_key: str) -> Optional[Dict]:
        """Check if extraction is cached."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return None
    
    async def _cache_result(self, cache_key: str, result: Dict):
        """Cache extraction result."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
    
    async def _save_result(self, result: Dict, output_path: Path):
        """Save extraction result."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved extraction to {output_path}")
    
    def _show_extraction_summary(self, result: Dict):
        """Display extraction summary table."""
        if not result.get("success"):
            console.print(f"[red]Extraction failed: {result.get('error')}[/red]")
            return
        
        data = result["data"]
        stats = data.get("statistics", {})
        
        table = Table(title="DOCX Extraction Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Blocks", str(stats.get("total_blocks", 0)))
        table.add_row("Text Length", f"{stats.get('total_text_length', 0):,} chars")
        table.add_row("Tables", str(stats.get("table_count", 0)))
        table.add_row("Images", str(stats.get("image_count", 0)))
        table.add_row("Headings", str(stats.get("heading_count", 0)))
        
        # Add metadata
        metadata = data.get("metadata", {})
        if metadata.get("title"):
            table.add_row("Title", metadata["title"])
        if metadata.get("author"):
            table.add_row("Author", metadata["author"])
        
        console.print(table)


# Initialize worker
worker = DOCXExtractionWorker()


@app.command()
def extract(
    docx_path: Path = typer.Argument(..., help="Path to DOCX file to extract"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path for results"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache lookup"),
    show_summary: bool = typer.Option(True, "--summary", help="Show extraction summary")
):
    """Extract content from a DOCX file with native extraction."""
    if not docx_path.exists():
        console.print(f"[red]Error: DOCX file not found: {docx_path}[/red]")
        raise typer.Exit(1)
    
    if not docx_path.suffix.lower() in ['.docx', '.doc']:
        console.print(f"[yellow]Warning: File may not be a Word document: {docx_path}[/yellow]")
    
    async def run():
        try:
            result = await worker.extract_docx(
                docx_path=docx_path,
                output_path=output
            )
            
            if show_summary:
                worker._show_extraction_summary(result)
            
            if result.get("success"):
                console.print(f"\n[green] Extraction complete![/green]")
                console.print(f"Time: {result['extraction_metadata']['extraction_time']:.2f}s")
            else:
                console.print(f"\n[red] Extraction failed[/red]")
                
        except Exception as e:
            console.print(f"[red]Extraction failed: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command("analyze")
def analyze_structure(
    docx_path: Path = typer.Argument(..., help="Path to DOCX file to analyze")
):
    """Analyze DOCX structure and features."""
    if not docx_path.exists():
        console.print(f"[red]Error: DOCX file not found: {docx_path}[/red]")
        raise typer.Exit(1)
    
    async def run():
        try:
            result = await worker.analyze_docx_structure(docx_path)
            
            if result.get("success"):
                analysis = result["analysis"]
                
                table = Table(title="DOCX Structure Analysis")
                table.add_column("Feature", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Total Blocks", str(analysis["total_blocks"]))
                table.add_row("Hierarchy Depth", str(analysis["hierarchy_depth"]))
                
                # Show block types
                console.print("\n[bold]Block Type Distribution:[/bold]")
                for block_type, count in analysis["block_types"].items():
                    console.print(f"  {block_type}: {count}")
                
                # Show features
                console.print("\n[bold]Document Features:[/bold]")
                for feature, present in analysis["features"].items():
                    status = "" if present else ""
                    color = "green" if present else "dim"
                    console.print(f"  [{color}]{status} {feature}[/{color}]")
                
                console.print(table)
            else:
                console.print(f"[red]Analysis failed: {result.get('error')}[/red]")
                
        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command("extract-tables")
def extract_tables(
    docx_path: Path = typer.Argument(..., help="Path to DOCX file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path for table data")
):
    """Extract only tables from DOCX file."""
    if not docx_path.exists():
        console.print(f"[red]Error: DOCX file not found: {docx_path}[/red]")
        raise typer.Exit(1)
    
    async def run():
        try:
            result = await worker.extract_tables(docx_path)
            
            if result.get("success"):
                console.print(f"\n[green]Found {result['total_tables']} tables[/green]")
                
                # Show first table as preview
                if result["tables"]:
                    first_table = result["tables"][0]
                    console.print(f"\nPreview of first table ({first_table['rows']}x{first_table['cols']}):")
                    
                    # Create rich table for display
                    display_table = Table()
                    
                    # Add columns
                    for col_idx in range(first_table['cols']):
                        display_table.add_column(f"Col {col_idx + 1}")
                    
                    # Add rows (max 5 for preview)
                    for row_idx, row in enumerate(first_table['data'][:5]):
                        display_table.add_row(*[str(cell) for cell in row])
                    
                    if first_table['rows'] > 5:
                        display_table.add_row(*["..." for _ in range(first_table['cols'])])
                    
                    console.print(display_table)
                
                # Save if output specified
                if output:
                    with open(output, 'w') as f:
                        json.dump(result, f, indent=2)
                    console.print(f"\n[green]Saved table data to {output}[/green]")
                    
            else:
                console.print(f"[red]Table extraction failed: {result.get('error')}[/red]")
                
        except Exception as e:
            console.print(f"[red]Table extraction failed: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


# Worker functions for direct use
async def working_usage():
    """Demonstrate DOCX extraction capabilities."""
    test_docx = Path("test_data/sample.docx")
    
    if test_docx.exists():
        logger.info(f"Extracting {test_docx}...")
        result = await worker.extract_docx(test_docx)
        
        if result.get("success"):
            data = result["data"]
            stats = data.get("statistics", {})
            
            logger.info(f"\nExtraction Results:")
            logger.info(f"- Total blocks: {stats.get('total_blocks', 0)}")
            logger.info(f"- Tables: {stats.get('table_count', 0)}")
            logger.info(f"- Images: {stats.get('image_count', 0)}")
            logger.info(f"- Headings: {stats.get('heading_count', 0)}")
            
            # Show metadata
            metadata = data.get("metadata", {})
            if metadata.get("title"):
                logger.info(f"- Title: {metadata['title']}")
            if metadata.get("author"):
                logger.info(f"- Author: {metadata['author']}")
    else:
        logger.warning(f"Test DOCX not found: {test_docx}")
        logger.info("Creating mock extraction...")
        
        # Mock result for testing
        mock_result = {
            "success": True,
            "data": {
                "blocks": [
                    {"id": "1", "type": "HEADING", "content": "Introduction"},
                    {"id": "2", "type": "PARAGRAPH", "content": "This is a test document."},
                    {"id": "3", "type": "TABLE", "rows": 2, "cols": 3}
                ],
                "statistics": {
                    "total_blocks": 3,
                    "table_count": 1,
                    "heading_count": 1
                }
            }
        }
        
        logger.info(f"\nMock extraction complete:")
        logger.info(f"- Blocks: {len(mock_result['data']['blocks'])}")


async def debug_function():
    """Debug function for testing edge cases."""
    logger.info("Testing DOCX provider initialization...")
    
    # Test provider creation
    provider = DOCXProvider(config={"enable_table_merge_analysis": False})
    logger.info(f" Provider created: {provider}")
    
    # Test cache functionality
    logger.info("\nTesting cache system...")
    test_path = Path("test.docx")
    cache_key = worker._get_cache_key(test_path)
    logger.info(f"Cache key for test.docx: {cache_key}")
    
    # Test block serialization
    logger.info("\nTesting block serialization...")
    from extractor.core.schema.unified_document import BaseBlock, BlockMetadata
    
    test_block = BaseBlock(
        id="test-1",
        type=BlockType.PARAGRAPH,
        content="Test paragraph",
        metadata=BlockMetadata(
            attributes={"style": "Normal"},
            confidence=0.95
        )
    )
    
    serialized = worker._serialize_block(test_block)
    logger.info(f"Serialized block: {json.dumps(serialized, indent=2)}")
    
    logger.info("\nDebug complete!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()