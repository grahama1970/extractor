#!/usr/bin/env python3
"""
EPUB Document Extractor Worker

Extracts content from EPUB files while preserving structure, chapters,
images, styles, and table of contents.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib
import base64
import re

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel

try:
    from ebooklib import epub
    from bs4 import BeautifulSoup, Tag, NavigableString, Comment
    EPUB_AVAILABLE = True
except ImportError:
    EPUB_AVAILABLE = False
    logger.warning("ebooklib and BeautifulSoup not available - EPUB support disabled")

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Extract content from EPUB documents")
console = Console()


class EPUBExtractor:
    """Extract content from EPUB documents."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "extractor" / "epub"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.block_counter = 0
        
    async def extract_epub(self,
                          epub_path: Path,
                          extract_images: bool = True,
                          extract_styles: bool = True,
                          extract_toc: bool = True,
                          embed_images: bool = False,
                          max_image_size_mb: int = 10) -> Dict:
        """Extract content from EPUB file.
        
        Args:
            epub_path: Path to EPUB file
            extract_images: Whether to extract embedded images
            extract_styles: Whether to extract CSS styles
            extract_toc: Whether to extract table of contents
            embed_images: Whether to embed images as base64
            max_image_size_mb: Maximum image size to embed
            
        Returns:
            Extracted content with metadata
        """
        # Validate path
        epub_path = Path(epub_path).resolve()
        if not epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")
        if epub_path.suffix.lower() not in ['.epub', '.epub3']:
            raise ValueError(f"Not an EPUB file: {epub_path}")
        
        if not EPUB_AVAILABLE:
            raise ImportError("ebooklib is required for EPUB extraction")
        
        # Check cache
        cache_key = self._get_cache_key(epub_path, extract_images, embed_images)
        cached = await self._check_cache(cache_key)
        if cached:
            logger.info(f"Using cached extraction for {epub_path.name}")
            return cached
        
        # Read EPUB
        book = epub.read_epub(str(epub_path))
        
        # Extract metadata
        metadata = self._extract_metadata(book, epub_path)
        
        # Extract chapters (spine items)
        chapters = []
        items = [book.get_item_with_id(i[0]) for i in book.spine]
        items = [i for i in items if i and i.media_type == "application/xhtml+xml"]
        
        for idx, item in enumerate(items):
            chapter_data = await self._extract_chapter(item, idx)
            chapters.append(chapter_data)
        
        # Extract images
        images = []
        if extract_images:
            images = await self._extract_images(book, embed_images, max_image_size_mb)
        
        # Extract styles
        styles = []
        if extract_styles:
            styles = self._extract_styles(book)
        
        # Extract TOC
        toc = {}
        if extract_toc and book.toc:
            toc = self._extract_toc(book.toc, chapters)
        
        result = {
            "chapters": chapters,
            "metadata": metadata,
            "images": images,
            "styles": styles,
            "toc": toc,
            "statistics": self._calculate_statistics(chapters, images, styles)
        }
        
        # Cache result
        await self._cache_result(cache_key, result)
        
        return result
    
    async def _extract_chapter(self, item: epub.EpubItem, chapter_idx: int) -> Dict:
        """Extract content from a single chapter."""
        self.block_counter = 0  # Reset for each chapter
        
        chapter_data = {
            "index": chapter_idx,
            "id": item.id or f"chapter_{chapter_idx}",
            "filename": item.file_name,
            "title": item.title or f"Chapter {chapter_idx + 1}",
            "blocks": []
        }
        
        # Parse XHTML content
        soup = BeautifulSoup(item.get_content(), "lxml")
        
        # Remove script/style tags
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        
        # Extract blocks
        body = soup.body or soup
        await self._parse_html_content(body, chapter_data["blocks"])
        
        return chapter_data
    
    async def _parse_html_content(self, node: Any, blocks: List[Dict], parent_id: Optional[str] = None):
        """Parse HTML content into structured blocks."""
        if isinstance(node, Comment):
            return
        
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                blocks.append({
                    "id": self._generate_block_id(),
                    "type": "text",
                    "content": text,
                    "parent_id": parent_id
                })
            return
        
        if not hasattr(node, 'name'):
            return
        
        tag = node.name.lower()
        
        # Headings
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            text = node.get_text(" ", strip=True)
            if text:
                block = {
                    "id": self._generate_block_id(),
                    "type": "heading",
                    "level": level,
                    "content": text,
                    "parent_id": parent_id
                }
                blocks.append(block)
                parent_id = block["id"]  # Children nest under heading
        
        # Paragraphs
        elif tag == "p":
            text = node.get_text(" ", strip=True)
            if text:
                blocks.append({
                    "id": self._generate_block_id(),
                    "type": "paragraph",
                    "content": text,
                    "parent_id": parent_id
                })
        
        # Lists
        elif tag in {"ul", "ol"}:
            list_block = {
                "id": self._generate_block_id(),
                "type": "list",
                "list_type": "ordered" if tag == "ol" else "unordered",
                "items": [],
                "parent_id": parent_id
            }
            
            for idx, li in enumerate(node.find_all("li", recursive=False)):
                li_text = li.get_text(" ", strip=True)
                if li_text:
                    list_block["items"].append({
                        "index": idx,
                        "content": li_text
                    })
            
            if list_block["items"]:
                blocks.append(list_block)
        
        # Tables
        elif tag == "table":
            table_block = await self._parse_table(node, parent_id)
            if table_block:
                blocks.append(table_block)
        
        # Images
        elif tag == "img":
            src = node.get("src", "")
            if src:
                blocks.append({
                    "id": self._generate_block_id(),
                    "type": "image",
                    "src": src,
                    "alt": node.get("alt", ""),
                    "title": node.get("title", ""),
                    "parent_id": parent_id
                })
        
        # Code blocks
        elif tag in {"pre", "code"}:
            # Check for language class
            lang = None
            classes = node.get("class", [])
            if isinstance(classes, list):
                for cls in classes:
                    if cls.startswith("language-"):
                        lang = cls.replace("language-", "")
                        break
            
            text = node.get_text()
            blocks.append({
                "id": self._generate_block_id(),
                "type": "code",
                "content": text,
                "language": lang,
                "parent_id": parent_id
            })
        
        # Blockquotes
        elif tag == "blockquote":
            text = node.get_text(" ", strip=True)
            if text:
                blocks.append({
                    "id": self._generate_block_id(),
                    "type": "blockquote",
                    "content": text,
                    "parent_id": parent_id
                })
        
        # Recurse into children
        else:
            for child in node.children:
                await self._parse_html_content(child, blocks, parent_id)
    
    async def _parse_table(self, table_node: Tag, parent_id: Optional[str]) -> Optional[Dict]:
        """Parse HTML table."""
        rows = table_node.find_all("tr")
        if not rows:
            return None
        
        table_data = {
            "id": self._generate_block_id(),
            "type": "table",
            "headers": [],
            "rows": [],
            "parent_id": parent_id
        }
        
        # Process rows
        for r_idx, tr in enumerate(rows):
            cells = tr.find_all(["td", "th"])
            row_data = []
            
            for cell in cells:
                cell_text = cell.get_text(" ", strip=True)
                colspan = int(cell.get("colspan", 1))
                rowspan = int(cell.get("rowspan", 1))
                
                cell_data = {
                    "content": cell_text,
                    "is_header": cell.name == "th"
                }
                
                if colspan > 1:
                    cell_data["colspan"] = colspan
                if rowspan > 1:
                    cell_data["rowspan"] = rowspan
                
                row_data.append(cell_data)
            
            # Check if this is a header row
            if r_idx == 0 and all(c.name == "th" for c in cells):
                table_data["headers"] = [c["content"] for c in row_data]
            else:
                table_data["rows"].append(row_data)
        
        return table_data if table_data["rows"] else None
    
    async def _extract_images(self, book: epub.EpubBook, 
                            embed: bool, 
                            max_size_mb: int) -> List[Dict]:
        """Extract embedded images from EPUB."""
        images = []
        max_bytes = max_size_mb * 1024 * 1024
        
        for item in book.get_items():
            if item.media_type and item.media_type.startswith("image/"):
                image_data = {
                    "id": item.id or item.file_name,
                    "filename": item.file_name,
                    "media_type": item.media_type,
                    "size": len(item.get_content())
                }
                
                if embed and image_data["size"] <= max_bytes:
                    # Embed as base64
                    content = item.get_content()
                    b64 = base64.b64encode(content).decode("utf-8")
                    image_data["data_uri"] = f"data:{item.media_type};base64,{b64}"
                else:
                    image_data["embedded"] = False
                
                images.append(image_data)
        
        return images
    
    def _extract_styles(self, book: epub.EpubBook) -> List[Dict]:
        """Extract CSS styles from EPUB."""
        styles = []
        
        for item in book.get_items():
            if item.media_type == "text/css":
                styles.append({
                    "id": item.id or item.file_name,
                    "filename": item.file_name,
                    "content": item.get_content().decode('utf-8', errors='ignore')
                })
        
        return styles
    
    def _extract_toc(self, toc, chapters: List[Dict]) -> Dict:
        """Extract table of contents with hierarchy."""
        def build_toc_tree(entries, level=0):
            items = []
            for entry in entries:
                if hasattr(entry, 'title') and hasattr(entry, 'href'):
                    item = {
                        "title": entry.title or "Untitled",
                        "href": entry.href,
                        "level": level
                    }
                    
                    # Try to link to chapter
                    for ch in chapters:
                        if entry.href and ch["filename"] in entry.href:
                            item["chapter_index"] = ch["index"]
                            break
                    
                    # Process children
                    if hasattr(entry, 'children') and entry.children:
                        item["children"] = build_toc_tree(entry.children, level + 1)
                    
                    items.append(item)
            
            return items
        
        return {
            "items": build_toc_tree(toc)
        }
    
    def _extract_metadata(self, book: epub.EpubBook, file_path: Path) -> Dict:
        """Extract EPUB metadata."""
        metadata = {
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size,
            "format": "EPUB"
        }
        
        # Dublin Core metadata
        dc_fields = [
            ("title", "title"),
            ("creator", "author"),
            ("publisher", "publisher"),
            ("date", "date"),
            ("language", "language"),
            ("identifier", "identifier"),
            ("description", "description"),
            ("subject", "subjects")
        ]
        
        for dc_field, key in dc_fields:
            values = book.get_metadata("DC", dc_field)
            if values:
                if key == "subjects":
                    metadata[key] = [v[0] for v in values if v]
                elif key == "author":
                    metadata[key] = "; ".join([v[0] for v in values if v])
                else:
                    metadata[key] = values[0][0] if values[0] else ""
        
        # Additional metadata
        metadata["spine_items"] = len(book.spine)
        metadata["total_items"] = len(list(book.get_items()))
        
        return metadata
    
    def _calculate_statistics(self, chapters: List[Dict], 
                            images: List[Dict], 
                            styles: List[Dict]) -> Dict:
        """Calculate extraction statistics."""
        stats = {
            "total_chapters": len(chapters),
            "total_blocks": 0,
            "block_types": {},
            "total_images": len(images),
            "total_styles": len(styles),
            "embedded_images": 0,
            "total_text_length": 0
        }
        
        for chapter in chapters:
            for block in chapter.get("blocks", []):
                stats["total_blocks"] += 1
                block_type = block.get("type", "unknown")
                stats["block_types"][block_type] = stats["block_types"].get(block_type, 0) + 1
                
                if "content" in block and isinstance(block["content"], str):
                    stats["total_text_length"] += len(block["content"])
        
        # Count embedded images
        stats["embedded_images"] = sum(1 for img in images if img.get("data_uri"))
        
        return stats
    
    def _generate_block_id(self) -> str:
        """Generate unique block ID."""
        self.block_counter += 1
        return f"block_{self.block_counter}"
    
    def _get_cache_key(self, file_path: Path, extract_images: bool, embed_images: bool) -> str:
        """Generate cache key."""
        stat = file_path.stat()
        data = f"{file_path.absolute()}:{stat.st_size}:{stat.st_mtime}:{extract_images}:{embed_images}"
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
        """Display table of contents as tree."""
        tree = Tree("[bold]Table of Contents[/bold]")
        
        def add_items(parent_node, items):
            for item in items:
                node_text = f"{item['title']}"
                if "chapter_index" in item:
                    node_text += f" [dim](Chapter {item['chapter_index'] + 1})[/dim]"
                
                node = parent_node.add(node_text)
                
                if "children" in item:
                    add_items(node, item["children"])
        
        if toc.get("items"):
            add_items(tree, toc["items"])
        
        console.print(tree)
    
    def display_chapter_preview(self, chapter: Dict, max_blocks: int = 5):
        """Display preview of chapter content."""
        title = chapter.get("title", f"Chapter {chapter['index'] + 1}")
        blocks = chapter.get("blocks", [])
        
        content = []
        content.append(f"[bold]File:[/bold] {chapter['filename']}")
        content.append(f"[bold]Blocks:[/bold] {len(blocks)}")
        
        if blocks:
            content.append("\n[bold]Content Preview:[/bold]")
            for block in blocks[:max_blocks]:
                block_type = block.get("type", "unknown")
                if block_type == "heading":
                    level = block.get("level", 1)
                    content.append(f"  {'#' * level} {block.get('content', '')}")
                elif block_type == "paragraph":
                    text = block.get("content", "")[:100]
                    if len(block.get("content", "")) > 100:
                        text += "..."
                    content.append(f"  {text}")
                elif block_type == "list":
                    list_type = block.get("list_type", "unordered")
                    items_count = len(block.get("items", []))
                    content.append(f"  {list_type.title()} list with {items_count} items")
                elif block_type == "image":
                    alt = block.get("alt", "No description")
                    content.append(f"  [Image: {alt}]")
            
            if len(blocks) > max_blocks:
                content.append(f"  ... and {len(blocks) - max_blocks} more blocks")
        
        console.print(Panel(
            "\n".join(content),
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan"
        ))


