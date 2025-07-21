"""
Module: table_text_extractor.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import importlib
from typing import List, Tuple

import fitz
import regex as re

from app.backend.utils.bbox_converter import camelot_to_pymupdf_coords


class TableTextExtractor:
    """
    The TableTextExtractor class handles the conversion of table bounding box (BBox) coordinates between Camelot and PyMuPDF,
    as well as the extraction and formatting of surrounding text for each table. These methods are critical for identifying
    and organizing relevant textual context around tables for further processing, such as LLM inference.

    Args:
        doc (fitz.Document): The PDF document.
    """

    def __init__(self, doc: fitz.Document):
        """
        Initialize TableTextExtractor with the document instance.

        Args:
            doc (fitz.Document): The PyMuPDF document.
        """
        self.doc = doc
        self._logger = None
        self._text_normalizer = None
        self._regex_patterns = None

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
                self._logger.setLevel(logging.DEBUG)
        return self._logger

    @property
    def text_normalizer(self):
        """Lazy load TextNormalizer."""
        if self._text_normalizer is None:
            try:
                TextNormalizer = importlib.import_module('verifaix.utils.text_normalizer').TextNormalizer
                TextNormalizerConfig = importlib.import_module('verifaix.utils.text_normalizer').TextNormalizerConfig
                config = TextNormalizerConfig(settings_type='basic')
                self._text_normalizer = TextNormalizer(config=config)
            except ImportError as e:
                self.logger.error(f'Failed to import TextNormalizer: {e}')
                raise
        return self._text_normalizer

    @property
    def regex_patterns(self):
        """Lazy load RegexPatterns."""
        if self._regex_patterns is None:
            try:
                RegexPatterns = importlib.import_module('verifaix.utils.regex_patterns').RegexPatterns
                self._regex_patterns = RegexPatterns()
            except ImportError as e:
                self.logger.error(f'Failed to import RegexPatterns: {e}')
                raise
        return self._regex_patterns

    def extract_surrounding_text(self, page_num: int, table_bbox: List[float], page_height: float, margin: float=5.0, block_threshold: int=3) -> Tuple[str, str, str]:
        """
        Extract surrounding text (above and below a table) and format it for LLM inference.

        Args:
            page_num (int): Page number.
            table_bbox (List[float]): Bounding box of the table.
            page_height (float): Height of the page.
            margin (float): Margin to add around the table_bbox to ensure surrounding text is captured.
            block_threshold (int): Number of blocks to capture above and below the table.

        Returns:
            Tuple[str, str, str]: Text above, text below, and detected table title (if any).
        """
        self.logger.debug(f'Extracting and formatting surrounding text for table on page {page_num + 1}')
        pymupdf_bbox = camelot_to_pymupdf_coords(table_bbox, page_height)
        self.logger.debug(f'PyMuPDF converted bbox: {pymupdf_bbox}')
        page = self.doc[page_num]
        blocks = page.get_text('blocks')
        above_text = []
        below_text = []
        table_title = None

        def clean_and_format_text(text_blocks):
            """Cleans text by removing excessive whitespace and ensuring proper sentence endings."""
            full_text = ' '.join(text_blocks)
            full_text = re.sub('\\s+', ' ', full_text).strip()
            if not full_text.endswith(('.', '!', '?')):
                full_text += '.'
            normalized_text = self.text_normalizer.normalize(full_text, settings_type='basic')
            return normalized_text
        for block in reversed(blocks):
            block_bottom_y = block[3]
            if block_bottom_y <= pymupdf_bbox[1]:
                block_text = block[4].strip()
                above_text.insert(0, block_text)
                if len(above_text) >= block_threshold:
                    break
        table_title_patterns = self.regex_patterns.get_patterns()['table_titles']
        for block_text in above_text:
            for pattern in table_title_patterns:
                match = pattern.search(block_text)
                if match:
                    table_title = match.group(0)
                    self.logger.debug(f'Table title found: {table_title}')
                    break
            if table_title:
                break
        for block in blocks:
            block_top_y = block[1]
            if block_top_y >= pymupdf_bbox[3]:
                block_text = block[4].strip()
                below_text.append(block_text)
                if len(below_text) >= block_threshold:
                    break
        above_text_str = clean_and_format_text(above_text) if above_text else None
        below_text_str = clean_and_format_text(below_text) if below_text else None
        self.logger.debug(f'Final formatted above text: {above_text_str}')
        self.logger.debug(f'Final formatted below text: {below_text_str}')
        return (above_text_str, below_text_str, table_title)