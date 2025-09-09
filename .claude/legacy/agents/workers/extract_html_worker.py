#!/usr/bin/env python3
"""
HTML Document Extractor Worker

Extracts content from HTML documents while preserving structure and semantics.
Handles various HTML formats including web pages, emails, and structured documents.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from bs4 import BeautifulSoup, NavigableString
import html2text

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Extract content from HTML documents")
console = Console()


class HTMLExtractor:
    """Extract content from HTML documents."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "extractor" / "html"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure html2text
        self.h2t = html2text.HTML2Text()
        self.h2t.body_width = 0  # No line wrapping
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        
    async def extract_html(self,
                          html_path: Path,
                          mode: str = "structured",
                          extract_metadata: bool = True,
                          extract_links: bool = True,
                          extract_images: bool = True) -> Dict:
        """Extract content from HTML file.
        
        Args:
            html_path: Path to HTML file
            mode: Extraction mode ('structured' or 'text')
            extract_metadata: Whether to extract meta tags
            extract_links: Whether to extract links
            extract_images: Whether to extract image references
            
        Returns:
            Extracted content with metadata
        """
        # Validate path
        html_path = Path(html_path).resolve()
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")
        if html_path.suffix.lower() not in ['.html', '.htm', '.xhtml']:
            raise ValueError(f"Not an HTML file: {html_path}")
        
        # Check cache
        cache_key = self._get_cache_key(html_path, mode)
        cached = await self._check_cache(cache_key)
        if cached:
            logger.info(f"Using cached extraction for {html_path.name}")
            return cached
        
        # Read HTML content
        with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
            html_content = f.read()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract based on mode
        if mode == "structured":
            result = await self._extract_structured(soup, extract_metadata, extract_links, extract_images)
        else:  # text mode
            result = await self._extract_text(soup, html_content)
        
        # Add file metadata
        result["metadata"]["source_file"] = str(html_path)
        result["metadata"]["extraction_time"] = datetime.now().isoformat()
        result["metadata"]["file_size"] = html_path.stat().st_size
        
        # Cache result
        await self._cache_result(cache_key, result)
        
        return result
    
    async def _extract_structured(self, 
                                soup: BeautifulSoup,
                                extract_metadata: bool,
                                extract_links: bool,
                                extract_images: bool) -> Dict:
        """Extract structured content preserving HTML semantics."""
        blocks = []
        metadata = {}
        
        # Extract metadata from head
        if extract_metadata and soup.head:
            metadata = self._extract_metadata(soup.head)
        
        # Extract title
        if soup.title:
            blocks.append({
                "type": "Title",
                "content": soup.title.get_text(strip=True),
                "level": 0
            })
        
        # Extract body content
        body = soup.body if soup.body else soup
        
        # Process all elements
        for element in body.descendants:
            if isinstance(element, NavigableString):
                continue
            
            block = self._process_element(element, extract_links, extract_images)
            if block:
                blocks.append(block)
        
        # Extract tables separately for better structure
        tables = self._extract_tables(soup)
        
        # Extract forms
        forms = self._extract_forms(soup)
        
        return {
            "blocks": blocks,
            "tables": tables,
            "forms": forms,
            "metadata": metadata,
            "statistics": self._calculate_statistics(blocks, tables, forms)
        }
    
    async def _extract_text(self, soup: BeautifulSoup, html_content: str) -> Dict:
        """Extract plain text using html2text."""
        # Convert to markdown
        markdown_text = self.h2t.handle(html_content)
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in markdown_text.split('\n\n') if p.strip()]
        
        blocks = []
        for para in paragraphs:
            # Detect headers (markdown style)
            if para.startswith('#'):
                level = len(para) - len(para.lstrip('#'))
                content = para.lstrip('#').strip()
                blocks.append({
                    "type": "Heading",
                    "content": content,
                    "level": level
                })
            else:
                blocks.append({
                    "type": "Text",
                    "content": para
                })
        
        return {
            "blocks": blocks,
            "metadata": {},
            "statistics": {"total_blocks": len(blocks)}
        }
    
    def _process_element(self, element, extract_links: bool, extract_images: bool) -> Optional[Dict]:
        """Process a single HTML element."""
        tag_name = element.name.lower()
        
        # Skip certain tags
        if tag_name in ['script', 'style', 'meta', 'link', 'br', 'hr']:
            return None
        
        # Skip if no text content
        text = element.get_text(strip=True)
        if not text and tag_name != 'img':
            return None
        
        # Headings
        if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag_name[1])
            return {
                "type": "Heading",
                "content": text,
                "level": level,
                "id": element.get('id', None)
            }
        
        # Paragraphs
        elif tag_name == 'p':
            block = {
                "type": "Paragraph",
                "content": text
            }
            
            # Extract links if requested
            if extract_links:
                links = self._extract_element_links(element)
                if links:
                    block["links"] = links
            
            return block
        
        # Lists
        elif tag_name in ['ul', 'ol']:
            items = []
            for li in element.find_all('li', recursive=False):
                items.append(li.get_text(strip=True))
            
            if items:
                return {
                    "type": "List",
                    "content": items,
                    "ordered": tag_name == 'ol'
                }
        
        # Images
        elif tag_name == 'img' and extract_images:
            return {
                "type": "Image",
                "src": element.get('src', ''),
                "alt": element.get('alt', ''),
                "title": element.get('title', '')
            }
        
        # Blockquotes
        elif tag_name == 'blockquote':
            return {
                "type": "Quote",
                "content": text
            }
        
        # Code blocks
        elif tag_name in ['pre', 'code']:
            return {
                "type": "Code",
                "content": text,
                "language": element.get('class', [''])[0] if element.get('class') else None
            }
        
        return None
    
    def _extract_metadata(self, head) -> Dict:
        """Extract metadata from HTML head."""
        metadata = {
            "title": "",
            "description": "",
            "keywords": [],
            "author": "",
            "charset": "utf-8",
            "og_data": {},
            "custom_meta": {}
        }
        
        # Title
        title_tag = head.find('title')
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)
        
        # Meta tags
        for meta in head.find_all('meta'):
            name = meta.get('name', '').lower()
            property = meta.get('property', '').lower()
            content = meta.get('content', '')
            
            if name == 'description':
                metadata["description"] = content
            elif name == 'keywords':
                metadata["keywords"] = [k.strip() for k in content.split(',')]
            elif name == 'author':
                metadata["author"] = content
            elif name == 'charset' or meta.get('charset'):
                metadata["charset"] = meta.get('charset', content)
            elif property.startswith('og:'):
                metadata["og_data"][property] = content
            elif name and content:
                metadata["custom_meta"][name] = content
        
        return metadata
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract tables from HTML."""
        tables = []
        
        for table in soup.find_all('table'):
            # Extract headers
            headers = []
            thead = table.find('thead')
            if thead:
                for th in thead.find_all('th'):
                    headers.append(th.get_text(strip=True))
            else:
                # Look for headers in first row
                first_row = table.find('tr')
                if first_row:
                    for th in first_row.find_all('th'):
                        headers.append(th.get_text(strip=True))
            
            # Extract rows
            rows = []
            tbody = table.find('tbody') or table
            for tr in tbody.find_all('tr'):
                row = []
                for td in tr.find_all(['td', 'th']):
                    row.append(td.get_text(strip=True))
                if row and not all(cell == '' for cell in row):
                    rows.append(row)
            
            if rows:
                tables.append({
                    "headers": headers,
                    "rows": rows,
                    "caption": table.find('caption').get_text(strip=True) if table.find('caption') else None,
                    "summary": table.get('summary', None)
                })
        
        return tables
    
    def _extract_forms(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract form structures."""
        forms = []
        
        for form in soup.find_all('form'):
            form_data = {
                "action": form.get('action', ''),
                "method": form.get('method', 'get').upper(),
                "fields": []
            }
            
            # Extract form fields
            for input_elem in form.find_all(['input', 'textarea', 'select']):
                field = {
                    "type": input_elem.name,
                    "name": input_elem.get('name', ''),
                    "id": input_elem.get('id', ''),
                    "required": input_elem.has_attr('required')
                }
                
                if input_elem.name == 'input':
                    field["input_type"] = input_elem.get('type', 'text')
                    field["placeholder"] = input_elem.get('placeholder', '')
                elif input_elem.name == 'select':
                    field["options"] = [opt.get_text(strip=True) for opt in input_elem.find_all('option')]
                
                form_data["fields"].append(field)
            
            if form_data["fields"]:
                forms.append(form_data)
        
        return forms
    
    def _extract_element_links(self, element) -> List[Dict]:
        """Extract links from an element."""
        links = []
        
        for a in element.find_all('a'):
            href = a.get('href', '')
            if href:
                links.append({
                    "url": href,
                    "text": a.get_text(strip=True),
                    "title": a.get('title', '')
                })
        
        return links
    
    def _calculate_statistics(self, blocks: List[Dict], tables: List[Dict], forms: List[Dict]) -> Dict:
        """Calculate extraction statistics."""
        stats = {
            "total_blocks": len(blocks),
            "total_tables": len(tables),
            "total_forms": len(forms),
            "block_types": {},
            "total_characters": 0,
            "total_links": 0,
            "total_images": 0
        }
        
        for block in blocks:
            block_type = block.get("type", "Unknown")
            stats["block_types"][block_type] = stats["block_types"].get(block_type, 0) + 1
            
            if "content" in block and isinstance(block["content"], str):
                stats["total_characters"] += len(block["content"])
            
            if "links" in block:
                stats["total_links"] += len(block["links"])
            
            if block_type == "Image":
                stats["total_images"] += 1
        
        return stats
    
    def _get_cache_key(self, file_path: Path, mode: str) -> str:
        """Generate cache key."""
        stat = file_path.stat()
        data = f"{file_path.absolute()}:{stat.st_size}:{stat.st_mtime}:{mode}"
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
    
    async def batch_extract(self, 
                          input_dir: Path,
                          output_dir: Path,
                          pattern: str = "*.html",
                          mode: str = "structured") -> Dict:
        """Extract multiple HTML files."""
        html_files = list(input_dir.glob(pattern))
        
        if not html_files:
            logger.warning(f"No HTML files found matching {pattern}")
            return {"processed": 0, "errors": 0}
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            "processed": 0,
            "errors": 0,
            "files": []
        }
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Processing {len(html_files)} HTML files...", total=len(html_files))
            
            for html_file in html_files:
                try:
                    result = await self.extract_html(html_file, mode=mode)
                    
                    # Save result
                    output_file = output_dir / f"{html_file.stem}_extracted.json"
                    with open(output_file, 'w') as f:
                        json.dump(result, f, indent=2)
                    
                    results["processed"] += 1
                    results["files"].append(str(html_file))
                    
                except Exception as e:
                    logger.error(f"Failed to extract {html_file}: {e}")
                    results["errors"] += 1
                
                progress.advance(task)
        
        return results


