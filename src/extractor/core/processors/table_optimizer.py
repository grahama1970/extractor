"""
Table Optimizer Module for Marker
Module: table_optimizer.py

This module provides parameter optimization for table extraction processes,
helping to find the optimal parameters for table detection and extraction
based on various metrics like completeness, accuracy, structure, and speed.

Example usage:
    from extractor.core.processors.table_optimizer import TableOptimizer
    
    optimizer = TableOptimizer(config=optimizer_config)
    optimal_params = optimizer.optimize(document, table_block)
    
    # Use optimal params for extraction
    processor.process_with_params(document, table_block, optimal_params)
"""

import time
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import traceback
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from extractor.core.config.table import TableOptimizerConfig, OptimizationMetric
from extractor.core.schema import BlockTypes
from extractor.core.schema.document import Document
from extractor.core.schema.blocks import Block, Table, TableCell
from extractor.core.schema.polygon import PolygonBox

# Import camelot for table extraction
try:
    import camelot
    import cv2
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False


class TableOptimizer:
    """
    Optimizer for table extraction parameters.
    
    This class provides functionality to optimize parameters for table extraction
    based on different metrics like completeness, accuracy, structure, and speed.
    """
    
    def __init__(self, config: TableOptimizerConfig):
        """
        Initialize the TableOptimizer.
        
        Args:
            config: Configuration for the table optimizer
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Define default parameter space if not provided
        if not self.config.param_space:
            self.param_space = {
                "flavor": ["lattice", "stream"],
                "line_width": [10, 15, 20],
                "line_scale": [30, 40, 50, 60],
                "copy_text": [True, False],
                "edge_tol": [30, 50, 70],
                "row_tol": [1, 2, 3]
            }
        else:
            self.param_space = self.config.param_space
    
    def optimize(self, document: Document, table_block: Block, filepath: str) -> Dict[str, Any]:
        """
        Optimize parameters for table extraction.
        
        Args:
            document: The document containing the table
            table_block: The table block to optimize for
            filepath: Path to the original PDF file
            
        Returns:
            Dictionary of optimal parameters
        """
        if not CAMELOT_AVAILABLE:
            self.logger.warning("Camelot is not available. Cannot optimize table extraction parameters.")
            return {}
            
        if not self.config.enabled:
            self.logger.info("Table parameter optimization is disabled.")
            return {}
            
        # Get the page for the table block
        page = next((p for p in document.pages if p.page_id == table_block.page_id), None)
        if not page:
            self.logger.error(f"Page {table_block.page_id} not found in document")
            return {}
            
        # Get bbox in Camelot format (left, top, right, bottom) in PDF coordinates as percentage
        bbox = table_block.polygon.bbox
        page_height = page.polygon.height
        page_width = page.polygon.width
        camelot_bbox = [
            bbox[0] / page_width,
            (page_height - bbox[3]) / page_height,  # Flip Y coordinate (PDF origin is bottom-left)
            bbox[2] / page_width,
            (page_height - bbox[1]) / page_height,  # Flip Y coordinate
        ]
        
        # Camelot page index is 1-based
        page_idx = table_block.page_id + 1
        
        # Generate parameter combinations to test
        param_combinations = self._generate_parameter_combinations()
        
        # Test each combination
        results = []
        for params in tqdm(param_combinations, desc="Optimizing table parameters", disable=not self.config.enabled):
            try:
                start_time = time.time()
                
                # Set timeout for this optimization attempt
                if time.time() - start_time > self.config.timeout:
                    self.logger.warning(f"Optimization timed out after {self.config.timeout} seconds")
                    continue
                    
                table_result = camelot.read_pdf(
                    filepath,
                    pages=str(page_idx),
                    flavor=params["flavor"],
                    table_areas=[camelot_bbox],
                    line_scale=params.get("line_scale", 40),
                    line_width=params.get("line_width", 15),
                    copy_text=params.get("copy_text", True),
                    edge_tol=params.get("edge_tol", 50),
                    row_tol=params.get("row_tol", 2)
                )
                
                if len(table_result) == 0 or table_result[0].df.empty:
                    continue
                    
                camelot_table = table_result[0]
                
                # Calculate metrics
                metrics = self._calculate_metrics(camelot_table, params, time.time() - start_time)
                
                results.append({
                    "params": params,
                    "metrics": metrics,
                    "score": self._calculate_score(metrics)
                })
                
            except Exception as e:
                self.logger.error(f"Error optimizing with params {params}: {str(e)}")
                traceback.print_exc()
                continue
                
        # Find optimal parameters
        if not results:
            self.logger.warning("No valid parameter combinations found")
            return {}
            
        # Sort by score (descending)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[0]["params"]
    
    def _generate_parameter_combinations(self) -> List[Dict[str, Any]]:
        """
        Generate all parameter combinations to test.
        
        Returns:
            List of parameter combinations as dictionaries
        """
        import itertools
        
        # Get all keys and values
        keys = list(self.param_space.keys())
        values = list(self.param_space.values())
        
        # Generate combinations
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
            
        return combinations
    
    def _calculate_metrics(self, camelot_table, params: Dict[str, Any], execution_time: float) -> Dict[str, float]:
        """
        Calculate metrics for a table extraction result.
        
        Args:
            camelot_table: The Camelot table result
            params: The parameters used for extraction
            execution_time: The time taken for extraction
            
        Returns:
            Dictionary of metrics
        """
        metrics = {}
        
        # Basic metrics from Camelot
        metrics["accuracy"] = float(camelot_table.accuracy)
        metrics["whitespace"] = float(camelot_table.whitespace)
        
        # Calculate completeness (ratio of non-empty cells)
        df = camelot_table.df
        total_cells = df.size
        non_empty_cells = df.notnull().sum().sum()
        metrics["completeness"] = float(non_empty_cells / total_cells) if total_cells > 0 else 0.0
        
        # Calculate structure score (how well aligned the cells are)
        row_lengths = [len(row) for row in df.itertuples(index=False)]
        row_length_variance = np.var(row_lengths) if row_lengths else 0
        metrics["structure"] = 1.0 / (1.0 + row_length_variance)  # Higher variance = worse structure
        
        # Speed metric (inverse of execution time, normalized)
        metrics["speed"] = 1.0 / (1.0 + execution_time)  # Higher time = lower speed score
        
        return metrics
    
    def _calculate_score(self, metrics: Dict[str, float]) -> float:
        """
        Calculate an overall score based on metrics and configured weights.
        
        Args:
            metrics: Dictionary of metric values
            
        Returns:
            Overall score
        """
        score = 0.0
        
        # Use configured metrics in order of priority
        for i, metric in enumerate(self.config.metrics):
            # Lower priority metrics have less weight
            weight = 1.0 / (i + 1)
            metric_value = metrics.get(metric, 0.0)
            score += weight * metric_value
            
        return score


class TableQualityEvaluator:
    """
    Evaluates the quality of table extraction results.
    
    This class provides functionality to evaluate the quality of table extraction
    results based on different metrics like completeness, accuracy, structure, and speed.
    """
    
    def __init__(self, config):
        """
        Initialize the TableQualityEvaluator.
        
        Args:
            config: Configuration for the table quality evaluator
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def evaluate(self, table_cells: List[TableCell], extraction_method: str = "default") -> float:
        """
        Evaluate the quality of a table extraction result.
        
        Args:
            table_cells: The table cells to evaluate
            extraction_method: The method used for extraction
            
        Returns:
            Quality score between 0 and 1
        """
        if not self.config.enabled:
            return 1.0
            
        metrics = {}
        
        # Calculate completeness (ratio of non-empty cells)
        total_cells = len(table_cells)
        non_empty_cells = sum(1 for cell in table_cells if cell.text_lines and any(line.strip() for line in cell.text_lines))
        metrics["completeness"] = float(non_empty_cells / total_cells) if total_cells > 0 else 0.0
        
        # Calculate structure score
        metrics["structure"] = self._calculate_structure_score(table_cells)
        
        # Accuracy is harder to measure directly, estimate based on extraction method
        if extraction_method == "camelot":
            metrics["accuracy"] = 0.8  # Assume good accuracy for Camelot
        elif extraction_method == "llm":
            metrics["accuracy"] = 0.9  # Assume excellent accuracy for LLM-processed tables
        else:
            metrics["accuracy"] = 0.7  # Default accuracy estimate
        
        # Speed metric - always 1.0 for evaluation (we're evaluating result, not process)
        metrics["speed"] = 1.0
        
        # Calculate overall score
        if self.config.weights:
            # Use configured weights
            score = sum(self.config.weights.get(metric, 0.0) * metrics.get(metric, 0.0) 
                       for metric in self.config.evaluation_metrics)
        else:
            # Equal weights
            score = sum(metrics.get(metric, 0.0) for metric in self.config.evaluation_metrics) / len(self.config.evaluation_metrics)
        
        return score
    
    def _calculate_structure_score(self, table_cells: List[TableCell]) -> float:
        """
        Calculate a structure score for table cells.
        
        Args:
            table_cells: The table cells to evaluate
            
        Returns:
            Structure score between 0 and 1
        """
        if not table_cells:
            return 0.0
            
        # Get all unique row and column IDs
        row_ids = set(cell.row_id for cell in table_cells)
        col_ids = set(cell.col_id for cell in table_cells)
        
        # Check column alignment if enabled
        col_alignment_score = 1.0
        if self.config.check_column_alignment:
            # For each row, check if all expected columns exist
            columns_per_row = {}
            for row_id in row_ids:
                row_cells = [cell for cell in table_cells if cell.row_id == row_id]
                columns_per_row[row_id] = set(cell.col_id for cell in row_cells)
            
            # Calculate variance in number of columns per row
            col_counts = [len(cols) for cols in columns_per_row.values()]
            if col_counts:
                col_variance = np.var(col_counts)
                col_alignment_score = 1.0 / (1.0 + col_variance)  # Higher variance = worse alignment
        
        # Check for empty cells if enabled
        empty_cells_score = 1.0
        if self.config.check_empty_cells:
            # Calculate percentage of non-empty cells
            total_cells = len(table_cells)
            non_empty_cells = sum(1 for cell in table_cells if cell.text_lines and any(line.strip() for line in cell.text_lines))
            empty_cells_score = float(non_empty_cells / total_cells) if total_cells > 0 else 0.0
        
        # Combine scores
        return (col_alignment_score + empty_cells_score) / 2.0