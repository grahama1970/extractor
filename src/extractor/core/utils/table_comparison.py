"""
Table comparison utilities for detecting and merging related tables.
Module: table_comparison.py
Description: Functions for table comparison operations

This module provides functions for comparing tables to determine if they are related
or should be merged. It includes methods for comparing table structure, content,
and position to make informed decisions about table relationships.

References:
- pandas documentation: https://pandas.pydata.org/docs/
- fuzzywuzzy documentation: https://github.com/seatgeek/fuzzywuzzy

Sample input:
- Two tables (either as Camelot Table objects or pandas DataFrames)
- Table metadata including position and page information

Expected output:
- Similarity scores and merge recommendations
"""

import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from loguru import logger
from rapidfuzz import fuzz


def compare_table_structure(
    table1: pd.DataFrame,
    table2: pd.DataFrame
) -> Dict[str, Union[bool, float]]:
    """
    Compare the structure of two tables.
    
    This function compares the column structure, data types, and other 
    structural aspects of two tables to determine their similarity.
    
    Args:
        table1: First DataFrame to compare
        table2: Second DataFrame to compare
        
    Returns:
        Dict containing comparison results:
            - column_match: Whether the columns match
            - column_similarity: Similarity score of column structures (0-1)
            - dtype_match: Whether the data types match
            - row_ratio: Ratio of row counts
    """
    # Check for empty DataFrames
    if table1.empty or table2.empty:
        return {
            'column_match': False,
            'column_similarity': 0.0,
            'dtype_match': False,
            'row_ratio': 0.0
        }
    
    # Column matching
    column_match = table1.columns.equals(table2.columns)
    
    # Calculate column similarity using fuzzy matching
    column_similarity = 0.0
    if len(table1.columns) == len(table2.columns):
        # Direct match
        similarities = [
            fuzz.ratio(str(col1), str(col2)) / 100.0
            for col1, col2 in zip(table1.columns, table2.columns)
        ]
        column_similarity = sum(similarities) / len(similarities) if similarities else 0.0
    else:
        # Cross-comparison to find best matches
        total_sim = 0.0
        for col1 in table1.columns:
            best_match = max(
                [fuzz.ratio(str(col1), str(col2)) / 100.0 for col2 in table2.columns], 
                default=0.0
            )
            total_sim += best_match
        
        column_similarity = total_sim / len(table1.columns) if len(table1.columns) > 0 else 0.0
    
    # Data type matching
    dtype_match = False
    if column_match:
        # Check if data types match for each column
        dtype_match = all([
            str(table1[col].dtype) == str(table2[col].dtype)
            for col in table1.columns
        ])
    
    # Row count ratio
    max_rows = max(len(table1), len(table2))
    min_rows = min(len(table1), len(table2))
    row_ratio = min_rows / max_rows if max_rows > 0 else 0.0
    
    return {
        'column_match': column_match,
        'column_similarity': column_similarity,
        'dtype_match': dtype_match,
        'row_ratio': row_ratio
    }


