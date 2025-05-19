"""
Enhanced Table Processor Module for Marker

This module provides an enhanced table processor that combines the original table
detection and recognition with improved table extraction capabilities, parameter
optimization, quality evaluation, and table merging.

Example usage:
    from marker.processors.enhanced_table import EnhancedTableProcessor
    from marker.config.table import TableConfig, TABLE_HIGH_QUALITY
    
    processor = EnhancedTableProcessor(
        detection_model, recognition_model, table_rec_model,
        config=TABLE_HIGH_QUALITY
    )
    processor(document)
"""

import re
import html
import os
import time
import logging
from collections import defaultdict, Counter
from copy import deepcopy
from typing import Annotated, List, Optional, Tuple, Dict, Any, Union

import numpy as np
from ftfy import fix_text
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor, OCRResult
from surya.table_rec import TableRecPredictor
from surya.table_rec.schema import TableResult, TableCell as SuryaTableCell
from pdftext.extraction import table_output
from tqdm import tqdm

# Import camelot for heuristic table extraction
try:
    import camelot
    import cv2
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False

from marker.processors import BaseProcessor
from marker.processors.table_optimizer import TableOptimizer, TableQualityEvaluator
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.blocks.tablecell import TableCell
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from marker.settings import settings
from marker.util import matrix_intersection_area
from marker.config.table import (
    TableConfig, 
    CamelotConfig, 
    TableOptimizerConfig, 
    TableQualityEvaluatorConfig,
    TableMergerConfig,
    PRESET_BALANCED
)


