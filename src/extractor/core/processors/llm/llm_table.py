"""
Module: llm_table.py

External Dependencies:
- bs4: [Documentation URL]
- PIL: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from typing import Annotated, List, Tuple, Optional, Dict, Any
import logging
import json
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image
from pydantic import BaseModel
import pandas as pd
from io import StringIO

from extractor.core.processors.llm import BaseLLMComplexBlockProcessor
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block, TableCell, Table
from extractor.core.schema.document import Document
from extractor.core.schema.groups.page import PageGroup
from extractor.core.schema.polygon import PolygonBox

# Import MetadataKey from pipeline_orchestrator
from enum import Enum


async def call_claude_subprocess(
    prompt: str, image_path: Optional[str] = None, timeout: int = 30, use_ultrathink: bool = False
) -> str:
    """
    Call Claude CLI using proper subprocess with correct syntax.

    Args:
        prompt: The prompt to send to Claude
        image_path: Optional path to image file (will be included in prompt)
        timeout: Timeout in seconds
        use_ultrathink: Whether to prefix prompt with 'ultrathink:'

    Returns:
        Claude's response as string
    """
    # Build the full prompt
    full_prompt = prompt
    if image_path and os.path.exists(image_path):
        # Include image path in the prompt for Claude to analyze
        full_prompt = f"Please analyze the image at {image_path}\n\n{prompt}"

    if use_ultrathink:
        full_prompt = f"ultrathink: {full_prompt}"

    # Set up environment with proper PATH
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin:/usr/local/bin:/home/graham/.bun/bin:" + env.get("PATH", "")
    env["BUN_INSTALL"] = "/home/graham/.bun"

    # Use correct claude -p syntax (NOT --print)
    cmd = ["/home/graham/.bun/bin/claude", "-p", "--dangerously-skip-permissions"]

    try:
        # Create subprocess with proper stream handling
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Send prompt and get response
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=full_prompt.encode()), timeout=timeout
        )

        if proc.returncode == 0 and stdout:
            return stdout.decode().strip()
        else:
            error_msg = stderr.decode() if stderr else "No error message"
            logger.error(f"Claude subprocess failed: {error_msg}")
            return ""

    except asyncio.TimeoutError:
        logger.error(f"Claude subprocess timed out after {timeout}s")
        if proc:
            proc.terminate()
            await proc.wait()
        return ""
    except Exception as e:
        logger.error(f"Claude subprocess error: {e}")
        return ""


def call_claude_subprocess_sync(
    prompt: str, image_path: Optional[str] = None, timeout: int = 30, use_ultrathink: bool = False
) -> str:
    """
    Synchronous version of call_claude_subprocess.
    """
    import asyncio

    return asyncio.run(call_claude_subprocess(prompt, image_path, timeout, use_ultrathink))


class MetadataKey(Enum):
    """Defines keys for the 'metadata' dictionary within a block."""

    IS_SUSPICIOUS = "is_suspicious"
    SUSPICIOUS_REASON = "suspicious_reason"
    OVERRIDE_REASON = "override_reason"
    CONFIDENCE = "confidence"
    SOURCE_PROCESSOR = "source_processor"
    OCR_DETECTED_TABLE = "ocr_detected_table"
    MARKER_EXTRACTED = "marker_extracted"
    CAMELOT_EXTRACTED = "camelot_extracted"
    PANDAS_ANALYSIS = "pandas_analysis"
    SIMILAR_ANNOTATIONS = "similar_annotations"


# Set up logger first
logger = logging.getLogger(__name__)

# Try to import Camelot for table extraction fallback
try:
    import camelot

    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    logger.warning("Camelot-py not available. Install with: pip install camelot-py[cv]")


class LLMTableProcessor(BaseLLMComplexBlockProcessor):
    block_types: Annotated[
        Tuple[BlockTypes],
        "The block types to process.",
    ] = (BlockTypes.Table, BlockTypes.TableOfContents)
    max_rows_per_batch: Annotated[
        int,
        "If the table has more rows than this, chunk the table. (LLMs can be inaccurate with a lot of rows)",
    ] = 60
    max_table_rows: Annotated[
        int,
        "The maximum number of rows in a table to process with the LLM processor.  Beyond this will be skipped.",
    ] = 175
    table_image_expansion_ratio: Annotated[
        float,
        "The ratio to expand the image by when cropping.",
    ] = 0
    rotation_max_wh_ratio: Annotated[
        float,
        "The maximum width/height ratio for table cells for a table to be considered rotated.",
    ] = 0.6
    table_rewriting_prompt: Annotated[
        str,
        "The prompt to use for rewriting text.",
        "Default is a string containing the Gemini rewriting prompt.",
    ] = """You are a text correction expert specializing in accurately reproducing tables from images.

