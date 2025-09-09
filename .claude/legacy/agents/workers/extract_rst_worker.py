#!/usr/bin/env python3
"""
ReStructuredText Document Extractor Worker

Extracts content from RST files while preserving structure, directives,
roles, and semantic markup.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib
import re

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.syntax import Syntax

try:
    import docutils.core
    import docutils.parsers.rst
    from docutils import nodes
    from docutils.parsers.rst import directives, roles
    DOCUTILS_AVAILABLE = True
except ImportError:
    DOCUTILS_AVAILABLE = False
    logger.warning("docutils not available - RST support disabled")

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Extract content from ReStructuredText documents")
console = Console()


class RSTExtractor:
    """Extract content from ReStructuredText documents."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "extractor" / "rst"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Common RST roles and directives
        self.known_directives = {
            'code', 'code-block', 'sourcecode', 'literalinclude',
            'math', 'figure', 'image', 'table', 'csv-table', 'list-table',
            'note', 'warning', 'tip', 'important', 'caution', 'danger',
            'seealso', 'todo', 'versionadded', 'versionchanged',
            'deprecated', 'toctree', 'glossary', 'index'
        }
        
        self.known_roles = {
            'math', 'eq', 'doc', 'ref', 'numref', 'keyword', 'abbr',
            'command', 'dfn', 'file', 'guilabel', 'kbd', 'menuselection',
            'program', 'regexp', 'samp', 'pep', 'rfc'
        }
        
    async def extract_rst(self,
                         rst_path: Path,
                         extract_raw: bool = False,
                         extract_toc: bool = True,
                         extract_metadata: bool = True,
                         parse_directives: bool = True) -> Dict:
        """Extract content from RST file.
        
        Args:
            rst_path: Path to RST file
            extract_raw: Whether to include raw RST source
            extract_toc: Whether to extract table of contents
            extract_metadata: Whether to extract document metadata
            parse_directives: Whether to parse custom directives
            
        Returns:
            Extracted content with metadata
        """
        # Validate path
        rst_path = Path(rst_path).resolve()
        if not rst_path.exists():
            raise FileNotFoundError(f"RST file not found: {rst_path}")
        if rst_path.suffix.lower() not in ['.rst', '.rest', '.txt']:
            logger.warning(f"Unusual extension for RST file: {rst_path}")
        
        if not DOCUTILS_AVAILABLE:
            # Fallback to regex-based extraction
            return await self._extract_rst_fallback(rst_path, extract_raw)
        
        # Check cache
        cache_key = self._get_cache_key(rst_path)
        cached = await self._check_cache(cache_key)
        if cached:
            logger.info(f"Using cached extraction for {rst_path.name}")
            return cached
        
        # Read content
        with open(rst_path, 'r', encoding='utf-8') as f:
            rst_content = f.read()
        
        # Parse with docutils
        settings = {
            'input_encoding': 'utf-8',
            'halt_level': 5,  # Don't halt on warnings
            'report_level': 5,  # Suppress warnings
            'syntax_highlight': 'short'
        }
        
        parts = docutils.core.publish_parts(
            source=rst_content,
            writer_name='html',
            settings_overrides=settings
        )
        
        # Parse document tree
        doctree = docutils.core.publish_doctree(
            source=rst_content,
            settings_overrides=settings
        )
        
        # Extract structured content
        blocks = await self._extract_blocks(doctree)
        
        # Extract metadata
        metadata = {}
        if extract_metadata:
            metadata = self._extract_metadata(doctree, parts)
            metadata["source_file"] = str(rst_path)
            metadata["file_size"] = rst_path.stat().st_size
        
        # Extract TOC
        toc = {}
        if extract_toc:
            toc = self._extract_toc(doctree)
        
        # Parse custom directives
        directives_found = {}
        roles_found = {}
        if parse_directives:
            directives_found = self._find_directives(rst_content)
            roles_found = self._find_roles(rst_content)
        
        result = {
            "blocks": blocks,
            "metadata": metadata,
            "toc": toc,
            "directives": directives_found,
            "roles": roles_found,
            "statistics": self._calculate_statistics(blocks, directives_found, roles_found)
        }
        
        # Add raw content if requested
        if extract_raw:
            result["raw"] = rst_content
        
        # Cache result
        await self._cache_result(cache_key, result)
        
        return result
    
    async def _extract_rst_fallback(self, rst_path: Path, extract_raw: bool) -> Dict:
        """Fallback RST extraction using regex when docutils not available."""
        with open(rst_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        blocks = []
        
        # Extract titles/sections
        title_patterns = [
            (r'^(.*)\n={3,}$', 1),  # Main title
            (r'^(.*)\n-{3,}$', 2),  # Subtitle
            (r'^(.*)\n\^{3,}$', 3), # Section
            (r'^(.*)\n"{3,}$', 4),  # Subsection
        ]
        
        for pattern, level in title_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                blocks.append({
                    "type": "heading",
                    "level": level,
                    "content": match.group(1).strip(),
                    "line": content[:match.start()].count('\n') + 1
                })
        
        # Extract code blocks
        code_pattern = r'::\n\n((?:    .*\n)*)'
        for match in re.finditer(code_pattern, content):
            code_text = '\n'.join(line[4:] for line in match.group(1).split('\n') if line)
            blocks.append({
                "type": "code",
                "content": code_text,
                "language": "text",
                "line": content[:match.start()].count('\n') + 1
            })
        
        # Extract directives
        directive_pattern = r'^\.\. ([a-z-]+)::(.*?)(?:\n\n|\Z)'
        for match in re.finditer(directive_pattern, content, re.MULTILINE | re.DOTALL):
            blocks.append({
                "type": "directive",
                "directive": match.group(1),
                "content": match.group(2).strip(),
                "line": content[:match.start()].count('\n') + 1
            })
        
        # Sort blocks by line number
        blocks.sort(key=lambda x: x.get('line', 0))
        
        result = {
            "blocks": blocks,
            "metadata": {
                "source_file": str(rst_path),
                "file_size": rst_path.stat().st_size,
                "extraction_method": "regex_fallback"
            },
            "statistics": {
                "total_blocks": len(blocks),
                "block_types": {}
            }
        }
        
        # Count block types
        for block in blocks:
            block_type = block.get("type", "unknown")
            result["statistics"]["block_types"][block_type] = \
                result["statistics"]["block_types"].get(block_type, 0) + 1
        
        if extract_raw:
            result["raw"] = content
        
        return result
    
    async def _extract_blocks(self, doctree) -> List[Dict]:
        """Extract content blocks from docutils document tree."""
        blocks = []
        
        def visit_node(node, depth=0):
            block = None
            
            if isinstance(node, nodes.title):
                block = {
                    "type": "heading",
                    "level": depth,
                    "content": node.astext()
                }
            
            elif isinstance(node, nodes.paragraph):
                block = {
                    "type": "paragraph",
                    "content": node.astext()
                }
            
            elif isinstance(node, nodes.literal_block):
                block = {
                    "type": "code",
                    "content": node.astext(),
                    "language": node.get('language', 'text')
                }
            
            elif isinstance(node, nodes.bullet_list):
                items = []
                for item in node.traverse(nodes.list_item):
                    items.append(item.astext())
                block = {
                    "type": "list",
                    "list_type": "bullet",
                    "items": items
                }
            
            elif isinstance(node, nodes.enumerated_list):
                items = []
                for item in node.traverse(nodes.list_item):
                    items.append(item.astext())
                block = {
                    "type": "list",
                    "list_type": "enumerated",
                    "items": items
                }
            
            elif isinstance(node, nodes.table):
                block = self._extract_table(node)
            
            elif isinstance(node, nodes.figure):
                block = self._extract_figure(node)
            
            elif isinstance(node, nodes.image):
                block = {
                    "type": "image",
                    "uri": node.get('uri', ''),
                    "alt": node.get('alt', '')
                }
            
            elif isinstance(node, nodes.note):
                block = {
                    "type": "admonition",
                    "admonition_type": "note",
                    "content": node.astext()
                }
            
            elif isinstance(node, nodes.warning):
                block = {
                    "type": "admonition",
                    "admonition_type": "warning",
                    "content": node.astext()
                }
            
            elif isinstance(node, nodes.math_block):
                block = {
                    "type": "math",
                    "content": node.astext(),
                    "display": "block"
                }
            
            elif isinstance(node, nodes.math):
                block = {
                    "type": "math",
                    "content": node.astext(),
                    "display": "inline"
                }
            
            elif isinstance(node, nodes.block_quote):
                block = {
                    "type": "blockquote",
                    "content": node.astext()
                }
            
            elif isinstance(node, nodes.definition_list):
                terms = []
                for item in node.traverse(nodes.definition_list_item):
                    term = item.traverse(nodes.term)[0].astext() if item.traverse(nodes.term) else ""
                    definition = item.traverse(nodes.definition)[0].astext() if item.traverse(nodes.definition) else ""
                    terms.append({"term": term, "definition": definition})
                block = {
                    "type": "definition_list",
                    "items": terms
                }
            
            if block:
                # Add source line if available
                if hasattr(node, 'line') and node.line:
                    block['line'] = node.line
                blocks.append(block)
            
            # Recurse into sections
            if isinstance(node, nodes.section):
                for child in node:
                    visit_node(child, depth + 1)
            elif hasattr(node, 'children'):
                for child in node.children:
                    if not isinstance(child, (nodes.title,)):  # Skip already processed
                        visit_node(child, depth)
        
        visit_node(doctree)
        return blocks
    
    def _extract_table(self, table_node) -> Dict:
        """Extract table data from docutils table node."""
        table_data = {
            "type": "table",
            "rows": [],
            "headers": []
        }
        
        tgroup = table_node.traverse(nodes.tgroup)[0] if table_node.traverse(nodes.tgroup) else None
        if not tgroup:
            return table_data
        
        # Extract headers
        thead = tgroup.traverse(nodes.thead)
        if thead:
            for row in thead[0].traverse(nodes.row):
                header_row = []
                for entry in row.traverse(nodes.entry):
                    header_row.append(entry.astext())
                table_data["headers"].append(header_row)
        
        # Extract body
        tbody = tgroup.traverse(nodes.tbody)
        if tbody:
            for row in tbody[0].traverse(nodes.row):
                data_row = []
                for entry in row.traverse(nodes.entry):
                    data_row.append(entry.astext())
                table_data["rows"].append(data_row)
        
        return table_data
    
    def _extract_figure(self, figure_node) -> Dict:
        """Extract figure data from docutils figure node."""
        figure_data = {
            "type": "figure",
            "caption": "",
            "image": None
        }
        
        # Extract caption
        caption = figure_node.traverse(nodes.caption)
        if caption:
            figure_data["caption"] = caption[0].astext()
        
        # Extract image
        image = figure_node.traverse(nodes.image)
        if image:
            figure_data["image"] = {
                "uri": image[0].get('uri', ''),
                "alt": image[0].get('alt', '')
            }
        
        return figure_data
    
    def _extract_metadata(self, doctree, parts) -> Dict:
        """Extract document metadata."""
        metadata = {
            "title": parts.get('title', ''),
            "subtitle": parts.get('subtitle', ''),
            "author": "",
            "date": "",
            "docinfo": {}
        }
        
        # Extract docinfo fields
        docinfo = doctree.traverse(nodes.docinfo)
        if docinfo:
            for field in docinfo[0]:
                if isinstance(field, nodes.author):
                    metadata["author"] = field.astext()
                elif isinstance(field, nodes.date):
                    metadata["date"] = field.astext()
                elif isinstance(field, nodes.field):
                    field_name = field[0].astext() if len(field) > 0 else ""
                    field_body = field[1].astext() if len(field) > 1 else ""
                    metadata["docinfo"][field_name] = field_body
        
        return metadata
    
    def _extract_toc(self, doctree) -> Dict:
        """Extract table of contents structure."""
        toc = {
            "sections": []
        }
        
        def extract_sections(node, level=0):
            sections = []
            for section in node.traverse(nodes.section):
                if section.parent == node:  # Direct children only
                    title_node = section.traverse(nodes.title)[0] if section.traverse(nodes.title) else None
                    if title_node:
                        section_data = {
                            "title": title_node.astext(),
                            "level": level,
                            "subsections": extract_sections(section, level + 1)
                        }
                        sections.append(section_data)
            return sections
        
        toc["sections"] = extract_sections(doctree)
        return toc
    
    def _find_directives(self, content: str) -> Dict[str, int]:
        """Find all directives used in the document."""
        directives_found = {}
        
        # Pattern for directives
        directive_pattern = r'^\.\. ([a-z-]+)::'
        
        for match in re.finditer(directive_pattern, content, re.MULTILINE):
            directive = match.group(1)
            directives_found[directive] = directives_found.get(directive, 0) + 1
        
        return directives_found
    
    def _find_roles(self, content: str) -> Dict[str, int]:
        """Find all roles used in the document."""
        roles_found = {}
        
        # Pattern for roles
        role_pattern = r':([a-z-]+):`[^`]+`'
        
        for match in re.finditer(role_pattern, content):
            role = match.group(1)
            roles_found[role] = roles_found.get(role, 0) + 1
        
        return roles_found
    
    def _calculate_statistics(self, blocks: List[Dict], 
                            directives: Dict[str, int], 
                            roles: Dict[str, int]) -> Dict:
        """Calculate document statistics."""
        stats = {
            "total_blocks": len(blocks),
            "block_types": {},
            "heading_levels": {},
            "total_directives": sum(directives.values()),
            "unique_directives": len(directives),
            "total_roles": sum(roles.values()),
            "unique_roles": len(roles),
            "code_blocks": 0,
            "tables": 0,
            "figures": 0,
            "math_blocks": 0
        }
        
        for block in blocks:
            block_type = block.get("type", "unknown")
            stats["block_types"][block_type] = stats["block_types"].get(block_type, 0) + 1
            
            if block_type == "heading":
                level = block.get("level", 0)
                stats["heading_levels"][level] = stats["heading_levels"].get(level, 0) + 1
            elif block_type == "code":
                stats["code_blocks"] += 1
            elif block_type == "table":
                stats["tables"] += 1
            elif block_type == "figure":
                stats["figures"] += 1
            elif block_type == "math":
                stats["math_blocks"] += 1
        
        return stats
    
    def _get_cache_key(self, file_path: Path) -> str:
        """Generate cache key."""
        stat = file_path.stat()
        data = f"{file_path.absolute()}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def _check_cache(self, cache_key: str) -> Optional[Dict]:
        """Check cache for existing extraction."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except:
                pass
        return None
    
    async def _cache_result(self, cache_key: str, result: Dict):
        """Cache extraction result."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to cache: {e}")
    
    def display_toc(self, toc: Dict):
        """Display table of contents as a tree."""
        tree = Tree("[bold]Table of Contents[/bold]")
        
        def add_sections(parent_node, sections):
            for section in sections:
                section_node = parent_node.add(section["title"])
                if section.get("subsections"):
                    add_sections(section_node, section["subsections"])
        
        if toc.get("sections"):
            add_sections(tree, toc["sections"])
        
        console.print(tree)