def compare_table_content(
    table1: pd.DataFrame,
    table2: pd.DataFrame,
    check_cell_by_cell: bool = False
) -> Dict[str, Union[bool, float]]:
    """
    Compare the content of two tables.
    
    This function compares the actual data content of two tables to
    determine their similarity and whether one might be a continuation
    of the other.
    
    Args:
        table1: First DataFrame to compare
        table2: Second DataFrame to compare
        check_cell_by_cell: Whether to compare individual cell values
        
    Returns:
        Dict containing comparison results:
            - header_similarity: Similarity of header rows (0-1)
            - content_similarity: Overall content similarity (0-1)
            - is_continuation: Whether table2 appears to be a continuation of table1
    """
    # Check for empty DataFrames
    if table1.empty or table2.empty:
        return {
            'header_similarity': 0.0,
            'content_similarity': 0.0,
            'is_continuation': False
        }
    
    # Compare header rows (first row)
    header_similarity = 0.0
    if len(table1) > 0 and len(table2) > 0:
        # Convert first rows to strings for comparison
        row1 = ' '.join([str(x) for x in table1.iloc[0].values])
        row2 = ' '.join([str(x) for x in table2.iloc[0].values])
        header_similarity = fuzz.ratio(row1, row2) / 100.0
    
    # Compare all content
    content_similarity = 0.0
    if check_cell_by_cell and len(table1.columns) == len(table2.columns):
        # Check cell by cell for tables with the same structure
        common_row_count = min(len(table1), len(table2))
        
        if common_row_count > 0:
            # Compare each cell in the common rows
            cell_similarities = []
            for i in range(common_row_count):
                for j in range(len(table1.columns)):
                    val1 = str(table1.iloc[i, j])
                    val2 = str(table2.iloc[i, j])
                    cell_similarities.append(fuzz.ratio(val1, val2) / 100.0)
            
            content_similarity = sum(cell_similarities) / len(cell_similarities) if cell_similarities else 0.0
    else:
        # Compare the tables as whole strings
        text1 = ' '.join([' '.join([str(x) for x in row]) for row in table1.values])
        text2 = ' '.join([' '.join([str(x) for x in row]) for row in table2.values])
        content_similarity = fuzz.ratio(text1, text2) / 100.0
    
    # Determine if table2 is a continuation of table1
    is_continuation = False
    
    # Check if last row of table1 is similar to first row of table2 - continuation indicator
    if len(table1) > 1 and len(table2) > 1 and len(table1.columns) == len(table2.columns):
        last_row1 = ' '.join([str(x) for x in table1.iloc[-1].values])
        first_row2 = ' '.join([str(x) for x in table2.iloc[0].values])
        last_first_similarity = fuzz.ratio(last_row1, first_row2) / 100.0
        
        # If headers are similar but last-to-first rows are different, it might be a continuation
        if header_similarity > 0.8 and last_first_similarity < 0.5:
            is_continuation = True
    
    return {
        'header_similarity': header_similarity,
        'content_similarity': content_similarity,
        'is_continuation': is_continuation
    }


def compare_table_position(
    table1_metadata: Dict[str, Any],
    table2_metadata: Dict[str, Any],
    page_height: float
) -> Dict[str, Union[bool, float]]:
    """
    Compare the position of two tables.
    
    This function evaluates the spatial relationship between two tables to
    determine if they are adjacent or otherwise positioned in a way that
    suggests they should be merged.
    
    Args:
        table1_metadata: Metadata for the first table including 'bbox' and 'page'
        table2_metadata: Metadata for the second table including 'bbox' and 'page'
        page_height: Height of the page for distance calculations
        
    Returns:
        Dict containing comparison results:
            - same_page: Whether the tables are on the same page
            - adjacent_pages: Whether the tables are on adjacent pages
            - vertical_proximity: Vertical proximity score (0-1, higher means closer)
            - horizontal_overlap: Horizontal overlap score (0-1, higher means more overlap)
    """
    # Extract page and bbox information
    page1 = table1_metadata.get('page', -1)
    page2 = table2_metadata.get('page', -1)
    bbox1 = table1_metadata.get('bbox', [0, 0, 0, 0])
    bbox2 = table2_metadata.get('bbox', [0, 0, 0, 0])
    
    # Check if on same page
    same_page = page1 == page2
    
    # Check if on adjacent pages
    adjacent_pages = abs(page1 - page2) == 1
    
    # Calculate vertical proximity
    vertical_proximity = 0.0
    if same_page:
        # On same page: measure distance between bottom of table1 and top of table2
        if bbox1[3] <= bbox2[1]:  # table1 is above table2
            distance = bbox2[1] - bbox1[3]
        else:  # table2 is above table1
            distance = bbox1[1] - bbox2[3]
        
        # Convert distance to a proximity score (inverse relationship)
        vertical_proximity = max(0, 1.0 - (distance / page_height))
    elif adjacent_pages and page1 < page2:
        # table1 is near bottom of page1 and table2 is near top of page2
        bottom_proximity = 1.0 - (bbox1[3] / page_height)  # how close to bottom
        top_proximity = 1.0 - (bbox2[1] / page_height)  # how close to top (inverted)
        vertical_proximity = (bottom_proximity + top_proximity) / 2.0
    elif adjacent_pages and page2 < page1:
        # table2 is near bottom of page2 and table1 is near top of page1
        bottom_proximity = 1.0 - (bbox2[3] / page_height)  # how close to bottom
        top_proximity = 1.0 - (bbox1[1] / page_height)  # how close to top (inverted)
        vertical_proximity = (bottom_proximity + top_proximity) / 2.0
    
    # Calculate horizontal overlap
    horizontal_overlap = 0.0
    left1, _, right1, _ = bbox1
    left2, _, right2, _ = bbox2
    
    # Width of each table
    width1 = right1 - left1
    width2 = right2 - left2
    
    if right1 >= left2 and right2 >= left1:  # There is some overlap
        overlap_width = min(right1, right2) - max(left1, left2)
        total_width = max(right1, right2) - min(left1, left2)
        horizontal_overlap = overlap_width / total_width if total_width > 0 else 0.0
    
    return {
        'same_page': same_page,
        'adjacent_pages': adjacent_pages,
        'vertical_proximity': vertical_proximity,
        'horizontal_overlap': horizontal_overlap
    }


