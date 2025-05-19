import csv
import json
import io
from typing import List, Dict, Any

from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockOutput
from marker.schema.blocks.tablecell import TableCell


class BaseTable(Block):
    block_type: BlockTypes | None = None
    html: str | None = None
    include_csv: bool = True
    include_json: bool = True

    @staticmethod
    def build_table_data(document, child_blocks, child_cells: List[TableCell] | None = None):
        """
        Extract the table data into a structured format

        Returns:
            Dict containing:
            - unique_rows: list of row IDs
            - rows: list of lists containing cell data for each row
            - is_header: whether each row contains header cells
            - header_row_idx: index of the first header row (if any)
            - table_data: processed 2D array of cell values
        """
        if child_cells is None:
            child_cells: List[TableCell] = [document.get_block(c.id) for c in child_blocks if c.id.block_type == BlockTypes.TableCell]

        unique_rows = sorted(list(set([c.row_id for c in child_cells])))
        rows = []
        is_header = []

        for row_id in unique_rows:
            row_cells = sorted([c for c in child_cells if c.row_id == row_id], key=lambda x: x.col_id)
            row_data = []
            row_is_header = any(cell.is_header for cell in row_cells)

            for cell in row_cells:
                # Get the text content of the cell
                cell_text = " ".join(cell.text_lines) if hasattr(cell, "text_lines") and cell.text_lines else ""
                row_data.append({
                    "text": cell_text,
                    "colspan": cell.colspan,
                    "rowspan": cell.rowspan,
                    "is_header": cell.is_header,
                    "col_id": cell.col_id,
                    "row_id": cell.row_id
                })

            rows.append(row_data)
            is_header.append(row_is_header)

        # Process the table data into a 2D array for CSV/JSON export
        header_row_idx = is_header.index(True) if True in is_header else None

        # Create a 2D array of cell values
        table_data = []
        for row in rows:
            table_row = []
            for cell in row:
                table_row.append(cell["text"])
            table_data.append(table_row)

        return {
            "unique_rows": unique_rows,
            "rows": rows,
            "is_header": is_header,
            "header_row_idx": header_row_idx,
            "table_data": table_data
        }

    @staticmethod
    def format_cells(document, child_blocks, child_cells: List[TableCell] | None = None):
        if child_cells is None:
            child_cells: List[TableCell] = [document.get_block(c.id) for c in child_blocks if c.id.block_type == BlockTypes.TableCell]

        unique_rows = sorted(list(set([c.row_id for c in child_cells])))
        html_repr = "<table><tbody>"
        for row_id in unique_rows:
            row_cells = sorted([c for c in child_cells if c.row_id == row_id], key=lambda x: x.col_id)
            html_repr += "<tr>"
            for cell in row_cells:
                html_repr += cell.assemble_html(document, child_blocks, None)
            html_repr += "</tr>"
        html_repr += "</tbody></table>"
        return html_repr

    def generate_csv(self, document, child_blocks, child_cells: List[TableCell] | None = None):
        """
        Generate a CSV representation of the table
        """
        table_data = self.build_table_data(document, child_blocks, child_cells)
        output = io.StringIO()
        writer = csv.writer(output)

        for row in table_data["table_data"]:
            writer.writerow(row)

        return output.getvalue()

    def generate_json(self, document, child_blocks, child_cells: List[TableCell] | None = None):
        """
        Generate a JSON representation of the table
        """
        table_data = self.build_table_data(document, child_blocks, child_cells)

        # Create a more structured JSON representation
        json_data = {
            "headers": [],
            "rows": []
        }

        # If we have headers, use them as column names
        if table_data["header_row_idx"] is not None:
            json_data["headers"] = table_data["table_data"][table_data["header_row_idx"]]
            data_rows = [i for i, is_header in enumerate(table_data["is_header"]) if not is_header]

            # Build row data
            for row_idx in data_rows:
                row = table_data["table_data"][row_idx]
                if json_data["headers"]:
                    # Create row with column headers as keys
                    row_obj = {}
                    for col_idx, header in enumerate(json_data["headers"]):
                        if col_idx < len(row):
                            row_obj[header] = row[col_idx]
                    json_data["rows"].append(row_obj)
                else:
                    json_data["rows"].append(row)
        else:
            # No headers, just use raw data
            json_data["rows"] = table_data["table_data"]

        return json.dumps(json_data, ensure_ascii=False, indent=2)

    def assemble_html(self, document, child_blocks: List[BlockOutput], parent_structure=None):
        # Filter out the table cells, so they don't render twice
        child_ref_blocks = [block for block in child_blocks if block.id.block_type == BlockTypes.Reference]
        template = super().assemble_html(document, child_ref_blocks, parent_structure)

        child_block_types = set([c.id.block_type for c in child_blocks])
        html_content = ""

        if self.html:
            # LLM processor
            html_content = self.html
        elif len(child_blocks) > 0 and BlockTypes.TableCell in child_block_types:
            # Table processor
            html_content = self.format_cells(document, child_blocks)

            # Add CSV and JSON representations if enabled
            if self.include_csv:
                csv_content = self.generate_csv(document, child_blocks)
                html_content += f'<div class="table-csv" style="display:none">{csv_content}</div>'

            if self.include_json:
                json_content = self.generate_json(document, child_blocks)
                html_content += f'<div class="table-json" style="display:none">{json_content}</div>'

            return template + html_content
        else:
            # Default text lines and spans
            return f"<p>{template}</p>"

        return template + html_content
