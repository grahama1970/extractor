#!/usr/bin/env python3
"""
XML Document Extractor Worker

Extracts content from XML documents while preserving structure and semantics.
Handles various XML formats including DocBook, TEI, DITA, and custom schemas.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib
import xml.etree.ElementTree as ET
from xml.dom import minidom

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Extract content from XML documents")
console = Console()


class XMLExtractor:
    """Extract content from XML documents."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "extractor" / "xml"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Common XML namespaces
        self.namespaces = {
            'docbook': 'http://docbook.org/ns/docbook',
            'tei': 'http://www.tei-c.org/ns/1.0',
            'dita': 'http://dita.oasis-open.org/architecture/2005/',
            'xhtml': 'http://www.w3.org/1999/xhtml',
            'mathml': 'http://www.w3.org/1998/Math/MathML',
            'svg': 'http://www.w3.org/2000/svg'
        }
        
        # Element mappings for common schemas
        self.element_mappings = {
            'docbook': {
                'title': 'Title',
                'chapter': 'Section',
                'section': 'Section',
                'para': 'Paragraph',
                'itemizedlist': 'List',
                'orderedlist': 'List',
                'table': 'Table',
                'programlisting': 'Code',
                'equation': 'Equation',
                'figure': 'Figure'
            },
            'tei': {
                'head': 'Title',
                'div': 'Section',
                'p': 'Paragraph',
                'list': 'List',
                'table': 'Table',
                'code': 'Code',
                'formula': 'Equation',
                'figure': 'Figure'
            }
        }
        
    async def extract_xml(self,
                         xml_path: Path,
                         schema: Optional[str] = None,
                         preserve_namespaces: bool = True,
                         extract_attributes: bool = True,
                         extract_comments: bool = True) -> Dict:
        """Extract content from XML file.
        
        Args:
            xml_path: Path to XML file
            schema: XML schema type (docbook, tei, dita, or auto-detect)
            preserve_namespaces: Whether to preserve namespace information
            extract_attributes: Whether to extract element attributes
            extract_comments: Whether to extract XML comments
            
        Returns:
            Extracted content with metadata
        """
        # Validate path
        xml_path = Path(xml_path).resolve()
        if not xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")
        if xml_path.suffix.lower() not in ['.xml', '.xsl', '.xslt', '.xsd']:
            raise ValueError(f"Not an XML file: {xml_path}")
        
        # Check cache
        cache_key = self._get_cache_key(xml_path, schema)
        cached = await self._check_cache(cache_key)
        if cached:
            logger.info(f"Using cached extraction for {xml_path.name}")
            return cached
        
        try:
            # Parse XML
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Auto-detect schema if not specified
            if not schema:
                schema = self._detect_schema(root)
            
            # Extract content based on schema
            blocks = await self._extract_blocks(
                root, 
                schema, 
                preserve_namespaces,
                extract_attributes
            )
            
            # Extract metadata
            metadata = self._extract_metadata(root, schema)
            
            # Extract comments if requested
            if extract_comments:
                comments = self._extract_comments(xml_path)
                blocks.extend(comments)
            
            # Build hierarchy
            hierarchy = self._build_hierarchy(root, schema)
            
            result = {
                "blocks": blocks,
                "metadata": metadata,
                "hierarchy": hierarchy,
                "statistics": self._calculate_statistics(blocks),
                "schema": schema
            }
            
            # Cache result
            await self._cache_result(cache_key, result)
            
            return result
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            raise ValueError(f"Invalid XML: {e}")
    
    def _detect_schema(self, root: ET.Element) -> str:
        """Auto-detect XML schema from root element."""
        # Check namespace
        ns = root.tag.split('}')[0][1:] if '}' in root.tag else ''
        
        for schema_name, namespace in self.namespaces.items():
            if namespace in ns:
                return schema_name
        
        # Check root element name
        tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        
        if tag in ['book', 'article', 'chapter']:
            return 'docbook'
        elif tag in ['TEI', 'text']:
            return 'tei'
        elif tag in ['topic', 'concept', 'task']:
            return 'dita'
        
        return 'generic'
    
    async def _extract_blocks(self, 
                            element: ET.Element,
                            schema: str,
                            preserve_namespaces: bool,
                            extract_attributes: bool,
                            parent_path: str = "") -> List[Dict]:
        """Extract content blocks from XML element tree."""
        blocks = []
        
        # Get element tag without namespace
        tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
        
        # Build element path
        element_path = f"{parent_path}/{tag}" if parent_path else tag
        
        # Determine block type
        block_type = self._get_block_type(tag, schema)
        
        # Extract text content
        text = self._extract_text(element)
        
        # Create block if there's content or it's a structural element
        if text or block_type in ['Section', 'List', 'Table', 'Figure']:
            block = {
                "type": block_type,
                "tag": tag,
                "path": element_path,
                "content": text
            }
            
            # Add namespace if preserving
            if preserve_namespaces and '}' in element.tag:
                ns = element.tag.split('}')[0][1:]
                block["namespace"] = ns
            
            # Add attributes if extracting
            if extract_attributes and element.attrib:
                block["attributes"] = dict(element.attrib)
            
            # Special handling for specific types
            if block_type == 'Table':
                block["table_data"] = self._extract_table(element, schema)
            elif block_type == 'List':
                block["items"] = self._extract_list_items(element, schema)
            elif block_type == 'Code':
                block["language"] = element.get('language', element.get('lang', ''))
            elif block_type == 'Figure':
                block["caption"] = self._extract_figure_caption(element, schema)
                block["src"] = element.get('src', element.get('href', ''))
            
            blocks.append(block)
        
        # Process child elements
        for child in element:
            child_blocks = await self._extract_blocks(
                child, 
                schema,
                preserve_namespaces,
                extract_attributes,
                element_path
            )
            blocks.extend(child_blocks)
        
        return blocks
    
    def _get_block_type(self, tag: str, schema: str) -> str:
        """Map XML element to block type."""
        if schema in self.element_mappings:
            mapping = self.element_mappings[schema]
            return mapping.get(tag, 'Element')
        
        # Generic mapping
        generic_mapping = {
            'title': 'Title',
            'heading': 'Heading',
            'h1': 'Heading',
            'h2': 'Heading',
            'h3': 'Heading',
            'p': 'Paragraph',
            'para': 'Paragraph',
            'paragraph': 'Paragraph',
            'ul': 'List',
            'ol': 'List',
            'list': 'List',
            'table': 'Table',
            'code': 'Code',
            'pre': 'Code',
            'img': 'Image',
            'image': 'Image',
            'figure': 'Figure',
            'equation': 'Equation',
            'math': 'Equation'
        }
        
        return generic_mapping.get(tag.lower(), 'Element')
    
    def _extract_text(self, element: ET.Element) -> str:
        """Extract all text from element and descendants."""
        texts = []
        
        # Get element's text
        if element.text:
            texts.append(element.text.strip())
        
        # Get text from children
        for child in element:
            # Add child's tail text
            if child.tail:
                texts.append(child.tail.strip())
        
        # For leaf elements, get all text content
        if not list(element):  # No children
            text = ''.join(element.itertext()).strip()
            if text:
                return text
        
        return ' '.join(texts) if texts else ''
    
    def _extract_table(self, element: ET.Element, schema: str) -> Dict:
        """Extract table data from element."""
        table_data = {
            "rows": [],
            "headers": [],
            "caption": ""
        }
        
        # Schema-specific extraction
        if schema == 'docbook':
            # Look for thead/tbody structure
            thead = element.find('.//thead')
            if thead:
                for row in thead.findall('.//row'):
                    header_row = []
                    for cell in row.findall('.//entry'):
                        header_row.append(self._extract_text(cell))
                    if header_row:
                        table_data["headers"].append(header_row)
            
            tbody = element.find('.//tbody')
            if tbody:
                for row in tbody.findall('.//row'):
                    data_row = []
                    for cell in row.findall('.//entry'):
                        data_row.append(self._extract_text(cell))
                    if data_row:
                        table_data["rows"].append(data_row)
            
            # Caption
            caption = element.find('.//caption')
            if caption is not None:
                table_data["caption"] = self._extract_text(caption)
        
        else:
            # Generic table extraction
            for row in element.findall('.//tr'):
                cells = []
                for cell in row.findall('.//td') + row.findall('.//th'):
                    cells.append(self._extract_text(cell))
                if cells:
                    if row.findall('.//th'):  # Header row
                        table_data["headers"].append(cells)
                    else:
                        table_data["rows"].append(cells)
        
        return table_data
    
    def _extract_list_items(self, element: ET.Element, schema: str) -> List[str]:
        """Extract list items from element."""
        items = []
        
        # Schema-specific extraction
        if schema == 'docbook':
            for item in element.findall('.//listitem'):
                text = self._extract_text(item)
                if text:
                    items.append(text)
        elif schema == 'tei':
            for item in element.findall('.//item'):
                text = self._extract_text(item)
                if text:
                    items.append(text)
        else:
            # Generic extraction
            for item in element.findall('.//li'):
                text = self._extract_text(item)
                if text:
                    items.append(text)
        
        return items
    
    def _extract_figure_caption(self, element: ET.Element, schema: str) -> str:
        """Extract figure caption."""
        if schema == 'docbook':
            caption = element.find('.//caption')
            if caption is not None:
                return self._extract_text(caption)
        elif schema == 'tei':
            figDesc = element.find('.//figDesc')
            if figDesc is not None:
                return self._extract_text(figDesc)
        else:
            # Look for common caption elements
            for tag in ['caption', 'figcaption', 'title']:
                caption = element.find(f'.//{tag}')
                if caption is not None:
                    return self._extract_text(caption)
        
        return ""
    
    def _extract_metadata(self, root: ET.Element, schema: str) -> Dict:
        """Extract document metadata."""
        metadata = {
            "title": "",
            "author": "",
            "date": "",
            "language": "",
            "description": "",
            "keywords": [],
            "custom": {}
        }
        
        # Schema-specific metadata extraction
        if schema == 'docbook':
            info = root.find('.//info') or root.find('.//bookinfo') or root.find('.//articleinfo')
            if info is not None:
                title = info.find('.//title')
                if title is not None:
                    metadata["title"] = self._extract_text(title)
                
                author = info.find('.//author')
                if author is not None:
                    name_parts = []
                    for part in ['firstname', 'surname', 'personname']:
                        elem = author.find(f'.//{part}')
                        if elem is not None:
                            name_parts.append(self._extract_text(elem))
                    metadata["author"] = ' '.join(name_parts)
                
                date = info.find('.//date') or info.find('.//pubdate')
                if date is not None:
                    metadata["date"] = self._extract_text(date)
        
        elif schema == 'tei':
            header = root.find('.//teiHeader')
            if header is not None:
                title = header.find('.//titleStmt/title')
                if title is not None:
                    metadata["title"] = self._extract_text(title)
                
                author = header.find('.//titleStmt/author')
                if author is not None:
                    metadata["author"] = self._extract_text(author)
                
                date = header.find('.//publicationStmt/date')
                if date is not None:
                    metadata["date"] = date.get('when', self._extract_text(date))
        
        # Language detection
        metadata["language"] = root.get('{http://www.w3.org/XML/1998/namespace}lang', 
                                      root.get('lang', ''))
        
        return metadata
    
    def _extract_comments(self, xml_path: Path) -> List[Dict]:
        """Extract XML comments from file."""
        blocks = []
        
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse with minidom to preserve comments
            dom = minidom.parseString(content)
            
            def extract_comments_recursive(node, path=""):
                if node.nodeType == node.COMMENT_NODE:
                    blocks.append({
                        "type": "Comment",
                        "content": node.data.strip(),
                        "path": path
                    })
                
                if hasattr(node, 'childNodes'):
                    for child in node.childNodes:
                        child_path = f"{path}/{child.nodeName}" if path else child.nodeName
                        extract_comments_recursive(child, child_path)
            
            extract_comments_recursive(dom)
            
        except Exception as e:
            logger.warning(f"Failed to extract comments: {e}")
        
        return blocks
    
    def _build_hierarchy(self, root: ET.Element, schema: str) -> Dict:
        """Build document hierarchy."""
        def build_node(element: ET.Element, level: int = 0) -> Dict:
            tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            node = {
                "tag": tag,
                "level": level,
                "text": self._extract_text(element),
                "children": []
            }
            
            # Add attributes
            if element.attrib:
                node["attributes"] = dict(element.attrib)
            
            # Process children that are structural elements
            structural_tags = {'chapter', 'section', 'div', 'part', 'subsection'}
            for child in element:
                child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if child_tag.lower() in structural_tags or self._get_block_type(child_tag, schema) == 'Section':
                    child_node = build_node(child, level + 1)
                    node["children"].append(child_node)
            
            return node
        
        return build_node(root)
    
    def _calculate_statistics(self, blocks: List[Dict]) -> Dict:
        """Calculate extraction statistics."""
        stats = {
            "total_blocks": len(blocks),
            "block_types": {},
            "total_characters": 0,
            "elements_by_path": {},
            "namespaces": set()
        }
        
        for block in blocks:
            # Count by type
            block_type = block.get("type", "Unknown")
            stats["block_types"][block_type] = stats["block_types"].get(block_type, 0) + 1
            
            # Count characters
            if "content" in block:
                stats["total_characters"] += len(block["content"])
            
            # Track paths
            path = block.get("path", "")
            if path:
                stats["elements_by_path"][path] = stats["elements_by_path"].get(path, 0) + 1
            
            # Track namespaces
            if "namespace" in block:
                stats["namespaces"].add(block["namespace"])
        
        # Convert set to list for JSON serialization
        stats["namespaces"] = list(stats["namespaces"])
        
        return stats
    
    def _get_cache_key(self, file_path: Path, schema: Optional[str]) -> str:
        """Generate cache key."""
        stat = file_path.stat()
        data = f"{file_path.absolute()}:{stat.st_size}:{stat.st_mtime}:{schema}"
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
    
    async def validate_xml(self, xml_path: Path, schema_path: Optional[Path] = None) -> Dict:
        """Validate XML against schema."""
        result = {
            "valid": False,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Basic XML validation
            tree = ET.parse(xml_path)
            result["valid"] = True
            
            # Schema validation if provided
            if schema_path and schema_path.exists():
                # This would require lxml for full schema validation
                result["warnings"].append("Schema validation requires lxml library")
            
        except ET.ParseError as e:
            result["errors"].append(str(e))
        
        return result
    
    def display_hierarchy(self, hierarchy: Dict):
        """Display hierarchy as a tree."""
        tree = Tree(f"[bold]{hierarchy['tag']}[/bold]")
        
        def add_children(node: Dict, tree_node):
            for child in node.get("children", []):
                child_node = tree_node.add(f"{child['tag']}")
                add_children(child, child_node)
        
        add_children(hierarchy, tree)
        console.print(tree)


# Initialize extractor
extractor = XMLExtractor()


@app.command()
def extract(
    xml_file: Path = typer.Argument(..., help="XML file to extract"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    schema: Optional[str] = typer.Option(None, "--schema", "-s", help="XML schema type"),
    no_namespaces: bool = typer.Option(False, "--no-namespaces", help="Don't preserve namespaces"),
    no_attributes: bool = typer.Option(False, "--no-attributes", help="Don't extract attributes"),
    no_comments: bool = typer.Option(False, "--no-comments", help="Don't extract comments"),
    show_hierarchy: bool = typer.Option(False, "--hierarchy", "-h", help="Display document hierarchy")
):
    """Extract content from XML document."""
    async def run():
        try:
            result = await extractor.extract_xml(
                xml_file,
                schema=schema,
                preserve_namespaces=not no_namespaces,
                extract_attributes=not no_attributes,
                extract_comments=not no_comments
            )
            
            if show_hierarchy:
                extractor.display_hierarchy(result["hierarchy"])
            
            if output:
                with open(output, 'w') as f:
                    json.dump(result, f, indent=2)
                console.print(f"[green] Saved to {output}[/green]")
            else:
                # Display summary
                stats = result["statistics"]
                table = Table(title=f"XML Extraction Summary ({result['schema']} schema)")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Total Blocks", str(stats["total_blocks"]))
                table.add_row("Total Characters", f"{stats['total_characters']:,}")
                table.add_row("Namespaces", str(len(stats.get("namespaces", []))))
                
                # Block type breakdown
                for block_type, count in stats["block_types"].items():
                    table.add_row(f"  {block_type}", str(count))
                
                console.print(table)
        
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command()
def validate(
    xml_file: Path = typer.Argument(..., help="XML file to validate"),
    schema: Optional[Path] = typer.Option(None, "--schema", "-s", help="XSD schema file")
):
    """Validate XML document."""
    async def run():
        result = await extractor.validate_xml(xml_file, schema)
        
        if result["valid"]:
            console.print("[green] XML is valid[/green]")
        else:
            console.print("[red] XML is invalid[/red]")
            for error in result["errors"]:
                console.print(f"  Error: {error}")
        
        if result["warnings"]:
            for warning in result["warnings"]:
                console.print(f"  [yellow]Warning: {warning}[/yellow]")
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate XML extraction."""
    logger.info("Testing XML extraction...")
    
    # Create test XML
    test_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <book xmlns="http://docbook.org/ns/docbook" version="5.0">
        <info>
            <title>Test Document</title>
            <author>
                <personname>
                    <firstname>John</firstname>
                    <surname>Doe</surname>
                </personname>
            </author>
            <pubdate>2024-01-01</pubdate>
        </info>
        
        <chapter>
            <title>Introduction</title>
            <para>This is the introduction paragraph.</para>
            
            <section>
                <title>Background</title>
                <para>Some background information.</para>
                
                <itemizedlist>
                    <listitem><para>First item</para></listitem>
                    <listitem><para>Second item</para></listitem>
                </itemizedlist>
            </section>
        </chapter>
        
        <chapter>
            <title>Conclusion</title>
            <para>This is the conclusion.</para>
        </chapter>
    </book>
    """
    
    # Save test file
    test_file = Path("/tmp/test_extract.xml")
    with open(test_file, 'w') as f:
        f.write(test_xml)
    
    # Extract
    result = await extractor.extract_xml(test_file)
    
    logger.info(f"\nDetected schema: {result['schema']}")
    logger.info(f"Extracted blocks: {result['statistics']['total_blocks']}")
    logger.info(f"Document title: {result['metadata']['title']}")
    logger.info(f"Author: {result['metadata']['author']}")
    
    # Show hierarchy
    logger.info("\nDocument structure:")
    extractor.display_hierarchy(result["hierarchy"])


async def debug_function():
    """Test edge cases in XML extraction."""
    logger.info("Testing XML edge cases...")
    
    # Test with namespaced XML
    namespaced_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ns:root xmlns:ns="http://example.com/namespace" 
             xmlns:other="http://example.com/other">
        <ns:element attr="value">
            <other:child>Mixed namespace content</other:child>
        </ns:element>
        <!-- This is a comment -->
        <![CDATA[This is CDATA content with <markup>]]>
    </ns:root>
    """
    
    test_file = Path("/tmp/test_namespaced.xml")
    with open(test_file, 'w') as f:
        f.write(namespaced_xml)
    
    result = await extractor.extract_xml(test_file)
    logger.info(f"Namespaces found: {result['statistics']['namespaces']}")
    
    # Test malformed XML
    malformed_xml = """<?xml version="1.0"?>
    <root>
        <unclosed>
        <another>Content
    </root>
    """
    
    test_file2 = Path("/tmp/test_malformed.xml")
    with open(test_file2, 'w') as f:
        f.write(malformed_xml)
    
    try:
        result = await extractor.extract_xml(test_file2)
    except ValueError as e:
        logger.info(f"Correctly caught malformed XML: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()