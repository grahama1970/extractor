"""
Module: table.py
Description: Implementation of table functionality

External Dependencies:
- html: [Documentation URL]
- ftfy: [Documentation URL]
- surya: [Documentation URL]
- pdftext: [Documentation URL]
- camelot: [Documentation URL]
- cv2: [Documentation URL]
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

import re
import html
import os
from collections import defaultdict
from copy import deepcopy
from typing import Annotated, List, Optional
from collections import Counter

from ftfy import fix_text
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor, OCRResult
from surya.table_rec import TableRecPredictor
from surya.table_rec.schema import TableResult, TableCell as SuryaTableCell
from pdftext.extraction import table_output

# Import camelot for heuristic table extraction fallback
try:
    import camelot
    import cv2
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False

from extractor.core.processors import BaseProcessor
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks.tablecell import TableCell
from extractor.core.schema.document import Document
from extractor.core.schema.polygon import PolygonBox
from extractor.core.settings import settings
from extractor.core.util import matrix_intersection_area


class TableProcessor(BaseProcessor):
    """
    A processor for recognizing tables in the document.
    """
    block_types = (BlockTypes.Table, BlockTypes.TableOfContents, BlockTypes.Form)
    detect_boxes: Annotated[
        bool,
        "Whether to detect boxes for the table recognition model.",
    ] = False
    detection_batch_size: Annotated[
        int,
        "The batch size to use for the table detection model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    table_rec_batch_size: Annotated[
        int,
        "The batch size to use for the table recognition model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    recognition_batch_size: Annotated[
        int,
        "The batch size to use for the table recognition model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    contained_block_types: Annotated[
        List[BlockTypes],
        "Block types to remove if they're contained inside the tables."
    ] = (BlockTypes.Text, BlockTypes.TextInlineMath)
    row_split_threshold: Annotated[
        float,
        "The percentage of rows that need to be split across the table before row splitting is active.",
    ] = 0.5
    pdftext_workers: Annotated[
        int,
        "The number of workers to use for pdftext.",
    ] = 1
    disable_tqdm: Annotated[
        bool,
        "Whether to disable the tqdm progress bar.",
    ] = False
    use_camelot_fallback: Annotated[
        bool,
        "Whether to use Camelot as a fallback for table extraction when the primary method fails or produces poor results.",
    ] = True
    camelot_min_cell_threshold: Annotated[
        int,
        "Minimum number of cells required in a table. If below this threshold, try Camelot as fallback.",
    ] = 4
    camelot_flavor: Annotated[
        str,
        "The Camelot flavor to use: 'lattice' or 'stream'. Lattice works better for tables with borders, stream for borderless tables.",
    ] = "lattice"
    camelot_line_width: Annotated[
        int,
        "The line width parameter for Camelot. Higher values (10-20) work better for tables with thick borders.",
    ] = 15

    def __init__(
        self,
        detection_model: DetectionPredictor,
        recognition_model: RecognitionPredictor,
        table_rec_model: TableRecPredictor,
        config=None
    ):
        super().__init__(config)

        self.detection_model = detection_model
        self.recognition_model = recognition_model
        self.table_rec_model = table_rec_model

    def __call__(self, document: Document):
        filepath = document.filepath  # Path to original pdf file

        table_data = []
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                image = block.get_image(document, highres=True)
                image_poly = block.polygon.rescale((page.polygon.width, page.polygon.height), page.get_image(highres=True).size)

                table_data.append({
                    "block_id": block.id,
                    "page_id": page.page_id,
                    "table_image": image,
                    "table_bbox": image_poly.bbox,
                    "img_size": page.get_image(highres=True).size,
                    "ocr_block": page.text_extraction_method == "surya",
                    "block": block,  # Store reference to the original block
                })

        extract_blocks = [t for t in table_data if not t["ocr_block"]]
        self.assign_pdftext_lines(extract_blocks, filepath) # Handle tables where good text exists in the PDF

        ocr_blocks = [t for t in table_data if t["ocr_block"]]
        self.assign_ocr_lines(ocr_blocks)  # Handle tables where OCR is needed
        assert all("table_text_lines" in t for t in table_data), "All table data must have table cells"

        self.table_rec_model.disable_tqdm = self.disable_tqdm
        tables: List[TableResult] = self.table_rec_model(
            [t["table_image"] for t in table_data],
            batch_size=self.get_table_rec_batch_size()
        )
        self.assign_text_to_cells(tables, table_data)
        self.split_combined_rows(tables) # Split up rows that were combined
        self.combine_dollar_column(tables) # Combine columns that are just dollar signs

        # Track tables that need fallback processing
        fallback_tables = []

        # Assign table cells to the table
        table_idx = 0
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                block.structure = [] # Remove any existing lines, spans, etc.
                cells: List[SuryaTableCell] = tables[table_idx].cells

                # Check if we should use Camelot fallback
                # Trigger on: 1) too few cells, 2) low quality score, 3) extraction issues
                quality_score = getattr(block, 'quality_score', 1.0) or 1.0
                extraction_method = getattr(block, 'extraction_method', None)
                
                should_use_camelot = (
                    self.use_camelot_fallback and 
                    CAMELOT_AVAILABLE and
                    (len(cells) < self.camelot_min_cell_threshold or
                     quality_score < 0.6 or
                     extraction_method == 'failed')
                )
                
                if should_use_camelot:
                    fallback_tables.append({
                        "page": page,
                        "block": block,
                        "page_idx": page.page_id,
                        "table_data": table_data[table_idx]
                    })
                else:
                    # Process with default method
                    for cell in cells:
                        # Rescale the cell polygon to the page size
                        cell_polygon = PolygonBox(polygon=cell.polygon).rescale(page.get_image(highres=True).size, page.polygon.size)

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
                    
                    # Add extraction metadata for Surya tables (only for Table blocks)
                    if block.block_type == BlockTypes.Table:
                        # Set as dynamic attributes for the JSON renderer to pick up
                        block.extraction_method = "surya"
                        block.extraction_details = {
                            "model": "table_recognition",  
                            "confidence": None  # Surya doesn't provide confidence scores directly
                        }
                        # Initialize quality fields to None - will be set by other processors if needed
                        block.quality_score = None
                        block.quality_metrics = None
                        block.merge_info = None
                table_idx += 1

        # Process fallback tables with Camelot if needed
        if fallback_tables:
            self.process_with_camelot_fallback(document, filepath, fallback_tables)

        # Clean out other blocks inside the table
        # This can happen with stray text blocks inside the table post-merging
        for page in document.pages:
            child_contained_blocks = page.contained_blocks(document, self.contained_block_types)
            for block in page.contained_blocks(document, self.block_types):
                intersections = matrix_intersection_area([c.polygon.bbox for c in child_contained_blocks], [block.polygon.bbox])
                for child, intersection in zip(child_contained_blocks, intersections):
                    # Adjust this to percentage of the child block that is enclosed by the table
                    intersection_pct = intersection / max(child.polygon.area, 1)
                    if intersection_pct > 0.95 and child.id in page.structure:
                        page.structure.remove(child.id)

    def finalize_cell_text(self, cell: SuryaTableCell):
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
                        table.cells = [c for c in table.cells if c.cell_id != cell.cell_id] # Remove original cell
                        next_row_col[0].col_id -= col_offset
                else:
                    for cell in col_cells:
                        cell.col_id -= col_offset


    def split_combined_rows(self, tables: List[TableResult]):
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
                    len(row_cells) > 3, # Only split if there are more than 3 cells
                    len(rowspan_cells) == 0,
                    all([r == 1 for r in rowspans]),
                    len(line_lens_counter) == 2 and counter_keys[0] <= 1 and counter_keys[1] > 1 and line_lens_counter[counter_keys[0]] == 1, # Allow a single column with a single line - keys are the line lens, values are the counts
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
                            current_bbox = [cell.bbox[0], cell.bbox[1] + i * split_height, cell.bbox[2], cell.bbox[1] + (i + 1) * split_height]

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
                                    is_header=cell.is_header and i == 0, # Only first line is header
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
                        block["ocr_block"] = True # Re-OCR the block if pdftext didn't find any text
                    else:
                        block["table_text_lines"] = page_tables[table_idx]
                    table_idx += 1
            assert table_idx == len(page_tables), "Number of tables and table inputs must match"

    def assign_ocr_lines(self, ocr_blocks: list):
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
        if self.detection_batch_size is not None:
            return self.detection_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 4
        return 4

    def get_table_rec_batch_size(self):
        if self.table_rec_batch_size is not None:
            return self.table_rec_batch_size
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 6
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        return 6

    def get_recognition_batch_size(self):
        if self.recognition_batch_size is not None:
            return self.recognition_batch_size
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 32
        return 32

    def process_with_camelot_fallback(self, document: Document, filepath: str, fallback_tables: List[dict]):
        """
        Process tables using Camelot as a fallback when the primary method fails or produces poor results.

        Args:
            document: The document object
            filepath: Path to the original PDF file
            fallback_tables: List of tables that need fallback processing
        """
        if not CAMELOT_AVAILABLE or not fallback_tables:
            return

        try:
            for table_info in fallback_tables:
                page = table_info["page"]
                block = table_info["block"]
                page_idx = table_info["page_idx"]

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

                # Try Camelot with the specified flavor
                try:
                    tables = camelot.read_pdf(
                        filepath,
                        pages=str(camelot_page_idx),
                        flavor=self.camelot_flavor,
                        table_areas=[camelot_bbox],
                        line_scale=self.camelot_line_width
                    )

                    # If no tables or empty tables, try the other flavor
                    if len(tables) == 0 or tables[0].df.empty:
                        alt_flavor = "stream" if self.camelot_flavor == "lattice" else "lattice"
                        tables = camelot.read_pdf(
                            filepath,
                            pages=str(camelot_page_idx),
                            flavor=alt_flavor,
                            table_areas=[camelot_bbox],
                            line_scale=self.camelot_line_width
                        )

                    # Process the extracted table
                    if len(tables) > 0 and not tables[0].df.empty:
                        camelot_table = tables[0]
                        self.camelot_table_to_cells(document, page, block, camelot_table)
                        block.update_extraction_metadata(method="camelot", details={
                            "flavor": alt_flavor,
                            "line_scale": self.camelot_line_width
                        })
                except Exception as e:
                    print(f"Camelot fallback error: {e}")
                    continue

        except Exception as e:
            print(f"Camelot processing error: {e}")

    def camelot_table_to_cells(self, document: Document, page, block, camelot_table):
        """
        Convert a Camelot table to TableCell objects and add them to the document.

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
                is_header = row_id == 0  # Assume first row is header
                cell_block = TableCell(
                    polygon=cell_polygon,
                    text_lines=[cell_text.strip()],
                    rowspan=1,  # Camelot doesn't preserve rowspan/colspan information
                    colspan=1,
                    row_id=row_id,
                    col_id=col_id,
                    is_header=is_header,
                    page_id=page.page_id,
                )

                # Add cell to page and table
                page.add_full_block(cell_block)
                block.add_structure(cell_block)
        
        # Add extraction metadata for Camelot tables
        if block.block_type == BlockTypes.Table:
            # Set as dynamic attributes for the JSON renderer to pick up
            block.extraction_method = "camelot"
            block.extraction_details = {
                "model": "camelot",
                "method": "heuristic",
                "flavor": alt_flavor if 'alt_flavor' in locals() else "lattice"
            }
            # Initialize quality fields to None - will be set by other processors if needed
            block.quality_score = None
            block.quality_metrics = None
            block.merge_info = None
