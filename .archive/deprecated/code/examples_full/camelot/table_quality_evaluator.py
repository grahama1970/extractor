"""
Module: table_quality_evaluator.py

External Dependencies:
- pandas: https://pandas.pydata.org/docs/
- pydantic: https://docs.pydantic.dev/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import importlib
from itertools import chain, product
from typing import Any, Dict, List, Optional, Tuple

import camelot
import pandas as pd
from pydantic import BaseModel, Field

from app.backend.utils.calculate_iou import calculate_iou


class ExtractionResult(BaseModel):
    tables: Optional[List[Any]] = Field(default=None, description='Extracted tables')
    quality: float = Field(ge=0.0, le=1.0, description='Quality score of the extraction')
    params: Dict[str, Any] = Field(default_factory=dict, description='Parameters used for extraction')

    class Config:
        frozen = True

class TableQualityEvaluator:
    """
    The TableQualityEvaluator class is responsible for evaluating the quality of tables extracted from PDFs.
    It calculates quality scores based on various metrics such as accuracy, completeness, and consistency.
    This class also identifies the best table extraction parameters by iterating over different combinations 
    of extraction settings and comparing the results.

    Methods:
        evaluate_extraction(tables, current_params, best_quality, best_tables, best_params):
            Evaluate the quality of extracted tables and update the best result if necessary.

        calculate_table_quality(tables):
            Calculate the quality of the provided tables based on accuracy, completeness, and consistency.

        calculate_table_confidence(table):
            Calculate the confidence score for an individual table using configurable weights.

        find_best_table_extraction(page_num, known_table=False):
            Find the best table extraction for a given page by testing various parameters.

        extract_table_with_params(page_num, known_table, **params):
            Extract tables from a specific page using the provided parameters.
    """

    def __init__(self, pdf_path: str):
        """
        Initialize TableQualityEvaluator as a standalone class without reliance on external managers.
        """
        self._logger = None
        self.pdf_path = pdf_path
        self.success_count = {}

    @property
    def logger(self):
        """Lazy load the ColoredLogger. Fallback to standard logger if import fails."""
        if self._logger is None:
            try:
                ColoredLogger = importlib.import_module('verifaix.utils.colored_logger_mini').setup_logger
                self._logger = ColoredLogger(__name__)
            except ImportError as e:
                print(f'Failed to import ColoredLogger: {e}. Using standard logger.')
                import logging
                self._logger = logging.getLogger(__name__)
                self._logger.setLevel(logging.INFO)
        return self._logger

    def evaluate_extraction(self, tables: Optional[List[Any]], current_params: Dict[str, Any], best_quality: float, best_tables: Optional[List[Any]], best_params: Dict[str, Any]) -> Tuple[float, Optional[List[Any]], Dict[str, Any]]:
        """
        Evaluate the quality of extracted tables and update the best result if necessary.

        Args:
            tables: The extracted tables.
            current_params: The parameters used for extraction.
            best_quality: The current best quality score.
            best_tables: The current best tables.
            best_params: The current best parameters.

        Returns:
            Tuple[float, Optional[List[Any]], Dict[str, Any]]: Updated best quality, tables, and parameters.
        """
        if tables is None:
            return (best_quality, best_tables, best_params)
        quality_result = self.calculate_table_quality(tables)
        overall_quality = quality_result.get('table_extraction_quality_score', 0.0)
        if overall_quality > best_quality:
            best_quality = overall_quality
            best_tables = tables
            best_params = current_params
            self.logger.info(f'New best quality: {best_quality}')
        return (best_quality, best_tables, best_params)

    def calculate_table_quality(self, tables: List[Any]) -> Dict[str, Any]:
        """
        Calculate the quality of the provided tables based on accuracy, completeness, and consistency.

        Args:
            tables (List[Any]): The extracted tables to evaluate.

        Returns:
            Dict[str, Any]: Quality results including average quality score and individual table scores.
        """
        self.logger.debug(f'Calculating table quality for {len(tables)} tables')
        if not tables:
            self.logger.warning('No tables provided for quality calculation')
            return {'average_table_extraction_quality': 0.0, 'table_scores': []}
        table_scores = []
        for (i, table) in enumerate(tables):
            try:
                self.logger.debug(f'Processing table {i + 1}')
                if table is None or not hasattr(table, 'df') or table.df.empty:
                    self.logger.error(f'Table {i + 1} has no DataFrame or DataFrame is empty')
                    continue
                df = table.df
                accuracy_score = self.calculate_accuracy_score(table)
                completeness_score = self.calculate_completeness_score(df)
                consistency_score = self.calculate_consistency_score(df)
                self.logger.debug(f'Table {i + 1} scores - Accuracy: {accuracy_score:.4f}, Completeness: {completeness_score:.4f}, Consistency: {consistency_score:.4f}')
                weighted_score = accuracy_score * 0.4 + completeness_score * 0.3 + consistency_score * 0.3
                table_scores.append({'table_index': i, 'accuracy': accuracy_score, 'completeness': completeness_score, 'consistency': consistency_score, 'weighted_score': weighted_score})
                self.logger.debug(f'Table {i + 1} weighted score: {weighted_score:.4f}')
            except Exception as e:
                self.logger.error(f'Error calculating quality for table {i + 1}: {str(e)}')
        if not table_scores:
            self.logger.warning('No valid table scores calculated')
            return {'average_table_extraction_quality': 0.0, 'table_scores': []}
        average_quality = sum((score['weighted_score'] for score in table_scores)) / len(table_scores)
        self.logger.info(f'Average table extraction quality: {average_quality:.4f}')
        return {'average_table_extraction_quality': average_quality, 'table_scores': table_scores}

    def compare_bounding_boxes(self, image2table_json: List[Dict], camelot_table: Dict, page_num: int, iou_threshold: float=0.5) -> bool:
        """
        Compare the bounding box of a Camelot-extracted table with the Image2Table bounding boxes.

        This method checks if a bounding box from Camelot matches a bounding box extracted by Image2Table
        for a specific page using Intersection over Union (IoU) to determine overlap.

        Args:
            image2table_json (List[Dict]): The JSON list of tables extracted by Image2Table (PyMuPDF standard).
            camelot_table (Dict): A single table dictionary extracted by Camelot.
            page_num (int): The page number to compare bounding boxes on.
            iou_threshold (float): The minimum IoU overlap threshold to consider the boxes as matching.

        Returns:
            bool: True if the bounding boxes match within the specified IoU threshold, False otherwise.
        """
        camelot_bbox = camelot_table.get('bbox', None)
        if not camelot_bbox:
            self.logger.warning(f'No bounding box found for Camelot table on page {page_num + 1}')
            return False
        for img_table in image2table_json:
            if img_table['page'] == page_num + 1:
                img_bbox = img_table.get('bbox', None)
                if not img_bbox:
                    self.logger.warning(f'No bounding box found for Image2Table table on page {page_num + 1}')
                    continue
                iou = calculate_iou(img_bbox, camelot_bbox)
                if iou >= iou_threshold:
                    self.logger.info(f'Bounding boxes match on page {page_num + 1} with IoU: {iou}')
                    return True
                else:
                    self.logger.debug(f'Bounding boxes do not match on page {page_num + 1}. IoU: {iou}')
        self.logger.info(f'No matching bounding box found for Camelot table on page {page_num + 1}')
        return False

    def calculate_accuracy_score(self, table: Any) -> float:
        """
        Calculate the accuracy score for a given table.

        Args:
            table (Any): The table object to evaluate.

        Returns:
            float: The accuracy score.
        """
        self.logger.debug('Calculating accuracy score')
        accuracy_score = table.parsing_report.get('accuracy', 0)
        df = table.df
        non_numeric_columns = self.check_non_numeric_in_numeric_columns(df)
        if non_numeric_columns:
            self.logger.warning(f'Non-numeric data found in numeric columns: {non_numeric_columns}')
            accuracy_score *= 0.8
        accuracy_score = max(0.0, min(1.0, accuracy_score / 100))
        return accuracy_score

    def check_non_numeric_in_numeric_columns(self, df: pd.DataFrame) -> Dict[str, List[Any]]:
        """
        Check for non-numeric entries in columns expected to be numeric.

        Args:
            df (pd.DataFrame): The DataFrame containing the table data.

        Returns:
            Dict[str, List[Any]]: A dictionary with column names as keys and lists of non-numeric entries as values.
        """
        non_numeric_entries = {}
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                non_numeric = df[col][~pd.to_numeric(df[col], errors='coerce').notna()]
                if not non_numeric.empty:
                    non_numeric_entries[col] = non_numeric.tolist()
        return non_numeric_entries

    def calculate_completeness_score(self, df: pd.DataFrame) -> float:
        """
        Calculate the completeness score for the DataFrame.

        Args:
            df (pd.DataFrame): The DataFrame containing the table data.

        Returns:
            float: Completeness score (percentage of non-null cells).
        """
        total_cells = df.size
        if total_cells == 0:
            return 0.0
        filled_cells = total_cells - df.isna().sum().sum()
        completeness_score = filled_cells / total_cells
        completeness_score = max(0.0, min(1.0, completeness_score))
        self.logger.debug(f'Table completeness: {completeness_score:.2f}%')
        return completeness_score
        return completeness_score

    def calculate_consistency_score(self, df: pd.DataFrame) -> float:
        """
        Calculate the consistency score for the DataFrame.
        
        Args:
            df (pd.DataFrame): The DataFrame containing the table data.
        
        Returns:
            float: Consistency score (either 100 for consistent columns or 0 for inconsistent).
        """
        if df.empty:
            self.logger.warning('DataFrame is empty; consistency score cannot be calculated.')
            return 0.0
        consistent_columns = all((len(row) == len(df.columns) for row in df.values))
        if not consistent_columns:
            self.logger.info('Table has inconsistent row lengths.')
            return 0.0
        return 1.0 if consistent_columns else 0.0

    def calculate_table_confidence(self, table: Any, page_num: int, image2table_json: List[Dict]=[]) -> float:
        """
        Calculate the confidence score for a given table.

        Args:
            table (Any): The table object to evaluate.

        Returns:
            float: The calculated confidence score between 0 and 100.
        """
        self.logger.debug('Calculating table confidence')
        accuracy = self.calculate_accuracy_score(table)
        completeness = self.calculate_completeness_score(table.df)
        consistency = self.calculate_consistency_score(table.df)
        self.logger.debug(f'Accuracy: {accuracy:.2f}, Completeness: {completeness:.2f}, Consistency: {consistency:.2f}')
        bbox_match = self.compare_bounding_boxes(image2table_json, table, page_num)
        if bbox_match:
            self.logger.info(f'Bounding boxes match for table on page {page_num + 1}, boosting confidence.')
            bbox_adjustment = 1.0
        else:
            self.logger.warning(f'Bounding boxes do not match for table on page {page_num + 1}, reducing confidence.')
            bbox_adjustment = 0.8
        whitespace_score = self.calculate_whitespace_score(table)
        self.logger.debug(f'Adjusted Whitespace Score: {whitespace_score:.2f}')
        weights = {'accuracy': 0.4, 'completeness': 0.3, 'consistency': 0.1, 'whitespace': 0.2}
        confidence = weights['accuracy'] * accuracy + weights['completeness'] * completeness + weights['consistency'] * consistency + weights['whitespace'] * whitespace_score
        confidence = confidence * 100
        confidence = max(0, min(100, confidence))
        self.logger.debug(f'Calculated confidence: {confidence:.2f}')
        self.logger.debug(f'Calculated confidence metrics: confidence={confidence:.2f}, accuracy={accuracy:.2f}, completeness={completeness:.2f}, consistency={consistency:.2f}, whitespace={whitespace_score:.2f}')
        return {'confidence': confidence, 'accuracy': accuracy, 'completeness': completeness, 'consistency': consistency, 'whitespace': whitespace_score}

    def calculate_whitespace_score(self, table: Any) -> float:
        """
        Calculate the adjusted whitespace score for a given table.

        Args:
            table (Any): The table object to evaluate.

        Returns:
            float: Adjusted whitespace score (between 0 and 1).
        """
        self.logger.debug('Calculating whitespace score')
        whitespace = table.parsing_report.get('whitespace', 100)
        if whitespace < 0 or whitespace > 100:
            self.logger.warning(f'Whitespace value out of range: {whitespace}. Clamping to [0, 100].')
            whitespace = max(0, min(100, whitespace))
        whitespace_score = (100 - whitespace) / 100
        self.logger.debug(f'Whitespace: {whitespace}, Adjusted Whitespace Score: {whitespace_score:.2f}')
        return whitespace_score

    def find_best_table_extraction(self, page_num: int, known_table: bool=False) -> Tuple[Optional[List], Dict]:
        """
        Find the best table extraction for a given page by testing various parameters, prioritizing those
        with a history of successful extractions.

        Args:
            page_num (int): The page number to extract tables from.
            known_table (bool): Whether a table is known to exist on the page.

        Returns:
            Tuple[Optional[List], Dict]: A tuple containing:
                - A list of the best extracted tables (or None if extraction failed).
                - A dictionary of the parameters used for the best extraction.

        This method keeps track of successful extraction parameters, ensuring that the most effective
        settings are tried first, potentially improving extraction efficiency and accuracy.
        """
        self.logger.info(f'Finding best table extraction for page {page_num + 1}')
        best_result = ExtractionResult(tables=None, quality=0, params={})
        param_combinations = list(chain(({'flavor': 'lattice', 'line_scale': ls} for ls in [15, 40, 80]), ({'flavor': 'stream', 'edge_tol': et, 'min_text_height': mth, 'split_text': st} for (et, mth, st) in product([500, 1000, 1500], [1.0, 2.0, 3.0], [True, False]))))
        param_combinations.sort(key=lambda x: self.success_count.get(str(x), 0), reverse=True)
        total_attempts = 0
        for current_params in param_combinations:
            total_attempts += 1
            self.logger.debug(f'Attempt {total_attempts} with params: {current_params}')
            tables = self.extract_table_with_params(page_num, known_table, **current_params)
            if not tables:
                self.logger.debug('No tables extracted with these params')
                continue
            quality_result = self.calculate_table_quality(tables)
            current_quality = quality_result.get('average_table_extraction_quality', 0.0)
            if current_quality < 0 or current_quality > 1:
                self.logger.warning(f'Quality score {current_quality} is out of bounds (0-1). Clamping value.')
                current_quality = max(0.0, min(1.0, current_quality))
            if current_quality > best_result.quality:
                best_result = ExtractionResult(tables=tables, quality=current_quality, params=current_params)
                self.logger.info(f'New best quality found: {current_quality:.4f} with params: {current_params}')
                param_key = str(current_params)
                if param_key in self.success_count:
                    self.success_count[param_key] += 1
                else:
                    self.success_count[param_key] = 1
        self.logger.info(f'Best quality achieved: {best_result.quality:.4f} after {total_attempts} attempts')
        return (best_result.tables, best_result.params)

    def extract_table_with_params(self, page_num: int, known_table: bool, **params) -> Optional[List[Any]]:
        """
        Extract tables from a specific page using the provided parameters.

        Args:
            page_num (int): The page number to extract tables from.
            known_table (bool): Whether a table is known to exist on the page.
            **params: The parameters for table extraction.

        Returns:
            Optional[List[Any]]: The extracted tables or None if extraction fails.
        """
        try:
            self.logger.debug(f'Extracting table from page {page_num + 1} with params: {params}')
            if known_table:
                self.logger.debug('Extracting known table')
            tables = camelot.read_pdf(self.pdf_path, pages=str(page_num + 1), **params)
            if tables.n == 0:
                self.logger.debug(f'No tables found on page {page_num + 1}')
                return None
            return list(tables)
        except Exception as e:
            self.logger.error(f'Error extracting tables from page {page_num + 1} with params {params}: {str(e)}')
            return None