def calculate_iou(bbox1: List[float], bbox2: List[float]) -> float:
    """
    Calculate the Intersection over Union (IoU) of two bounding boxes.
    
    Args:
        bbox1: First bounding box [x1, y1, x2, y2]
        bbox2: Second bounding box [x1, y1, x2, y2]
        
    Returns:
        float: IoU value between 0 and 1
    """
    # Determine the coordinates of the intersection rectangle
    x_left = max(bbox1[0], bbox2[0])
    y_top = max(bbox1[1], bbox2[1])
    x_right = min(bbox1[2], bbox2[2])
    y_bottom = min(bbox1[3], bbox2[3])
    
    # If the intersection is invalid (no overlap), return 0
    if x_right < x_left or y_bottom < y_top:
        return 0.0
    
    # Calculate area of intersection
    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    
    # Calculate area of each bounding box
    bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    bbox2_area = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    
    # Calculate the union area
    union_area = bbox1_area + bbox2_area - intersection_area
    
    # Calculate IoU
    iou = intersection_area / union_area if union_area > 0 else 0.0
    
    return iou


def should_merge_tables(
    table1: Union[pd.DataFrame, Dict[str, Any]],
    table2: Union[pd.DataFrame, Dict[str, Any]],
    metadata1: Dict[str, Any],
    metadata2: Dict[str, Any],
    page_height: float,
    threshold_config: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Determine if two tables should be merged.
    
    This function evaluates multiple factors to decide if two tables should be merged.
    It considers table structure, content, and position to make a comprehensive decision.
    
    Args:
        table1: First table (DataFrame or dict with 'table_data' key)
        table2: Second table (DataFrame or dict with 'table_data' key)
        metadata1: Metadata for the first table
        metadata2: Metadata for the second table
        page_height: Height of the page
        threshold_config: Optional customized thresholds for decision making
        
    Returns:
        Dict containing the merge decision and supporting metrics
    """
    # Set default thresholds
    thresholds = {
        'structure_weight': 0.4,
        'content_weight': 0.3,
        'position_weight': 0.3,
        'column_similarity_threshold': 0.7,
        'header_similarity_threshold': 0.7,
        'vertical_proximity_threshold': 0.8,
        'horizontal_overlap_threshold': 0.7,
        'merge_threshold': 0.65
    }
    
    # Apply custom thresholds if provided
    if threshold_config:
        thresholds.update(threshold_config)
    
    # Convert to DataFrame if necessary
    if isinstance(table1, pd.DataFrame):
        df1 = table1
    elif isinstance(table1, dict):
        df1 = pd.DataFrame(table1.get('table_data', []))
    else:
        # table1 is already a list (table_data)
        df1 = pd.DataFrame(table1)
    
    if isinstance(table2, pd.DataFrame):
        df2 = table2
    elif isinstance(table2, dict):
        df2 = pd.DataFrame(table2.get('table_data', []))
    else:
        # table2 is already a list (table_data)
        df2 = pd.DataFrame(table2)
    
    # Compare table structure
    structure_comparison = compare_table_structure(df1, df2)
    
    # Compare table content
    content_comparison = compare_table_content(df1, df2)
    
    # Compare table position
    position_comparison = compare_table_position(metadata1, metadata2, page_height)
    
    # Calculate structure score
    structure_score = 0.7 * int(structure_comparison['column_match']) + \
                     0.3 * structure_comparison['column_similarity']
    
    # Calculate content score
    content_score = 0.5 * content_comparison['header_similarity'] + \
                   0.3 * content_comparison['content_similarity'] + \
                   0.2 * int(content_comparison['is_continuation'])
    
    # Calculate position score
    position_score = 0.5 * position_comparison['vertical_proximity'] + \
                    0.5 * position_comparison['horizontal_overlap']
    
    # Special case: If tables are on adjacent pages and top/bottom positions suggest continuation
    if position_comparison['adjacent_pages'] and \
       content_comparison['header_similarity'] > thresholds['header_similarity_threshold'] and \
       structure_comparison['column_similarity'] > thresholds['column_similarity_threshold']:
        position_score = max(position_score, 0.8)  # Boost the position score
    
    # Calculate overall merge score
    merge_score = thresholds['structure_weight'] * structure_score + \
                 thresholds['content_weight'] * content_score + \
                 thresholds['position_weight'] * position_score
    
    # Make merge decision
    should_merge = merge_score >= thresholds['merge_threshold']
    
    # If on same page, also check for special cases of merged cells
    if position_comparison['same_page']:
        # Check for vertical stacking with similar column structure
        if position_comparison['vertical_proximity'] > thresholds['vertical_proximity_threshold'] and \
           structure_comparison['column_similarity'] > thresholds['column_similarity_threshold']:
            should_merge = True
    
    return {
        'should_merge': should_merge,
        'merge_score': merge_score,
        'structure_score': structure_score,
        'content_score': content_score,
        'position_score': position_score,
        'structure_comparison': structure_comparison,
        'content_comparison': content_comparison,
        'position_comparison': position_comparison
    }


if __name__ == "__main__":
    """
    Validation function to test the table comparison utilities.
    """
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Table structure comparison with identical tables
    total_tests += 1
    try:
        # Create two identical DataFrames
        data = {'A': [1, 2, 3], 'B': ['x', 'y', 'z']}
        df1 = pd.DataFrame(data)
        df2 = pd.DataFrame(data)
        
        # Compare structure
        result = compare_table_structure(df1, df2)
        
        # Check results
        if not result['column_match']:
            all_validation_failures.append("Column match failed for identical tables")
        
        if result['column_similarity'] < 0.99:
            all_validation_failures.append(f"Column similarity too low for identical tables: {result['column_similarity']}")
        
        if not result['dtype_match']:
            all_validation_failures.append("Data type match failed for identical tables")
        
        if result['row_ratio'] != 1.0:
            all_validation_failures.append(f"Row ratio incorrect for identical tables: {result['row_ratio']}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 1: {str(e)}")
    
    # Test 2: Table content comparison
    total_tests += 1
    try:
        # Create two similar DataFrames
        data1 = {'A': [1, 2, 3], 'B': ['x', 'y', 'z']}
        data2 = {'A': [1, 2, 4], 'B': ['x', 'y', 'w']}  # Last row different
        df1 = pd.DataFrame(data1)
        df2 = pd.DataFrame(data2)
        
        # Compare content
        result = compare_table_content(df1, df2, check_cell_by_cell=True)
        
        # Headers should be identical (first row)
        if result['header_similarity'] < 0.99:
            all_validation_failures.append(f"Header similarity too low: {result['header_similarity']}")
        
        # Content should be similar but not identical
        if not (0.5 < result['content_similarity'] < 0.99):
            all_validation_failures.append(f"Content similarity out of expected range: {result['content_similarity']}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 2: {str(e)}")
    
    # Test 3: Table position comparison (same page)
    total_tests += 1
    try:
        # Create metadata for two tables on the same page
        metadata1 = {'page': 1, 'bbox': [100, 100, 300, 200]}
        metadata2 = {'page': 1, 'bbox': [100, 250, 300, 350]}  # Table 2 below Table 1
        page_height = 800
        
        # Compare position
        result = compare_table_position(metadata1, metadata2, page_height)
        
        # Should be on same page
        if not result['same_page']:
            all_validation_failures.append("Same page detection failed")
        
        # Should not be on adjacent pages
        if result['adjacent_pages']:
            all_validation_failures.append("Adjacent pages incorrectly detected")
        
        # Should have high horizontal overlap
        if result['horizontal_overlap'] < 0.99:
            all_validation_failures.append(f"Horizontal overlap too low: {result['horizontal_overlap']}")
        
        # Should have good vertical proximity
        if not (0.1 < result['vertical_proximity'] < 0.9):
            all_validation_failures.append(f"Vertical proximity out of expected range: {result['vertical_proximity']}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 3: {str(e)}")
    
    # Test 4: Merge decision (should merge case)
    total_tests += 1
    try:
        # Create data for tables that should be merged
        data = {'A': [1, 2, 3], 'B': ['x', 'y', 'z']}
        df1 = pd.DataFrame(data)
        df2 = pd.DataFrame(data)
        
        metadata1 = {'page': 1, 'bbox': [100, 100, 300, 200]}
        metadata2 = {'page': 1, 'bbox': [100, 250, 300, 350]}  # Table 2 below Table 1
        page_height = 800
        
        # Get merge decision
        result = should_merge_tables(df1, df2, metadata1, metadata2, page_height)
        
        # Should recommend merging
        if not result['should_merge']:
            all_validation_failures.append("Merge decision failed for tables that should be merged")
        
        # Should have high overall score
        if result['merge_score'] < 0.7:
            all_validation_failures.append(f"Merge score too low: {result['merge_score']}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 4: {str(e)}")
    
    # Test 5: Merge decision (should not merge case)
    total_tests += 1
    try:
        # Create data for tables that should not be merged
        data1 = {'A': [1, 2, 3], 'B': ['x', 'y', 'z']}
        data2 = {'C': [4, 5, 6], 'D': ['a', 'b', 'c']}  # Completely different structure
        df1 = pd.DataFrame(data1)
        df2 = pd.DataFrame(data2)
        
        metadata1 = {'page': 1, 'bbox': [100, 100, 300, 200]}
        metadata2 = {'page': 3, 'bbox': [400, 500, 600, 600]}  # Far away on different page
        page_height = 800
        
        # Get merge decision
        result = should_merge_tables(df1, df2, metadata1, metadata2, page_height)
        
        # Should not recommend merging
        if result['should_merge']:
            all_validation_failures.append("Merge decision failed for tables that should not be merged")
        
        # Should have low overall score
        if result['merge_score'] > 0.4:
            all_validation_failures.append(f"Merge score too high: {result['merge_score']}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 5: {str(e)}")
    
    # Final validation result
    if all_validation_failures:
        print(f" VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f" VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("Table comparison utilities are validated and formal tests can now be written")
        sys.exit(0)