"""
Module: xml_native.py
Purpose: Native XML extraction with support for modern XML standards

This module implements XML extraction using lxml for performance
and defusedxml for security when parsing untrusted sources.
Supports XML 1.0, 1.1, namespaces, XPath, and recent standards.

External Dependencies:
- lxml: https://lxml.de/ (for performance and full XPath support)
- defusedxml: https://pypi.org/project/defusedxml/ (for security)

Example Usage:
>>> from extractor.core.providers.xml_native import NativeXMLProvider
>>> provider = NativeXMLProvider()
>>> document = provider.extract_document("data.xml")
>>> print(document.source_type)  # SourceType.XML
"""

import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Set
from datetime import datetime
import re

from loguru import logger

# Use defusedxml for security when configured
try:
    import defusedxml.ElementTree as ET_secure
    DEFUSED_AVAILABLE = True
except ImportError:
    DEFUSED_AVAILABLE = False
    logger.warning("defusedxml not available, using standard ElementTree (less secure)")
    import xml.etree.ElementTree as ET_secure

# Use lxml for performance when available
try:
    from lxml import etree
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False
    logger.warning("lxml not available, using standard ElementTree (slower)")
    import xml.etree.ElementTree as etree

from extractor.core.schema.unified_document import (
    UnifiedDocument, BlockType, SourceType, BaseBlock, TableBlock,
    BlockMetadata, DocumentMetadata, HierarchyNode, TableCell
)


