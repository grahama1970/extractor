"""
Module: table_result_handler.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import importlib
import os
from typing import Any, Dict, List


class TableResultHandler:
    """
    The TableResultHandler class is responsible for managing the logging and saving of table extraction results.
    It provides functionality for logging the details of extracted tables, saving them to CSV files, and ensuring 
    proper file handling with checks for directory existence and permissions.

    This class handles the following tasks:
        - Logging the confidence and data for each extracted table.
        - Saving tables to CSV format in the specified directory.
        - Handling directory creation, file overwrite options, and error handling during the saving process.

    Methods:
        log_results(final_tables):
            Logs the extraction results, including page number, confidence score, and table data.
        
        save_to_csv(tables, output_dir, overwrite):
            Saves the extracted tables to CSV files, ensuring proper file and directory handling.
    """

    def __init__(self):
        """
        Initialize TableResultHandler with the CamelotExtractor instance.

        Args:
            extractor (CamelotExtractor): Instance of CamelotExtractor.
        """
        self._logger = None

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

    async def log_results(self, final_tables):
        self.logger.info('Logging extraction results')
        for table in final_tables:
            self.logger.info(f"Table on Page {table['page']}:")
            self.logger.info(f"Confidence: {table['confidence']}")
            self.logger.info(f"Data: {table['dataframe']}")
            self.logger.info('')

    def save_to_csv(self, tables: List[Dict[str, Any]], output_dir: str, overwrite: bool=False):
        self.logger.info(f'Saving {len(tables)} tables to CSV in {output_dir}')
        if os.path.exists(output_dir):
            if not os.access(output_dir, os.W_OK):
                self.logger.error(f'Write permission denied for directory {output_dir}')
                raise PermissionError(f'Write permission denied for directory {output_dir}')
        else:
            try:
                os.makedirs(output_dir)
            except PermissionError:
                self.logger.error(f'Permission denied when creating directory {output_dir}')
                raise PermissionError(f'Permission denied when creating directory {output_dir}')
            except OSError as e:
                self.logger.error(f'Failed to create directory {output_dir}: {e}')
                raise
        for (i, table) in enumerate(tables):
            csv_filename = f'table_{i + 1}.csv'
            csv_path = os.path.join(output_dir, csv_filename)
            if os.path.exists(csv_path) and (not overwrite):
                self.logger.warning(f'File {csv_path} already exists and overwrite is set to False. Skipping this table.')
                continue
            try:
                df = table['dataframe']
                df.to_csv(csv_path, index=False)
                self.logger.debug(f'Table {i + 1} saved to {csv_path}')
            except Exception as e:
                self.logger.error(f'Failed to save table {i + 1} to CSV: {e}')
                continue
        self.logger.info('All tables saved to CSV successfully')