You will receive an image and an HTML representation of the table in the image.

**Important Note**: If the initial OCR detection found a table but marker extraction failed or had low confidence, we may have used Camelot extraction with lattice mode (line_width=15) as a fallback. This is particularly useful for tables with clear borders and grid lines.

Your task is to correct any errors in the HTML representation. The HTML should accurately reflect the original table's content and intent, as a human would read it. The table image may be rotated, but ensure the HTML representation is not rotated. Make sure to include HTML for the full table, with appropriate opening and closing table tags.

Some guidelines:
- Reproduce the values from the image as faithfully as possible, while ensuring that the table is easily readable, well-structured, and semantically correct.
- For table header cells (`<th>`) that contain a single word split across multiple lines with a line break (for example, "Description"), join the fragments into a single complete word ("Description"). Only keep `<br>` or `<p>` inside header cells if the lines represent distinct words or concepts, not a single word split due to formatting.
- Fix stray characters, broken formatting, or obvious OCR errors.
- If you see inline math in a table cell, enclose it with the `<math>` tag. For block-level math, use `<math display="block">`.
- Replace any images inside table cells with a text description in the format: "Image: [description]".
- Only use the tags `<table>`, `<tr>`, `<th>`, `<td>`, `<br>`, `<span>`, `<sup>`, `<sub>`, `<i>`, `<b>`, `<math>`, and `<p>`. Only use the attributes `display`, `style`, `colspan`, and `rowspan` if present in the original.
- Ensure that columns and rows match the original table, and that the table remains human-readable and logically organized.
- If the table was extracted using Camelot (check metadata), pay special attention to verifying cell boundaries and merged cells are correctly represented.

Instructions:
1. Carefully examine the provided table image.
2. Analyze the supplied HTML representation.
3. Write a comparison of the table image and the HTML, with particular attention to any multi-line column headers split by a break, ensuring they match the correct column values.
4. If the HTML representation is completely correct, or if you cannot read the image properly, then write "No corrections needed." If the HTML representation has errors, generate only the corrected HTML representation. Output either the corrected HTML or "No corrections needed," but nothing else.

