"""
Table merger for detecting and merging related tables.

This module provides a class for detecting and merging related tables in a document.
It uses the table comparison utilities to determine if tables should be merged, and
provides methods for merging both Camelot tables and Marker document tables.

References:
- pandas documentation: https://pandas.pydata.org/docs/
- Camelot documentation: https://camelot-py.readthedocs.io/en/master/

Sample input:
- List of tables (either as Camelot Table objects or Marker document blocks)
- Document object containing tables

Expected output:
- Merged tables with proper structures and metadata
"""

import sys
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pandas as pd
from loguru import logger

from marker.schema import BlockTypes
from marker.schema.blocks.table import Table
from marker.schema.blocks.tablecell import TableCell
from marker.schema.document import Document
from marker.schema.polygon import PolygonBox
from marker.utils.table_comparison import should_merge_tables


class TableMerger:
    """
    Class for detecting and merging related tables in a document.
    """
    
    def __init__(self, config=None):
        """
        Initialize TableMerger with configuration options.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.merge_thresholds = self.config.get('merge_thresholds', {
            'structure_weight': 0.4,
            'content_weight': 0.3,
            'position_weight': 0.3,
            'column_similarity_threshold': 0.7,
            'header_similarity_threshold': 0.7,
            'vertical_proximity_threshold': 0.8,
            'horizontal_overlap_threshold': 0.7,
            'merge_threshold': 0.65
        })
    
    def check_tables_for_merges(
        self,
        tables: List[Dict[str, Any]],
        page_heights: Optional[Dict[int, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Check all tables for potential merges and return merged tables.
        
        Args:
            tables: List of table dictionaries with metadata
            page_heights: Dictionary mapping page numbers to page heights
            
        Returns:
            List of merged and unmerged tables
        """
        if len(tables) <= 1:
            return tables
        
        # Default page height if not provided
        if not page_heights:
            page_heights = {}
        default_page_height = 800.0  # Default value if unknown
        
        # Create a new list for merged tables
        merged_tables = []
        
        # Track which tables have been merged
        merged_indices = set()
        
        # Check each pair of tables
        for i in range(len(tables)):
            # Skip if this table was already merged
            if i in merged_indices:
                continue
            
            current_table = tables[i]
            current_metadata = {
                'page': current_table.get('page', 0),
                'bbox': current_table.get('bbox', [0, 0, 0, 0])
            }
            
            # Find tables to merge with current table
            tables_to_merge = []
            
            for j in range(i + 1, len(tables)):
                # Skip if this table was already merged
                if j in merged_indices:
                    continue
                
                next_table = tables[j]
                next_metadata = {
                    'page': next_table.get('page', 0),
                    'bbox': next_table.get('bbox', [0, 0, 0, 0])
                }
                
                # Get page height
                page1 = current_metadata['page']
                page2 = next_metadata['page']
                page_height = page_heights.get(max(page1, page2), default_page_height)
                
                # Check if tables should be merged
                merge_result = should_merge_tables(
                    current_table.get('table_data', []),
                    next_table.get('table_data', []),
                    current_metadata,
                    next_metadata,
                    page_height,
                    self.merge_thresholds
                )
                
                if merge_result['should_merge']:
                    tables_to_merge.append((j, next_table, merge_result))
            
            # If no tables to merge, add current table to result
            if not tables_to_merge:
                merged_tables.append(current_table)
                continue
            
            # Merge tables
            merged_table = self._merge_tables([current_table] + [t[1] for t in tables_to_merge])
            merged_tables.append(merged_table)
            
            # Mark tables as merged
            merged_indices.add(i)
            for j, _, _ in tables_to_merge:
                merged_indices.add(j)
        
        # Add any tables that weren't merged
        for i, table in enumerate(tables):
            if i not in merged_indices:
                merged_tables.append(table)
        
        return merged_tables
    
    def _merge_tables(self, tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple tables into a single table.
        
        Args:
            tables: List of table dictionaries to merge
            
        Returns:
            Merged table dictionary
        """
        if not tables:
            return {}
        
        if len(tables) == 1:
            return tables[0]
        
        # Create a new table dictionary
        merged_table = {
            'table_number': [t.get('table_number', i) for i, t in enumerate(tables)],
            'pages': [t.get('page', 0) for t in tables],
            'bbox': self._merge_bboxes([t.get('bbox', [0, 0, 0, 0]) for t in tables]),
            'table_data': self._merge_table_data([t.get('table_data', []) for t in tables]),
            'merged': True,
            'source_tables': tables
        }
        
        # Copy metadata from the first table
        if 'parsing_report' in tables[0]:
            merged_table['parsing_report'] = {
                'accuracy': max(t.get('parsing_report', {}).get('accuracy', 0) for t in tables),
                'whitespace': sum(t.get('parsing_report', {}).get('whitespace', 0) for t in tables) / len(tables),
                'order': tables[0].get('parsing_report', {}).get('order', 0)
            }
        
        return merged_table
    
    def _merge_bboxes(self, bboxes: List[List[float]]) -> List[float]:
        """
        Merge multiple bounding boxes into a single bounding box.
        
        Args:
            bboxes: List of bounding boxes to merge
            
        Returns:
            Merged bounding box
        """
        if not bboxes:
            return [0, 0, 0, 0]
        
        if len(bboxes) == 1:
            return bboxes[0]
        
        # Find the minimum and maximum coordinates
        min_x = min(bbox[0] for bbox in bboxes)
        min_y = min(bbox[1] for bbox in bboxes)
        max_x = max(bbox[2] for bbox in bboxes)
        max_y = max(bbox[3] for bbox in bboxes)
        
        return [min_x, min_y, max_x, max_y]
    
    def _merge_table_data(self, table_data_list: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Merge multiple table data lists into a single table data list.
        
        Args:
            table_data_list: List of table data lists to merge
            
        Returns:
            Merged table data list
        """
        if not table_data_list:
            return []
        
        if len(table_data_list) == 1:
            return table_data_list[0]
        
        # Convert all to DataFrames
        dfs = []
        for table_data in table_data_list:
            if table_data:
                dfs.append(pd.DataFrame(table_data))
        
        if not dfs:
            return []
        
        # Check if tables have the same column structure
        reference_df = dfs[0]
        same_columns = all(set(df.columns) == set(reference_df.columns) for df in dfs)
        
        if same_columns:
            # Simple concatenation for same structure
            merged_df = pd.concat(dfs, ignore_index=True)
        else:
            # For different column structures, use outer join
            merged_df = pd.concat(dfs, ignore_index=True, sort=False)
            # Fill any NaN values
            merged_df = merged_df.fillna('')
        
        # Convert back to list of dictionaries
        return merged_df.to_dict('records')
    
    def merge_document_tables(self, document: Document) -> None:
        """
        Detect and merge tables in a document.
        
        Args:
            document: The document object
        """
        # Get all tables from the document
        tables = []
        page_heights = {}
        
        for page in document.pages:
            page_heights[page.page_id] = page.polygon.height
            
            for block in page.contained_blocks(document, (BlockTypes.Table,)):
                # Create metadata for the table
                table_data = []
                cells = block.contained_blocks(document, (BlockTypes.TableCell,))
                
                if not cells:
                    continue
                
                # Convert cells to table data
                max_row = max(cell.row_id for cell in cells)
                max_col = max(cell.col_id for cell in cells)
                
                # Create empty table with appropriate dimensions
                table_data = [
                    {str(col): '' for col in range(max_col + 1)}
                    for _ in range(max_row + 1)
                ]
                
                # Fill in the table data
                for cell in cells:
                    row = cell.row_id
                    col = cell.col_id
                    text = ' '.join(cell.text_lines) if hasattr(cell, 'text_lines') else ''
                    
                    if 0 <= row < len(table_data) and str(col) in table_data[row]:
                        table_data[row][str(col)] = text
                
                # Add table to the list
                tables.append({
                    'block_id': block.id,
                    'page': page.page_id,
                    'bbox': block.polygon.bbox,
                    'table_data': table_data
                })
        
        # Check for tables to merge
        if len(tables) <= 1:
            return
        
        merged_tables = self.check_tables_for_merges(tables, page_heights)
        
        # Apply merges to the document
        self._apply_merges_to_document(document, merged_tables)
    
    def _apply_merges_to_document(
        self,
        document: Document,
        merged_tables: List[Dict[str, Any]]
    ) -> None:
        """
        Apply table merges to the document.
        
        Args:
            document: The document object
            merged_tables: List of merged tables
        """
        # Track merged table IDs
        merged_ids = set()
        
        # Process merged tables
        for merged_table in merged_tables:
            if not merged_table.get('merged', False):
                continue
            
            # Get source table IDs
            source_blocks = []
            for source_table in merged_table.get('source_tables', []):
                block_id = source_table.get('block_id')
                if block_id:
                    for page in document.pages:
                        for block in page.contained_blocks(document, (BlockTypes.Table,)):
                            if block.id == block_id:
                                source_blocks.append((page, block))
                                merged_ids.add(block_id)
                                break
            
            if not source_blocks:
                continue
            
            # Use the first source block as the base for the merged table
            base_page, base_block = source_blocks[0]
            
            # Remove cells from all source blocks
            for page, block in source_blocks:
                cells = block.contained_blocks(document, (BlockTypes.TableCell,))
                for cell in cells:
                    if cell.id in page.structure:
                        page.structure.remove(cell.id)
                block.structure = []
            
            # Create cells for the merged table
            table_data = merged_table.get('table_data', [])
            if not table_data:
                continue
            
            # Convert to DataFrame for easier processing
            df = pd.DataFrame(table_data)
            
            # Calculate cell dimensions based on the base block
            rows, cols = df.shape
            cell_width = base_block.polygon.width / cols
            cell_height = base_block.polygon.height / rows
            
            # Create cells for each cell in the dataframe
            for row_id, row in enumerate(df.index):
                for col_id, col in enumerate(df.columns):
                    cell_text = df.iloc[row_id, col_id]
                    
                    # Skip empty cells
                    if pd.isna(cell_text) or cell_text == '':
                        continue
                    
                    # Calculate cell bbox
                    x_start = base_block.polygon.bbox[0] + (col_id * cell_width)
                    y_start = base_block.polygon.bbox[1] + (row_id * cell_height)
                    x_end = x_start + cell_width
                    y_end = y_start + cell_height
                    
                    # Create cell polygon
                    cell_polygon = PolygonBox.from_bbox([x_start, y_start, x_end, y_end])
                    
                    # Create TableCell object
                    is_header = row_id == 0  # Assume first row is header
                    cell_block = TableCell(
                        polygon=cell_polygon,
                        text_lines=[str(cell_text)],
                        rowspan=1,
                        colspan=1,
                        row_id=row_id,
                        col_id=col_id,
                        is_header=is_header,
                        page_id=base_page.page_id,
                    )
                    
                    # Add cell to page and table
                    base_page.add_full_block(cell_block)
                    base_block.add_structure(cell_block)
            
            # Update metadata on the base block
            base_block.update_metadata(merged=True, source_ids=[b.id for _, b in source_blocks])
        
        # Remove other blocks that were merged
        for page in document.pages:
            to_remove = []
            for block in page.contained_blocks(document, (BlockTypes.Table,)):
                if block.id in merged_ids and not hasattr(block, 'merged'):
                    to_remove.append(block.id)
            
            for block_id in to_remove:
                if block_id in page.structure:
                    page.structure.remove(block_id)


if __name__ == "__main__":
    """
    Validation function to test the TableMerger class.
    """
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Check tables for merges
    total_tests += 1
    try:
        merger = TableMerger()
        
        # Create some test tables
        tables = [
            {
                'table_number': 1,
                'page': 1,
                'bbox': [100, 100, 300, 200],
                'table_data': [{'0': 'Header 1', '1': 'Header 2'}, {'0': 'A', '1': 'B'}]
            },
            {
                'table_number': 2,
                'page': 1,
                'bbox': [100, 250, 300, 350],
                'table_data': [{'0': 'Header 1', '1': 'Header 2'}, {'0': 'C', '1': 'D'}]
            },
            {
                'table_number': 3,
                'page': 2,
                'bbox': [400, 100, 600, 200],
                'table_data': [{'0': 'Header X', '1': 'Header Y'}, {'0': 'E', '1': 'F'}]
            }
        ]
        
        page_heights = {1: 800, 2: 800}
        
        # Check for merges
        merged_tables = merger.check_tables_for_merges(tables, page_heights)
        
        # Should have identified merges for tables 1 and 2
        merged_count = sum(1 for t in merged_tables if t.get('merged', False))
        total_count = len(merged_tables)
        
        # Check results
        if merged_count != 1:
            all_validation_failures.append(f"Expected 1 merged table, got {merged_count}")
        
        if total_count != 2:  # 1 merged table + 1 unmerged table
            all_validation_failures.append(f"Expected 2 total tables, got {total_count}")
        
        # Check merged table data
        merged_table = next((t for t in merged_tables if t.get('merged', False)), None)
        if merged_table:
            merged_data = merged_table.get('table_data', [])
            if len(merged_data) != 4:  # 2 rows from each table
                all_validation_failures.append(f"Expected 4 rows in merged table, got {len(merged_data)}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 1: {str(e)}")
    
    # Test 2: _merge_bboxes
    total_tests += 1
    try:
        merger = TableMerger()
        
        bboxes = [
            [100, 100, 300, 200],
            [150, 150, 350, 250],
            [50, 200, 250, 300]
        ]
        
        merged_bbox = merger._merge_bboxes(bboxes)
        expected_bbox = [50, 100, 350, 300]
        
        if merged_bbox != expected_bbox:
            all_validation_failures.append(f"Expected bbox {expected_bbox}, got {merged_bbox}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 2: {str(e)}")
    
    # Test 3: _merge_table_data
    total_tests += 1
    try:
        merger = TableMerger()
        
        table_data_lists = [
            [{'0': 'Header 1', '1': 'Header 2'}, {'0': 'A', '1': 'B'}],
            [{'0': 'Header 1', '1': 'Header 2'}, {'0': 'C', '1': 'D'}]
        ]
        
        merged_data = merger._merge_table_data(table_data_lists)
        expected_len = 4  # 2 rows from each table
        
        if len(merged_data) != expected_len:
            all_validation_failures.append(f"Expected {expected_len} rows in merged data, got {len(merged_data)}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 3: {str(e)}")
    
    # Final validation result
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("TableMerger is validated and formal tests can now be written")
        sys.exit(0)