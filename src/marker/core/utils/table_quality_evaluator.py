"""
TableQualityEvaluator for evaluating the quality of tables extracted from PDFs.

This module provides a class for evaluating the quality of tables extracted
from PDF documents using Camelot. It uses various metrics to determine the
overall quality of an extracted table, which can be used to decide whether
to use Camelot as a fallback for table extraction.

References:
- Camelot documentation: https://camelot-py.readthedocs.io/en/master/
- pandas documentation: https://pandas.pydata.org/docs/

Sample input:
- PDF path and page number to extract tables from
- Camelot Table object with DataFrame and parsing_report

Expected output:
- Quality evaluation results including confidence score
- Best extraction parameters for a given page
"""

import os
import sys
from itertools import chain, product
from typing import Any, Dict, List, Optional, Tuple

import camelot
import pandas as pd
from loguru import logger

from marker.core.utils.table_cache import cached
from marker.core.utils.table_quality_metrics import (
    calculate_accuracy_score,
    calculate_completeness_score,
    calculate_consistency_score,
    calculate_whitespace_score,
    calculate_table_confidence
)


class ExtractionResult:
    """
    Class to store and track the results of a table extraction attempt.
    """
    
    def __init__(
        self, 
        tables: Optional[List[Any]] = None, 
        quality: float = 0.0, 
        params: Dict[str, Any] = None
    ):
        """
        Initialize an ExtractionResult instance.
        
        Args:
            tables: List of extracted tables or None if extraction failed
            quality: Quality score of the extraction (0-1)
            params: Parameters used for extraction
        """
        self.tables = tables
        self.quality = quality
        self.params = params or {}


