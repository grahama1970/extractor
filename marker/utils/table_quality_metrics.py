"""
Table quality metrics for evaluating the quality of extracted tables.

This module provides functions to calculate various quality metrics for tables
extracted from PDF documents using Camelot. These metrics include accuracy,
completeness, consistency, and whitespace scores, which are used to determine
the overall quality of an extracted table.

References:
- Camelot documentation: https://camelot-py.readthedocs.io/en/master/
- Pandas documentation: https://pandas.pydata.org/docs/

Sample input:
- A Camelot Table object with a DataFrame and parsing_report

Expected output:
- Quality metrics as floating point values between 0 and 1
"""

import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from loguru import logger


def calculate_accuracy_score(table: Any) -> float:
    """
    Calculate the accuracy score for a given table.
    
    The accuracy score is derived from the Camelot parsing report's accuracy value,
    adjusted if non-numeric data is found in columns that appear to be numeric.
    
    Args:
        table: A Camelot Table object with parsing_report and df attributes
        
    Returns:
        float: The accuracy score between 0 and 1
    """
    # Get accuracy from parsing report
    try:
        accuracy_score = table.parsing_report.get('accuracy', 0)
    except (AttributeError, KeyError):
        logger.warning("Could not get accuracy from parsing report, using default value")
        return 0.0
    
    # Convert to 0-1 scale
    accuracy_score = max(0.0, min(1.0, accuracy_score / 100))
    
    # Check for non-numeric data in numeric columns 
    df = table.df
    non_numeric_columns = check_non_numeric_in_numeric_columns(df)
    if non_numeric_columns:
        logger.warning(f'Non-numeric data found in numeric columns: {non_numeric_columns}')
        # Penalize accuracy for inconsistent data types
        accuracy_score *= 0.8
    
    return accuracy_score


def check_non_numeric_in_numeric_columns(df: pd.DataFrame) -> Dict[str, List[Any]]:
    """
    Check for non-numeric entries in columns that appear to be numeric.
    
    Args:
        df: The pandas DataFrame to check
        
    Returns:
        Dict: A dictionary with column names as keys and lists of non-numeric entries as values
    """
    non_numeric_entries = {}
    for col in df.columns:
        # Skip columns with less than 3 rows (not enough to determine type)
        if len(df) < 3:
            continue
            
        # Check if column appears to be numeric 
        numeric_count = 0
        for value in df[col]:
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().replace('.', '', 1).isdigit()):
                numeric_count += 1
        
        # If more than 50% of values appear numeric, check for non-numeric entries
        if numeric_count / len(df) > 0.5:
            non_numeric = []
            for value in df[col]:
                if not (isinstance(value, (int, float)) or 
                        (isinstance(value, str) and value.strip().replace('.', '', 1).isdigit()) or
                        (isinstance(value, str) and not value.strip())):  # Allow empty strings
                    non_numeric.append(value)
            
            if non_numeric:
                non_numeric_entries[str(col)] = non_numeric
    
    return non_numeric_entries


def calculate_completeness_score(df: pd.DataFrame) -> float:
    """
    Calculate the completeness score for the DataFrame.
    
    The completeness score is the percentage of non-null cells in the DataFrame.
    
    Args:
        df: The pandas DataFrame to evaluate
        
    Returns:
        float: Completeness score between 0 and 1
    """
    if df.size == 0:
        return 0.0
    
    # Count non-null cells
    total_cells = df.size
    filled_cells = total_cells - df.isna().sum().sum() - df.isin(['', ' ']).sum().sum()
    
    # Calculate ratio of filled cells
    completeness_score = filled_cells / total_cells
    completeness_score = max(0.0, min(1.0, completeness_score))
    
    return completeness_score


def calculate_consistency_score(df: pd.DataFrame) -> float:
    """
    Calculate the consistency score for the DataFrame.
    
    The consistency score checks if all rows have the same number of columns
    and if column data types are consistent.
    
    Args:
        df: The pandas DataFrame to evaluate
        
    Returns:
        float: Consistency score between 0 and 1
    """
    if df.empty:
        logger.warning('DataFrame is empty; consistency score cannot be calculated.')
        return 0.0
    
    # Check if all rows have the same number of columns
    consistent_columns = True
    for row in df.values:
        if len(row) != len(df.columns):
            consistent_columns = False
            break
    
    # Check if column data types are consistent
    consistent_data_types = True
    for col in df.columns:
        # Skip columns with less than 3 rows (not enough to determine consistency)
        if len(df) < 3:
            continue
            
        # Get non-empty values
        values = df[col][df[col].astype(str).str.strip() != '']
        if len(values) < 2:
            continue
            
        # Check if all values are of the same type
        first_type = type(values.iloc[0])
        for value in values[1:]:
            if type(value) != first_type:
                consistent_data_types = False
                break
    
    # Weighted scoring: column consistency is more important than data type consistency
    column_weight = 0.7
    data_type_weight = 0.3
    
    consistency_score = (column_weight * int(consistent_columns) + 
                        data_type_weight * int(consistent_data_types))
    
    return consistency_score


