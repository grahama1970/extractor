"""
Module: llm_table_merge.py

External Dependencies:
- concurrent: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- tqdm: [Documentation URL]
- PIL: [Documentation URL]
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, List, Tuple, Literal

from pydantic import BaseModel
from tqdm import tqdm
from PIL import Image

from extractor.core.output import json_to_html
from extractor.core.processors.llm import BaseLLMComplexBlockProcessor
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block, TableCell
from extractor.core.schema.document import Document
from loguru import logger
import asyncio
import sys
from pathlib import Path
import subprocess
import json

# Direct ArangoDB connection - NO MORE DUMMY FUNCTIONS!
ARANGO_WORKER_PATH = "/home/graham/workspace/experiments/cc_executor/.claude/agents/workers/arango_tools_worker.py"


class LLMTableMergeProcessor(BaseLLMComplexBlockProcessor):
    block_types: Annotated[
        Tuple[BlockTypes],
        "The block types to process.",
    ] = (BlockTypes.Table, BlockTypes.TableOfContents)
    
    def __init__(self, llm_service=None, config=None):
        # Handle the complex initialization with multiple inheritance
        # We need to manually call the right initializers
        
        # First, initialize BaseProcessor attributes via assign_config
        from extractor.core.util import assign_config
        assign_config(self, config)
        
        # Set LLM-specific attributes from BaseLLMProcessor
        self.llm_service = None
        if hasattr(self, 'use_llm') and not self.use_llm:
            self.llm_service = None
        else:
            self.llm_service = llm_service
        
        # Initialize KnowledgeAwareProcessor attributes
        self._pattern_cache = {}
        self._batch_queries = []
        
        # Test ArangoDB connection (from KnowledgeAwareProcessor)
        self._test_arango_connection()
    table_height_threshold: Annotated[
        float,
        "The minimum height ratio relative to the page for the first table in a pair to be considered for merging.",
    ] = 0.6
    table_start_threshold: Annotated[
        float,
        "The maximum percentage down the page the second table can start to be considered for merging."
    ] = 0.2
    vertical_table_height_threshold: Annotated[
        float,
        "The height tolerance for 2 adjacent tables to be merged into one."
    ] = 0.25
    vertical_table_distance_threshold: Annotated[
        int,
        "The maximum distance between table edges for adjacency."
    ] = 20
    horizontal_table_width_threshold: Annotated[
        float,
        "The width tolerance for 2 adjacent tables to be merged into one."
    ] = 0.25
    horizontal_table_distance_threshold: Annotated[
        int,
        "The maximum distance between table edges for adjacency."
    ] = 10
    column_gap_threshold: Annotated[
        int,
        "The maximum gap between columns to merge tables"
    ] = 50
    disable_tqdm: Annotated[
        bool,
        "Whether to disable the tqdm progress bar.",
    ] = False
    table_merge_prompt: Annotated[
        str,
        "The prompt to use for rewriting text.",
        "Default is a string containing the Gemini rewriting prompt."
    ] = """You're a table analysis expert specializing in identifying split tables in PDFs.

You'll receive two images and HTML representations of tables from a PDF. Table 1 comes first, and Table 2 appears after it (possibly on the next page). Your job is to determine if these tables should be merged because they're actually parts of the same larger table that was split.

**Important Analysis Steps:**
1. I will use pandas.read_html() to parse both tables and analyze their structure
2. Compare column counts and column names/headers
3. Check if Table 2 has headers or continues without headers
4. Analyze data patterns and content relationships
5. Determine if tables are semantically related

**Merge Decision Criteria:**
- BOTTOM merge: Table 2 continues rows from Table 1 (same columns, no repeated headers)
- RIGHT merge: Table 2 adds columns to Table 1 (same rows, additional attributes)
- NO merge: Tables are independent and complete on their own

