"""
Module: table_merger.py
Description: Implementation of table merger functionality

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
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import fitz
import pandas as pd
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

load_dotenv('../../.env')
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator


class BBoxModel(BaseModel):
    bbox: List[float] = Field(..., min_length=4, max_length=4, description='A list of 4 float values representing the bounding box coordinates [x1, y1, x2, y2].')

    @field_validator('bbox')
    @classmethod
    def validate_bbox_values(cls, v):
        if not all((isinstance(coord, (int, float)) for coord in v)):
            raise ValueError('All values in bbox must be of type int or float.')
        return v
    model_config = {'validate_assignment': True}

class TableModel(BaseModel):
    table_number: int = Field(..., description='The number of the table.')
    page: int = Field(..., description='The page number where the table is located.')
    bbox: BBoxModel = Field(..., description='The bounding box of the table.')
    dataframe: Optional[List[Dict[str, Any]]] = Field(None, description='The table data as a list of dictionaries.')
    parsing_report: Dict[str, Any] = Field(..., description='Report on the parsing process.')
    table_metrics: Dict[str, Any] = Field(..., description='Extracted metrics from the table: accuracy, completeness, consistency, whitespace, and confidence.')
    page_height: float = Field(..., gt=0, description='The height of the page.')
    dpi: Optional[float] = Field(default=72.0, description='The dots per inch of the image, defaults to 72.0.')

    @model_validator(mode='before')
    @classmethod
    def convert_bbox_to_model(cls, values):
        bbox = values.get('bbox')
        if isinstance(bbox, list):
            values['bbox'] = BBoxModel(bbox=bbox)
        return values
    model_config = {'validate_assignment': True}

class TableMerger:

    def __init__(self, doc: fitz.Document, bottom_threshold_ratio: float=0.2, top_threshold_ratio: float=0.2, fuzzy_similarity_threshold: int=95, distance_from_top: float=20.0, margin: float=10.0, debug_output_dir: str=None):
        """
        Initialize the TableMerger with tweakable parameters.

        Args:
            doc (fitz.Document): PyMuPDF Document.
            bottom_threshold_ratio (float): Ratio for bottom threshold when comparing tables.
            top_threshold_ratio (float): Ratio for top threshold when comparing tables.
            fuzzy_similarity_threshold (int): Similarity threshold for fuzzy matching (0-100).
            margin (float): Margin around tables to detect nearby text elements.
            debug_output_dir (str): Directory to save debug images.
        """
        self.doc = doc
        self.bottom_threshold_ratio = bottom_threshold_ratio
        self.top_threshold_ratio = top_threshold_ratio
        self.fuzzy_similarity_threshold = fuzzy_similarity_threshold
        self.distance_from_top = distance_from_top
        self.margin = margin
        self.debug_output_dir = debug_output_dir
        self._logger = None
        self._regex_patterns = None

    @property
    def logger(self):
        """Lazy-load the logger."""
        if self._logger is None:
            ColoredLogger = importlib.import_module('verifaix.utils.colored_logger_mini').setup_logger
            self._logger = ColoredLogger(__name__)
        return self._logger

    @property
    def regex_patterns(self):
        """Lazy-load the RegexPatterns for text pattern matching."""
        if self._regex_patterns is None:
            RegexPatterns = importlib.import_module('verifaix.utils.regex_patterns').RegexPatterns
            self._regex_patterns = RegexPatterns()
        return self._regex_patterns

    def check_tables_for_merges(self, all_tables: List[Dict[str, Any]], debug_output_dir: str=None) -> List[Dict[str, Any]]:
        """Check all processed tables for potential merges and only output the merged table or unmerged tables."""
        i = 0
        merged_tables = []
        while i < len(all_tables):
            current_table = all_tables[i]
            if i + 1 >= len(all_tables):
                self.logger.debug(f'Reached the last table at index {i}. No more tables to compare.')
                merged_tables.append(current_table)
                break
            next_table = all_tables[i + 1]
            if 'page' not in current_table or 'page' not in next_table:
                self.logger.warning(f"Missing 'page' key in one of the tables: {(current_table if 'page' not in current_table else next_table)}. Skipping merge check for this table.")
                merged_tables.append(current_table)
                i += 1
                continue
            should_merge = self.check_table_merge(current_table, next_table)
            if should_merge:
                merged_table = self.merge_tables(current_table, next_table)
                if merged_table:
                    merged_tables.append(merged_table)
                    i += 2
                    continue
            else:
                merged_tables.append(current_table)
            i += 1
        if i == len(all_tables) - 1:
            merged_tables.append(all_tables[i])
        if debug_output_dir:
            os.makedirs(debug_output_dir, exist_ok=True)
            for page_num in range(self.doc.page_count):
                tables_on_page = [table['merged_table'] for table in merged_tables if isinstance(table, dict) and 'merged_table' in table and (page_num + 1 in table['merged_table']['pages'])]
                if tables_on_page:
                    output_path = os.path.join(debug_output_dir, f'debug_page_{page_num + 1}.png')
                    self.create_debug_image(page_num, tables_on_page, output_path)
        return merged_tables

    def validate_tables(self, current_table: Dict[str, Any], next_table: Dict[str, Any]) -> bool:
        """Validate the structure and fields of the tables using Pydantic models."""
        try:
            self.current_table_validated = TableModel(**current_table)
            self.next_table_validated = TableModel(**next_table)
            self.logger.debug(f'Validated current table: {self.current_table_validated}')
            self.logger.debug(f'Validated next table: {self.next_table_validated}')
            return True
        except ValidationError as e:
            self.logger.error(f'Validation error: {e}')
            return False

    def convert_tables_to_dataframes(self, current_table: Dict[str, Any], next_table: Dict[str, Any]) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """Convert table data from JSON or list of dicts into pandas DataFrames."""
        try:
            current_df = pd.DataFrame(current_table['dataframe']) if not isinstance(current_table['dataframe'], pd.DataFrame) else current_table['dataframe']
            next_df = pd.DataFrame(next_table['dataframe']) if not isinstance(next_table['dataframe'], pd.DataFrame) else next_table['dataframe']
            if current_df.empty or next_df.empty:
                self.logger.debug('One of the tables is empty. Cannot merge.')
                return (None, None)
            return (current_df, next_df)
        except ValueError as e:
            self.logger.error(f'Error converting table data to DataFrame: {e}')
            return (None, None)
        except Exception as e:
            self.logger.error(f'Unexpected error during DataFrame conversion: {e}')
            return (None, None)

    def dataframe_to_json_records(self, df: pd.DataFrame) -> list:
        """Utility function to convert a DataFrame to JSON records."""
        return df.to_dict(orient='records')

    def run_dataframe_checks(self, current_df: pd.DataFrame, next_df: pd.DataFrame) -> bool:
        """Check for column consistency, data type matching, and other relevant checks."""
        if len(current_df) == 1:
            self.logger.debug('Current table has only one row. Assuming it may be a header row.')
            header_only = True
        else:
            header_only = False
        if len(current_df.columns) != len(next_df.columns):
            self.logger.debug('Tables have different column counts. They should not be merged.')
            return False
        if not current_df.columns.equals(next_df.columns):
            self.logger.debug('Tables have different column headers. They should not be merged.')
            return False
        if not header_only and (not current_df.dtypes.equals(next_df.dtypes)):
            self.logger.debug('Tables have mismatched data types. They should not be merged.')
            return False
        if current_df.empty or next_df.empty:
            self.logger.debug('One of the tables is empty. They should not be merged.')
            return False
        row_difference_ratio = abs(len(current_df) - len(next_df)) / max(len(current_df), len(next_df))
        if not header_only and row_difference_ratio > 0.5:
            self.logger.debug('The row counts of the two tables are too different to be merged.')
            return False
        self.logger.debug('Dataframe checks completed:')
        self.logger.debug(f"- Column count consistency: {('Passed' if len(current_df.columns) == len(next_df.columns) else 'Failed')}")
        self.logger.debug(f"- Column header consistency: {('Passed' if current_df.columns.equals(next_df.columns) else 'Failed')}")
        self.logger.debug(f"- Data type consistency: {('Passed' if header_only or current_df.dtypes.equals(next_df.dtypes) else 'Failed')}")
        self.logger.debug(f"- Non-empty tables: {('Passed' if not current_df.empty and (not next_df.empty) else 'Failed')}")
        self.logger.debug(f"- Row count similarity: {('Passed' if header_only or row_difference_ratio <= 0.5 else 'Failed')}")
        return True

    def check_table_merge(self, current_table: Dict[str, Any], next_table: Dict[str, Any]) -> bool:
        """Main method to check if two tables should be merged."""
        self.logger.debug(f"Checking table merge between page {current_table['page']} and page {next_table['page']}")
        if not self.validate_tables(current_table, next_table):
            return False
        (current_df, next_df) = self.convert_tables_to_dataframes(current_table, next_table)
        if current_df is None or next_df is None:
            return False
        if not self.run_dataframe_checks(current_df, next_df):
            return False
        if current_table['page'] != next_table['page']:
            return self.check_cross_page_merge(current_table, next_table, current_df, next_df)
        return self.check_same_page_merge(current_table, next_table)

    def check_cross_page_merge(self, current_table: Dict[str, Any], next_table: Dict[str, Any], current_df: pd.DataFrame, next_df: pd.DataFrame) -> bool:
        """Handle cross-page table merging based on proximity and content."""
        (current_top, current_bottom) = self.get_content_boundaries(current_table['page'] - 1)
        (next_top, next_bottom) = self.get_content_boundaries(next_table['page'] - 1)
        distance_to_bottom = abs(current_bottom - current_table['bbox'][3])
        distance_from_top = abs(next_table['bbox'][1] - next_top)
        self.logger.debug(f'Calculated distances: distance_to_bottom={distance_to_bottom}, distance_from_top={distance_from_top}')
        if distance_from_top < self.distance_from_top:
            self.logger.debug('Tables are very close and there is no intervening text. Allowing merge based on proximity.')
            return True
        bottom_margin_current_page = self.get_page_margin(self.doc[current_table['page'] - 1], margin_type='bottom')
        top_margin_next_page = self.get_page_margin(self.doc[next_table['page'] - 1], margin_type='top')
        if current_bottom > bottom_margin_current_page and next_top < top_margin_next_page:
            self.logger.debug('Tables span across pages and are close enough to be merged based on margins.')
            return True
        self.logger.debug('Tables are not close enough to be merged based on margins between pages.')
        return False

    def check_same_page_merge(self, current_table: Dict[str, Any], next_table: Dict[str, Any]) -> bool:
        """Check if two tables on the same page should be merged by comparing content, position, and surrounding text."""
        (current_df, next_df) = self.convert_tables_to_dataframes(current_table, next_table)
        if current_df is None or next_df is None:
            return False
        current_table_bbox = current_table['bbox']
        next_table_bbox = next_table['bbox']
        distance_between_tables = abs(next_table_bbox[1] - current_table_bbox[3])
        self.logger.debug(f'Distance between tables: {distance_between_tables}')
        (current_top, current_bottom) = self.get_content_boundaries(current_table['page'] - 1)
        current_content_height = abs(current_bottom - current_top)
        margin_threshold = self.bottom_threshold_ratio * current_content_height
        if len(current_df.columns) != len(next_df.columns):
            self.logger.debug('Tables have different column counts. Not merging.')
            return False
        (current_page_text_below, next_page_text_above) = self.get_text_elements_around_table(current_table['page'] - 1, current_table_bbox)
        if len(current_page_text_below) == 0 and len(next_page_text_above) == 0:
            self.logger.debug('Tables are very close, with no intervening text or spaces. Considering merge.')
            return True
        elif any(current_page_text_below) or any(next_page_text_above):
            self.logger.debug('There is intervening text or multiple blank spaces. Not merging.')
            return False
        if distance_between_tables < margin_threshold:
            self.logger.debug('Tables are close enough and have the same column count. Allowing merge.')
            return True
        else:
            self.logger.debug('Tables are not close enough based on margin thresholds. Not merging.')
            return False

    def merge_tables(self, current_table: Dict[str, Any], next_table: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two table objects and prepare them for LLM validation.

        Args:
            current_table (Dict[str, Any]): The first table to be merged.
            next_table (Dict[str, Any]): The second table to be merged.

        Returns:
            Dict[str, Any]: Merged table with references to the original tables, all in JSON-friendly format.
        """

        def convert_table_to_json(table: Dict[str, Any]) -> Dict[str, Any]:
            """Helper function to convert a table's DataFrame to JSON-friendly format."""
            return {**table, 'dataframe': self.dataframe_to_json_records(pd.DataFrame(table['dataframe']))}

        def merge_dataframes(tables: List[Dict[str, Any]]) -> pd.DataFrame:
            """Helper function to merge DataFrames from a list of tables."""
            return pd.concat([pd.DataFrame(table['dataframe']) for table in tables], ignore_index=True)
        tables = [current_table, next_table]
        source_tables_json = [convert_table_to_json(table) for table in tables]
        merged_table_json = self.dataframe_to_json_records(merge_dataframes(tables))
        merged_table = {'table_number': [current_table['table_number'], next_table['table_number']], 'pages': [current_table['page'], next_table['page']], 'bbox': [min(current_table['bbox'][0], next_table['bbox'][0]), min(current_table['bbox'][1], next_table['bbox'][1]), max(current_table['bbox'][2], next_table['bbox'][2]), max(current_table['bbox'][3], next_table['bbox'][3])], 'table_data': merged_table_json, 'merged': True, 'parsing_report': {'accuracy': max(current_table['parsing_report']['accuracy'], next_table['parsing_report']['accuracy']), 'whitespace': (current_table['parsing_report']['whitespace'] + next_table['parsing_report']['whitespace']) / 2, 'order': current_table['parsing_report']['order']}, 'source_tables': source_tables_json}
        return merged_table

    def get_text_elements_around_table(self, page_num: int, table_bbox: List[float], margin: float=10.0) -> Tuple[List[str], List[str]]:
        """Extract text elements above and below a table on a given page with a larger margin."""
        self.logger.debug(f'Extracting text elements around table on page {page_num + 1} with margin {margin}')
        page = self.doc[page_num]
        blocks = page.get_text('blocks')
        above_text_blocks = []
        below_text_blocks = []
        for block in blocks:
            block_top_y = block[1]
            block_bottom_y = block[3]
            block_text = block[4] if len(block) > 4 else ''
            if block_bottom_y <= table_bbox[1] - margin:
                above_text_blocks.append(block_text)
            if block_top_y >= table_bbox[3] + margin:
                below_text_blocks.append(block_text)
        self.logger.debug(f'Found {len(above_text_blocks)} text blocks above and {len(below_text_blocks)} below the table on page {page_num + 1}')
        return (above_text_blocks, below_text_blocks)

    def get_page_margin(self, page: fitz.Page, margin_type: str='bottom', buffer: float=10.0) -> float:
        """
        Calculate the top or bottom margin of a page, considering both text and image blocks, and applying an optional buffer.

        Args:
            page (fitz.Page): The page to analyze.
            margin_type (str): 'top' or 'bottom' to specify which margin to calculate.
            buffer (float): A buffer to adjust the calculated margin.

        Returns:
            float: The calculated top or bottom margin, adjusted by the buffer.
        """
        blocks = page.get_text('dict')['blocks']
        relevant_blocks = [block for block in blocks if 'bbox' in block]
        if not relevant_blocks:
            return page.rect.height if margin_type == 'bottom' else 0
        if margin_type == 'bottom':
            last_block = max(relevant_blocks, key=lambda b: b['bbox'][3])
            return page.rect.height - last_block['bbox'][3] + buffer
        elif margin_type == 'top':
            first_block = min(relevant_blocks, key=lambda b: b['bbox'][1])
            return first_block['bbox'][1] - buffer
        return 0

    def get_content_boundaries(self, page_num: int) -> Tuple[float, float]:
        """Get the top and bottom boundaries of the content area on a page."""
        page = self.doc[page_num]
        elements = page.get_text('dict')['blocks']
        if not elements:
            return (0, page.rect.height)
        first_element = next((elem for elem in elements if 'bbox' in elem and elem['bbox'][3] > elem['bbox'][1]), None)
        last_element = next((elem for elem in reversed(elements) if 'bbox' in elem and elem['bbox'][3] > elem['bbox'][1]), None)
        if not first_element or not last_element:
            return (0, page.rect.height)
        content_top = first_element['bbox'][1]
        content_bottom = last_element['bbox'][3]
        self.logger.debug(f'Content boundaries for page {page_num + 1}: top={content_top}, bottom={content_bottom}')
        return (content_top, content_bottom)

    def table_json_to_dataframe(self, table: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert a table stored as JSON to a pandas DataFrame.

        Args:
            table (Dict[str, Any]): Table object containing JSON data.

        Returns:
            pd.DataFrame: Converted pandas DataFrame.
        """
        if 'dataframe_json' in table:
            return pd.DataFrame(table['dataframe_json'])
        else:
            raise ValueError("Table object does not contain 'dataframe_json' key.")

    def normalize_table_data(self, dataframe: Union[pd.DataFrame, list]) -> str:
        """
        Normalize the table data by converting to lowercase and removing excessive whitespace.
        We are normalizing table data to compare tables as strings
        Args:
            dataframe: Either a pandas DataFrame or a list of dictionaries representing the table data.
        
        Returns:
            str: Normalized table data as a string.
        """
        try:
            if isinstance(dataframe, list) and all((isinstance(item, dict) for item in dataframe)):
                self.logger.debug('Converting list of dictionaries to pandas DataFrame for normalization')
                dataframe = pd.DataFrame(dataframe)
            self.logger.debug('Normalizing data from pandas DataFrame')
            table_data = dataframe.to_string(index=False, header=False)
            table_data_normalized = ' '.join(table_data.lower().split())
            return table_data_normalized
        except Exception as e:
            self.logger.error(f'Error during normalization: {str(e)}')
            raise ValueError('Failed to normalize table data') from e

    def filter_similar_text(self, text_blocks: List[str], table_data: str) -> List[str]:
        """Filter out text blocks that are 95% or more similar to the normalized Camelot table data."""
        if not isinstance(text_blocks, list):
            self.logger.error(f'Expected a list of text blocks but got {type(text_blocks)}')
            return []
        filtered_text_blocks = []
        for text in text_blocks:
            if isinstance(text, str):
                text_normalized = ' '.join(text.lower().split())
                similarity = fuzz.ratio(text_normalized, table_data)
                self.logger.debug(f'Text block similarity: {similarity}% for text block: {text_normalized}')
                if similarity < self.fuzzy_similarity_threshold:
                    filtered_text_blocks.append(text)
                else:
                    self.logger.debug(f'Removed text block due to high similarity ({similarity}%): {text}')
            else:
                self.logger.error(f'Skipping non-string text block: {text}')
        return filtered_text_blocks

    def dataframe_to_json_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Convert a pandas DataFrame to a JSON-friendly format using 'records' orientation.

        Args:
            df (pd.DataFrame): DataFrame to be converted.

        Returns:
            List[Dict[str, Any]]: JSON-ready object in 'records' format.
        """
        return df.to_dict(orient='records')

    def convert_to_llm_friendly_format(self, merged_table: dict) -> str:
        """
        Converts merged_table output to a more LLM-friendly format, keeping only necessary fields.
        
        Args:
            merged_table (dict): The original merged table output with detailed fields.
        
        Returns:
            str: JSON string with the pruned and optimized structure for LLM input.
        """
        merged_table_json = self.dataframe_to_json_records(pd.DataFrame(merged_table['merged_table']))
        llm_friendly_output = {'table_number': merged_table['table_number'], 'pages': merged_table['pages'], 'bbox': merged_table['bbox'], 'merged_table': merged_table_json, 'parsing_report': {'accuracy': merged_table['parsing_report']['accuracy'], 'whitespace': merged_table['parsing_report']['whitespace'], 'order': merged_table['parsing_report']['order']}, 'source_tables': [{'table_number': table['table_number'], 'page': table['page'], 'bbox': table['bbox'], 'dataframe': self.dataframe_to_json_records(pd.DataFrame(table['dataframe']))} for table in merged_table['source_tables']]}
        return json.dumps(llm_friendly_output, indent=4)

    def create_debug_image(self, page_num: int, tables: List[Dict[str, Any]], output_path: str):
        """
        Create a debug image showing the page content, text items, image items, coordinate system, and detected tables.
        
        Args:
            page_num (int): The page number to visualize.
            tables (List[Dict[str, Any]]): List of tables on the page.
            output_path (str): Path to save the output image.
        """
        page = self.doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.line((0, 0, pix.width, 0), fill='red', width=2)
        draw.line((0, 0, 0, pix.height), fill='green', width=2)
        for i in range(0, pix.width, 100):
            draw.line((i, 0, i, 10), fill='red', width=1)
            draw.text((i, 15), str(i), fill='red', font=font)
        for i in range(0, pix.height, 100):
            draw.line((0, i, 10, i), fill='green', width=1)
            draw.text((15, i), str(i), fill='green', font=font)
        for table in tables:
            bbox = table['bbox']
            scaled_bbox = [coord * 2 for coord in bbox]
            draw.rectangle(scaled_bbox, outline='blue', width=2)
            draw.text((scaled_bbox[0], scaled_bbox[1] - 20), f"Table {table['page']}", fill='blue', font=font)
        blocks = page.get_text('dict')['blocks']
        for block in blocks:
            block_bbox = [block['bbox'][0] * 2, block['bbox'][1] * 2, block['bbox'][2] * 2, block['bbox'][3] * 2]
            if 'text' in block:
                draw.rectangle(block_bbox, outline='purple', width=1)
                draw.text((block_bbox[0], block_bbox[1] - 10), f'Text', fill='purple', font=font)
            elif 'image' in block:
                draw.rectangle(block_bbox, outline='orange', width=1)
                draw.text((block_bbox[0], block_bbox[1] - 10), f'Image', fill='orange', font=font)
        top_margin = self.get_page_margin(page, margin_type='top') * 2
        bottom_margin = self.get_page_margin(page, margin_type='bottom') * 2
        draw.line((0, top_margin, pix.width, top_margin), fill='yellow', width=2)
        draw.line((0, bottom_margin, pix.width, bottom_margin), fill='yellow', width=2)
        img.save(output_path)
        self.logger.debug(f'Debug image saved to {output_path}')
if __name__ == '__main__':
    project_path = os.getenv('PROJECT_PATH', '.')
    pdf_path = os.path.join(project_path, 'documents/BHT_CV32A65X.pdf')
    output_dir = os.path.join(project_path, 'verifaix/data/images')
    doc = fitz.open(pdf_path)
    merger = TableMerger(doc, bottom_threshold_ratio=0.2, top_threshold_ratio=0.2, fuzzy_similarity_threshold=95, margin=10.0, debug_output_dir=output_dir)