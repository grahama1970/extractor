"""
MARKER FORK ADDITION - Font Metrics Enhancement

Module: font_header.py
Description: Font-based section header detection and correction processor

This processor analyzes font transitions between blocks to identify section headers
that may have been misclassified by the layout model. It runs after initial layout
detection but before other processors that depend on correct block types.

Note: Limited by marker's JSON serialization - font data only available in internal Document object.

External Dependencies:
- pypdfium2: For font extraction
- numpy: For font analysis

Sample Input:
>>> document with blocks that have font metadata from PdfProvider

Expected Output:
>>> document with corrected block types based on font transitions

Example Usage:
>>> processor = FontHeaderProcessor(config)
>>> processor(document)
"""

from typing import Annotated, Dict, List, Optional, Set, Tuple
import numpy as np
from loguru import logger

from extractor.core.processors import BaseProcessor
from extractor.core.schema import BlockTypes
from extractor.core.schema.document import Document
from extractor.core.schema.blocks import Block
from extractor.core.providers.pdf import PdfProvider


class FontHeaderProcessor(BaseProcessor):
    """
    A processor that uses font transitions to identify and correct section headers.
    
    This processor analyzes font changes between adjacent blocks to detect headers
    that were misclassified by the layout model. Headers typically have different
    fonts from both their preceding and following blocks.
    """
    
    block_types = (BlockTypes.Text, BlockTypes.SectionHeader)  # Process both types
    
    confidence_threshold: Annotated[
        float,
        "Minimum confidence score to reclassify a block as a section header",
    ] = 0.7
    
    header_fonts: Annotated[
        Set[str],
        "Common font families used for headers",
    ] = {"Arial", "Helvetica", "Calibri", "Verdana", "Tahoma", "Franklin", "Myriad"}
    
    body_fonts: Annotated[
        Set[str],
        "Common font families used for body text",
    ] = {"Times", "Georgia", "Garamond", "Century", "Bookman", "Palatino", "Cambria"}
    
    min_font_size_difference: Annotated[
        float,
        "Minimum font size difference (in points) to consider significant",
    ] = 1.5
    
    check_both_neighbors: Annotated[
        bool,
        "Whether to check font differences with both previous and next blocks",
    ] = True

    def __init__(self, config=None):
        super().__init__(config)
        self._corrections_made = 0
        self._font_data_cache = {}

    def __call__(self, document: Document):
        """Process document to detect and correct font-based section headers."""
        logger.info("FontHeaderProcessor: Starting font-based header detection")
        
        # Extract font data for all blocks
        self._extract_font_data(document)
        
        # Analyze font transitions and correct block types
        for page in document.pages:
            self._process_page(page, document)
        
        logger.info(f"FontHeaderProcessor: Completed with {self._corrections_made} corrections")

    def _extract_font_data(self, document: Document):
        """Extract font information from document blocks."""
        for page in document.pages:
            for block in page.children:
                # Get font data from the block's text content
                fonts = []
                font_sizes = []
                
                # First try: Check if block has direct line/span structure
                if hasattr(block, 'structure') and block.structure:
                    for child_id in block.structure:
                        child = page.get_block(child_id)
                        if child and hasattr(child, 'structure') and child.structure:
                            # This might be a line with spans
                            for span_id in child.structure:
                                span = page.get_block(span_id)
                                if span and hasattr(span, 'font') and hasattr(span, 'font_size'):
                                    if span.font and span.font_size:
                                        fonts.append(span.font)
                                        font_sizes.append(float(span.font_size))
                
                # Second try: Check all contained blocks recursively
                if not fonts and hasattr(page, 'contained_blocks'):
                    # Get all blocks within this block's boundaries
                    contained = list(page.contained_blocks(document, [block.block_type]))
                    for contained_block in contained:
                        if contained_block.id == block.id:
                            # Look at its children
                            if hasattr(contained_block, 'children'):
                                for child in contained_block.children:
                                    if hasattr(child, 'font') and hasattr(child, 'font_size'):
                                        if child.font and child.font_size:
                                            fonts.append(child.font)
                                            font_sizes.append(float(child.font_size))
                
                # Third try: Use raw_text method to get spans
                if not fonts and hasattr(block, 'get_spans'):
                    try:
                        spans = block.get_spans(document)
                        for span in spans:
                            if hasattr(span, 'font') and hasattr(span, 'font_size'):
                                if span.font and span.font_size:
                                    fonts.append(span.font)
                                    font_sizes.append(float(span.font_size))
                    except:
                        pass
                
                # Fourth try: Check the page's span data directly
                if not fonts:
                    # Look for spans that overlap with this block's area
                    block_polygon = getattr(block, 'polygon', None)
                    if block_polygon:
                        for other_block in page.children:
                            if hasattr(other_block, 'font') and hasattr(other_block, 'font_size'):
                                other_polygon = getattr(other_block, 'polygon', None)
                                if other_polygon and block_polygon.intersection_pct(other_polygon) > 0.5:
                                    if other_block.font and other_block.font_size:
                                        fonts.append(other_block.font)
                                        font_sizes.append(float(other_block.font_size))
                
                if fonts and font_sizes:
                    # Use FIRST font as per user requirement
                    # "we only care about the first font font style"
                    first_font = fonts[0]
                    first_size = font_sizes[0]
                    
                    self._font_data_cache[block.id] = {
                        'font': first_font,
                        'size': first_size,
                        'all_fonts': list(set(fonts)),
                        'size_range': (min(font_sizes), max(font_sizes)),
                        'first_font_info': {
                            'font': first_font,
                            'size': first_size
                        }
                    }
                    
                    logger.debug(f"Extracted font data for block {block.id}: {first_font} @ {first_size:.1f}pt (first font)")

    def _process_page(self, page, document: Document):
        """Process a single page to detect font-based headers."""
        blocks = [b for b in page.children if b.block_type in self.block_types]
        
        for i, block in enumerate(blocks):
            # Skip if no font data available
            if block.id not in self._font_data_cache:
                continue
            
            current_font = self._font_data_cache[block.id]
            
            # Get neighboring blocks' font data
            prev_font = None
            next_font = None
            
            if i > 0 and blocks[i-1].id in self._font_data_cache:
                prev_font = self._font_data_cache[blocks[i-1].id]
            
            if i < len(blocks) - 1 and blocks[i+1].id in self._font_data_cache:
                next_font = self._font_data_cache[blocks[i+1].id]
            
            # Analyze font transitions
            confidence, reasons = self._analyze_font_transition(
                current_font, prev_font, next_font
            )
            
            # Correct block type if confidence is high
            if confidence >= self.confidence_threshold and block.block_type != BlockTypes.SectionHeader:
                self._correct_block_type(block, confidence, reasons, document)

    def _analyze_font_transition(self, 
                                current_font: Dict, 
                                prev_font: Optional[Dict], 
                                next_font: Optional[Dict]) -> Tuple[float, List[str]]:
        """
        Analyze font transitions to determine section header likelihood.
        
        Returns confidence score and list of reasons.
        """
        confidence = 0.0
        reasons = []
        
        # Extract base font names (remove modifiers like Bold, Italic)
        current_base = self._get_base_font(current_font['font'])
        
        # Check differences with previous block
        if prev_font and self.check_both_neighbors:
            prev_base = self._get_base_font(prev_font['font'])
            
            # Different font family
            if current_base != prev_base:
                confidence += 0.3
                reasons.append(f"font_differs_from_above: {prev_font['font']} → {current_font['font']}")
            
            # Significant size difference
            size_diff = abs(current_font['size'] - prev_font['size'])
            if size_diff >= self.min_font_size_difference:
                confidence += 0.2
                reasons.append(f"size_differs_from_above: {prev_font['size']:.1f} → {current_font['size']:.1f}")
        
        # Check differences with next block
        if next_font:
            next_base = self._get_base_font(next_font['font'])
            
            # Different font family
            if current_base != next_base:
                confidence += 0.3
                reasons.append(f"font_differs_from_below: {current_font['font']} → {next_font['font']}")
            
            # Significant size difference
            size_diff = abs(current_font['size'] - next_font['size'])
            if size_diff >= self.min_font_size_difference:
                confidence += 0.2
                reasons.append(f"size_differs_from_below: {current_font['size']:.1f} → {next_font['size']:.1f}")
            
            # Extra confidence for header→body font pattern
            if (any(hf in current_base for hf in self.header_fonts) and 
                any(bf in next_base for bf in self.body_fonts)):
                confidence += 0.3
                reasons.append("header_to_body_pattern")
        
        # Check if different from BOTH neighbors (strong indicator)
        if self.check_both_neighbors and prev_font and next_font:
            if (current_base != self._get_base_font(prev_font['font']) and 
                current_base != self._get_base_font(next_font['font'])):
                confidence += 0.2
                reasons.append("different_from_both_neighbors")
        
        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)
        
        return confidence, reasons

    def _get_base_font(self, font_name: str) -> str:
        """Extract base font name without style modifiers."""
        # Remove common style suffixes
        for suffix in ['-Bold', '-Italic', '-BoldItalic', 'PS-BoldMT', 'PSMT', 'MT', '-Regular']:
            font_name = font_name.replace(suffix, '')
        
        # Extract base name before remaining hyphens
        if '-' in font_name:
            font_name = font_name.split('-')[0]
        
        # Remove font ID prefixes (like CAAAAA+)
        if '+' in font_name:
            font_name = font_name.split('+')[-1]
        
        return font_name

    def _correct_block_type(self, block: Block, confidence: float, reasons: List[str], document: Document):
        """Correct a block's type to SectionHeader."""
        # Store original type for traceability
        if not hasattr(block, 'metadata') or block.metadata is None:
            block.metadata = {}
        
        block.metadata['original_block_type'] = str(block.block_type)
        block.metadata['font_correction_confidence'] = confidence
        block.metadata['font_correction_reasons'] = reasons
        
        # Get text for logging
        text = ''
        if hasattr(block, 'raw_text'):
            text = block.raw_text(document).strip()[:50]
        elif hasattr(block, 'text'):
            text = str(block.text)[:50]
        
        logger.info(f"Correcting block type to SectionHeader: '{text}...' (confidence: {confidence:.2f})")
        
        # Change block type
        block.block_type = BlockTypes.SectionHeader
        self._corrections_made += 1

    def get_statistics(self) -> Dict:
        """Get statistics about font-based corrections."""
        return {
            'corrections_made': self._corrections_made,
            'blocks_with_font_data': len(self._font_data_cache),
            'unique_fonts': len(set(fd['font'] for fd in self._font_data_cache.values()))
        }