**Technical Analysis Process:**
```python
import pandas as pd
from io import StringIO

# Parse tables using pandas
try:
    df1 = pd.read_html(StringIO(table1_html))[0]
    df2 = pd.read_html(StringIO(table2_html))[0]
    
    # Analyze structure
    t1_shape = df1.shape
    t2_shape = df2.shape
    t1_columns = list(df1.columns)
    t2_columns = list(df2.columns)
    
    # Check for header patterns
    has_headers_t2 = not all(isinstance(col, int) for col in df2.columns)
    columns_match = t1_columns == t2_columns
    
except Exception as e:
    # Fallback to manual analysis
    pass
```

**Instructions:**
1. Examine the provided table images
2. Parse the HTML representations using the pandas approach shown above
3. Analyze table structure, headers, and data patterns
4. Determine if tables are split parts of a larger table
5. Make a conservative decision - only merge if clearly necessary

**Example Analysis:**
Input:
Table 1
```html
<table>
    <tr>
        <th>Signal</th>
        <th>IO</th>
        <th>Description</th>
        <th>Type</th>
    </tr>
    <tr>
        <td>clk_i</td>
        <td>in</td>
        <td>Clock input</td>
        <td>logic</td>
    </tr>
</table>
```
Table 2
```html
<table>
    <tr>
        <td>rst_ni</td>
        <td>in</td>
        <td>Reset active low</td>
        <td>logic</td>
    </tr>
    <tr>
        <td>valid_i</td>
        <td>in</td>
        <td>Valid signal</td>
        <td>logic</td>
    </tr>
</table>
```

Output:
```json
{
    "table1_description": "Signal interface table with 4 columns (Signal, IO, Description, Type) and 1 data row after headers",
    "table2_description": "Continuation of signal table with same 4 columns but no headers, containing 2 additional signal rows",
    "pandas_analysis": {
        "t1_shape": [1, 4],
        "t2_shape": [2, 4],
        "t1_has_headers": true,
        "t2_has_headers": false,
        "column_count_match": true,
        "data_pattern_match": true
    },
    "explanation": "Table 2 is a direct continuation of Table 1. Both have 4 columns with identical structure. Table 2 lacks headers and contains additional signal definitions that follow the same pattern as Table 1.",
    "merge": "true",
    "direction": "bottom"
}
```