**Input:**
```html
{block_html}
```
"""

    # not going to use
    @staticmethod
    def clean_multiline_headers(html):
        soup = BeautifulSoup(html, "html.parser")
        for th in soup.find_all("th"):
            # Join fragments if the header cell is really a single word split by <br>
            frags = list(th.stripped_strings)
            # If there are no spaces in any fragment, it's likely one word split by <br>
            if len(frags) > 1 and all(" " not in f for f in frags):
                th.string = "".join(frags)
        return str(soup)

    def analyze_table_with_pandas(self, table_html: str) -> Dict[str, Any]:
        """
        Analyze table structure and content using pandas.

        Args:
            table_html: HTML representation of the table

        Returns:
            Dictionary with pandas analysis results
        """
        try:
            # Parse table with pandas
            tables = pd.read_html(StringIO(table_html))
            if not tables:
                return {"error": "No tables found in HTML"}

            df = tables[0]

            analysis = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": {str(col): str(dtype) for col, dtype in df.dtypes.items()},
                "has_headers": not all(isinstance(col, int) for col in df.columns),
                "null_count": df.isnull().sum().to_dict(),
                "numeric_columns": df.select_dtypes(include=["number"]).columns.tolist(),
                "text_columns": df.select_dtypes(include=["object"]).columns.tolist(),
                "sample_data": df.head(3).to_dict("records") if len(df) > 0 else [],
            }

            # Check for potential issues
            issues = []
            if df.shape[0] == 0:
                issues.append("Table has no data rows")
            if df.shape[1] == 0:
                issues.append("Table has no columns")
            if df.isnull().sum().sum() > df.size * 0.5:
                issues.append("Table has >50% null values")

            analysis["potential_issues"] = issues
            analysis["quality_score"] = 1.0 - (len(issues) * 0.25)

            return analysis

        except Exception as e:
            logger.error(f"Pandas analysis failed: {e}")
            return {"error": str(e), "quality_score": 0.0}

    def find_similar_annotations(self, table_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find similar table annotations from previous human corrections.

        Args:
            table_context: Dictionary with table metadata and features

        Returns:
            List of similar annotation rules
        """
        if not ANNOTATION_LEARNER_AVAILABLE:
            logger.warning("AnnotationLearner not available for similarity search")
            return []

        try:
            learner = AnnotationLearner()

            # Try to load learned rules
            rules_path = Path("tmp/learned_extraction_rules.json")
            if rules_path.exists():
                learner.load_rules(str(rules_path))
            else:
                logger.info("No learned rules found")
                return []

            # Find relevant rules based on context
            relevant_rules = []

            for rule in learner.rules:
                relevance_score = 0.0

                # Check rule type relevance
                if rule.rule_type in ["merge_table", "correct_table", "table_structure"]:
                    relevance_score += 0.3

                # Check context similarity
                if rule.context:
                    # Column count similarity
                    if "column_count" in rule.context and "shape" in table_context:
                        expected_cols = rule.context.get("column_count", 0)
                        actual_cols = table_context["shape"][1] if table_context.get("shape") else 0
                        if expected_cols == actual_cols:
                            relevance_score += 0.2

                    # Header pattern similarity
                    if "has_headers" in rule.context and "has_headers" in table_context:
                        if rule.context["has_headers"] == table_context["has_headers"]:
                            relevance_score += 0.1

                    # Quality issues similarity
                    if "quality_issues" in rule.context and "potential_issues" in table_context:
                        common_issues = set(rule.context.get("quality_issues", [])) & set(
                            table_context.get("potential_issues", [])
                        )
                        if common_issues:
                            relevance_score += 0.2 * len(common_issues)

                # Add rule if relevant
                if relevance_score > 0.3:
                    relevant_rules.append(
                        {"rule": rule.to_dict(), "relevance_score": relevance_score}
                    )

            # Sort by relevance
            relevant_rules.sort(key=lambda x: x["relevance_score"], reverse=True)

            # Return top 3 most relevant rules
            return relevant_rules[:3]

        except Exception as e:
            logger.error(f"Failed to find similar annotations: {e}")
            return []

    def extract_table_with_camelot(
        self, document: Document, page: PageGroup, block: Table
    ) -> Optional[List[TableCell]]:
        """
        Extract table using Camelot when OCR detects a table but marker can't find it properly.
        Uses lattice mode with line_width=15 as specified.

        Args:
            document: The document being processed
            page: The page containing the table
            block: The table block detected by OCR

        Returns:
            List of TableCell objects if successful, None otherwise
        """
        if not CAMELOT_AVAILABLE:
            logger.warning("Camelot not available for table extraction fallback")
            return None

        try:
            # Get the PDF file path from document
            pdf_path = getattr(document, "filepath", None)
            if not pdf_path:
                logger.warning("No PDF file path available for Camelot extraction")
                return None

            # Get page number (1-indexed for Camelot)
            page_num = page.page_id + 1

            # Get table bbox in PDF coordinates
            bbox = block.polygon.bbox

            # Extract table using Camelot with lattice mode and line_width=15
            logger.info(
                f"Attempting Camelot extraction for table on page {page_num} with bbox {bbox}"
            )

            # Use table area to focus extraction
            table_area = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

            tables = camelot.read_pdf(
                pdf_path,
                pages=str(page_num),
                flavor="lattice",
                line_scale=15,  # line_width parameter as specified
                table_areas=[table_area],
                strip_text="\n",
            )

            if not tables or len(tables) == 0:
                logger.warning("Camelot found no tables in specified area")
                return None

            # Convert Camelot table to TableCell objects
            camelot_table = tables[0]
            cells = []

            for row_idx, row in enumerate(camelot_table.df.values):
                for col_idx, cell_text in enumerate(row):
                    # Create TableCell with appropriate coordinates
                    cell = TableCell(
                        polygon=PolygonBox.from_bbox([0, 0, 1, 1]),  # Placeholder bbox
                        text=str(cell_text),
                        row_id=row_idx,
                        col_id=col_idx,
                    )
                    cells.append(cell)

            logger.info(f"Camelot extracted {len(cells)} cells from table")
            return cells

        except Exception as e:
            logger.error(f"Camelot extraction failed: {e}")
            return None

    def handle_image_rotation(self, children: List[TableCell], image: Image.Image):
        ratios = [c.polygon.width / c.polygon.height for c in children]
        if len(ratios) < 2:
            return image

        is_rotated = all([r < self.rotation_max_wh_ratio for r in ratios])
        if not is_rotated:
            return image

        first_col_id = min([c.col_id for c in children])
        first_col = [c for c in children if c.col_id == first_col_id]
        first_col_cell = first_col[0]

        last_col_id = max([c.col_id for c in children])
        if last_col_id == first_col_id:
            return image

        last_col_cell = [c for c in children if c.col_id == last_col_id][0]
        cell_diff = first_col_cell.polygon.y_start - last_col_cell.polygon.y_start
        if cell_diff == 0:
            return image

        if cell_diff > 0:
            return image.rotate(270, expand=True)
        else:
            return image.rotate(90, expand=True)

    def process_rewriting(self, document: Document, page: PageGroup, block: Table):
        """
        Process table extraction following the complete pipeline:
        1. OCR page (is there a table) - already done by marker
        2. Marker (can I extract an actual table) - check children
        3. If no, use Camelot to try to extract the table/s
        4. Use pandas to analyze the table
        5. Look for similar annotation with feature relevance from ArangoDB
        6. Feed all results to the LLM prompt
        """
        # Initialize metadata
        extraction_metadata = {
            MetadataKey.OCR_DETECTED_TABLE.value: True,  # We're in table processor, so OCR detected it
            MetadataKey.MARKER_EXTRACTED.value: False,
            MetadataKey.CAMELOT_EXTRACTED.value: False,
        }

        # CRITICAL: Check if this is a single sentence that should be text
        # This handles the edge case like "The BHT is never flushed."
        if hasattr(block, "text") and block.text:
            text = block.text.strip()
            # If it's a single sentence ending with punctuation, skip table processing
            if text and text[-1] in ".!?" and "\n" not in text:
                logger.info(f"Skipping table processing for single sentence: '{text}'")
                # Mark it as suspicious so it can be converted to text
                block.setdefault("metadata", {})
                block.metadata[MetadataKey.IS_SUSPICIOUS.value] = True
                block.metadata[MetadataKey.SUSPICIOUS_REASON.value] = (
                    "Single sentence detected - should be text, not table"
                )
                return

        # Step 1 & 2: Check if marker extracted table cells
        children: List[TableCell] = block.contained_blocks(document, (BlockTypes.TableCell,))

        if children and len(children) > 0:
            extraction_metadata[MetadataKey.MARKER_EXTRACTED.value] = True
            logger.info(f"Marker extracted {len(children)} cells")
        else:
            # Step 3: Use Camelot as fallback
            logger.info("No cells extracted by marker, attempting Camelot extraction")
            camelot_cells = self.extract_table_with_camelot(document, page, block)

            if camelot_cells:
                children = camelot_cells
                extraction_metadata[MetadataKey.CAMELOT_EXTRACTED.value] = True
                extraction_metadata[MetadataKey.SOURCE_PROCESSOR.value] = "camelot_lattice_15"
                logger.info(f"Camelot extracted {len(children)} cells")
            else:
                logger.warning("Both marker and Camelot extraction failed, skipping table")
                return

        if not children:
            return

        # Step 4: Analyze table with pandas
        block_html = block.format_cells(document, [], children)
        pandas_analysis = self.analyze_table_with_pandas(block_html)
        extraction_metadata[MetadataKey.PANDAS_ANALYSIS.value] = pandas_analysis

        logger.info(
            f"Pandas analysis - shape: {pandas_analysis.get('shape', 'N/A')}, "
            f"quality: {pandas_analysis.get('quality_score', 0):.2f}"
        )

        # Step 5: Find similar annotations
        table_context = {
            "shape": pandas_analysis.get("shape"),
            "has_headers": pandas_analysis.get("has_headers"),
            "potential_issues": pandas_analysis.get("potential_issues", []),
            "column_count": pandas_analysis.get("shape", [0, 0])[1],
            "row_count": pandas_analysis.get("shape", [0, 0])[0],
            "extraction_method": (
                "camelot" if extraction_metadata[MetadataKey.CAMELOT_EXTRACTED.value] else "marker"
            ),
        }

        similar_annotations = self.find_similar_annotations(table_context)
        if similar_annotations:
            extraction_metadata[MetadataKey.SIMILAR_ANNOTATIONS.value] = similar_annotations
            logger.info(f"Found {len(similar_annotations)} similar annotations")

        # Update block metadata with all extraction info
        block.update_metadata(**extraction_metadata)

        # LLMs don't handle tables with a lot of rows very well
        unique_rows = set([cell.row_id for cell in children])
        row_count = len(unique_rows)
        row_idxs = sorted(list(unique_rows))

        if row_count > self.max_table_rows:
            return

        # Inference by chunk to handle long tables better
        parsed_cells = []
        row_shift = 0
        block_image = self.extract_image(document, block)
        block_rescaled_bbox = block.polygon.rescale(
            page.polygon.size, page.get_image(highres=True).size
        ).bbox
        for i in range(0, row_count, self.max_rows_per_batch):
            batch_row_idxs = row_idxs[i : i + self.max_rows_per_batch]
            batch_cells = [cell for cell in children if cell.row_id in batch_row_idxs]
            batch_cell_bboxes = [
                cell.polygon.rescale(page.polygon.size, page.get_image(highres=True).size).bbox
                for cell in batch_cells
            ]
            # bbox relative to the block
            batch_bbox = [
                min([bbox[0] for bbox in batch_cell_bboxes]) - block_rescaled_bbox[0],
                min([bbox[1] for bbox in batch_cell_bboxes]) - block_rescaled_bbox[1],
                max([bbox[2] for bbox in batch_cell_bboxes]) - block_rescaled_bbox[0],
                max([bbox[3] for bbox in batch_cell_bboxes]) - block_rescaled_bbox[1],
            ]
            if i == 0:
                # Ensure first image starts from the beginning
                batch_bbox[0] = 0
                batch_bbox[1] = 0
            elif i > row_count - self.max_rows_per_batch + 1:
                # Ensure final image grabs the entire height and width
                batch_bbox[2] = block_image.size[0]
                batch_bbox[3] = block_image.size[1]

            batch_image = block_image.crop(batch_bbox)

            block_html = block.format_cells(document, [], batch_cells)

            # add cleaning for table headers that have line breaks
            # block_html = self._clean_multiline_headers(block_html)

            batch_image = self.handle_image_rotation(batch_cells, batch_image)
            batch_parsed_cells = self.rewrite_single_chunk(
                page, block, block_html, batch_cells, batch_image
            )
            if batch_parsed_cells is None:
                return  # Error occurred or no corrections needed

            for cell in batch_parsed_cells:
                cell.row_id += row_shift
                parsed_cells.append(cell)
            row_shift += max([cell.row_id for cell in batch_parsed_cells])

        block.structure = []
        for cell in parsed_cells:
            page.add_full_block(cell)
            block.add_structure(cell)

    def rewrite_single_chunk(
        self,
        page: PageGroup,
        block: Block,
        block_html: str,
        children: List[TableCell],
        image: Image.Image,
    ):
        prompt = self.table_rewriting_prompt.replace("{block_html}", block_html)

        # TODO: Fix async call - for now skip LLM processing
        response = None  # await call_claude_subprocess(prompt)

        if not response or "corrected_html" not in response:
            block.update_metadata(llm_error_count=1)
            # Use the standard metadata dictionary
            block.setdefault("metadata", {})[MetadataKey.IS_SUSPICIOUS] = True
            block.metadata[MetadataKey.SUSPICIOUS_REASON] = "LLM response missing or malformed"
            return

        corrected_html = response["corrected_html"]

        # The original table is okay
        if "no corrections" in corrected_html.lower():
            return

        # --- Centralized Validation and Suspicious Flagging ---
        suspicious_reasons = []

        corrected_html = corrected_html.strip().lstrip("```html").rstrip("```").strip()
        parsed_cells = self.parse_html_table(corrected_html, block, page)

        if len(parsed_cells) <= 1:
            suspicious_reasons.append("Insufficient table cells parsed")

        if not corrected_html.endswith("</table>"):
            suspicious_reasons.append("Incomplete HTML table structure")

        error_indicators = ["error", "failed", "cannot", "unable", "sorry", "invalid"]
        html_lower = corrected_html.lower()
        for indicator in error_indicators:
            if indicator in html_lower and len(corrected_html) < 200:
                suspicious_reasons.append(f"LLM may have returned error: '{indicator}'")

        parsed_cell_text = "".join([cell.text for cell in parsed_cells])
        orig_cell_text = "".join([cell.text for cell in children])
        if len(parsed_cell_text) < len(orig_cell_text) * 0.5:
            suspicious_reasons.append("Significantly reduced table content")

        if suspicious_reasons:
            # Use the standard metadata dictionary
            block.setdefault("metadata", {})[MetadataKey.IS_SUSPICIOUS] = True
            block.metadata[MetadataKey.SUSPICIOUS_REASON] = "; ".join(suspicious_reasons)
            block.update_metadata(llm_error_count=1)
            return

        return parsed_cells

    @staticmethod
    def get_cell_text(element, keep_tags=("br", "i", "b", "span", "math")) -> str:
        for tag in element.find_all(True):
            if tag.name not in keep_tags:
                tag.unwrap()
        return element.decode_contents()

    def parse_html_table(self, html_text: str, block: Block, page: PageGroup) -> List[TableCell]:
        soup = BeautifulSoup(html_text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        # Initialize grid
        rows = table.find_all("tr")
        cells = []

        # Find maximum number of columns in colspan-aware way
        max_cols = 0
        for row in rows:
            row_tds = row.find_all(["td", "th"])
            curr_cols = 0
            for cell in row_tds:
                colspan = int(cell.get("colspan", 1))
                curr_cols += colspan
            if curr_cols > max_cols:
                max_cols = curr_cols

        grid = [[True] * max_cols for _ in range(len(rows))]

        for i, row in enumerate(rows):
            cur_col = 0
            row_cells = row.find_all(["td", "th"])
            for j, cell in enumerate(row_cells):
                while cur_col < max_cols and not grid[i][cur_col]:
                    cur_col += 1

                if cur_col >= max_cols:
                    logger.warning(
                        "Table parsing warning: found more columns in a row than the table's max width."
                    )
                    break

                cell_text = self.get_cell_text(cell).strip()

                # --- SAFE PARSING BLOCK ---
                try:
                    rowspan = min(int(cell.get("rowspan", 1)), len(rows) - i)
                    colspan = min(int(cell.get("colspan", 1)), max_cols - cur_col)
                except (ValueError, TypeError):
                    logger.warning(
                        "Invalid rowspan/colspan value found in LLM output. Defaulting to 1."
                    )
                    rowspan, colspan = 1, 1

                cell_rows = list(range(i, i + rowspan))
                cell_cols = list(range(cur_col, cur_col + colspan))

                if colspan == 0 or rowspan == 0:
                    logger.warning(
                        "Table parsing warning: invalid colspan or rowspan of 0 found. Skipping cell."
                    )
                    continue

                for r in cell_rows:
                    for c in cell_cols:
                        grid[r][c] = False

                cell_bbox = [
                    block.polygon.bbox[0] + cur_col,
                    block.polygon.bbox[1] + i,
                    block.polygon.bbox[0] + cur_col + colspan,
                    block.polygon.bbox[1] + i + rowspan,
                ]
                cell_polygon = PolygonBox.from_bbox(cell_bbox)

                cell_obj = TableCell(
                    text_lines=[cell_text],
                    row_id=i,
                    col_id=cur_col,
                    rowspan=rowspan,
                    colspan=colspan,
                    is_header=cell.name == "th",
                    polygon=cell_polygon,
                    page_id=page.page_id,
                )
                cells.append(cell_obj)
                cur_col += colspan

        return cells


class TableSchema(BaseModel):
    comparison: str
    corrected_html: str
