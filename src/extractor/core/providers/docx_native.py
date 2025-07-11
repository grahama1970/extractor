"""
Module: docx_native.py
Purpose: Native DOCX extraction without PDF conversion

This module implements direct DOCX extraction using docx2python,
preserving all document features including comments, track changes,
styles, and complex formatting without lossy conversions.

External Dependencies:
- docx2python: https://github.com/ShayHill/docx2python

Example Usage:
>>> from extractor.core.providers.docx_native import NativeDOCXProvider
>>> provider = NativeDOCXProvider()
>>> document = provider.extract_document("example.docx")
>>> print(document.source_type)  # SourceType.DOCX
"""

import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime

from docx2python import docx2python
from docx2python.iterators import iter_at_depth, iter_tables
from loguru import logger

from extractor.core.schema.unified_document import (
    UnifiedDocument, BlockType, SourceType, BaseBlock, TableBlock,
    ImageBlock, BlockMetadata, DocumentMetadata,
    HierarchyNode, TableCell
)


class NativeDOCXProvider:
    """Direct DOCX extraction without PDF conversion"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0
        self.style_hierarchy = {
            'Title': 0,
            'Heading 1': 1,
            'Heading 2': 2,
            'Heading 3': 3,
            'Heading 4': 4,
            'Heading 5': 5,
            'Heading 6': 6,
            'Subtitle': 1,
        }
        
    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        """Extract DOCX content to unified document format"""
        filepath = Path(filepath)
        logger.info(f"Extracting DOCX document: {filepath}")
        
        # Extract with docx2python
        with docx2python(str(filepath)) as docx_content:
            # Extract all components
            metadata = self._extract_metadata(docx_content)
            blocks = self._extract_blocks(docx_content)
            
            # Add comments as blocks
            comment_blocks = self._extract_comments(docx_content)
            blocks.extend(comment_blocks)
            
            # Build hierarchy from styles
            hierarchy = self._build_hierarchy(blocks)
            
            # Extract images
            image_blocks = self._extract_images(docx_content)
            blocks.extend(image_blocks)
            
            # Apply Claude table merge analysis if enabled
            if self.config.get('enable_table_merge_analysis', True):
                blocks = self._analyze_and_merge_tables(blocks)
            
            # Create unified document
            doc = UnifiedDocument(
                id=self._generate_doc_id(filepath),
                source_type=SourceType.DOCX,
                source_path=str(filepath),
                blocks=blocks,
                hierarchy=hierarchy,
                metadata=metadata,
                full_text=self._extract_full_text(blocks),
                keywords=self._extract_keywords(docx_content)
            )
            
            logger.info(f"Extracted {len(blocks)} blocks from DOCX")
            return doc
    
    def _generate_doc_id(self, filepath: Path) -> str:
        """Generate unique document ID"""
        return hashlib.md5(str(filepath).encode()).hexdigest()
    
    def _extract_metadata(self, docx_content) -> DocumentMetadata:
        """Extract document metadata"""
        props = docx_content.core_properties
        
        metadata = DocumentMetadata()
        
        # Map core properties
        if props:
            metadata.title = props.get('title', '')
            metadata.author = props.get('creator', '') or props.get('lastModifiedBy', '')
            
            # Parse dates
            created = props.get('created')
            if created:
                try:
                    metadata.created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                except:
                    pass
                    
            modified = props.get('modified')
            if modified:
                try:
                    metadata.modified_date = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                except:
                    pass
            
            # Language from properties
            metadata.language = props.get('language', '')
            
            # Store all properties as format metadata
            metadata.format_metadata = {
                'file_type': 'docx',  # Add file type for consistency
                'core_properties': props,
                'has_comments': bool(docx_content.comments),
                'has_footnotes': bool(docx_content.footnotes),
                'has_endnotes': bool(docx_content.endnotes)
            }
        
        return metadata
    
    def _extract_blocks(self, docx_content) -> List[BaseBlock]:
        """Extract all content blocks from DOCX"""
        blocks = []
        
        # Check if we have paragraph-level data with styles
        if hasattr(docx_content, 'document_pars'):
            # Use paragraph-level extraction for better style detection
            blocks.extend(self._extract_blocks_with_styles(docx_content))
        else:
            # Fallback to basic extraction
            blocks.extend(self._extract_blocks_basic(docx_content))
        
        # Extract tables separately using iter_tables
        table_blocks = self._extract_tables_properly(docx_content)
        blocks.extend(table_blocks)
        
        # Process headers and footers
        if docx_content.header:
            for section_idx, header in enumerate(docx_content.header):
                header_blocks = self._process_header_footer(
                    header, 
                    BlockType.PAGEHEADER,
                    f"section-{section_idx}"
                )
                blocks.extend(header_blocks)
        
        if docx_content.footer:
            for section_idx, footer in enumerate(docx_content.footer):
                footer_blocks = self._process_header_footer(
                    footer,
                    BlockType.PAGEFOOTER,
                    f"section-{section_idx}"
                )
                blocks.extend(footer_blocks)
        
        # Process footnotes
        if docx_content.footnotes:
            footnote_blocks = self._process_footnotes(docx_content.footnotes)
            blocks.extend(footnote_blocks)
            
        # Process endnotes
        if docx_content.endnotes:
            endnote_blocks = self._process_endnotes(docx_content.endnotes)
            blocks.extend(endnote_blocks)
        
        return blocks
    
    def _extract_blocks_with_styles(self, docx_content) -> List[BaseBlock]:
        """Extract blocks using paragraph-level style information"""
        blocks = []
        
        # Debug: Let's see what docx2python returns for body
        logger.debug(f"Body content type: {type(docx_content.body)}")
        logger.debug(f"Body content length: {len(docx_content.body) if hasattr(docx_content.body, '__len__') else 'N/A'}")
        if docx_content.body and len(docx_content.body) > 0:
            logger.debug(f"First body element type: {type(docx_content.body[0])}")
        
        # Iterate through document paragraphs at depth 4
        for par_idx, par in enumerate(iter_at_depth(docx_content.document_pars, 4)):
            # Check if this is a Par object (from docx2python v3)
            if hasattr(par, 'style') and hasattr(par, 'runs'):
                # Extract text from runs
                text_parts = []
                for run in par.runs:
                    if hasattr(run, 'text') and run.text:
                        text_parts.append(run.text)
                
                text = ''.join(text_parts).strip()
                if not text:
                    continue
                
                # Get style
                style = par.style if hasattr(par, 'style') else ''
                
                # Determine block type based on style
                block_type = BlockType.PARAGRAPH
                level = None
                
                if style:
                    # Handle various heading styles (case insensitive)
                    # docx2python returns styles without spaces (e.g., "Heading1" not "Heading 1")
                    if style == 'Title':
                        block_type = BlockType.HEADING
                        level = 0
                    elif style == 'Subtitle':
                        block_type = BlockType.HEADING
                        level = 1
                    elif style.startswith('Heading'):
                        block_type = BlockType.HEADING
                        # Extract level from style name (e.g., "Heading1" -> 1)
                        try:
                            # Style names from docx2python are like "Heading1", "Heading2", etc.
                            level_str = style.replace('Heading', '').strip()
                            if level_str.isdigit():
                                level = int(level_str)
                            else:
                                level = 1
                        except:
                            level = 1
                
                metadata = BlockMetadata(
                    attributes={
                        'style': style,
                        'paragraph_index': par_idx
                    },
                    confidence=1.0
                )
                
                if level is not None:
                    metadata.attributes['level'] = level
                
                blocks.append(BaseBlock(
                    id=self._generate_block_id(),
                    type=block_type,
                    content=text,
                    metadata=metadata
                ))
            elif isinstance(par, str) and par.strip():
                # Plain text paragraph (shouldn't happen with document_pars)
                blocks.append(self._process_paragraph(par, 0, par_idx))
        
        # Don't extract tables here - they're already extracted as paragraphs
        # Tables in docx2python are part of the document structure, not separate
        
        return blocks
    
    def _extract_blocks_basic(self, docx_content) -> List[BaseBlock]:
        """Basic extraction when style information is not available"""
        blocks = []
        body_content = docx_content.body
        
        for section_idx, section in enumerate(body_content):
            section_blocks = self._process_section(section, section_idx)
            blocks.extend(section_blocks)
        
        return blocks
    
    def _extract_tables_from_body(self, body_content) -> List[BaseBlock]:
        """Extract tables from document body"""
        blocks = []
        
        for section_idx, section in enumerate(body_content):
            if isinstance(section, list):
                for element_idx, element in enumerate(section):
                    # Check if this is really a table (list of lists with consistent structure)
                    if isinstance(element, list) and len(element) > 0:
                        # All rows should be lists for this to be a table
                        if all(isinstance(row, list) for row in element):
                            # Check that this isn't just a flat list of paragraphs
                            # Tables have multiple rows with multiple cells
                            if len(element) > 1 or (len(element) == 1 and len(element[0]) > 1):
                                table_block = self._process_table(element, section_idx, element_idx)
                                if table_block:
                                    blocks.append(table_block)
        
        return blocks
    
    def _process_section(self, section: List, section_idx: int) -> List[BaseBlock]:
        """Process a document section"""
        blocks = []
        
        for element_idx, element in enumerate(section):
            if isinstance(element, list):
                # This is a table
                table_block = self._process_table(element, section_idx, element_idx)
                if table_block:
                    blocks.append(table_block)
            elif isinstance(element, str):
                # This is a paragraph
                if element.strip():
                    para_block = self._process_paragraph(element, section_idx, element_idx)
                    if para_block:
                        blocks.append(para_block)
            elif hasattr(element, '__iter__'):
                # Handle nested structures
                for item in element:
                    if isinstance(item, str) and item.strip():
                        para_block = self._process_paragraph(item, section_idx, element_idx)
                        if para_block:
                            blocks.append(para_block)
        
        return blocks
    
    def _process_paragraph(self, text: str, section_idx: int, para_idx: int) -> Optional[BaseBlock]:
        """Process a paragraph"""
        text = text.strip()
        if not text:
            return None
        
        # Try to detect heading style from content patterns
        block_type = BlockType.PARAGRAPH
        level = None
        
        # Common heading patterns
        if re.match(r'^(Chapter|Section|Part)\s+\d+', text, re.IGNORECASE):
            block_type = BlockType.HEADING
            level = 1
        elif re.match(r'^\d+\.\s+[A-Z]', text):  # Numbered heading
            block_type = BlockType.HEADING
            level = text.count('.') + 1
        elif len(text) < 100 and text.isupper():  # Short all-caps likely heading
            block_type = BlockType.HEADING
            level = 2
        
        block_id = self._generate_block_id()
        
        metadata = BlockMetadata(
            attributes={
                'section_index': section_idx,
                'paragraph_index': para_idx
            },
            confidence=0.95
        )
        
        if level:
            metadata.attributes['level'] = level
        
        return BaseBlock(
            id=block_id,
            type=block_type,
            content=text,
            metadata=metadata
        )
    
    def _extract_tables_properly(self, docx_content) -> List[BaseBlock]:
        """Extract tables using docx2python's table iterator"""
        blocks = []
        
        # docx2python puts all content in a table-like structure
        # Real tables can be found by checking the lineage
        table_idx = 0
        
        # Get all tables from the body
        for table in iter_tables(docx_content.body):
            # Check if this is actually a table (not just the document structure)
            # Real tables will have multiple rows and/or multiple columns
            if len(table) > 1 or (len(table) == 1 and len(table[0]) > 1):
                # This looks like a real table
                table_block = self._process_table(table, 0, table_idx)
                if table_block:
                    blocks.append(table_block)
                    table_idx += 1
        
        return blocks
    
    def _process_table(self, table_data: List, section_idx: int, table_idx: int) -> Optional[TableBlock]:
        """Process a table"""
        if not table_data or not any(table_data):
            return None
        
        cells = []
        headers = []
        
        for row_idx, row in enumerate(table_data):
            if not isinstance(row, list):
                continue
                
            # Check if this is a header row (first row often is)
            if row_idx == 0 and all(isinstance(cell, str) for cell in row):
                # Simple heuristic: if all cells are short text, likely headers
                if all(len(str(cell).strip()) < 50 for cell in row if cell):
                    headers.append(row_idx)
            
            for col_idx, cell in enumerate(row):
                # Cell might be a list of paragraphs
                if isinstance(cell, list):
                    # Join all paragraphs in the cell
                    cell_text = ' '.join(str(p).strip() for p in cell if p)
                else:
                    cell_text = str(cell).strip() if cell else ""
                    
                cells.append(TableCell(
                    row=row_idx,
                    col=col_idx,
                    content=cell_text
                ))
        
        if not cells:
            return None
        
        # Calculate dimensions
        max_row = max(cell.row for cell in cells) if cells else 0
        max_col = max(cell.col for cell in cells) if cells else 0
        
        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={},
            rows=max_row + 1,
            cols=max_col + 1,
            cells=cells,
            headers=headers,
            metadata=BlockMetadata(
                attributes={
                    'section_index': section_idx,
                    'table_index': table_idx
                },
                confidence=0.95
            )
        )
    
    def _process_header_footer(self, content: List, block_type: BlockType, section_id: str) -> List[BaseBlock]:
        """Process headers or footers"""
        blocks = []
        
        if not content:
            return blocks
        
        # Flatten nested structure and extract text
        text_parts = []
        
        def extract_text(item):
            if isinstance(item, str):
                if item.strip():
                    text_parts.append(item.strip())
            elif isinstance(item, list):
                for subitem in item:
                    extract_text(subitem)
        
        extract_text(content)
        
        if text_parts:
            combined_text = ' '.join(text_parts)
            blocks.append(BaseBlock(
                id=self._generate_block_id(),
                type=block_type,
                content=combined_text,
                metadata=BlockMetadata(
                    attributes={'section': section_id},
                    confidence=0.95
                )
            ))
        
        return blocks
    
    def _process_footnotes(self, footnotes: List) -> List[BaseBlock]:
        """Process footnotes"""
        blocks = []
        
        for idx, footnote in enumerate(footnotes):
            if isinstance(footnote, str) and footnote.strip():
                blocks.append(BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.FOOTNOTE,
                    content=footnote.strip(),
                    metadata=BlockMetadata(
                        attributes={'footnote_index': idx + 1},
                        confidence=0.95
                    )
                ))
            elif isinstance(footnote, list):
                # Handle nested footnote structure
                text = ' '.join(str(item) for item in footnote if item)
                if text.strip():
                    blocks.append(BaseBlock(
                        id=self._generate_block_id(),
                        type=BlockType.FOOTNOTE,
                        content=text.strip(),
                        metadata=BlockMetadata(
                            attributes={'footnote_index': idx + 1},
                            confidence=0.95
                        )
                    ))
        
        return blocks
    
    def _process_endnotes(self, endnotes: List) -> List[BaseBlock]:
        """Process endnotes - similar to footnotes"""
        blocks = []
        
        for idx, endnote in enumerate(endnotes):
            if isinstance(endnote, str) and endnote.strip():
                blocks.append(BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.REFERENCE,
                    content=endnote.strip(),
                    metadata=BlockMetadata(
                        attributes={'endnote_index': idx + 1},
                        confidence=0.95
                    )
                ))
        
        return blocks
    
    def _extract_comments(self, docx_content) -> List[BaseBlock]:
        """Extract comments as blocks"""
        blocks = []
        
        if not docx_content.comments:
            return blocks
        
        for idx, comment in enumerate(docx_content.comments):
            if isinstance(comment, str) and comment.strip():
                blocks.append(BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.COMMENT,
                    content=comment.strip(),
                    metadata=BlockMetadata(
                        attributes={
                            'comment_index': idx + 1,
                            'comment_type': 'document_comment'
                        },
                        confidence=0.95
                    )
                ))
            elif isinstance(comment, dict):
                # Handle structured comment data
                text = comment.get('text', '')
                author = comment.get('author', '')
                if text:
                    blocks.append(BaseBlock(
                        id=self._generate_block_id(),
                        type=BlockType.COMMENT,
                        content=text,
                        metadata=BlockMetadata(
                            attributes={
                                'comment_index': idx + 1,
                                'author': author,
                                'comment_type': 'document_comment'
                            },
                            confidence=0.95
                        )
                    ))
        
        return blocks
    
    def _extract_images(self, docx_content) -> List[ImageBlock]:
        """Extract images as blocks"""
        blocks = []
        
        if not hasattr(docx_content, 'images') or not docx_content.images:
            return blocks
        
        for filename, image_data in docx_content.images.items():
            # Create base64 data URI
            import base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Detect image format from filename
            ext = Path(filename).suffix.lower()
            mime_type = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.tiff': 'image/tiff',
                '.svg': 'image/svg+xml'
            }.get(ext, 'image/png')
            
            data_uri = f"data:{mime_type};base64,{image_base64}"
            
            blocks.append(ImageBlock(
                id=self._generate_block_id(),
                type=BlockType.IMAGE,
                content="",
                src=data_uri,
                alt=filename,
                format=ext[1:] if ext else 'unknown',
                metadata=BlockMetadata(
                    attributes={
                        'original_filename': filename,
                        'embedded': True
                    },
                    confidence=1.0
                )
            ))
        
        return blocks
    
    def _build_hierarchy(self, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        """Build document hierarchy from heading blocks"""
        heading_blocks = [b for b in blocks if b.type == BlockType.HEADING]
        
        if not heading_blocks:
            # Try to build from other structural elements
            return self._build_default_hierarchy(blocks)
        
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
                breadcrumb=[n.title for n in stack] + [block.content]
            )
            
            # Add to parent
            if stack:
                stack[-1].children.append(node)
            
            # Update stack
            if len(stack) <= level:
                stack.append(node)
            else:
                stack[level] = node
        
        return root
    
    def _build_default_hierarchy(self, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        """Build a default hierarchy when no headings are found"""
        root = HierarchyNode(
            id="root",
            title="Document",
            level=0,
            block_id="root",
            children=[]
        )
        
        # Group by section if we have that info
        sections = {}
        for block in blocks:
            section_idx = block.metadata.attributes.get('section_index', 0)
            if section_idx not in sections:
                sections[section_idx] = []
            sections[section_idx].append(block)
        
        # Create section nodes
        for section_idx in sorted(sections.keys()):
            if len(sections) > 1:  # Only create section nodes if multiple sections
                section_node = HierarchyNode(
                    id=f"section-{section_idx}",
                    title=f"Section {section_idx + 1}",
                    level=1,
                    block_id=f"section-{section_idx}",
                    parent_id="root",
                    breadcrumb=["Document", f"Section {section_idx + 1}"]
                )
                root.children.append(section_node)
        
        return root if root.children else None
    
    def _extract_full_text(self, blocks: List[BaseBlock]) -> str:
        """Extract all text content from blocks"""
        text_parts = []
        for block in blocks:
            if hasattr(block, 'content') and isinstance(block.content, str):
                text_parts.append(block.content)
            elif block.type == BlockType.TABLE and hasattr(block, 'cells'):
                # Extract table text
                for cell in block.cells:
                    if cell.content:
                        text_parts.append(cell.content)
        return '\n'.join(text_parts)
    
    def _extract_keywords(self, docx_content) -> List[str]:
        """Extract keywords from document properties"""
        keywords = []
        
        if docx_content.core_properties:
            # Check for keywords in properties
            props = docx_content.core_properties
            if 'keywords' in props and props['keywords']:
                # Keywords might be comma-separated
                kw_string = props['keywords']
                keywords = [k.strip() for k in kw_string.split(',') if k.strip()]
            
            # Also check subject
            if 'subject' in props and props['subject']:
                keywords.append(props['subject'])
        
        return keywords
    
    def _generate_block_id(self) -> str:
        """Generate unique block ID"""
        self.block_counter += 1
        return f"docx-block-{self.block_counter}"
    
    def _analyze_and_merge_tables(self, blocks: List[BaseBlock]) -> List[BaseBlock]:
        """Analyze tables for potential merging using Claude's logic"""
        # Import the Claude table merge analyzer if available
        try:
            from extractor.core.processors.claude_table_merge_analyzer import ClaudeTableMergeAnalyzer
            analyzer = ClaudeTableMergeAnalyzer()
            return analyzer.analyze_and_merge_tables(blocks)
        except ImportError:
            logger.debug("Claude table merge analyzer not available, skipping table merge analysis")
            return blocks


if __name__ == "__main__":
    # Test the DOCX extractor
    import tempfile
    
    # For testing, we'll create a simple test
    # In real usage, we'd have an actual DOCX file
    provider = NativeDOCXProvider()
    
    # Since we can't easily create a DOCX file in memory for testing,
    # we'll just verify the class initializes correctly
    assert provider is not None
    assert provider.block_counter == 0
    
    print("✅ Native DOCX provider initialized successfully")
    print("Note: Full testing requires actual DOCX files")