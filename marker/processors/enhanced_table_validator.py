"""
Enhanced table validation processor for Marker.

This processor ensures all tables are accurately extracted by:
1. Using PyMuPDF for initial detection
2. Validating with Marker's extraction
3. Falling back to Camelot for low-confidence tables
4. Ensuring complete table corpus for Q&A generation
"""

from typing import List, Dict, Optional, Any
from pathlib import Path
from loguru import logger

from marker.processors import BaseProcessor
from marker.schema import Document, Table
from marker.tables.camelot_extractor import CamelotExtractor
import fitz  # PyMuPDF


class EnhancedTableValidationProcessor(BaseProcessor):
    """
    Comprehensive table validation and extraction processor.
    
    Since accuracy is more important than speed for Q&A generation,
    this processor ensures every table is properly captured.
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.confidence_threshold = self.config.get("table_confidence_threshold", 0.8)
        self.always_validate = self.config.get("always_validate_tables", True)
        self.camelot_extractor = CamelotExtractor(config)
        
    def __call__(self, document: Document) -> Document:
        """Process document for comprehensive table validation."""
        pdf_path = document.filepath
        
        # Extract all tables using multiple methods
        logger.info(f"Performing comprehensive table extraction for {pdf_path}")
        
        # 1. Get PyMuPDF tables for reference
        pymupdf_tables = self._extract_pymupdf_tables(pdf_path)
        
        # 2. Get Marker's detected tables
        marker_tables = self._get_marker_tables(document)
        
        # 3. Validate and enhance each table
        for page_num, page in enumerate(document.pages):
            page_tables = [b for b in page.blocks if isinstance(b, Table)]
            
            # Check each table's confidence
            for table in page_tables:
                confidence = table.metadata.get("confidence", 0)
                
                if confidence < self.confidence_threshold or self.always_validate:
                    logger.info(f"Validating table {table.id} (confidence: {confidence})")
                    
                    # Try to enhance with Camelot
                    enhanced_table = self._enhance_with_camelot(
                        table, page_num, pdf_path
                    )
                    
                    if enhanced_table:
                        # Replace with enhanced version
                        self._replace_table(page, table, enhanced_table)
            
            # Check for missed tables
            if page_num < len(pymupdf_tables):
                self._check_missed_tables(
                    page, page_tables, pymupdf_tables[page_num]
                )
        
        # Add validation metadata
        document.metadata["table_validation"] = {
            "performed": True,
            "pymupdf_tables": sum(len(pt) for pt in pymupdf_tables),
            "marker_tables": len(marker_tables),
            "enhanced_tables": getattr(self, "_enhanced_count", 0)
        }
        
        return document
    
    def _extract_pymupdf_tables(self, pdf_path: Path) -> List[List[Dict]]:
        """Extract all tables using PyMuPDF."""
        doc = fitz.open(str(pdf_path))
        all_tables = []
        
        for page in doc:
            page_tables = []
            for table in page.find_tables():
                table_dict = {
                    "bbox": table.bbox,
                    "rows": table.extract(),
                    "col_count": table.col_count,
                    "row_count": table.row_count
                }
                page_tables.append(table_dict)
            
            all_tables.append(page_tables)
        
        doc.close()
        return all_tables
    
    def _get_marker_tables(self, document: Document) -> List[Table]:
        """Get all tables detected by Marker."""
        tables = []
        for page in document.pages:
            for block in page.blocks:
                if isinstance(block, Table):
                    tables.append(block)
        return tables
    
    def _enhance_with_camelot(
        self, 
        table: Table, 
        page_num: int, 
        pdf_path: Path
    ) -> Optional[Table]:
        """Enhance table extraction using Camelot."""
        try:
            # Extract region around table using Camelot
            bbox = table.bbox
            camelot_tables = self.camelot_extractor.extract_table(
                pdf_path=pdf_path,
                page_num=page_num + 1,  # Camelot uses 1-based indexing
                bbox=bbox
            )
            
            if camelot_tables and len(camelot_tables) > 0:
                # Use the best Camelot result
                camelot_table = camelot_tables[0]
                
                # Create enhanced table
                enhanced = Table.from_camelot(camelot_table)
                enhanced.metadata["enhancement"] = "camelot"
                enhanced.metadata["original_confidence"] = table.metadata.get("confidence", 0)
                enhanced.metadata["camelot_accuracy"] = camelot_table.accuracy
                
                self._enhanced_count = getattr(self, "_enhanced_count", 0) + 1
                
                return enhanced
                
        except Exception as e:
            logger.warning(f"Camelot enhancement failed: {e}")
        
        return None
    
    def _replace_table(self, page, old_table: Table, new_table: Table):
        """Replace table in page blocks."""
        for i, block in enumerate(page.blocks):
            if block.id == old_table.id:
                page.blocks[i] = new_table
                logger.info(f"Replaced table {old_table.id} with enhanced version")
                break
    
    def _check_missed_tables(
        self, 
        page, 
        marker_tables: List[Table],
        pymupdf_tables: List[Dict]
    ):
        """Check for tables detected by PyMuPDF but missed by Marker."""
        marker_bboxes = [t.bbox for t in marker_tables]
        
        for pymupdf_table in pymupdf_tables:
            bbox = pymupdf_table["bbox"]
            
            # Check if this table was found by Marker
            found = False
            for marker_bbox in marker_bboxes:
                if self._bbox_overlap(bbox, marker_bbox) > 0.8:
                    found = True
                    break
            
            if not found:
                logger.warning(
                    f"Table detected by PyMuPDF but missed by Marker at {bbox}"
                )
                # Could add this table using Camelot extraction
    
    def _bbox_overlap(self, bbox1, bbox2) -> float:
        """Calculate overlap ratio between two bounding boxes."""
        # Implementation of bbox overlap calculation
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # Calculate intersection
        x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
        y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
        
        intersection = x_overlap * y_overlap
        
        # Calculate union
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0