class TableQualityEvaluator:
    """
    The TableQualityEvaluator class evaluates the quality of tables extracted
    from PDFs and identifies the best extraction parameters.
    """
    
    def __init__(self, config=None):
        """
        Initialize TableQualityEvaluator.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.success_count = {}  # Track successful parameter combinations
        self.confidence_threshold = self.config.get('confidence_threshold', 60.0)
        self.max_search_iterations = self.config.get('max_search_iterations', 10)
        self.quality_weights = self.config.get('quality_weights', {
            'accuracy': 0.4,
            'completeness': 0.3,
            'consistency': 0.1,
            'whitespace': 0.2
        })
    
    def evaluate_extraction(
        self,
        tables: Optional[List[Any]],
        current_params: Dict[str, Any],
        best_quality: float,
        best_tables: Optional[List[Any]],
        best_params: Dict[str, Any]
    ) -> Tuple[float, Optional[List[Any]], Dict[str, Any]]:
        """
        Evaluate the quality of extracted tables and update the best result if necessary.
        
        Args:
            tables: The extracted tables
            current_params: The parameters used for extraction
            best_quality: The current best quality score
            best_tables: The current best tables
            best_params: The current best parameters
            
        Returns:
            Tuple containing updated best quality, tables, and parameters
        """
        if tables is None or len(tables) == 0:
            return best_quality, best_tables, best_params
        
        # Calculate quality for each table and average them
        table_qualities = []
        for table in tables:
            if table.df.empty:
                continue
            
            quality_metrics = calculate_table_confidence(table)
            overall_quality = quality_metrics['confidence'] / 100.0  # Convert to 0-1 scale
            table_qualities.append(overall_quality)
        
        # Average quality across all tables, or 0 if no tables
        overall_quality = sum(table_qualities) / len(table_qualities) if table_qualities else 0.0
        
        if overall_quality > best_quality:
            best_quality = overall_quality
            best_tables = tables
            best_params = current_params
            logger.info(f'New best quality: {best_quality:.4f} with params: {best_params}')
            
            # Track successful parameters
            param_key = str(current_params)
            if param_key in self.success_count:
                self.success_count[param_key] += 1
            else:
                self.success_count[param_key] = 1
        
        return best_quality, best_tables, best_params
    
    def calculate_table_quality(self, tables: List[Any]) -> Dict[str, Any]:
        """
        Calculate the quality of the provided tables.
        
        Args:
            tables: The extracted tables to evaluate
            
        Returns:
            Dict containing quality results
        """
        logger.debug(f'Calculating table quality for {len(tables)} tables')
        
        if not tables:
            logger.warning('No tables provided for quality calculation')
            return {'average_table_extraction_quality': 0.0, 'table_scores': []}
        
        table_scores = []
        for i, table in enumerate(tables):
            try:
                logger.debug(f'Processing table {i + 1}')
                
                if table is None or not hasattr(table, 'df') or table.df.empty:
                    logger.error(f'Table {i + 1} has no DataFrame or DataFrame is empty')
                    continue
                
                quality_metrics = calculate_table_confidence(table)
                weighted_score = quality_metrics['confidence'] / 100.0  # Convert to 0-1 scale
                
                table_scores.append({
                    'table_index': i,
                    'metrics': quality_metrics,
                    'weighted_score': weighted_score
                })
                
                logger.debug(f'Table {i + 1} weighted score: {weighted_score:.4f}')
                
            except Exception as e:
                logger.error(f'Error calculating quality for table {i + 1}: {str(e)}')
        
        if not table_scores:
            logger.warning('No valid table scores calculated')
            return {'average_table_extraction_quality': 0.0, 'table_scores': []}
        
        average_quality = sum(score['weighted_score'] for score in table_scores) / len(table_scores)
        logger.info(f'Average table extraction quality: {average_quality:.4f}')
        
        return {
            'average_table_extraction_quality': average_quality,
            'table_scores': table_scores
        }
    
    @cached
    def find_best_table_extraction(
        self,
        page_num: int,
        filepath: str,
        bbox: Optional[List[float]] = None,
        cache_enabled: bool = True
    ) -> Tuple[Optional[List], Dict]:
        """
        Find the best table extraction for a given page by testing various parameters.
        
        Args:
            page_num: The page number to extract tables from (0-based)
            filepath: Path to the PDF file
            bbox: Optional bounding box to constrain extraction [left, top, right, bottom]
            cache_enabled: Whether to use caching (default: True)
            
        Returns:
            Tuple containing the best extracted tables and the parameters used
        """
        logger.info(f'Finding best table extraction for page {page_num + 1}')
        
        best_result = ExtractionResult()
        
        # Define parameter combinations to try
        # Start with the ones that have worked well in the past
        param_combinations = list(chain(
            ({'flavor': 'lattice', 'line_scale': ls} for ls in [15, 40, 80]),
            ({'flavor': 'stream', 'edge_tol': et, 'split_text': st} 
             for (et, st) in product([500, 1000, 1500], [True, False]))
        ))
        
        # Sort by past success
        param_combinations.sort(key=lambda x: self.success_count.get(str(x), 0), reverse=True)
        
        # Limit the number of attempts
        param_combinations = param_combinations[:self.max_search_iterations]
        
        total_attempts = 0
        for current_params in param_combinations:
            total_attempts += 1
            logger.debug(f'Attempt {total_attempts} with params: {current_params}')
            
            # Add bbox if provided
            params_with_bbox = current_params.copy()
            if bbox:
                params_with_bbox['table_areas'] = [bbox]
            
            # Try to extract tables
            tables = self.extract_table_with_params(
                page_num, filepath, 
                cache_enabled=cache_enabled, 
                **params_with_bbox
            )
            if not tables:
                logger.debug('No tables extracted with these params')
                continue
            
            # Evaluate the quality
            quality_result = self.calculate_table_quality(tables)
            current_quality = quality_result.get('average_table_extraction_quality', 0.0)
            
            # Make sure quality is in valid range
            current_quality = max(0.0, min(1.0, current_quality))
            
            # Update best result if this is better
            if current_quality > best_result.quality:
                best_result = ExtractionResult(tables=tables, quality=current_quality, params=current_params)
                logger.info(f'New best quality found: {current_quality:.4f} with params: {current_params}')
            
            # Early exit if quality is good enough
            if current_quality >= 0.9:
                logger.info(f'Found excellent quality table ({current_quality:.4f}), stopping search')
                break
        
        logger.info(f'Best quality achieved: {best_result.quality:.4f} after {total_attempts} attempts')
        return best_result.tables, best_result.params
    
    def extract_table_with_params(
        self,
        page_num: int,
        filepath: str,
        **params
    ) -> Optional[List[Any]]:
        """
        Extract tables from a specific page using the provided parameters.
        
        Args:
            page_num: The page number to extract tables from (0-based)
            filepath: Path to the PDF file
            **params: The parameters for table extraction
            
        Returns:
            List of extracted tables or None if extraction fails
        """
        try:
            logger.debug(f'Extracting table from page {page_num + 1} with params: {params}')
            
            # Camelot uses 1-based page numbers
            camelot_page = page_num + 1
            
            # Extract tables
            tables = camelot.read_pdf(filepath, pages=str(camelot_page), **params)
            
            if tables.n == 0:
                logger.debug(f'No tables found on page {page_num + 1}')
                return None
            
            return list(tables)
            
        except Exception as e:
            logger.error(f'Error extracting tables from page {page_num + 1} with params {params}: {str(e)}')
            return None


if __name__ == "__main__":
    """
    Validation function to test the TableQualityEvaluator on a real PDF.
    """
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Find a test PDF
    test_pdf = "."
    if not os.path.exists(test_pdf):
        all_validation_failures.append(f"Test PDF not found: {test_pdf}")
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    
    # Test 1: Basic evaluation
    total_tests += 1
    try:
        evaluator = TableQualityEvaluator()
        
        # Try to extract tables from the first few pages
        page_to_test = -1
        for page in range(0, 5):  # Pages 0-4 (0-based)
            try:
                tables = camelot.read_pdf(test_pdf, pages=str(page + 1), flavor='lattice')
                if tables.n > 0:
                    page_to_test = page
                    break
            except Exception:
                continue
        
        if page_to_test == -1:
            all_validation_failures.append("No tables found in first 5 pages of test PDF")
        else:
            # Extract table with default parameters
            tables = camelot.read_pdf(test_pdf, pages=str(page_to_test + 1), flavor='lattice')
            
            # Evaluate the quality
            quality_result = evaluator.calculate_table_quality(tables)
            
            # Check that we got a result
            if 'average_table_extraction_quality' not in quality_result:
                all_validation_failures.append("Missing 'average_table_extraction_quality' in quality result")
            
            # Check that the quality is in valid range
            quality = quality_result.get('average_table_extraction_quality', -1)
            if not (0 <= quality <= 1):
                all_validation_failures.append(f"Quality score out of range: {quality}")
            
            # Check that we got table scores
            if 'table_scores' not in quality_result:
                all_validation_failures.append("Missing 'table_scores' in quality result")
                
            # Check that there's at least one table score
            if len(quality_result.get('table_scores', [])) == 0:
                all_validation_failures.append("No table scores in quality result")
            
            print(f"Table quality evaluation for page {page_to_test + 1}:")
            print(f"  - Average quality: {quality_result.get('average_table_extraction_quality', 0.0):.4f}")
            print(f"  - Number of tables scored: {len(quality_result.get('table_scores', []))}")
    except Exception as e:
        all_validation_failures.append(f"Error in test 1: {str(e)}")
    
    # Test 2: Parameter optimization
    total_tests += 1
    try:
        evaluator = TableQualityEvaluator({
            'max_search_iterations': 3  # Limit to 3 iterations for testing
        })
        
        if page_to_test != -1:
            # Find the best parameters for the test page
            best_tables, best_params = evaluator.find_best_table_extraction(page_to_test, test_pdf)
            
            # Check that we got results
            if best_tables is None:
                all_validation_failures.append("No tables returned from parameter optimization")
            
            # Check that we got parameters
            if not best_params:
                all_validation_failures.append("No parameters returned from parameter optimization")
            
            # Check that the parameters are valid
            if 'flavor' not in best_params:
                all_validation_failures.append("Missing 'flavor' in optimized parameters")
            
            print(f"Best parameters for page {page_to_test + 1}:")
            print(f"  - Parameters: {best_params}")
            if best_tables:
                print(f"  - Number of tables: {len(best_tables)}")
                
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
        print("TableQualityEvaluator is validated and formal tests can now be written")
        sys.exit(0)