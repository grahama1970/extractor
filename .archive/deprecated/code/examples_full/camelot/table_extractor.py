"""
Module: table_extractor.py

External Dependencies:
- pandas: https://pandas.pydata.org/docs/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import asyncio
import importlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import fitz
import pandas as pd
import spacy
from tqdm.asyncio import tqdm

from app.backend.utils.bbox_converter import camelot_to_pymupdf_coords
from app.backend.utils.calculate_iou import calculate_iou
from app.backend.utils.load_json_file import load_json_file
from app.backend.utils.memory import check_memory_usage, clear_cache_and_collect_garbage
from app.backend.utils.save_cache_to_json import save_cache_to_json


class TableExtractor:

    def __init__(self, pdf_path: str, output_dir: str, pymupdf_tables: List[Dict]=None, tests: List[str]=None, image2table_json_path: str=None):
        """
        Initialize TableExtractor with PDF and output configurations.

        Args:
            pdf_path (str): Path to the input PDF.
            output_dir (str): Directory for output files.
            tests (List[str]): Optional tests for quality checking.
        """
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.nlp = spacy.load('en_core_web_sm')
        self.target_dpi = float(os.getenv('PYMUPDF_DPI', 72))
        self.table_extraction_quality_threshold = float(os.getenv('TABLE_ACCURACY_THRESHOLD', 0.9))
        self.page_edge_threshold = float(os.getenv('PAGE_EDGE_THRESHOLD', 0.2))
        self.max_memory_usage = int(os.getenv('MAX_MEMORY_USAGE', 1024 * 1024 * 1024))
        self.pymupdf_tables = pymupdf_tables
        if image2table_json_path and os.path.exists(image2table_json_path):
            self.load_image2table_json(image2table_json_path)
        self.table_schema = [{'index': "Original line index (from the 'index' field)"}, {'data_type': "'table_row' or 'table_header'"}, {'cell': 'the original text of the cell'}, {'page': "Original page number (from the 'page' field)"}, {'bbox': "Bounding box of the text (from the 'bbox' field)"}, {'title': 'Title of the table (verbatim or inferred, as per instructions)'}, {'rationale': 'Explanation of why this line is classified as a table header or row'}]
        self.table_quality_scores = {}
        self.extracted_tables_cache = {}
        self.best_params_cache = {}
        self.table_extraction_quality_threshold = float(os.environ.get('TABLE_ACCURACY_THRESHOLD', 0.9))
        self.page_edge_threshold = float(os.environ.get('PAGE_EDGE_THRESHOLD', 0.2))
        self.tests = tests if tests is not None else ['shape', 'column_names', 'dtypes', 'values', 'continuity', 'completeness']
        self.doc = fitz.open(self.pdf_path)
        self.file_name = Path(self.pdf_path).stem
        self._logger = None
        self._table_quality_evaluator = None
        self._table_text_extractor = None
        self._table_merger = None

    @property
    def logger(self):
        """Lazy-load the ColoredLogger."""
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

    @property
    def table_quality_evaluator(self):
        """Lazy-load TableQualityEvaluator."""
        if self._table_quality_evaluator is None:
            try:
                table_quality_module = importlib.import_module('verifaix.camelot_extractor.table_quality_evaluator')
                TableQualityEvaluator = table_quality_module.TableQualityEvaluator
                self._table_quality_evaluator = TableQualityEvaluator(self.pdf_path)
            except ImportError as e:
                self.logger.error(f'Failed to import TableQualityEvaluator: {e}')
                raise
        return self._table_quality_evaluator

    @property
    def table_text_extractor(self):
        """Lazy-load TableTextExtractor."""
        if self._table_text_extractor is None:
            try:
                table_text_extractor_module = importlib.import_module('verifaix.camelot_extractor.table_text_extractor')
                TableTextExtractor = table_text_extractor_module.TableTextExtractor
                self._table_text_extractor = TableTextExtractor(self.doc)
            except ImportError as e:
                self.logger.error(f'Failed to import TableTextExtractor: {e}')
                raise
        return self._table_text_extractor

    @property
    def table_merger(self):
        """Lazy-load TableMerger."""
        if self._table_merger is None:
            try:
                table_merger_module = importlib.import_module('verifaix.camelot_extractor.table_merger')
                TableMerger = table_merger_module.TableMerger
                self._table_merger = TableMerger(self.doc)
            except ImportError as e:
                self.logger.error(f'Failed to import TableMerger: {e}')
                raise
        return self._table_merger

    @property
    def text_normalizer(self):
        """Lazy-load TextNormalizer."""
        if self._text_normalizer is None:
            try:
                text_normalizer_module = importlib.import_module('verifaix.utils.text_normalizer')
                TextNormalizer = text_normalizer_module.TextNormalizer
                TextNormalizerConfig = text_normalizer_module.TextNormalizerConfig
                config = TextNormalizerConfig(settings_type='advanced')
                self._text_normalizer = TextNormalizer(config)
            except ImportError as e:
                self.logger.error(f'Failed to import TextNormalizer: {e}')
                raise
        return self._text_normalizer

    async def process_pdf(self, force_extract: bool=False):
        """
        Process the PDF file to extract tables, merge related tables, and assemble final output.

        Returns:
            List[Dict]: A list of dictionaries representing the final tables.
        """
        self.logger.info('Starting PDF table extraction process')
        try:
            extracted_tables = await self.load_or_extract_tables(force_extract=force_extract)
            merged_tables = self.table_merger.check_tables_for_merges(extracted_tables)
            final_tables = merged_tables
            self.logger.info('Completed table extraction and comparison process')
            json_cache_path = os.path.join(self.output_dir, f'{self.file_name}_tables_cache.json')
            save_cache_to_json(final_tables, json_cache_path)
            self.logger.info(f'Saved extracted tables to cache: {json_cache_path}')
            return final_tables
        except Exception as e:
            self.logger.error(f'Error in process_pdf: {str(e)}')
            raise

    async def load_or_extract_tables(self, force_extract=False) -> List[Dict]:
        """
        Load tables from a cached JSON file if it exists, or extract them if not.

        Args:
            force_extract (bool): If True, always extract tables even if cache exists.

        Returns:
            List[Dict]: A list of dictionaries containing details about each extracted table.
        """
        self.logger.info('Starting load_or_extract_tables process')
        json_cache_path = os.path.join(self.output_dir, 'tables', f'{self.file_name}_tables_cache.json')
        if not force_extract:
            cached_tables = load_json_file(json_cache_path)
            if cached_tables:
                self.logger.info(f'Loaded {len(cached_tables)} tables from cache: {json_cache_path}')
                return cached_tables
            else:
                self.logger.warning(f'Cache not available or invalid. Proceeding with table extraction.')
        self.logger.info('Extracting tables...')
        extracted_tables = await self.extract_tables()
        return extracted_tables

    async def extract_tables(self, save=True):
        """
        Extracts tables from the PDF using Camelot.

        Args:
            save (bool): Whether to save the extracted tables to a JSON file. Defaults to True.

        Returns:
            List[Dict]: A list of dictionaries containing details about each extracted table.
        """
        self.logger.info('Starting table extraction process')
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            extracted_tables = []
            for page_num in tqdm(range(len(self.doc)), desc='Processing pages'):
                page_tables = await self.process_page(page_num)
                extracted_tables.extend(page_tables)
            self.logger.info(f'Extracted {len(extracted_tables)} tables in total')
            if extracted_tables and save:
                json_cache_path = os.path.join(self.output_dir, 'tables', f'{self.file_name}_tables_cache.json')
                save_cache_to_json(extracted_tables, json_cache_path)
                self.logger.info(f'Saved extracted tables to cache: {json_cache_path}')
            return extracted_tables
        except Exception as e:
            self.logger.error(f'Critical error in extract_tables: {str(e)}')
            raise

    async def process_page(self, page_num: int) -> List[Dict]:
        """
        Process a single page and extract tables.

        Args:
            page_num (int): The zero-based index of the page to process.

        Returns:
            List[Dict]: A list of dictionaries containing processed table information.
        """
        self.logger.info(f'Starting processing of page {page_num + 1}')
        try:
            if check_memory_usage(self.max_memory_usage, self.logger):
                clear_cache_and_collect_garbage(self.output_dir, self.logger)
            page = self.doc[page_num]
            page_rect = page.rect
            page_height = page_rect.height
            zoom = self.target_dpi / 72
            if not page.get_text().strip():
                self.logger.info(f'Page {page_num + 1} appears to be empty or has no text content. Skipping.')
                return []
            tables = self.read_tables_from_page(page_num)
            if not tables:
                self.logger.info(f'No tables found on page {page_num + 1}')
                return []
            processed_tables = await self.process_tables(tables, page, page_num, page_height, zoom)
            self.logger.info(f'Successfully processed {len(processed_tables)} tables on page {page_num + 1}')
            return processed_tables
        except Exception as e:
            self.logger.error(f'Critical error processing page {page_num + 1}: {str(e)}')
            self.logger.exception('Traceback:')
            raise

    async def process_tables(self, tables, page, page_num, page_height, zoom):
        """Process all tables found on a page."""
        page_tables = []
        for (i, table) in enumerate(tables):
            try:
                table_info = await self.process_single_table(table, page, i, page_num, page_height, zoom)
                if table_info:
                    page_tables.append(table_info)
            except Exception as e:
                self.logger.error(f'Error processing table {i + 1} on page {page_num + 1}: {str(e)}')
        return page_tables

    def clean_table_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean a pandas DataFrame by removing newline characters,
        excessive whitespace, and converting numerical strings to numbers.

        Args:
            df (pd.DataFrame): The DataFrame to clean.

        Returns:
            pd.DataFrame: The cleaned DataFrame.
        """
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].apply(lambda x: self.text_normalizer.normalize(str(x)) if pd.notna(x) else x)
        df = df.replace('\\n', '', regex=True).applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.apply(pd.to_numeric, errors='ignore')
        return df

    async def process_single_table(self, table, page, table_index, page_num, page_height, zoom):
        """Process a single table and return its information."""
        self.logger.debug(f'Processing table {table_index + 1} on page {page_num + 1}')
        if not self.image2table_json:
            self.logger.warning('Image2Table JSON is empty, skipping IoU checks')
        table_metrics = self.table_quality_evaluator.calculate_table_confidence(table, page_num, self.image2table_json)
        table_confidence = table_metrics['confidence']
        if table_confidence < self.table_extraction_quality_threshold:
            self.logger.warning(f'Low confidence table detected on page {page_num + 1}. Confidence: {table_confidence}')
            return None
        bbox = table._bbox
        df = table.df
        report = table.parsing_report
        csv_string = ''
        if not df.empty:
            df = self.clean_table_dataframe(df)
            csv_string = df.to_csv(index=False)
            self.logger.debug('Created CSV string from dataframe')
        else:
            self.logger.debug('Dataframe is empty, no CSV string created')
        bbox_adjusted = camelot_to_pymupdf_coords(bbox, page_height, zoom)
        (above_text, below_text, title) = self.table_text_extractor.extract_surrounding_text(page_num, bbox, page_height)
        intersects_with_image2table = any((calculate_iou(bbox_adjusted, img2table['bbox'], logger=self.logger) > 0 for img2table in self.image2table_json if img2table['page'] == page_num + 1))
        if not intersects_with_image2table:
            self.logger.warning(f'No intersecting table found for table {table_index + 1} on page {page_num + 1} with Image2Table results.')
        pymupdf_tables = page.find_tables()
        intersects_with_pymupdf = any((calculate_iou(bbox_adjusted, pymupdf_table['bbox'], logger=self.logger) > 0 for pymupdf_table in pymupdf_tables))
        if not intersects_with_pymupdf:
            self.logger.warning(f'No intersecting table found for table {table_index + 1} on page {page_num + 1} with PyMuPDF results.')
        img_path = self.save_table_image(table, page_num, table_index)
        table_info = {'table_number': table_index + 1, 'page': page_num + 1, 'bbox': bbox_adjusted, 'bbox_camelot': bbox, 'table_data': df.to_dict(orient='records'), 'merged': False, 'parsing_report': report, 'table_metrics': table_metrics, 'image_path': img_path, 'should_merge': False, 'dpi': self.target_dpi, 'page_height': page_height * zoom, 'confidence': table_confidence, 'above_text': above_text, 'below_text': below_text, 'intersections': {'intersects_with_image2table': intersects_with_image2table, 'intersects_with_pymupdf': intersects_with_pymupdf}}
        return table_info

    def read_tables_from_page(self, page_num: int) -> List[Any]:
        """
        Read tables from a single page using Camelot with optimized parameters.
        Uses cached results if available.

        Args:
            page_num (int): The zero-based index of the page to process.

        Returns:
            List[Any]: A list of Camelot Table objects if tables are found, or an empty list if no tables are detected.
        """
        if page_num in self.extracted_tables_cache:
            self.logger.info(f'Using cached tables for page {page_num + 1}')
            return self.extracted_tables_cache[page_num]
        self.logger.info(f'Attempting to read tables from page {page_num + 1}')
        (best_tables, best_params) = self.table_quality_evaluator.find_best_table_extraction(page_num)
        if best_tables is None or len(best_tables) == 0:
            self.logger.warning(f'No tables found on page {page_num + 1}')
            best_tables = []
        self.logger.info(f'Successfully extracted {len(best_tables)} table(s) from page {page_num + 1} with params: {best_params}')
        return best_tables

    def save_table_image(self, table, page_num, table_index):
        """
        Save the table as an image using PyMuPDF and the table's bounding box, accounting for target_dpi.'

        Args:
            table (camelot.core.Table): The Camelot table object.
            page_num (int): The page number (0-based index).
            table_index (int): The index of the table on the page.

        Returns:
            str: The path to the saved image file, or an empty string if saving fails.
        """
        try:
            img_filename = f'{self.file_name}_page_{page_num + 1}_table_{table_index + 1}.png'
            img_path = os.path.join(self.output_dir, 'images', img_filename)
            try:
                output_path = Path(self.output_dir) / 'images'
                output_path.mkdir(parents=True, exist_ok=True)
                temp_file = output_path / '.write_test'
                temp_file.touch(exist_ok=True)
                temp_file.unlink()
                self.logger.info(f'Output directory is ready: {self.output_dir}')
            except OSError as e:
                self.logger.error(f'Failed to create or write to output directory {self.output_dir}: {str(e)}')
                return ''
            page = self.doc[page_num]
            zoom = self.target_dpi / 72.0
            page_height = page.rect.height
            bbox = table._bbox
            bbox_adjusted = camelot_to_pymupdf_coords(bbox, page_height, zoom)
            self.logger.debug(f'Original Camelot bbox: {bbox}')
            self.logger.debug(f'Adjusted PyMuPDF bbox: {bbox_adjusted}')
            self.logger.debug(f'Page height: {page_height}')
            rect = fitz.Rect(bbox_adjusted)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, clip=rect)
            try:
                pix.save(img_path)
            except PermissionError:
                self.logger.error(f'Permission denied when trying to save image to {img_path}')
                return ''
            except OSError as os_error:
                self.logger.error(f'OS error when trying to save image: {str(os_error)}')
                return ''
            self.logger.info(f'Saved table image to {img_path} with target DPI: {self.target_dpi}')
            return img_path
        except Exception as e:
            self.logger.error(f'Error saving table image: {str(e)}')
            return ''

    def load_image2table_json(self, image2table_json_path: str):
        """Load the Image2Table JSON file containing extracted table information."""
        try:
            with open(image2table_json_path, 'r') as f:
                self.image2table_json = json.load(f)
            self.logger.info(f'Loaded Image2Table JSON: {image2table_json_path}')
        except Exception as e:
            self.logger.error(f'Error loading Image2Table JSON: {str(e)}')
            raise

    async def check_bounding_boxes(self):
        """Check for intersections between Image2TableExtractor and TableExtractor bounding boxes."""
        for img2table_entry in self.image2table_json:
            img2table_bbox = img2table_entry['bbox']
            table_found = False
            for table in self.pymupdf_tables:
                pymupdf_bbox = table['bbox']
                iou = calculate_iou(img2table_bbox, pymupdf_bbox)
                if iou > 0.0:
                    self.logger.info(f'Found intersecting table with IoU: {iou}')
                    table_found = True
                    break
            if not table_found:
                self.logger.warning(f"No intersecting table found for Image2Table table on page {img2table_entry['page']}.")

async def main():
    project_path = os.getenv('PROJECT_PATH', '.')
    pdf_path = os.path.join(project_path, 'documents/BHT_CV32A65X.pdf')
    output_dir = os.path.join(project_path, 'verifaix/data')
    pymupdf_tables = []
    tests = ['shape', 'column_names']
    table_extractor = TableExtractor(pdf_path=pdf_path, output_dir=output_dir, pymupdf_tables=pymupdf_tables, tests=tests)
    try:
        final_tables = await table_extractor.process_pdf()
        for table in final_tables:
            print(f"Extracted Table on Page {table['pages']}:")
            print(f"DataFrame:\n{table['merged_table']}")
            print(f"Confidence Score: {table['parsing_report']}")
            print('----------------------------------------------------')
    except Exception as e:
        print(f'Error during table extraction: {e}')
if __name__ == '__main__':
    asyncio.run(main())