# Initialize extractor
extractor = RSTExtractor()


@app.command()
def extract(
    rst_file: Path = typer.Argument(..., help="RST file to extract"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Include raw RST source"),
    no_toc: bool = typer.Option(False, "--no-toc", help="Don't extract table of contents"),
    no_metadata: bool = typer.Option(False, "--no-metadata", help="Don't extract metadata"),
    show_toc: bool = typer.Option(False, "--toc", "-t", help="Display table of contents")
):
    """Extract content from ReStructuredText document."""
    async def run():
        try:
            result = await extractor.extract_rst(
                rst_file,
                extract_raw=raw,
                extract_toc=not no_toc,
                extract_metadata=not no_metadata
            )
            
            if show_toc and result.get("toc"):
                extractor.display_toc(result["toc"])
            
            if output:
                with open(output, 'w') as f:
                    json.dump(result, f, indent=2)
                console.print(f"[green] Saved to {output}[/green]")
            else:
                # Display summary
                stats = result["statistics"]
                metadata = result.get("metadata", {})
                
                table = Table(title="RST Extraction Summary")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                if metadata.get("title"):
                    table.add_row("Title", metadata["title"])
                if metadata.get("author"):
                    table.add_row("Author", metadata["author"])
                
                table.add_row("Total Blocks", str(stats["total_blocks"]))
                table.add_row("Code Blocks", str(stats["code_blocks"]))
                table.add_row("Tables", str(stats["tables"]))
                table.add_row("Figures", str(stats["figures"]))
                table.add_row("Math Blocks", str(stats["math_blocks"]))
                
                if stats["unique_directives"]:
                    table.add_row("Directives Used", str(stats["unique_directives"]))
                if stats["unique_roles"]:
                    table.add_row("Roles Used", str(stats["unique_roles"]))
                
                console.print(table)
                
                # Show directive usage
                if result.get("directives"):
                    console.print("\n[bold]Directives Found:[/bold]")
                    for directive, count in sorted(result["directives"].items()):
                        console.print(f"  {directive}: {count}")
        
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command()
def preview(
    rst_file: Path = typer.Argument(..., help="RST file to preview"),
    lines: int = typer.Option(50, "--lines", "-l", help="Number of lines to show")
):
    """Preview RST file with syntax highlighting."""
    try:
        with open(rst_file, 'r') as f:
            content = f.read()
        
        # Truncate if needed
        content_lines = content.split('\n')
        if len(content_lines) > lines:
            content = '\n'.join(content_lines[:lines])
            truncated = True
        else:
            truncated = False
        
        # Display with syntax highlighting
        syntax = Syntax(content, "rst", theme="monokai", line_numbers=True)
        console.print(syntax)
        
        if truncated:
            console.print(f"\n[dim]... showing first {lines} lines of {len(content_lines)} total[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# Worker functions
async def working_usage():
    """Demonstrate RST extraction."""
    logger.info("Testing RST extraction...")
    
    # Create test RST
    test_rst = """====================
Test RST Document
====================

:Author: John Doe
:Date: 2024-01-01

Introduction
============

This is a test RST document for extraction demonstration.

Features
--------

The extractor supports:

* Bullet lists
* Numbered lists
* Code blocks
* Tables
* Math expressions

Code Example
------------

Here's a code example::

    def hello_world():
        print("Hello, RST!")
    
    hello_world()

Mathematics
-----------

Inline math: :math:`E = mc^2`

.. math::

   \\frac{\\partial u}{\\partial t} = \\nabla^2 u

Tables
------

.. csv-table:: Sample Data
   :header: "Name", "Value", "Description"
   :widths: 20, 10, 50

   "Alpha", "1.0", "First value"
   "Beta", "2.0", "Second value"
   "Gamma", "3.0", "Third value"

.. note::
   This is a note admonition.

.. warning::
   This is a warning admonition.

Conclusion
==========

This concludes our RST extraction demo.
"""
    
    # Save test file
    test_file = Path("/tmp/test_extract.rst")
    with open(test_file, 'w') as f:
        f.write(test_rst)
    
    # Extract
    result = await extractor.extract_rst(test_file)
    
    logger.info(f"\nExtraction complete:")
    logger.info(f"  Title: {result['metadata'].get('title', 'N/A')}")
    logger.info(f"  Author: {result['metadata'].get('author', 'N/A')}")
    logger.info(f"  Total blocks: {result['statistics']['total_blocks']}")
    logger.info(f"  Code blocks: {result['statistics']['code_blocks']}")
    
    # Show TOC
    if result.get("toc"):
        logger.info("\nTable of Contents:")
        extractor.display_toc(result["toc"])


async def debug_function():
    """Test edge cases in RST extraction."""
    logger.info("Testing RST edge cases...")
    
    # Test with complex directives
    complex_rst = """Complex RST Test
================

.. toctree::
   :maxdepth: 2
   :caption: Contents:
   
   intro
   guide/index
   api/reference

.. automodule:: mymodule
   :members:
   :undoc-members:
   :show-inheritance:

.. code-block:: python
   :linenos:
   :emphasize-lines: 2,4
   
   def complex_function(x, y):
       # This is highlighted
       result = x + y
       # This too
       return result

.. list-table:: Complex Table
   :widths: 25 25 50
   :header-rows: 1
   
   * - Heading 1
     - Heading 2
     - Heading 3
   * - Row 1, Col 1
     - Row 1, Col 2
     - Row 1, Col 3
   * - Row 2, Col 1
     - Row 2, Col 2
     - Row 2, Col 3

.. figure:: _static/image.png
   :scale: 50 %
   :alt: Alternative text
   
   This is the figure caption.

Custom Roles
------------

This uses :abbr:`RST (ReStructuredText)` and :pep:`8` references.

Also :doc:`another_doc` and :ref:`some-label`.
"""
    
    test_file = Path("/tmp/test_complex.rst")
    with open(test_file, 'w') as f:
        f.write(complex_rst)
    
    result = await extractor.extract_rst(test_file)
    
    logger.info(f"\nComplex RST extracted:")
    logger.info(f"  Unique directives: {result['statistics']['unique_directives']}")
    logger.info(f"  Unique roles: {result['statistics']['unique_roles']}")
    
    if result.get("directives"):
        logger.info("\nDirectives found:")
        for directive, count in result["directives"].items():
            logger.info(f"  {directive}: {count}")
    
    if result.get("roles"):
        logger.info("\nRoles found:")
        for role, count in result["roles"].items():
            logger.info(f"  {role}: {count}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()