def calculate_whitespace_score(table: Any) -> float:
    """
    Calculate the whitespace score for a given table.
    
    Tables with lots of whitespace typically have poor structure recognition.
    This score penalizes tables with excessive whitespace.
    
    Args:
        table: A Camelot Table object with parsing_report
        
    Returns:
        float: Whitespace score between 0 and 1 (1 is best - minimal whitespace)
    """
    try:
        whitespace = table.parsing_report.get('whitespace', 100)
    except (AttributeError, KeyError):
        logger.warning("Could not get whitespace from parsing report, using default value")
        return 0.5  # Default middle value when unknown
    
    # Ensure whitespace is within valid range
    whitespace = max(0, min(100, whitespace))
    
    # Convert to 0-1 scale where 1 is best (minimal whitespace)
    whitespace_score = (100 - whitespace) / 100
    
    return whitespace_score


def calculate_table_confidence(table: Any) -> Dict[str, float]:
    """
    Calculate the overall confidence score for a table based on multiple quality metrics.
    
    Args:
        table: A Camelot Table object with df and parsing_report attributes
        
    Returns:
        Dict: Dictionary containing confidence score and individual metrics
    """
    # Calculate individual metrics
    try:
        accuracy = calculate_accuracy_score(table)
        completeness = calculate_completeness_score(table.df)
        consistency = calculate_consistency_score(table.df)
        whitespace = calculate_whitespace_score(table)
    except Exception as e:
        logger.error(f"Error calculating quality metrics: {str(e)}")
        return {
            'confidence': 0.0,
            'accuracy': 0.0,
            'completeness': 0.0,
            'consistency': 0.0,
            'whitespace': 0.0
        }
    
    # Define weights for each metric
    weights = {
        'accuracy': 0.4,    # Most important - from Camelot's own accuracy assessment
        'completeness': 0.3, # Fairly important - measures data presence
        'consistency': 0.1,  # Less important but still relevant
        'whitespace': 0.2    # Indicator of good structure detection
    }
    
    # Calculate weighted confidence score
    confidence = (
        weights['accuracy'] * accuracy +
        weights['completeness'] * completeness +
        weights['consistency'] * consistency +
        weights['whitespace'] * whitespace
    )
    
    # Scale to 0-100 for easier interpretation
    confidence = confidence * 100
    confidence = max(0, min(100, confidence))
    
    return {
        'confidence': confidence,
        'accuracy': accuracy,
        'completeness': completeness,
        'consistency': consistency,
        'whitespace': whitespace
    }


if __name__ == "__main__":
    """
    Validation function to test the quality metrics on a real PDF.
    
    This uses the Camelot library to extract a table and then evaluates its quality.
    """
    import sys
    import os
    import camelot
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Find a test PDF
    test_pdf = "/home/graham/workspace/experiments/marker/data/input/2505.03335v2.pdf"
    if not os.path.exists(test_pdf):
        all_validation_failures.append(f"Test PDF not found: {test_pdf}")
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    
    # Test 1: Basic table extraction and quality calculation
    total_tests += 1
    try:
        # Try to extract tables from the first few pages
        found_table = False
        for page in range(1, 6):  # Try pages 1-5
            tables = camelot.read_pdf(test_pdf, pages=str(page), flavor='lattice')
            if tables.n > 0:
                found_table = True
                break
        
        if not found_table:
            all_validation_failures.append("No tables found in first 5 pages of test PDF")
        else:
            # Get first table
            table = tables[0]
            
            # Calculate metrics
            accuracy = calculate_accuracy_score(table)
            completeness = calculate_completeness_score(table.df)
            consistency = calculate_consistency_score(table.df)
            whitespace = calculate_whitespace_score(table)
            confidence = calculate_table_confidence(table)
            
            # Validate metric ranges
            if not (0 <= accuracy <= 1):
                all_validation_failures.append(f"Accuracy score out of range: {accuracy}")
            
            if not (0 <= completeness <= 1):
                all_validation_failures.append(f"Completeness score out of range: {completeness}")
                
            if not (0 <= consistency <= 1):
                all_validation_failures.append(f"Consistency score out of range: {consistency}")
                
            if not (0 <= whitespace <= 1):
                all_validation_failures.append(f"Whitespace score out of range: {whitespace}")
                
            if not (0 <= confidence['confidence'] <= 100):
                all_validation_failures.append(f"Confidence score out of range: {confidence['confidence']}")
            
            # Validate confidence contains all metrics
            expected_keys = ['confidence', 'accuracy', 'completeness', 'consistency', 'whitespace']
            for key in expected_keys:
                if key not in confidence:
                    all_validation_failures.append(f"Missing key in confidence result: {key}")
            
            print(f"Table metrics on page {page}:")
            print(f"  - Accuracy: {accuracy:.4f}")
            print(f"  - Completeness: {completeness:.4f}")
            print(f"  - Consistency: {consistency:.4f}")
            print(f"  - Whitespace: {whitespace:.4f}")
            print(f"  - Overall confidence: {confidence['confidence']:.4f}")
            
    except Exception as e:
        all_validation_failures.append(f"Error in test 1: {str(e)}")
    
    # Test 2: Edge case - empty DataFrame
    total_tests += 1
    try:
        empty_df = pd.DataFrame()
        completeness = calculate_completeness_score(empty_df)
        consistency = calculate_consistency_score(empty_df)
        
        # Should return 0 for empty DataFrame
        if completeness != 0:
            all_validation_failures.append(f"Completeness for empty DataFrame should be 0, got {completeness}")
            
        if consistency != 0:
            all_validation_failures.append(f"Consistency for empty DataFrame should be 0, got {consistency}")
    except Exception as e:
        all_validation_failures.append(f"Error in test 2: {str(e)}")
    
    # Final validation result
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("Table quality metrics are validated and formal tests can now be written")
        sys.exit(0)