# Initialize extractor
extractor = EPUBExtractor()


@app.command()
def extract(
    epub_file: Path = typer.Argument(..., help="EPUB file to extract"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    no_images: bool = typer.Option(False, "--no-images", help="Don't extract images"),
    no_styles: bool = typer.Option(False, "--no-styles", help="Don't extract CSS styles"),
    no_toc: bool = typer.Option(False, "--no-toc", help="Don't extract table of contents"),
    embed_images: bool = typer.Option(False, "--embed", "-e", help="Embed images as base64"),
    show_toc: bool = typer.Option(False, "--toc", "-t", help="Display table of contents")
):
    """Extract content from EPUB document."""
    async def run():
        try:
            result = await extractor.extract_epub(
                epub_file,
                extract_images=not no_images,
                extract_styles=not no_styles,
                extract_toc=not no_toc,
                embed_images=embed_images
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
                
                table = Table(title="EPUB Extraction Summary")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                if metadata.get("title"):
                    table.add_row("Title", metadata["title"])
                if metadata.get("author"):
                    table.add_row("Author", metadata["author"])
                
                table.add_row("Chapters", str(stats["total_chapters"]))
                table.add_row("Total Blocks", str(stats["total_blocks"]))
                table.add_row("Text Length", f"{stats['total_text_length']:,} chars")
                table.add_row("Images", str(stats["total_images"]))
                
                if stats["embedded_images"] > 0:
                    table.add_row("Embedded Images", str(stats["embedded_images"]))
                
                table.add_row("CSS Files", str(stats["total_styles"]))
                
                console.print(table)
                
                # Show block type breakdown
                if stats.get("block_types"):
                    console.print("\n[bold]Block Types:[/bold]")
                    for block_type, count in sorted(stats["block_types"].items()):
                        console.print(f"  {block_type}: {count}")
        
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command()
def preview(
    epub_file: Path = typer.Argument(..., help="EPUB file to preview"),
    chapters: Optional[str] = typer.Option(None, "--chapters", "-c", help="Chapter indices to preview (e.g. 0,2-4)"),
    max_blocks: int = typer.Option(5, "--blocks", "-b", help="Max blocks per chapter to show")
):
    """Preview EPUB content structure."""
    async def run():
        try:
            result = await extractor.extract_epub(epub_file)
            
            # Parse chapter selection
            chapter_indices = None
            if chapters:
                chapter_indices = _parse_range(chapters)
            
            # Show metadata
            metadata = result.get("metadata", {})
            console.print(f"\n[bold]EPUB: {metadata.get('title', epub_file.name)}[/bold]")
            if metadata.get("author"):
                console.print(f"Author: {metadata['author']}")
            if metadata.get("publisher"):
                console.print(f"Publisher: {metadata['publisher']}")
            console.print()
            
            # Show chapter previews
            chapters_list = result.get("chapters", [])
            if chapter_indices:
                chapters_list = [ch for ch in chapters_list if ch["index"] in chapter_indices]
            
            for chapter in chapters_list[:10]:  # Max 10 chapters
                extractor.display_chapter_preview(chapter, max_blocks)
                console.print()
            
            if len(chapters_list) > 10:
                console.print(f"[dim]... and {len(chapters_list) - 10} more chapters[/dim]")
        
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command()
def metadata(
    epub_file: Path = typer.Argument(..., help="EPUB file to analyze")
):
    """Display EPUB metadata and structure."""
    async def run():
        try:
            result = await extractor.extract_epub(
                epub_file,
                extract_images=True,
                extract_styles=True,
                extract_toc=True
            )
            
            metadata = result.get("metadata", {})
            stats = result.get("statistics", {})
            
            # Metadata table
            meta_table = Table(title="EPUB Metadata")
            meta_table.add_column("Field", style="cyan")
            meta_table.add_column("Value", style="green")
            
            for field, value in metadata.items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                elif isinstance(value, int) and field == "file_size":
                    value = f"{value:,} bytes"
                meta_table.add_row(field.replace("_", " ").title(), str(value))
            
            console.print(meta_table)
            
            # TOC if available
            if result.get("toc") and result["toc"].get("items"):
                console.print("\n")
                extractor.display_toc(result["toc"])
            
            # Images info
            if result.get("images"):
                console.print(f"\n[bold]Images ({len(result['images'])}):[/bold]")
                for img in result["images"][:5]:
                    size_mb = img["size"] / (1024 * 1024)
                    console.print(f"  {img['filename']} ({img['media_type']}, {size_mb:.1f}MB)")
                if len(result["images"]) > 5:
                    console.print(f"  ... and {len(result['images']) - 5} more")
        
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


def _parse_range(range_str: str) -> List[int]:
    """Parse range string (e.g. '0,2-4,6')."""
    indices = []
    for part in range_str.split(','):
        if '-' in part:
            start, end = part.split('-')
            indices.extend(range(int(start), int(end) + 1))
        else:
            indices.append(int(part))
    return indices


# Worker functions
async def working_usage():
    """Demonstrate EPUB extraction."""
    logger.info("Testing EPUB extraction...")
    
    if not EPUB_AVAILABLE:
        logger.warning("ebooklib not installed - skipping demo")
        return
    
    # Create minimal test EPUB
    book = epub.EpubBook()
    book.set_identifier('test123')
    book.set_title('Test EPUB Document')
    book.set_language('en')
    book.add_author('Test Author')
    
    # Chapter 1
    c1 = epub.EpubHtml(title='Introduction', file_name='intro.xhtml')
    c1.content = '''<html>
    <head><title>Introduction</title></head>
    <body>
        <h1>Introduction</h1>
        <p>This is a test EPUB document for extraction demonstration.</p>
        <p>It contains multiple chapters and various content types.</p>
    </body>
</html>'''
    book.add_item(c1)
    
    # Chapter 2 with more content
    c2 = epub.EpubHtml(title='Main Content', file_name='chapter1.xhtml')
    c2.content = '''<html>
    <head><title>Chapter 1</title></head>
    <body>
        <h1>Chapter 1: Features</h1>
        <p>This chapter demonstrates various features:</p>
        
        <h2>Lists</h2>
        <ul>
            <li>Bullet point 1</li>
            <li>Bullet point 2</li>
            <li>Bullet point 3</li>
        </ul>
        
        <h2>Tables</h2>
        <table border="1">
            <tr><th>Name</th><th>Value</th></tr>
            <tr><td>Item 1</td><td>100</td></tr>
            <tr><td>Item 2</td><td>200</td></tr>
        </table>
        
        <h2>Code</h2>
        <pre><code class="language-python">
def hello_world():
    print("Hello from EPUB!")
</code></pre>
        
        <blockquote>
            <p>This is a blockquote with important information.</p>
        </blockquote>
    </body>
</html>'''
    book.add_item(c2)
    
    # Add to spine
    book.spine = ['nav', c1, c2]
    
    # Add navigation
    book.toc = [
        epub.Link('intro.xhtml', 'Introduction', 'intro'),
        epub.Link('chapter1.xhtml', 'Chapter 1: Features', 'ch1')
    ]
    
    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Save test EPUB
    test_file = Path("/tmp/test_document.epub")
    epub.write_epub(str(test_file), book)
    
    # Extract and display
    result = await extractor.extract_epub(test_file)
    
    logger.info(f"\nExtraction complete:")
    logger.info(f"  Title: {result['metadata'].get('title', 'N/A')}")
    logger.info(f"  Author: {result['metadata'].get('author', 'N/A')}")
    logger.info(f"  Chapters: {result['statistics']['total_chapters']}")
    logger.info(f"  Total blocks: {result['statistics']['total_blocks']}")
    
    # Show chapter content
    for chapter in result["chapters"]:
        logger.info(f"\nChapter {chapter['index'] + 1}: {chapter['title']}")
        logger.info(f"  Blocks: {len(chapter['blocks'])}")
        
        # Show first few blocks
        for block in chapter["blocks"][:3]:
            if block["type"] == "heading":
                logger.info(f"  - Heading (L{block['level']}): {block['content']}")
            elif block["type"] == "paragraph":
                preview = block["content"][:50] + "..." if len(block["content"]) > 50 else block["content"]
                logger.info(f"  - Paragraph: {preview}")


async def debug_function():
    """Test EPUB edge cases."""
    logger.info("Testing EPUB edge cases...")
    
    if not EPUB_AVAILABLE:
        logger.warning("ebooklib not installed - skipping tests")
        return
    
    # Create EPUB with complex content
    book = epub.EpubBook()
    book.set_identifier('complex123')
    book.set_title('Complex EPUB Test')
    book.set_language('en')
    book.add_metadata('DC', 'subject', 'Testing')
    book.add_metadata('DC', 'subject', 'EPUB')
    book.add_metadata('DC', 'description', 'A complex EPUB for testing edge cases')
    
    # Add CSS
    style = '''
@namespace epub "http://www.idpf.org/2007/ops";
body {
    font-family: Cambria, Liberation Serif, serif;
}
h1, h2 {
    text-align: left;
    text-transform: uppercase;
}
    '''
    nav_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content=style
    )
    book.add_item(nav_css)
    
    # Chapter with nested lists
    c1 = epub.EpubHtml(title='Nested Content', file_name='nested.xhtml')
    c1.content = '''<html>
    <body>
        <h1>Nested Content Test</h1>
        <ol>
            <li>First level
                <ul>
                    <li>Second level A</li>
                    <li>Second level B
                        <ol>
                            <li>Third level 1</li>
                            <li>Third level 2</li>
                        </ol>
                    </li>
                </ul>
            </li>
            <li>Back to first level</li>
        </ol>
        
        <table>
            <tr>
                <th colspan="2">Merged Header</th>
            </tr>
            <tr>
                <td rowspan="2">Tall cell</td>
                <td>Normal cell</td>
            </tr>
            <tr>
                <td>Another cell</td>
            </tr>
        </table>
    </body>
</html>'''
    book.add_item(c1)
    
    # Add fake image reference
    c2 = epub.EpubHtml(title='Media Test', file_name='media.xhtml')
    c2.content = '''<html>
    <body>
        <h1>Media Content</h1>
        <p>Image reference:</p>
        <img src="image.jpg" alt="Test image" title="A test image"/>
        <p>Content after image.</p>
    </body>
</html>'''
    book.add_item(c2)
    
    # Set up spine and TOC
    book.spine = ['nav', c1, c2]
    book.toc = [
        epub.Link('nested.xhtml', 'Nested Content', 'nested'),
        (
            epub.Section('Advanced'),
            [epub.Link('media.xhtml', 'Media Test', 'media')]
        )
    ]
    
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Save and extract
    test_file = Path("/tmp/test_complex.epub")
    epub.write_epub(str(test_file), book)
    
    result = await extractor.extract_epub(
        test_file,
        extract_styles=True,
        extract_toc=True
    )
    
    logger.info(f"\nComplex EPUB extracted:")
    logger.info(f"  Subjects: {result['metadata'].get('subjects', [])}")
    logger.info(f"  Description: {result['metadata'].get('description', 'N/A')}")
    logger.info(f"  CSS files: {len(result.get('styles', []))}")
    
    # Check nested TOC
    if result.get("toc"):
        logger.info("\nTable of Contents structure:")
        extractor.display_toc(result["toc"])
    
    # Check complex tables
    for chapter in result["chapters"]:
        for block in chapter["blocks"]:
            if block["type"] == "table":
                logger.info(f"\nFound table with {len(block.get('rows', []))} rows")
                if block.get("headers"):
                    logger.info(f"  Headers: {block['headers']}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()