**Input:**
Table 1
```html
{{table1}}
```
Table 2
```html
{{table2}}
```
"""

    @staticmethod
    def get_row_count(cells: List[TableCell]):
        if not cells:
            return 0

        max_rows = None
        for col_id in set([cell.col_id for cell in cells]):
            col_cells = [cell for cell in cells if cell.col_id == col_id]
            rows = 0
            for cell in col_cells:
                rows += cell.rowspan
            if max_rows is None or rows > max_rows:
                max_rows = rows
        return max_rows

    @staticmethod
    def get_column_count(cells: List[TableCell]):
        if not cells:
            return 0

        max_cols = None
        for row_id in set([cell.row_id for cell in cells]):
            row_cells = [cell for cell in cells if cell.row_id == row_id]
            cols = 0
            for cell in row_cells:
                cols += cell.colspan
            if max_cols is None or cols > max_cols:
                max_cols = cols
        return max_cols

    def rewrite_blocks(self, document: Document):
        pbar = tqdm(desc=f"{self.__class__.__name__} running", disable=self.disable_tqdm)
        table_runs = []
        table_run = []
        prev_block = None
        prev_page_block_count = None
        for page in document.pages:
            page_blocks = page.contained_blocks(document, self.block_types)
            for block in page_blocks:
                merge_condition = False
                if prev_block is not None:
                    prev_cells = prev_block.contained_blocks(document, (BlockTypes.TableCell,))
                    curr_cells = block.contained_blocks(document, (BlockTypes.TableCell,))
                    row_match = abs(self.get_row_count(prev_cells) - self.get_row_count(curr_cells)) < 5, # Similar number of rows
                    col_match = abs(self.get_column_count(prev_cells) - self.get_column_count(curr_cells)) < 2

                    subsequent_page_table = all([
                        prev_block.page_id == block.page_id - 1, # Subsequent pages
                        max(prev_block.polygon.height / page.polygon.height,
                            block.polygon.height / page.polygon.height) > self.table_height_threshold, # Take up most of the page height
                            (len(page_blocks) == 1 or prev_page_block_count == 1), # Only table on the page
                            (row_match or col_match)
                        ])

                    same_page_vertical_table = all([
                        prev_block.page_id == block.page_id, # On the same page
                        (1 - self.vertical_table_height_threshold) < prev_block.polygon.height / block.polygon.height < (1 + self.vertical_table_height_threshold), # Similar height
                        abs(block.polygon.x_start - prev_block.polygon.x_end) < self.vertical_table_distance_threshold, # Close together in x
                        abs(block.polygon.y_start - prev_block.polygon.y_start) < self.vertical_table_distance_threshold, # Close together in y
                        row_match
                    ])

                    same_page_horizontal_table = all([
                        prev_block.page_id == block.page_id, # On the same page
                        (1 - self.horizontal_table_width_threshold) < prev_block.polygon.width / block.polygon.width < (1 + self.horizontal_table_width_threshold), # Similar width
                        abs(block.polygon.y_start - prev_block.polygon.y_end) < self.horizontal_table_distance_threshold, # Close together in y
                        abs(block.polygon.x_start - prev_block.polygon.x_start) < self.horizontal_table_distance_threshold, # Close together in x
                        col_match
                    ])

                    same_page_new_column = all([
                        prev_block.page_id == block.page_id, # On the same page
                        abs(block.polygon.x_start - prev_block.polygon.x_end) < self.column_gap_threshold,
                        block.polygon.y_start < prev_block.polygon.y_end,
                        block.polygon.width * (1 - self.vertical_table_height_threshold) < prev_block.polygon.width  < block.polygon.width * (1 + self.vertical_table_height_threshold), # Similar width
                        col_match
                    ])
                    merge_condition = any([subsequent_page_table, same_page_vertical_table, same_page_new_column, same_page_horizontal_table])

                if prev_block is not None and merge_condition:
                    if prev_block not in table_run:
                        table_run.append(prev_block)
                    table_run.append(block)
                else:
                    if table_run:
                        table_runs.append(table_run)
                    table_run = []
                prev_block = block
            prev_page_block_count = len(page_blocks)

        if table_run:
            table_runs.append(table_run)

        try:
            with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
                futures = [
                    executor.submit(self.process_rewriting, document, blocks)
                    for blocks in table_runs
                ]
                for future in as_completed(futures):
                    future.result()  # Raise exceptions if any occurred
                    pbar.update(1)
        finally:
            pbar.close()

    def process_rewriting(self, document: Document, blocks: List[Block]):
        if len(blocks) < 2:
            # Can't merge single tables
            return

        start_block = blocks[0]
        for i in range(1, len(blocks)):
            curr_block = blocks[i]
            
            # KNOWLEDGE-FIRST: Check historical merge patterns
            merge_knowledge = asyncio.run(self._check_table_merge_knowledge(
                start_block, curr_block, document
            ))
            
            # If we have high confidence knowledge, use it
            if merge_knowledge and merge_knowledge.get('confidence_score', 0) > 0.85:
                logger.info(f"🧠 Using knowledge-based merge decision: {merge_knowledge['recommended_action']}")
                
                if merge_knowledge['recommended_action'] == 'merge':
                    direction = merge_knowledge.get('merge_direction', 'bottom')
                    self._apply_knowledge_merge(start_block, curr_block, direction, document)
                    continue
                elif merge_knowledge['recommended_action'] == 'skip':
                    start_block = curr_block
                    continue
            
            # Fall back to LLM analysis if no strong knowledge match
            children = start_block.contained_blocks(document, (BlockTypes.TableCell,))
            children_curr = curr_block.contained_blocks(document, (BlockTypes.TableCell,))
            if not children or not children_curr:
                # Happens if table/form processors didn't run
                break

            start_image = start_block.get_image(document, highres=False)
            curr_image = curr_block.get_image(document, highres=False)
            start_html = json_to_html(start_block.render(document))
            curr_html = json_to_html(curr_block.render(document))

            prompt = self.table_merge_prompt.replace("{{table1}}", start_html).replace("{{table2}}", curr_html)

            response = self.llm_service(
                prompt,
                [start_image, curr_image],
                curr_block,
                MergeSchema,
            )

            if not response or ("direction" not in response or "merge" not in response):
                curr_block.update_metadata(llm_error_count=1)
                break

            merge = response["merge"]

            # The original table is okay
            if "true" not in merge:
                start_block = curr_block
                continue

            # Merge the cells and images of the tables
            direction = response["direction"]
            if not self.validate_merge(children, children_curr, direction):
                start_block = curr_block
                continue

            merged_image = self.join_images(start_image, curr_image, direction)
            merged_cells = self.join_cells(children, children_curr, direction)
            curr_block.structure = []
            start_block.structure = [b.id for b in merged_cells]
            start_block.lowres_image = merged_image
            
            # Record the merge decision for learning
            asyncio.run(self._record_merge_decision(
                start_block, curr_block, direction, document
            ))

    def validate_merge(self, cells1: List[TableCell], cells2: List[TableCell], direction: Literal['right', 'bottom'] = 'right'):
        if direction == "right":
            # Check if the number of rows is the same
            cells1_row_count = self.get_row_count(cells1)
            cells2_row_count = self.get_row_count(cells2)
            return abs(cells1_row_count - cells2_row_count) < 5
        elif direction == "bottom":
            # Check if the number of columns is the same
            cells1_col_count = self.get_column_count(cells1)
            cells2_col_count = self.get_column_count(cells2)
            return abs(cells1_col_count - cells2_col_count) < 2


    def join_cells(self, cells1: List[TableCell], cells2: List[TableCell], direction: Literal['right', 'bottom'] = 'right') -> List[TableCell]:
        if direction == 'right':
            # Shift columns right
            col_count = self.get_column_count(cells1)
            for cell in cells2:
                cell.col_id += col_count
            new_cells = cells1 + cells2
        else:
            # Shift rows up
            row_count = self.get_row_count(cells1)
            for cell in cells2:
                cell.row_id += row_count
            new_cells = cells1 + cells2
        return new_cells

    @staticmethod
    def join_images(image1: Image.Image, image2: Image.Image, direction: Literal['right', 'bottom'] = 'right') -> Image.Image:
        # Get dimensions
        w1, h1 = image1.size
        w2, h2 = image2.size

        if direction == 'right':
            new_height = max(h1, h2)
            new_width = w1 + w2
            new_img = Image.new('RGB', (new_width, new_height), 'white')
            new_img.paste(image1, (0, 0))
            new_img.paste(image2, (w1, 0))
        else:
            new_width = max(w1, w2)
            new_height = h1 + h2
            new_img = Image.new('RGB', (new_width, new_height), 'white')
            new_img.paste(image1, (0, 0))
            new_img.paste(image2, (0, h1))
        return new_img
    
    # Knowledge-first methods required by KnowledgeAwareProcessor
    def process_with_knowledge(self, block, analysis, document):
        """Process block using knowledge analysis - not used in merge processor."""
        pass
    
    async def _check_table_merge_knowledge(self, table1: Block, table2: Block, document: Document):
        """Check knowledge base for similar table merge patterns - REAL ArangoDB queries!"""
        # Extract features from both tables
        features1 = self._extract_features(table1, document)
        features2 = self._extract_features(table2, document)
        
        # Search for similar table merge patterns
        merge_query = f"""
        FOR doc IN pdf_objects
          FILTER doc.object_type == 'table_merge_pattern'
          LET table1_similarity = BM25(doc.table1_text, @table1_text)
          LET table2_similarity = BM25(doc.table2_text, @table2_text)
          LET combined_score = (table1_similarity + table2_similarity) / 2
          FILTER combined_score > 0.3
          SORT combined_score DESC
          LIMIT 5
          RETURN {{
            case_id: doc._key,
            confidence: combined_score,
            merge_data: doc.merge_data,
            table1_text: doc.table1_text,
            table2_text: doc.table2_text,
            match_type: 'bm25'
          }}
        """
        
        result = self._call_arango(
            "query",
            aql=merge_query,
            bind_vars=json.dumps({
                "table1_text": features1.get('text', '')[:200],
                "table2_text": features2.get('text', '')[:200]
            })
        )
        
        if result.get("success") and result.get("results"):
            # Find best match
            matches = result["results"]
            best_match = max(matches, key=lambda m: m.get('confidence', 0))
            
            if best_match['confidence'] > 0.85:
                # Use the historical merge decision
                merge_data = best_match.get('merge_data', {})
                return {
                    'confidence_score': best_match['confidence'],
                    'recommended_action': merge_data.get('action', 'llm_analysis'),
                    'merge_direction': merge_data.get('direction', 'bottom'),
                    'similarity_matches': matches,
                    'source': best_match['match_type']
                }
        
        # No high-confidence match, fall back to LLM
        return {
            'confidence_score': 0.0,
            'recommended_action': 'llm_analysis',
            'similarity_matches': [],
            'source': 'none'
        }
    
    async def _record_merge_decision(self, table1: Block, table2: Block, direction: str, document: Document):
        """Record merge decision for future learning - REAL ArangoDB insert!"""
        import numpy as np
        
        # Extract full context
        features1 = self._extract_features(table1, document)
        features2 = self._extract_features(table2, document)
        
        # Create the merge pattern document
        doc = {
            'object_type': 'table_merge_pattern',
            'table1_text': features1.get('text', '')[:500],
            'table2_text': features2.get('text', '')[:500],
            'table1_bbox': features1.get('bbox', []),
            'table2_bbox': features2.get('bbox', []),
            'merge_data': {
                'action': 'merge',
                'direction': direction
            },
            'timestamp': str(np.datetime64('now')),
            'source': 'llm_decision',
            'confidence': 0.9,  # LLM decisions have high confidence
            'processor': 'LLMTableMergeProcessor',
            'document_path': str(document.filepath) if hasattr(document, 'filepath') else 'unknown'
        }
        
        # Insert into ArangoDB
        insert_result = self._call_arango(
            "insert",
            message=f"Table merge pattern: {direction}",
            level="INFO",
            **doc
        )
        
        if insert_result.get("success"):
            case_id = insert_result.get("_key")
            logger.info(f"📝 Recorded table merge decision to ArangoDB: {case_id}")
        else:
            logger.warning(f"Failed to record merge decision: {insert_result.get('error')}")
        
    def _apply_knowledge_merge(self, start_block: Block, curr_block: Block, direction: str, document: Document):
        """Apply merge based on knowledge recommendation."""
        children = start_block.contained_blocks(document, (BlockTypes.TableCell,))
        children_curr = curr_block.contained_blocks(document, (BlockTypes.TableCell,))
        
        if not children or not children_curr:
            return
            
        # Get images for merging
        start_image = start_block.get_image(document, highres=False)
        curr_image = curr_block.get_image(document, highres=False)
        
        # Perform the merge
        merged_image = self.join_images(start_image, curr_image, direction)
        merged_cells = self.join_cells(children, children_curr, direction)
        curr_block.structure = []
        start_block.structure = [b.id for b in merged_cells]
        start_block.lowres_image = merged_image
        
        logger.success(f"✅ Applied knowledge-based table merge (direction: {direction})")


class MergeSchema(BaseModel):
    table1_description: str
    table2_description: str
    explanation: str
    merge: Literal["true", "false"]
    direction: Literal["bottom", "right"]