# Initialize extractor
extractor = HTMLExtractor()


@app.command()
def extract(
    html_file: Path = typer.Argument(..., help="HTML file to extract"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    mode: str = typer.Option("structured", "--mode", "-m", help="Extraction mode: structured/text"),
    no_metadata: bool = typer.Option(False, "--no-metadata", help="Skip metadata extraction"),
    no_links: bool = typer.Option(False, "--no-links", help="Skip link extraction"),
    no_images: bool = typer.Option(False, "--no-images", help="Skip image extraction")
):
    """Extract content from HTML document."""
    async def run():
        try:
            result = await extractor.extract_html(
                html_file,
                mode=mode,
                extract_metadata=not no_metadata,
                extract_links=not no_links,
                extract_images=not no_images
            )
            
            if output:
                with open(output, 'w') as f:
                    json.dump(result, f, indent=2)
                console.print(f"[green] Saved to {output}[/green]")
            else:
                # Display summary
                stats = result.get("statistics", {})
                table = Table(title="Extraction Summary")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Total Blocks", str(stats.get("total_blocks", 0)))
                table.add_row("Total Tables", str(stats.get("total_tables", 0)))
                table.add_row("Total Forms", str(stats.get("total_forms", 0)))
                table.add_row("Total Characters", f"{stats.get('total_characters', 0):,}")
                
                console.print(table)
        
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command("batch")
def batch_extract(
    input_dir: Path = typer.Argument(..., help="Directory containing HTML files"),
    output_dir: Path = typer.Argument(..., help="Output directory"),
    pattern: str = typer.Option("*.html", "--pattern", "-p", help="File pattern"),
    mode: str = typer.Option("structured", "--mode", "-m", help="Extraction mode")
):
    """Extract multiple HTML files."""
    async def run():
        results = await extractor.batch_extract(input_dir, output_dir, pattern, mode)
        
        # Show summary
        table = Table(title="Batch Processing Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Files Processed", str(results["processed"]))
        table.add_row("Errors", str(results["errors"]))
        
        console.print(table)
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate HTML extraction."""
    logger.info("Testing HTML extraction...")
    
    # Create test HTML
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Document</title>
        <meta name="description" content="A test HTML document">
        <meta name="author" content="Test Author">
    </head>
    <body>
        <h1>Main Title</h1>
        <p>This is a paragraph with a <a href="https://example.com">link</a>.</p>
        
        <h2>Section 1</h2>
        <p>Another paragraph.</p>
        
        <table>
            <thead>
                <tr><th>Column 1</th><th>Column 2</th></tr>
            </thead>
            <tbody>
                <tr><td>Data 1</td><td>Data 2</td></tr>
                <tr><td>Data 3</td><td>Data 4</td></tr>
            </tbody>
        </table>
        
        <form action="/submit" method="post">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    """
    
    # Save test file
    test_file = Path("/tmp/test_extract.html")
    with open(test_file, 'w') as f:
        f.write(test_html)
    
    # Extract
    result = await extractor.extract_html(test_file)
    
    logger.info(f"\nExtraction complete:")
    logger.info(f"  Blocks: {result['statistics']['total_blocks']}")
    logger.info(f"  Tables: {result['statistics']['total_tables']}")
    logger.info(f"  Forms: {result['statistics']['total_forms']}")
    
    # Show first few blocks
    logger.info("\nFirst 3 blocks:")
    for block in result["blocks"][:3]:
        logger.info(f"  {block['type']}: {block.get('content', '')[:50]}...")


async def debug_function():
    """Test edge cases in HTML extraction."""
    logger.info("Testing HTML edge cases...")
    
    # Test malformed HTML
    malformed_html = """
    <html>
    <title>Unclosed tags test
    <body>
    <p>Paragraph without closing
    <h1>Header without closing
    <table>
        <tr><td>Table without proper structure
    </body>
    """
    
    test_file = Path("/tmp/test_malformed.html")
    with open(test_file, 'w') as f:
        f.write(malformed_html)
    
    try:
        result = await extractor.extract_html(test_file)
        logger.info(f"Malformed HTML extracted: {result['statistics']['total_blocks']} blocks")
    except Exception as e:
        logger.error(f"Failed on malformed HTML: {e}")
    
    # Test with special characters
    special_html = """
    <html>
    <body>
        <h1>Special Characters: £¬¥</h1>
        <p>Unicode test: `}L <</p>
        <pre><code>Code with &lt;brackets&gt; and &amp;symbols&amp;</code></pre>
    </body>
    </html>
    """
    
    test_file2 = Path("/tmp/test_special.html")
    with open(test_file2, 'w') as f:
        f.write(special_html)
    
    result = await extractor.extract_html(test_file2)
    logger.info(f"\nSpecial characters handled: {len(result['blocks'])} blocks extracted")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()