class EnhancedTableProcessor(BaseProcessor):
    """
    Enhanced processor for recognizing and processing tables in documents.
    
    This processor combines table detection, recognition, extraction,
    optimization, quality evaluation, and merging in a comprehensive pipeline.
    """
    block_types = (BlockTypes.Table, BlockTypes.TableOfContents, BlockTypes.Form)
    
    def __init__(
        self,
        detection_model: DetectionPredictor,
        recognition_model: RecognitionPredictor,
        table_rec_model: TableRecPredictor,
        config=None
    ):
        """
        Initialize the EnhancedTableProcessor.
        
        Args:
            detection_model: Model for detecting text within tables
            recognition_model: Model for recognizing text within tables
            table_rec_model: Model for recognizing table structure
            config: Configuration for the table processor
        """
        # Initialize with default balanced config if none provided
        if config is None:
            config = PRESET_BALANCED.dict()
            
        # If config is a TableConfig object, convert to dict
        if isinstance(config, TableConfig):
            config = config.dict()
            
        super().__init__(config)
        
        # Set up logger
        self.logger = logging.getLogger(__name__)
        
        # Initialize models
        self.detection_model = detection_model
        self.recognition_model = recognition_model
        self.table_rec_model = table_rec_model
        
        # Parse configuration
        self.parse_config()
        
        # Initialize optimizer and quality evaluator if enabled
        if self.optimizer_config.enabled:
            self.optimizer = TableOptimizer(self.optimizer_config)
        else:
            self.optimizer = None
            
        if self.quality_evaluator_config.enabled:
            self.quality_evaluator = TableQualityEvaluator(self.quality_evaluator_config)
        else:
            self.quality_evaluator = None
    
    def parse_config(self):
        """Parse and set up configuration from the provided config."""
        # Get main configuration
        self.table_config = self.config.get("table", {})
        
        # Extract sub-configurations
        self.camelot_config = self.config.get("camelot", {})
        self.optimizer_config = self.config.get("optimizer", {})
        self.quality_evaluator_config = self.config.get("quality_evaluator", {})
        self.merger_config = self.config.get("merger", {})
        
        # Convert to proper config objects if they're not already
        if not isinstance(self.camelot_config, CamelotConfig):
            self.camelot_config = CamelotConfig(**self.camelot_config)
            
        if not isinstance(self.optimizer_config, TableOptimizerConfig):
            self.optimizer_config = TableOptimizerConfig(**self.optimizer_config)
            
        if not isinstance(self.quality_evaluator_config, TableQualityEvaluatorConfig):
            self.quality_evaluator_config = TableQualityEvaluatorConfig(**self.quality_evaluator_config)
            
        if not isinstance(self.merger_config, TableMergerConfig):
            self.merger_config = TableMergerConfig(**self.merger_config)
        
        # Extract individual settings for convenience
        self.detect_boxes = self.config.get("detect_boxes", False)
        self.detection_batch_size = self.config.get("detection_batch_size", None)
        self.table_rec_batch_size = self.config.get("table_rec_batch_size", None)
        self.recognition_batch_size = self.config.get("recognition_batch_size", None)
        self.contained_block_types = self.config.get("contained_block_types", 
                                                    (BlockTypes.Text, BlockTypes.TextInlineMath))
        self.row_split_threshold = self.config.get("row_split_threshold", 0.5)
        self.pdftext_workers = self.config.get("pdftext_workers", 1)
        self.disable_tqdm = self.config.get("disable_tqdm", False)
        
        # Camelot-specific settings
        self.use_camelot_fallback = self.camelot_config.enabled
        self.camelot_min_cell_threshold = self.camelot_config.min_cell_threshold
        self.camelot_flavor = self.camelot_config.flavor
        self.camelot_line_width = self.camelot_config.line_width
        self.camelot_line_scale = self.camelot_config.line_scale
        self.camelot_copy_text = self.camelot_config.copy_text
        self.camelot_infer_cell_borders = self.camelot_config.infer_cell_borders
        self.camelot_edge_tol = self.camelot_config.edge_tol
        self.camelot_row_tol = self.camelot_config.row_tol
    
    def __call__(self, document: Document):
        """
        Process tables in the document.
        
        Args:
            document: The document to process
        """
        filepath = document.filepath  # Path to original pdf file
        
        # Collect table data
        table_data = []
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                image = block.get_image(document, highres=True)
                image_poly = block.polygon.rescale(
                    (page.polygon.width, page.polygon.height), 
                    page.get_image(highres=True).size
                )
                
                table_data.append({
                    "block_id": block.id,
                    "page_id": page.page_id,
                    "table_image": image,
                    "table_bbox": image_poly.bbox,
                    "img_size": page.get_image(highres=True).size,
                    "ocr_block": page.text_extraction_method == "surya",
                    "block": block,  # Store reference to the original block
                })
        
        # Process tables with existing text
        extract_blocks = [t for t in table_data if not t["ocr_block"]]
        self.assign_pdftext_lines(extract_blocks, filepath)
        
        # Process tables that need OCR
        ocr_blocks = [t for t in table_data if t["ocr_block"]]
        self.assign_ocr_lines(ocr_blocks)
        
        # Make sure all table data has text lines
        if not all("table_text_lines" in t for t in table_data):
            self.logger.error("Not all table data has table cells")
            
        # Configure and run table recognition
        self.table_rec_model.disable_tqdm = self.disable_tqdm
        tables: List[TableResult] = self.table_rec_model(
            [t["table_image"] for t in table_data],
            batch_size=self.get_table_rec_batch_size()
        )
        
        # Assign text to cells and perform processing
        self.assign_text_to_cells(tables, table_data)
        self.split_combined_rows(tables)
        self.combine_dollar_column(tables)
        
        # Track tables that need fallback processing
        fallback_tables = []
        optimized_params_cache = {}
        
        # Assign table cells to the table
        table_idx = 0
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                block.structure = []  # Remove any existing lines, spans, etc.
                cells: List[SuryaTableCell] = tables[table_idx].cells
                
                # Check if we should use fallback extraction
                use_fallback = False
                
                # Quality check for primary extraction
                if cells:
                    table_cells = []
                    for cell in cells:
                        # Create TableCell objects for quality evaluation
                        cell_polygon = PolygonBox(polygon=cell.polygon).rescale(
                            page.get_image(highres=True).size, 
                            page.polygon.size
                        )
                        
                        for corner in cell_polygon.polygon:
                            corner[0] += block.polygon.bbox[0]
                            corner[1] += block.polygon.bbox[1]
                            
                        cell_block = TableCell(
                            polygon=cell_polygon,
                            text_lines=self.finalize_cell_text(cell),
                            rowspan=cell.rowspan,
                            colspan=cell.colspan,
                            row_id=cell.row_id,
                            col_id=cell.col_id,
                            is_header=bool(cell.is_header),
                            page_id=page.page_id,
                        )
                        table_cells.append(cell_block)
                        
                    if self.quality_evaluator:
                        quality_score = self.quality_evaluator.evaluate(table_cells, "primary")
                        self.logger.info(f"Table quality score: {quality_score:.3f}")
                        
                        if quality_score < self.quality_evaluator_config.min_quality_score:
                            self.logger.info(f"Table quality below threshold ({quality_score:.3f} < {self.quality_evaluator_config.min_quality_score}), using fallback")
                            use_fallback = True
                            
                # Also use fallback if too few cells
                if len(cells) < self.camelot_min_cell_threshold:
                    use_fallback = True
                
                # Process with fallback if needed
                if self.use_camelot_fallback and CAMELOT_AVAILABLE and use_fallback:
                    fallback_tables.append({
                        "page": page,
                        "block": block,
                        "page_idx": page.page_id,
                        "table_data": table_data[table_idx],
                        "optimized_params": optimized_params_cache.get(page.page_id, None)
                    })
                else:
                    # Process with default method
                    for cell in cells:
                        # Rescale the cell polygon to the page size
                        cell_polygon = PolygonBox(polygon=cell.polygon).rescale(
                            page.get_image(highres=True).size, 
                            page.polygon.size
                        )
                        
                        # Rescale cell polygon to be relative to the page instead of the table
                        for corner in cell_polygon.polygon:
                            corner[0] += block.polygon.bbox[0]
                            corner[1] += block.polygon.bbox[1]
                            
                        cell_block = TableCell(
                            polygon=cell_polygon,
                            text_lines=self.finalize_cell_text(cell),
                            rowspan=cell.rowspan,
                            colspan=cell.colspan,
                            row_id=cell.row_id,
                            col_id=cell.col_id,
                            is_header=bool(cell.is_header),
                            page_id=page.page_id,
                        )
                        page.add_full_block(cell_block)
                        block.add_structure(cell_block)
                        
                table_idx += 1
        
        # Process fallback tables with Camelot if needed
        if fallback_tables:
            self.process_with_camelot_fallback(document, filepath, fallback_tables, optimized_params_cache)
            
        # Clean out other blocks inside the table
        self.clean_contained_blocks(document)
            
        # Perform table merging if enabled
        if self.merger_config.enabled:
            self.merge_tables(document)
    
    def clean_contained_blocks(self, document: Document):
        """
        Clean out blocks contained within tables.
        
        Args:
            document: The document to process
        """
        for page in document.pages:
            child_contained_blocks = page.contained_blocks(document, self.contained_block_types)
            for block in page.contained_blocks(document, self.block_types):
                intersections = matrix_intersection_area(
                    [c.polygon.bbox for c in child_contained_blocks], 
                    [block.polygon.bbox]
                )
                for child, intersection in zip(child_contained_blocks, intersections):
                    # Adjust this to percentage of the child block that is enclosed by the table
                    intersection_pct = intersection / max(child.polygon.area, 1)
                    if intersection_pct > 0.95 and child.id in page.structure:
                        page.structure.remove(child.id)
    
    def finalize_cell_text(self, cell: SuryaTableCell):
        """
        Clean and prepare cell text.
        
        Args:
            cell: The table cell to process
            
        Returns:
            List of cleaned text lines
        """
        fixed_text = []
        text_lines = cell.text_lines if cell.text_lines else []
        for line in text_lines:
            text = line["text"].strip()
            if not text or text == ".":
                continue
            text = re.sub(r"(\s\.){2,}", "", text)  # Replace . . .
            text = re.sub(r"\.{2,}", "", text)  # Replace ..., like in table of contents
            text = self.normalize_spaces(fix_text(text))
            fixed_text.append(html.escape(text))
        return fixed_text
    
    @staticmethod
    def normalize_spaces(text):
        """
        Normalize various space characters to standard spaces.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text
        """
        space_chars = [
            '\u2003',  # em space
            '\u2002',  # en space
            '\u00A0',  # non-breaking space
            '\u200B',  # zero-width space
            '\u3000',  # ideographic space
        ]
        for space in space_chars:
            text = text.replace(space, ' ')
        return text
    
    def combine_dollar_column(self, tables: List[TableResult]):
        """
        Combine dollar sign columns with their value columns.
        
        Args:
            tables: List of table results to process
        """
        for table in tables:
            if len(table.cells) == 0:
                # Skip empty tables
                continue
            unique_cols = sorted(list(set([c.col_id for c in table.cells])))
            max_col = max(unique_cols)
            dollar_cols = []
            for col in unique_cols:
                # Cells in this col
                col_cells = [c for c in table.cells if c.col_id == col]
                col_text = ["\n".join(self.finalize_cell_text(c)).strip() for c in col_cells]
                all_dollars = all([ct in ["", "$"] for ct in col_text])
                colspans = [c.colspan for c in col_cells]
                span_into_col = [c for c in table.cells if c.col_id != col and c.col_id + c.colspan > col > c.col_id]
                
                # This is a column that is entirely dollar signs
                if all([
                    all_dollars,
                    len(col_cells) > 1,
                    len(span_into_col) == 0,
                    all([c == 1 for c in colspans]),
                    col < max_col
                ]):
                    next_col_cells = [c for c in table.cells if c.col_id == col + 1]
                    next_col_rows = [c.row_id for c in next_col_cells]
                    col_rows = [c.row_id for c in col_cells]
                    if len(next_col_cells) == len(col_cells) and next_col_rows == col_rows:
                        dollar_cols.append(col)
            
            if len(dollar_cols) == 0:
                continue
                
            dollar_cols = sorted(dollar_cols)
            col_offset = 0
            for col in unique_cols:
                col_cells = [c for c in table.cells if c.col_id == col]
                if col_offset == 0 and col not in dollar_cols:
                    continue
                    
                if col in dollar_cols:
                    col_offset += 1
                    for cell in col_cells:
                        text_lines = cell.text_lines if cell.text_lines else []
                        next_row_col = [c for c in table.cells if c.row_id == cell.row_id and c.col_id == col + 1]
                        
                        # Add dollar to start of the next column
                        next_text_lines = next_row_col[0].text_lines if next_row_col[0].text_lines else []
                        next_row_col[0].text_lines = deepcopy(text_lines) + deepcopy(next_text_lines)
                        table.cells = [c for c in table.cells if c.cell_id != cell.cell_id]  # Remove original cell
                        next_row_col[0].col_id -= col_offset
                else:
                    for cell in col_cells:
                        cell.col_id -= col_offset
    
    def split_combined_rows(self, tables: List[TableResult]):
        """
        Split combined rows in tables.
        
        Args:
            tables: List of table results to process
        """
        for table in tables:
            if len(table.cells) == 0:
                # Skip empty tables
                continue
            unique_rows = sorted(list(set([c.row_id for c in table.cells])))
            row_info = []
            for row in unique_rows:
                # Cells in this row
                # Deepcopy is because we do an in-place mutation later, and that can cause rows to shift to match rows in unique_rows
                # making them be processed twice
                row_cells = deepcopy([c for c in table.cells if c.row_id == row])
                rowspans = [c.rowspan for c in row_cells]
                line_lens = [len(c.text_lines) if isinstance(c.text_lines, list) else 1 for c in row_cells]
                
                # Other cells that span into this row
                rowspan_cells = [c for c in table.cells if c.row_id != row and c.row_id + c.rowspan > row > c.row_id]
                should_split_entire_row = all([
                    len(row_cells) > 1,
                    len(rowspan_cells) == 0,
                    all([r == 1 for r in rowspans]),
                    all([l > 1 for l in line_lens]),
                    all([l == line_lens[0] for l in line_lens])
                ])
                line_lens_counter = Counter(line_lens)
                counter_keys = sorted(list(line_lens_counter.keys()))
                should_split_partial_row = all([
                    len(row_cells) > 3,  # Only split if there are more than 3 cells
                    len(rowspan_cells) == 0,
                    all([r == 1 for r in rowspans]),
                    len(line_lens_counter) == 2 and counter_keys[0] <= 1 and counter_keys[1] > 1 and line_lens_counter[counter_keys[0]] == 1,  # Allow a single column with a single line
                ])
                should_split = should_split_entire_row or should_split_partial_row
                row_info.append({
                    "should_split": should_split,
                    "row_cells": row_cells,
                    "line_lens": line_lens
                })
                
            # Don't split if we're not splitting most of the rows in the table.  This avoids splitting stray multiline rows.
            if sum([r["should_split"] for r in row_info]) / len(row_info) < self.row_split_threshold:
                continue
                
            new_cells = []
            shift_up = 0
            max_cell_id = max([c.cell_id for c in table.cells])
            new_cell_count = 0
            for row, item_info in zip(unique_rows, row_info):
                max_lines = max(item_info["line_lens"])
                if item_info["should_split"]:
                    for i in range(0, max_lines):
                        for cell in item_info["row_cells"]:
                            # Calculate height based on number of splits
                            split_height = cell.bbox[3] - cell.bbox[1]
                            current_bbox = [
                                cell.bbox[0], 
                                cell.bbox[1] + i * split_height, 
                                cell.bbox[2], 
                                cell.bbox[1] + (i + 1) * split_height
                            ]
                            
                            line = [cell.text_lines[i]] if cell.text_lines and i < len(cell.text_lines) else None
                            cell_id = max_cell_id + new_cell_count
                            new_cells.append(
                                SuryaTableCell(
                                    polygon=current_bbox,
                                    text_lines=line,
                                    rowspan=1,
                                    colspan=cell.colspan,
                                    row_id=cell.row_id + shift_up + i,
                                    col_id=cell.col_id,
                                    is_header=cell.is_header and i == 0,  # Only first line is header
                                    within_row_id=cell.within_row_id,
                                    cell_id=cell_id
                                )
                            )
                            new_cell_count += 1
                            
                    # For each new row we add, shift up subsequent rows
                    # The max is to account for partial rows
                    shift_up += max_lines - 1
                else:
                    for cell in item_info["row_cells"]:
                        cell.row_id += shift_up
                        new_cells.append(cell)
                        
            # Only update the cells if we added new cells
            if len(new_cells) > len(table.cells):
                table.cells = new_cells
    
    def assign_text_to_cells(self, tables: List[TableResult], table_data: list):
        """
        Assign text to table cells.
        
        Args:
            tables: List of table results
            table_data: Table data information
        """
        for table_result, table_page_data in zip(tables, table_data):
            table_text_lines = table_page_data["table_text_lines"]
            table_cells: List[SuryaTableCell] = table_result.cells
            text_line_bboxes = [t["bbox"] for t in table_text_lines]
            table_cell_bboxes = [c.bbox for c in table_cells]
            
            intersection_matrix = matrix_intersection_area(text_line_bboxes, table_cell_bboxes)
            
            cell_text = defaultdict(list)
            for text_line_idx, table_text_line in enumerate(table_text_lines):
                intersections = intersection_matrix[text_line_idx]
                if intersections.sum() == 0:
                    continue
                    
                max_intersection = intersections.argmax()
                cell_text[max_intersection].append(table_text_line)
                
            for k in cell_text:
                # TODO: see if the text needs to be sorted (based on rotation)
                text = cell_text[k]
                assert all("text" in t for t in text), "All text lines must have text"
                assert all("bbox" in t for t in text), "All text lines must have a bbox"
                table_cells[k].text_lines = text
    
    def assign_pdftext_lines(self, extract_blocks: list, filepath: str):
        """
        Assign text lines from PDF text extraction.
        
        Args:
            extract_blocks: Blocks to process
            filepath: Path to the PDF file
        """
        table_inputs = []
        unique_pages = list(set([t["page_id"] for t in extract_blocks]))
        if len(unique_pages) == 0:
            return
            
        for page in unique_pages:
            tables = []
            img_size = None
            for block in extract_blocks:
                if block["page_id"] == page:
                    tables.append(block["table_bbox"])
                    img_size = block["img_size"]
                    
            table_inputs.append({
                "tables": tables,
                "img_size": img_size
            })
            
        cell_text = table_output(filepath, table_inputs, page_range=unique_pages, workers=self.pdftext_workers)
        assert len(cell_text) == len(unique_pages), "Number of pages and table inputs must match"
        
        for pidx, (page_tables, pnum) in enumerate(zip(cell_text, unique_pages)):
            table_idx = 0
            for block in extract_blocks:
                if block["page_id"] == pnum:
                    table_text = page_tables[table_idx]
                    if len(table_text) == 0:
                        block["ocr_block"] = True  # Re-OCR the block if pdftext didn't find any text
                    else:
                        block["table_text_lines"] = page_tables[table_idx]
                    table_idx += 1
            assert table_idx == len(page_tables), "Number of tables and table inputs must match"
    
    def assign_ocr_lines(self, ocr_blocks: list):
        """
        Assign text lines from OCR.
        
        Args:
            ocr_blocks: Blocks to process with OCR
        """
        det_images = [t["table_image"] for t in ocr_blocks]
        self.recognition_model.disable_tqdm = self.disable_tqdm
        self.detection_model.disable_tqdm = self.disable_tqdm
        ocr_results: List[OCRResult] = self.recognition_model(
            det_images,
            [None] * len(det_images),
            self.detection_model,
            recognition_batch_size=self.get_recognition_batch_size(),
            detection_batch_size=self.get_detection_batch_size()
        )
        
        for block, ocr_res in zip(ocr_blocks, ocr_results):
            table_cells = []
            for line in ocr_res.text_lines:
                # Don't need to correct back to image size
                # Table rec boxes are relative to the table
                table_cells.append({
                    "bbox": line.bbox,
                    "text": line.text
                })
            block["table_text_lines"] = table_cells
    
    def get_detection_batch_size(self):
        """Get batch size for detection model."""
        if self.detection_batch_size is not None:
            return self.detection_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 4
        return 4
    
    def get_table_rec_batch_size(self):
        """Get batch size for table recognition model."""
        if self.table_rec_batch_size is not None:
            return self.table_rec_batch_size
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 6
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        return 6
    
    def get_recognition_batch_size(self):
        """Get batch size for text recognition model."""
        if self.recognition_batch_size is not None:
            return self.recognition_batch_size
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 32
        return 32
    
    def process_with_camelot_fallback(self, document: Document, filepath: str, fallback_tables: List[dict], optimized_params_cache: Dict[int, Dict[str, Any]]):
        """
        Process tables using Camelot as a fallback.
        
        Args:
            document: The document object
            filepath: Path to the original PDF file
            fallback_tables: List of tables that need fallback processing
            optimized_params_cache: Cache of optimized parameters by page ID
        """
        if not CAMELOT_AVAILABLE or not fallback_tables:
            return
            
        try:
            for table_info in fallback_tables:
                page = table_info["page"]
                block = table_info["block"]
                page_idx = table_info["page_idx"]
                
                # Get cached optimized parameters or use defaults
                optimized_params = table_info.get("optimized_params", None)
                
                # Try parameter optimization if enabled and not already optimized
                if self.optimizer and self.optimizer_config.enabled and not optimized_params:
                    self.logger.info(f"Optimizing parameters for table on page {page_idx}")
                    optimized_params = self.optimizer.optimize(document, block, filepath)
                    
                    # Cache optimized parameters for this page
                    optimized_params_cache[page_idx] = optimized_params
                    
                # Camelot is 1-indexed for pages
                camelot_page_idx = page_idx + 1
                
                # Get the bbox coordinates in PDF coordinates (top-left origin)
                bbox = block.polygon.bbox
                page_height = page.polygon.height
                
                # Convert to Camelot format [left, top, right, bottom] in PDF coordinates
                # Camelot expects coordinates as a percentage of the page
                page_width = page.polygon.width
                camelot_bbox = [
                    bbox[0] / page_width,
                    (page_height - bbox[3]) / page_height,  # Flip Y coordinate (PDF origin is bottom-left)
                    bbox[2] / page_width,
                    (page_height - bbox[1]) / page_height,  # Flip Y coordinate
                ]
                
                # Prepare Camelot parameters
                camelot_kwargs = {
                    "pages": str(camelot_page_idx),
                    "table_areas": [camelot_bbox],
                }
                
                # Use optimized parameters if available, otherwise use defaults
                if optimized_params:
                    camelot_kwargs.update(optimized_params)
                else:
                    camelot_kwargs.update({
                        "flavor": self.camelot_flavor if self.camelot_flavor != "auto" else "lattice",
                        "line_scale": self.camelot_line_scale,
                        "line_width": self.camelot_line_width,
                        "copy_text": self.camelot_copy_text,
                        "edge_tol": self.camelot_edge_tol,
                        "row_tol": self.camelot_row_tol
                    })
                
                # Try Camelot with the specified parameters
                try:
                    tables = camelot.read_pdf(filepath, **camelot_kwargs)
                    
                    # If no tables or empty tables, try the other flavor if auto is enabled
                    if (len(tables) == 0 or tables[0].df.empty) and self.camelot_flavor == "auto":
                        alt_flavor = "stream" if camelot_kwargs.get("flavor", "lattice") == "lattice" else "lattice"
                        camelot_kwargs["flavor"] = alt_flavor
                        tables = camelot.read_pdf(filepath, **camelot_kwargs)
                        
                    # Process the extracted table
                    if len(tables) > 0 and not tables[0].df.empty:
                        camelot_table = tables[0]
                        self.camelot_table_to_cells(document, page, block, camelot_table)
                        block.update_metadata(extraction_method="camelot")
                except Exception as e:
                    self.logger.error(f"Camelot fallback error: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Camelot processing error: {e}")
    
    def camelot_table_to_cells(self, document: Document, page: PageGroup, block, camelot_table):
        """
        Convert a Camelot table to TableCell objects.
        
        Args:
            document: The document object
            page: The page object
            block: The table block
            camelot_table: The Camelot table object
        """
        # Clear any existing structure
        block.structure = []
        
        # Get the table dataframe
        df = camelot_table.df
        
        # Identify likely header rows
        # Typically, the first row is a header, but some tables have multiple header rows
        # or no headers at all. Use heuristics to identify headers.
        is_header_row = [False] * len(df.index)
        is_header_row[0] = True  # Assume first row is header by default
        
        # Create cells for each cell in the dataframe
        for row_id, row in enumerate(df.index):
            for col_id, col in enumerate(df.columns):
                cell_text = df.iloc[row_id, col_id]
                
                # Skip empty cells
                if not cell_text or cell_text.strip() == "":
                    continue
                    
                # Calculate cell position - divide the table block into a grid
                rows, cols = df.shape
                cell_width = block.polygon.width / cols
                cell_height = block.polygon.height / rows
                
                # Calculate cell bbox
                x_start = block.polygon.bbox[0] + (col_id * cell_width)
                y_start = block.polygon.bbox[1] + (row_id * cell_height)
                x_end = x_start + cell_width
                y_end = y_start + cell_height
                
                # Create cell polygon
                cell_polygon = PolygonBox.from_bbox([x_start, y_start, x_end, y_end])
                
                # Create TableCell object
                cell_block = TableCell(
                    polygon=cell_polygon,
                    text_lines=[cell_text.strip()],
                    rowspan=1,  # Camelot doesn't preserve rowspan/colspan information
                    colspan=1,
                    row_id=row_id,
                    col_id=col_id,
                    is_header=is_header_row[row_id],
                    page_id=page.page_id,
                )
                
                # Add cell to page and table
                page.add_full_block(cell_block)
                block.add_structure(cell_block)
    
    def merge_tables(self, document: Document):
        """
        Merge tables that span multiple pages or regions.
        
        Args:
            document: The document to process
        """
        # Implement table merging based on TableMergerConfig
        # This is a simplified version - for a full implementation, consider
        # adapting LLMTableMergeProcessor or implementing a custom solution
        
        if not self.merger_config.enabled:
            return
            
        self.logger.info("Performing table merging...")
        
        # Find table runs (consecutive tables that might be merged)
        table_runs = []
        table_run = []
        prev_block = None
        prev_page_block_count = None
        
        for page in document.pages:
            page_blocks = page.contained_blocks(document, self.block_types)
            for block in page_blocks:
                merge_condition = False
                if prev_block is not None:
                    prev_cells = prev_block.contained_blocks(document, (BlockTypes.TableCell,))
                    curr_cells = block.contained_blocks(document, (BlockTypes.TableCell,))
                    
                    # Get row and column counts
                    prev_row_count = len(set([cell.row_id for cell in prev_cells]))
                    curr_row_count = len(set([cell.row_id for cell in curr_cells]))
                    prev_col_count = len(set([cell.col_id for cell in prev_cells]))
                    curr_col_count = len(set([cell.col_id for cell in curr_cells]))
                    
                    row_match = abs(prev_row_count - curr_row_count) < 5  # Similar number of rows
                    col_match = abs(prev_col_count - curr_col_count) < 2  # Similar number of columns
                    
                    # Check for different merge conditions
                    subsequent_page_table = all([
                        prev_block.page_id == block.page_id - 1,  # Subsequent pages
                        max(prev_block.polygon.height / page.polygon.height,
                            block.polygon.height / page.polygon.height) > self.merger_config.table_height_threshold,  # Take up most of page
                        (len(page_blocks) == 1 or prev_page_block_count == 1),  # Only table on the page
                        (row_match or col_match)  # Similar structure
                    ])
                    
                    same_page_vertical_table = all([
                        prev_block.page_id == block.page_id,  # On the same page
                        (1 - self.merger_config.vertical_table_height_threshold) < 
                            prev_block.polygon.height / block.polygon.height < 
                            (1 + self.merger_config.vertical_table_height_threshold),  # Similar height
                        abs(block.polygon.x_start - prev_block.polygon.x_end) < 
                            self.merger_config.vertical_table_distance_threshold,  # Close in x
                        abs(block.polygon.y_start - prev_block.polygon.y_start) < 
                            self.merger_config.vertical_table_distance_threshold,  # Close in y
                        row_match
                    ])
                    
                    same_page_horizontal_table = all([
                        prev_block.page_id == block.page_id,  # On the same page
                        (1 - self.merger_config.horizontal_table_width_threshold) < 
                            prev_block.polygon.width / block.polygon.width < 
                            (1 + self.merger_config.horizontal_table_width_threshold),  # Similar width
                        abs(block.polygon.y_start - prev_block.polygon.y_end) < 
                            self.merger_config.horizontal_table_distance_threshold,  # Close in y
                        abs(block.polygon.x_start - prev_block.polygon.x_start) < 
                            self.merger_config.horizontal_table_distance_threshold,  # Close in x
                        col_match
                    ])
                    
                    same_page_new_column = all([
                        prev_block.page_id == block.page_id,  # On the same page
                        abs(block.polygon.x_start - prev_block.polygon.x_end) < self.merger_config.column_gap_threshold,
                        block.polygon.y_start < prev_block.polygon.y_end,
                        block.polygon.width * (1 - self.merger_config.vertical_table_height_threshold) < 
                            prev_block.polygon.width < 
                            block.polygon.width * (1 + self.merger_config.vertical_table_height_threshold),  # Similar width
                        col_match
                    ])
                    
                    merge_condition = any([
                        subsequent_page_table,
                        same_page_vertical_table,
                        same_page_new_column,
                        same_page_horizontal_table
                    ])
                
                if prev_block is not None and merge_condition:
                    if prev_block not in table_run:
                        table_run.append(prev_block)
                    table_run.append(block)
                else:
                    if table_run:
                        table_runs.append(table_run)
                    table_run = []
                prev_block = block
            prev_page_block_count = len(page_blocks)
            
        if table_run:
            table_runs.append(table_run)
            
        # Merge tables in each run
        for run in table_runs:
            if len(run) < 2:
                continue
                
            self.logger.info(f"Merging table run with {len(run)} tables")
            self._merge_table_run(document, run)
    
    def _merge_table_run(self, document: Document, blocks: List[Block]):
        """
        Merge a run of tables.
        
        Args:
            document: The document object
            blocks: List of table blocks to merge
        """
        if len(blocks) < 2:
            return
            
        start_block = blocks[0]
        
        for i in range(1, len(blocks)):
            curr_block = blocks[i]
            
            # Get cells for both blocks
            children = start_block.contained_blocks(document, (BlockTypes.TableCell,))
            children_curr = curr_block.contained_blocks(document, (BlockTypes.TableCell,))
            
            if not children or not children_curr:
                break
                
            # Determine merge direction based on relative positions
            if curr_block.page_id > start_block.page_id:
                # Tables on different pages, likely bottom merge
                direction = "bottom"
            elif abs(curr_block.polygon.x_start - start_block.polygon.x_end) < self.merger_config.column_gap_threshold:
                # Tables side by side, likely right merge
                direction = "right"
            elif abs(curr_block.polygon.y_start - start_block.polygon.y_end) < self.merger_config.horizontal_table_distance_threshold:
                # Tables stacked vertically, likely bottom merge
                direction = "bottom"
            else:
                # Default to bottom merge
                direction = "bottom"
                
            # Validate the merge direction
            if direction == "right" and abs(len(children) - len(children_curr)) > 5:
                # Row counts differ too much for right merge
                direction = "bottom"
            elif direction == "bottom" and abs(max([c.col_id for c in children]) - max([c.col_id for c in children_curr])) > 2:
                # Column counts differ too much for bottom merge
                direction = "right"
                
            # Use LLM for merge decision if enabled
            if self.merger_config.use_llm_for_merge_decisions and hasattr(self, 'llm_service') and self.llm_service:
                # This would call an LLM to decide on the merge, similar to LLMTableMergeProcessor
                # For now, we'll use the heuristic decision above
                pass
                
            # Perform the merge if valid
            merged_cells = self._join_cells(children, children_curr, direction)
            curr_block.structure = []
            start_block.structure = [b.id for b in merged_cells]
            
            # Update metadata
            start_block.update_metadata(merge_direction=direction, merged_with=curr_block.id)
    
    def _join_cells(self, cells1: List[TableCell], cells2: List[TableCell], direction: str = 'right') -> List[TableCell]:
        """
        Join cells from two tables.
        
        Args:
            cells1: Cells from the first table
            cells2: Cells from the second table
            direction: Merge direction ('right' or 'bottom')
            
        Returns:
            List of merged cells
        """
        if direction == 'right':
            # Shift columns right
            col_count = max([cell.col_id for cell in cells1]) + 1
            for cell in cells2:
                cell.col_id += col_count
            new_cells = cells1 + cells2
        else:
            # Shift rows down
            row_count = max([cell.row_id for cell in cells1]) + 1
            for cell in cells2:
                cell.row_id += row_count
            new_cells = cells1 + cells2
            
        return new_cells