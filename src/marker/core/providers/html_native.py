"""
Module: html_native.py
Purpose: Native HTML extraction without PDF conversion

This module implements direct HTML extraction inspired by context7's approach,
preserving structure, metadata, and semantics while avoiding information loss
from HTML→PDF conversion.

External Dependencies:
- beautifulsoup4: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- markdownify: https://github.com/matthewwithanm/python-markdownify
- lxml: https://lxml.de/
- playwright: https://playwright.dev/python/ (optional, for JS rendering)

Example Usage:
>>> from marker.core.providers.html_native import NativeHTMLProvider
>>> provider = NativeHTMLProvider()
>>> document = provider.extract_document("example.html")
>>> print(document.source_type)  # SourceType.HTML
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from urllib.parse import urljoin, urlparse
import hashlib

from bs4 import BeautifulSoup, Tag, NavigableString, Comment
from markdownify import markdownify as md
from loguru import logger

from marker.core.schema.unified_document import (
    UnifiedDocument, BlockType, SourceType, BaseBlock, TableBlock,
    ImageBlock, FormFieldBlock, BlockMetadata, DocumentMetadata,
    HierarchyNode, TableCell
)


class NativeHTMLProvider:
    """Direct HTML extraction without PDF conversion"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0
        self.hierarchy_stack: List[Dict[str, Any]] = []
        self.current_headers: Dict[int, str] = {}  # Track h1-h6 for context
        
    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        """Extract HTML content to unified document format"""
        filepath = Path(filepath)
        logger.info(f"Extracting HTML document: {filepath}")
        
        # Read HTML content
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extract metadata
        metadata = self._extract_metadata(soup)
        
        # Extract blocks with hierarchy preservation
        blocks = self._extract_blocks(soup)
        
        # Build hierarchy from headers
        hierarchy = self._build_hierarchy(blocks)
        
        # Create unified document
        doc = UnifiedDocument(
            id=self._generate_doc_id(filepath),
            source_type=SourceType.HTML,
            source_path=str(filepath),
            blocks=blocks,
            hierarchy=hierarchy,
            metadata=metadata,
            full_text=self._extract_full_text(blocks),
            keywords=self._extract_keywords(soup)
        )
        
        logger.info(f"Extracted {len(blocks)} blocks from HTML")
        return doc
    
    def _generate_doc_id(self, filepath: Path) -> str:
        """Generate unique document ID"""
        return hashlib.md5(str(filepath).encode()).hexdigest()
    
    def _extract_metadata(self, soup: BeautifulSoup) -> DocumentMetadata:
        """Extract document metadata from HTML"""
        metadata = DocumentMetadata()
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata.title = title_tag.get_text(strip=True)
            
        # Meta tags
        meta_tags = soup.find_all('meta')
        format_metadata = {}
        
        for meta in meta_tags:
            name = meta.get('name', meta.get('property', ''))
            content = meta.get('content', '')
            
            if name and content:
                # Standard metadata
                if name.lower() == 'author':
                    metadata.author = content
                elif name.lower() == 'description':
                    format_metadata['description'] = content
                elif name.lower() == 'keywords':
                    format_metadata['keywords'] = content
                else:
                    format_metadata[name] = content
                    
        # Charset
        charset_meta = soup.find('meta', charset=True)
        if charset_meta:
            format_metadata['charset'] = charset_meta.get('charset')
            
        # Language
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata.language = html_tag.get('lang')
            
        format_metadata['file_type'] = 'html'  # Add file type for consistency
        metadata.format_metadata = format_metadata
        return metadata
    
    def _extract_blocks(self, soup: BeautifulSoup) -> List[BaseBlock]:
        """Extract all content blocks from HTML"""
        blocks = []
        
        # Find main content area (article, main, or body)
        content_areas = ['article', 'main', '[role="main"]', 'body']
        main_content = None
        
        for selector in content_areas:
            main_content = soup.select_one(selector)
            if main_content:
                break
                
        if not main_content:
            main_content = soup.body or soup
            
        # Process content recursively
        self._process_element(main_content, blocks)
        
        return blocks
    
    def _process_element(self, element: Union[Tag, NavigableString], 
                        blocks: List[BaseBlock], 
                        parent_id: Optional[str] = None) -> None:
        """Process HTML element recursively"""
        
        # Skip comments and pure whitespace
        if isinstance(element, Comment):
            return
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                # Handle text nodes within parent context
                pass
            return
            
        # Skip script and style tags
        if element.name in ['script', 'style', 'noscript']:
            return
            
        # Handle different element types
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            block = self._process_heading(element, parent_id)
            if block:
                blocks.append(block)
                parent_id = block.id
                
        elif element.name == 'p':
            block = self._process_paragraph(element, parent_id)
            if block:
                blocks.append(block)
                
        elif element.name == 'table':
            block = self._process_table(element, parent_id)
            if block:
                blocks.append(block)
                
        elif element.name == 'img':
            block = self._process_image(element, parent_id)
            if block:
                blocks.append(block)
                
        elif element.name in ['ul', 'ol']:
            list_blocks = self._process_list(element, parent_id)
            blocks.extend(list_blocks)
            
        elif element.name == 'form':
            form_blocks = self._process_form(element, parent_id)
            blocks.extend(form_blocks)
            
        elif element.name in ['pre', 'code']:
            block = self._process_code(element, parent_id)
            if block:
                blocks.append(block)
                
        elif element.name == 'blockquote':
            quote_blocks = self._process_blockquote(element, parent_id)
            blocks.extend(quote_blocks)
            
        else:
            # Process children for other elements
            for child in element.children:
                self._process_element(child, blocks, parent_id)
    
    def _process_heading(self, element: Tag, parent_id: Optional[str]) -> Optional[BaseBlock]:
        """Process heading element"""
        level = int(element.name[1])  # h1 -> 1, h2 -> 2, etc.
        text = element.get_text(strip=True)
        
        if not text:
            return None
            
        # Update header context
        self.current_headers[level] = text
        # Clear lower level headers
        for i in range(level + 1, 7):
            self.current_headers.pop(i, None)
            
        block_id = self._generate_block_id()
        
        # Build breadcrumb from current headers
        breadcrumb = []
        for i in range(1, level + 1):
            if i in self.current_headers:
                breadcrumb.append(self.current_headers[i])
                
        return BaseBlock(
            id=block_id,
            type=BlockType.HEADING,
            content=text,
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={
                    "level": level,
                    "tag": element.name,
                    "class": element.get('class', []),
                    "id": element.get('id', ''),
                    "breadcrumb": breadcrumb
                },
                confidence=1.0
            )
        )
    
    def _process_paragraph(self, element: Tag, parent_id: Optional[str]) -> Optional[BaseBlock]:
        """Process paragraph element"""
        # Convert to markdown to preserve formatting
        text = md(str(element), strip=['p'])
        
        if not text.strip():
            return None
            
        return BaseBlock(
            id=self._generate_block_id(),
            type=BlockType.PARAGRAPH,
            content=text.strip(),
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={
                    "tag": "p",
                    "class": element.get('class', [])
                },
                confidence=1.0
            )
        )
    
    def _process_table(self, element: Tag, parent_id: Optional[str]) -> Optional[TableBlock]:
        """Process table element"""
        rows = element.find_all('tr')
        if not rows:
            return None
            
        cells = []
        headers = []
        
        for row_idx, row in enumerate(rows):
            # Check if this is a header row
            if row.find_parent('thead') or all(cell.name == 'th' for cell in row.find_all(['td', 'th'])):
                headers.append(row_idx)
                
            for col_idx, cell in enumerate(row.find_all(['td', 'th'])):
                cells.append(TableCell(
                    row=row_idx,
                    col=col_idx,
                    content=cell.get_text(strip=True),
                    rowspan=int(cell.get('rowspan', 1)),
                    colspan=int(cell.get('colspan', 1)),
                    style={"is_header": cell.name == 'th'}
                ))
                
        # Calculate table dimensions
        max_row = max((cell.row for cell in cells), default=0)
        max_col = max((cell.col for cell in cells), default=0)
        
        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={},
            rows=max_row + 1,
            cols=max_col + 1,
            cells=cells,
            headers=headers,
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={
                    "tag": "table",
                    "class": element.get('class', [])
                },
                confidence=1.0
            )
        )
    
    def _process_image(self, element: Tag, parent_id: Optional[str]) -> Optional[ImageBlock]:
        """Process image element"""
        src = element.get('src', '')
        if not src:
            return None
            
        return ImageBlock(
            id=self._generate_block_id(),
            type=BlockType.IMAGE,
            content="",
            src=src,
            alt=element.get('alt', ''),
            width=self._parse_dimension(element.get('width')),
            height=self._parse_dimension(element.get('height')),
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={
                    "tag": "img",
                    "class": element.get('class', [])
                },
                confidence=1.0
            )
        )
    
    def _process_list(self, element: Tag, parent_id: Optional[str]) -> List[BaseBlock]:
        """Process list element"""
        blocks = []
        list_type = "ordered" if element.name == 'ol' else "unordered"
        
        # Create list container block
        list_block = BaseBlock(
            id=self._generate_block_id(),
            type=BlockType.LIST,
            content={"type": list_type},
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={"tag": element.name},
                confidence=1.0
            )
        )
        blocks.append(list_block)
        
        # Process list items
        for idx, li in enumerate(element.find_all('li', recursive=False)):
            item_text = md(str(li), strip=['li'])
            if item_text.strip():
                blocks.append(BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.LISTITEM,
                    content=item_text.strip(),
                    parent_id=list_block.id,
                    metadata=BlockMetadata(
                        attributes={
                            "index": idx,
                            "list_type": list_type
                        },
                        confidence=1.0
                    )
                ))
                
        return blocks
    
    def _process_form(self, element: Tag, parent_id: Optional[str]) -> List[BaseBlock]:
        """Process form element"""
        blocks = []
        
        # Create form container
        form_block = BaseBlock(
            id=self._generate_block_id(),
            type=BlockType.FORM,
            content={
                "action": element.get('action', ''),
                "method": element.get('method', 'get')
            },
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={"tag": "form"},
                confidence=1.0
            )
        )
        blocks.append(form_block)
        
        # Process form fields
        for field in element.find_all(['input', 'select', 'textarea']):
            field_type = field.get('type', 'text') if field.name == 'input' else field.name
            
            field_block = FormFieldBlock(
                id=self._generate_block_id(),
                type=BlockType.FORMFIELD,
                content="",
                field_type=field_type,
                name=field.get('name', ''),
                value=field.get('value', ''),
                required=field.get('required') is not None,
                parent_id=form_block.id,
                metadata=BlockMetadata(
                    attributes={
                        "tag": field.name,
                        "placeholder": field.get('placeholder', '')
                    },
                    confidence=1.0
                )
            )
            
            # For select, extract options
            if field.name == 'select':
                options = [opt.get_text(strip=True) for opt in field.find_all('option')]
                field_block.options = options
                
            blocks.append(field_block)
            
        return blocks
    
    def _process_code(self, element: Tag, parent_id: Optional[str]) -> Optional[BaseBlock]:
        """Process code element"""
        code_text = element.get_text()
        if not code_text.strip():
            return None
            
        # Try to detect language from class
        language = None
        classes = element.get('class', [])
        
        # Check the element itself
        for cls in classes:
            if isinstance(cls, str) and cls.startswith('language-'):
                language = cls.replace('language-', '')
                break
                
        # If this is a pre tag, check for code child
        if not language and element.name == 'pre':
            code_child = element.find('code')
            if code_child:
                child_classes = code_child.get('class', [])
                for cls in child_classes:
                    if isinstance(cls, str) and cls.startswith('language-'):
                        language = cls.replace('language-', '')
                        break
                
        return BaseBlock(
            id=self._generate_block_id(),
            type=BlockType.CODE,
            content=code_text,
            parent_id=parent_id,
            metadata=BlockMetadata(
                language=language,
                attributes={
                    "tag": element.name,
                    "class": classes
                },
                confidence=1.0
            )
        )
    
    def _process_blockquote(self, element: Tag, parent_id: Optional[str]) -> List[BaseBlock]:
        """Process blockquote element"""
        blocks = []
        
        # Create a container for the blockquote
        quote_text = md(str(element), strip=['blockquote'])
        if quote_text.strip():
            blocks.append(BaseBlock(
                id=self._generate_block_id(),
                type=BlockType.TEXT,
                content=quote_text.strip(),
                parent_id=parent_id,
                metadata=BlockMetadata(
                    attributes={
                        "tag": "blockquote",
                        "style": {"is_quote": True}
                    },
                    confidence=1.0
                )
            ))
            
        return blocks
    
    def _build_hierarchy(self, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        """Build document hierarchy from heading blocks"""
        # Find all heading blocks
        heading_blocks = [b for b in blocks if b.type == BlockType.HEADING]
        
        if not heading_blocks:
            return None
            
        # Create root node
        root = HierarchyNode(
            id="root",
            title="Document",
            level=0,
            block_id="root",
            children=[]
        )
        
        # Build hierarchy
        stack = [root]
        
        for block in heading_blocks:
            level = block.metadata.attributes.get('level', 1)
            
            # Pop stack until we find parent level
            while len(stack) > level:
                stack.pop()
                
            # Create node
            node = HierarchyNode(
                id=f"h-{block.id}",
                title=block.content,
                level=level,
                block_id=block.id,
                parent_id=stack[-1].id if stack else None,
                breadcrumb=block.metadata.attributes.get('breadcrumb', [])
            )
            
            # Add to parent
            if stack:
                stack[-1].children.append(node)
                
            # Add to stack if not already at this level
            if len(stack) <= level:
                stack.append(node)
            else:
                stack[level] = node
                
        return root
    
    def _extract_full_text(self, blocks: List[BaseBlock]) -> str:
        """Extract all text content from blocks"""
        text_parts = []
        for block in blocks:
            if hasattr(block, 'content') and isinstance(block.content, str):
                text_parts.append(block.content)
        return '\n'.join(text_parts)
    
    def _extract_keywords(self, soup: BeautifulSoup) -> List[str]:
        """Extract keywords from HTML"""
        keywords = []
        
        # From meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            keywords.extend([k.strip() for k in meta_keywords['content'].split(',')])
            
        return keywords
    
    def _generate_block_id(self) -> str:
        """Generate unique block ID"""
        self.block_counter += 1
        return f"html-block-{self.block_counter}"
    
    def _parse_dimension(self, value: Optional[str]) -> Optional[int]:
        """Parse dimension value (width/height)"""
        if not value:
            return None
        try:
            # Remove 'px' suffix if present
            if isinstance(value, str) and value.endswith('px'):
                value = value[:-2]
            return int(value)
        except (ValueError, TypeError):
            return None


if __name__ == "__main__":
    # Test the HTML extractor with a sample file
    import tempfile
    
    # Create test HTML
    test_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="author" content="Test Author">
        <title>Test HTML Document</title>
    </head>
    <body>
        <article>
            <h1>Main Title</h1>
            <p>This is a test paragraph with <strong>bold</strong> text.</p>
            
            <h2>Section 1</h2>
            <p>Content for section 1.</p>
            
            <table>
                <tr><th>Name</th><th>Value</th></tr>
                <tr><td>Item 1</td><td>100</td></tr>
            </table>
            
            <pre><code class="language-python">
def hello():
    print("Hello, World!")
            </code></pre>
            
            <form action="/submit" method="post">
                <input type="text" name="username" placeholder="Username" required>
                <input type="email" name="email" placeholder="Email">
                <button type="submit">Submit</button>
            </form>
        </article>
    </body>
    </html>
    """
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(test_html)
        temp_path = f.name
        
    # Test extraction
    provider = NativeHTMLProvider()
    doc = provider.extract_document(temp_path)
    
    # Validate
    assert doc.source_type == SourceType.HTML
    assert len(doc.blocks) > 0
    assert doc.metadata.title == "Test HTML Document"
    assert doc.metadata.author == "Test Author"
    
    # Check specific blocks
    heading_blocks = doc.get_blocks_by_type(BlockType.HEADING)
    assert len(heading_blocks) == 2
    assert heading_blocks[0].content == "Main Title"
    
    table_blocks = doc.get_blocks_by_type(BlockType.TABLE)
    assert len(table_blocks) == 1
    assert table_blocks[0].rows == 2
    
    code_blocks = doc.get_blocks_by_type(BlockType.CODE)
    assert len(code_blocks) == 1
    assert code_blocks[0].metadata.language == "python"
    
    form_blocks = doc.get_blocks_by_type(BlockType.FORM)
    assert len(form_blocks) == 1
    
    print("✅ Native HTML extraction passed")
    print(f"Extracted {len(doc.blocks)} blocks")
    
    # Cleanup
    import os
    os.unlink(temp_path)