class NativeXMLProvider:
    """Native XML extraction with modern standards support"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0
        self.use_secure = self.config.get('secure_parsing', True)
        self.use_lxml = self.config.get('use_lxml', LXML_AVAILABLE)
        self.preserve_namespaces = self.config.get('preserve_namespaces', True)
        self.extract_attributes = self.config.get('extract_attributes', True)
        self.xpath_queries = self.config.get('xpath_queries', {})
        
        # Choose parser
        if self.use_secure and DEFUSED_AVAILABLE:
            self.parser = ET_secure
            logger.info("Using defusedxml for secure parsing")
        elif self.use_lxml and LXML_AVAILABLE:
            self.parser = etree
            logger.info("Using lxml for performance")
        else:
            self.parser = etree
            logger.info("Using standard ElementTree")
    
    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        """Extract XML content to unified document format"""
        filepath = Path(filepath)
        logger.info(f"Extracting XML document: {filepath}")
        
        # Parse XML
        try:
            if self.use_lxml and LXML_AVAILABLE:
                # lxml parsing with iterparse for large files
                tree = etree.parse(str(filepath))
                root = tree.getroot()
            else:
                # Standard parsing
                tree = self.parser.parse(str(filepath))
                root = tree.getroot()
        except Exception as e:
            logger.error(f"Failed to parse XML: {e}")
            raise
        
        # Extract metadata
        metadata = self._extract_metadata(root, filepath)
        
        # Extract content blocks
        blocks = self._extract_blocks(root)
        
        # Build hierarchy
        hierarchy = self._build_hierarchy(root)
        
        # Apply XPath queries if configured
        if self.xpath_queries:
            xpath_blocks = self._apply_xpath_queries(root)
            blocks.extend(xpath_blocks)
        
        # Apply table detection heuristics
        table_blocks = self._detect_tables(root)
        blocks.extend(table_blocks)
        
        # Create unified document
        doc = UnifiedDocument(
            id=self._generate_doc_id(filepath),
            source_type=SourceType.XML,
            source_path=str(filepath),
            blocks=blocks,
            hierarchy=hierarchy,
            metadata=metadata,
            full_text=self._extract_full_text(blocks),
            keywords=self._extract_keywords(root)
        )
        
        logger.info(f"Extracted {len(blocks)} blocks from XML")
        return doc
    
    def _generate_doc_id(self, filepath: Path) -> str:
        """Generate unique document ID"""
        return hashlib.md5(str(filepath).encode()).hexdigest()
    
    def _extract_metadata(self, root, filepath: Path) -> DocumentMetadata:
        """Extract document metadata"""
        metadata = DocumentMetadata()
        
        # XML-specific metadata
        format_metadata = {
            'file_type': 'xml',
            'root_tag': root.tag,
            'encoding': 'utf-8',  # Default, could be extracted from declaration
            'namespaces': {}
        }
        
        # Extract namespaces
        if self.preserve_namespaces:
            if hasattr(root, 'nsmap'):  # lxml
                format_metadata['namespaces'] = dict(root.nsmap) if root.nsmap else {}
            else:
                # Extract from root attributes
                for attr, value in root.attrib.items():
                    if attr.startswith('xmlns'):
                        ns_name = attr.split(':')[-1] if ':' in attr else ''
                        format_metadata['namespaces'][ns_name] = value
        
        # Common metadata patterns
        # Try to find common metadata elements
        for tag in ['title', 'author', 'created', 'modified', 'description']:
            elements = root.findall(f".//{tag}")
            if elements and elements[0].text:
                if tag == 'title':
                    metadata.title = elements[0].text.strip()
                elif tag == 'author':
                    metadata.author = elements[0].text.strip()
                elif tag == 'created':
                    try:
                        metadata.created_date = datetime.fromisoformat(elements[0].text.strip())
                    except:
                        pass
                elif tag == 'modified':
                    try:
                        metadata.modified_date = datetime.fromisoformat(elements[0].text.strip())
                    except:
                        pass
                elif tag == 'description':
                    format_metadata['description'] = elements[0].text.strip()
        
        # File metadata
        metadata.file_size = filepath.stat().st_size if filepath.exists() else None
        metadata.format_metadata = format_metadata
        
        return metadata
    
    def _extract_blocks(self, element, parent_path: str = "") -> List[BaseBlock]:
        """Recursively extract content blocks from XML elements"""
        blocks = []
        
        # Current element path for context
        current_path = f"{parent_path}/{element.tag}" if parent_path else element.tag
        
        # Extract text content if present
        if element.text and element.text.strip():
            block = BaseBlock(
                id=self._generate_block_id(),
                type=self._determine_block_type(element),
                content=element.text.strip(),
                metadata=BlockMetadata(
                    attributes={
                        'xml_path': current_path,
                        'tag': element.tag,
                        'attributes': dict(element.attrib) if self.extract_attributes else {}
                    },
                    confidence=0.95
                )
            )
            blocks.append(block)
        
        # Process child elements
        for child in element:
            child_blocks = self._extract_blocks(child, current_path)
            blocks.extend(child_blocks)
            
            # Also check tail text (text after child element)
            if child.tail and child.tail.strip():
                tail_block = BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.PARAGRAPH,
                    content=child.tail.strip(),
                    metadata=BlockMetadata(
                        attributes={
                            'xml_path': current_path,
                            'context': 'tail_text'
                        },
                        confidence=0.9
                    )
                )
                blocks.append(tail_block)
        
        return blocks
    
    def _determine_block_type(self, element) -> BlockType:
        """Determine block type based on element tag and context"""
        tag_lower = element.tag.lower()
        
        # Common heading patterns
        if any(tag_lower.startswith(h) for h in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'heading', 'title']):
            return BlockType.HEADING
        
        # List patterns
        if tag_lower in ['li', 'listitem', 'item'] or tag_lower.endswith('item'):
            return BlockType.LISTITEM
        
        # Code patterns
        if tag_lower in ['code', 'sourcecode', 'programlisting', 'codeblock']:
            return BlockType.CODE
        
        # Table patterns (individual cells)
        if tag_lower in ['td', 'th', 'cell', 'tablecell']:
            return BlockType.TABLECELL
        
        # Default to paragraph
        return BlockType.PARAGRAPH
    
    def _detect_tables(self, root) -> List[TableBlock]:
        """Detect and extract table structures from XML"""
        tables = []
        
        # Common table patterns
        table_tags = ['table', 'grid', 'matrix']
        row_tags = ['tr', 'row', 'record']
        cell_tags = ['td', 'th', 'cell', 'field', 'column']
        
        # Find potential tables
        for table_tag in table_tags:
            for table_elem in root.findall(f".//{table_tag}"):
                table = self._extract_table_from_element(table_elem, row_tags, cell_tags)
                if table:
                    tables.append(table)
        
        # Also detect repeated structures that might be tables
        repeated_tables = self._detect_repeated_structures(root)
        tables.extend(repeated_tables)
        
        return tables
    
    def _extract_table_from_element(self, table_elem, row_tags: List[str], cell_tags: List[str]) -> Optional[TableBlock]:
        """Extract table from a table-like element"""
        rows = []
        
        # Find rows
        for row_tag in row_tags:
            row_elems = table_elem.findall(f".//{row_tag}")
            if row_elems:
                for row_elem in row_elems:
                    # Find cells in row
                    cells = []
                    for cell_tag in cell_tags:
                        cell_elems = row_elem.findall(f".//{cell_tag}")
                        cells.extend(cell_elems)
                    
                    if cells:
                        rows.append(cells)
                break
        
        if not rows:
            return None
        
        # Convert to TableBlock
        table_cells = []
        headers = []
        
        for row_idx, row in enumerate(rows):
            # First row might be headers
            if row_idx == 0 and all(elem.tag.lower() == 'th' for elem in row):
                headers.append(row_idx)
                
            for col_idx, cell_elem in enumerate(row):
                content = self._get_element_text(cell_elem)
                table_cells.append(TableCell(
                    row=row_idx,
                    col=col_idx,
                    content=content
                ))
        
        if not table_cells:
            return None
            
        max_row = max(cell.row for cell in table_cells)
        max_col = max(cell.col for cell in table_cells)
        
        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={},
            rows=max_row + 1,
            cols=max_col + 1,
            cells=table_cells,
            headers=headers,
            metadata=BlockMetadata(
                attributes={
                    'source_tag': table_elem.tag,
                    'xml_path': self._get_element_path(table_elem)
                },
                confidence=0.9
            )
        )
    
    def _detect_repeated_structures(self, root) -> List[TableBlock]:
        """Detect repeated structures that might represent tabular data"""
        tables = []
        
        # Look for elements with multiple children of the same type
        for elem in root.iter():
            children = list(elem)
            if len(children) < 2:
                continue
                
            # Check if all children have the same tag
            child_tags = [child.tag for child in children]
            if len(set(child_tags)) == 1:
                # Check if children have consistent sub-structure
                if self._is_tabular_structure(children):
                    table = self._create_table_from_repeated_structure(elem, children)
                    if table:
                        tables.append(table)
        
        return tables
    
    def _is_tabular_structure(self, elements: List) -> bool:
        """Check if elements have consistent tabular structure"""
        if not elements:
            return False
            
        # Get structure of first element
        first_structure = self._get_element_structure(elements[0])
        
        # Check if all elements have same structure
        for elem in elements[1:]:
            if self._get_element_structure(elem) != first_structure:
                return False
                
        # Must have at least 2 fields to be tabular
        return len(first_structure) >= 2
    
    def _get_element_structure(self, element) -> Set[str]:
        """Get the tag names of all child elements"""
        return {child.tag for child in element}
    
    def _create_table_from_repeated_structure(self, parent, elements: List) -> Optional[TableBlock]:
        """Create table from repeated XML structure"""
        if not elements:
            return None
            
        # Get column names from first element
        first_elem = elements[0]
        columns = [child.tag for child in first_elem]
        
        # Create header row
        cells = []
        for col_idx, col_name in enumerate(columns):
            cells.append(TableCell(
                row=0,
                col=col_idx,
                content=col_name
            ))
        
        # Create data rows
        for row_idx, elem in enumerate(elements, 1):
            for col_idx, child in enumerate(elem):
                content = self._get_element_text(child)
                cells.append(TableCell(
                    row=row_idx,
                    col=col_idx,
                    content=content
                ))
        
        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={},
            rows=len(elements) + 1,
            cols=len(columns),
            cells=cells,
            headers=[0],  # First row is headers
            metadata=BlockMetadata(
                attributes={
                    'source_tag': parent.tag,
                    'detection_method': 'repeated_structure'
                },
                confidence=0.85
            )
        )
    
    def _apply_xpath_queries(self, root) -> List[BaseBlock]:
        """Apply configured XPath queries to extract specific content"""
        blocks = []
        
        if not self.use_lxml or not LXML_AVAILABLE:
            logger.warning("XPath queries require lxml")
            return blocks
        
        for query_name, xpath in self.xpath_queries.items():
            try:
                results = root.xpath(xpath)
                for idx, result in enumerate(results):
                    if isinstance(result, str):
                        content = result
                    else:
                        content = self._get_element_text(result)
                        
                    if content:
                        blocks.append(BaseBlock(
                            id=self._generate_block_id(),
                            type=BlockType.PARAGRAPH,
                            content=content,
                            metadata=BlockMetadata(
                                attributes={
                                    'xpath_query': query_name,
                                    'xpath': xpath,
                                    'result_index': idx
                                },
                                confidence=1.0
                            )
                        ))
            except Exception as e:
                logger.warning(f"XPath query '{query_name}' failed: {e}")
        
        return blocks
    
    def _build_hierarchy(self, root) -> Optional[HierarchyNode]:
        """Build document hierarchy from XML structure"""
        def build_node(element, level: int = 0) -> HierarchyNode:
            node = HierarchyNode(
                id=f"xml-{id(element)}",
                title=element.tag,
                level=level,
                block_id=f"xml-elem-{id(element)}"
            )
            
            # Add children
            for child in element:
                if len(list(child)) > 0 or (child.text and child.text.strip()):
                    child_node = build_node(child, level + 1)
                    child_node.parent_id = node.id
                    node.children.append(child_node)
            
            return node
        
        return build_node(root)
    
    def _get_element_text(self, element) -> str:
        """Get all text content from an element"""
        if element is None:
            return ""
            
        # For lxml
        if hasattr(element, 'itertext'):
            return ' '.join(element.itertext()).strip()
        
        # For ElementTree
        text_parts = []
        if element.text:
            text_parts.append(element.text)
        for child in element:
            child_text = self._get_element_text(child)
            if child_text:
                text_parts.append(child_text)
            if child.tail:
                text_parts.append(child.tail)
        
        return ' '.join(text_parts).strip()
    
    def _get_element_path(self, element) -> str:
        """Get XPath-like path to element"""
        path_parts = []
        current = element
        
        while current is not None:
            path_parts.append(current.tag)
            current = current.getparent() if hasattr(current, 'getparent') else None
            
        return '/' + '/'.join(reversed(path_parts))
    
    def _extract_full_text(self, blocks: List[BaseBlock]) -> str:
        """Extract all text content"""
        text_parts = []
        for block in blocks:
            if hasattr(block, 'content') and isinstance(block.content, str):
                text_parts.append(block.content)
            elif block.type == BlockType.TABLE and hasattr(block, 'cells'):
                for cell in block.cells:
                    if cell.content:
                        text_parts.append(cell.content)
        return '\n'.join(text_parts)
    
    def _extract_keywords(self, root) -> List[str]:
        """Extract keywords from XML"""
        keywords = []
        
        # Look for common keyword elements
        keyword_tags = ['keyword', 'keywords', 'tag', 'tags', 'subject', 'category']
        
        for tag in keyword_tags:
            elements = root.findall(f".//{tag}")
            for elem in elements:
                text = self._get_element_text(elem)
                if text:
                    # Split by common delimiters
                    parts = re.split(r'[,;|]', text)
                    keywords.extend([p.strip() for p in parts if p.strip()])
        
        return list(set(keywords))  # Remove duplicates
    
    def _generate_block_id(self) -> str:
        """Generate unique block ID"""
        self.block_counter += 1
        return f"xml-block-{self.block_counter}"


if __name__ == "__main__":
    # Test the XML extractor
    provider = NativeXMLProvider()
    
    # Basic validation
    assert provider is not None
    assert provider.block_counter == 0
    
    print(" Native XML provider initialized successfully")
    print(f"lxml available: {LXML_AVAILABLE}")
    print(f"defusedxml available: {DEFUSED_AVAILABLE}")
    print("Note: Full testing requires actual XML files")