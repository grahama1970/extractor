"""
Module: spreadsheet.py
Purpose: Native spreadsheet extraction without PDF conversion

External Dependencies:
- openpyxl: https://openpyxl.readthedocs.io/  (XLSX/XLS)
- odfpy:      https://pypi.org/project/odfpy/  (ODS)

Example usage
-------------
>>> from extractor.core.providers.spreadsheet import SpreadsheetProvider
>>> doc = NativeSpreadsheetProvider().extract_document("data.xlsx")
>>> print(doc.source_type)   # SourceType.SPREADSHEET
>>> print(len(doc.blocks))   # all tables + images + metadata blocks
"""

import hashlib
import base64
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from openpyxl import load_workbook
from openpyxl.cell import Cell as OpxCell
from odf.table import Table as OdfTable, TableRow, TableCell as OdfCell
from odf.namespaces import OFFICENS
from odf.opendocument import load as odf_load

from loguru import logger

from extractor.core.schema.unified_document import (
    UnifiedDocument, BlockType, SourceType, BaseBlock, TableBlock,
    ImageBlock, BlockMetadata, DocumentMetadata, HierarchyNode, TableCell
)


class SpreadsheetProvider:
    """Direct spreadsheet extraction without PDF conversion."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        filepath = Path(filepath)
        logger.info(f"Extracting spreadsheet: {filepath}")

        suffix = filepath.suffix.lower()

        if suffix in {".xlsx", ".xlsm", ".xls"}:
            blocks, metadata = self._extract_openpyxl(filepath)
        elif suffix == ".ods":
            blocks, metadata = self._extract_ods(filepath)
        else:
            raise ValueError(f"Unsupported spreadsheet format: {suffix}")

        # Build hierarchy: Workbook → Worksheets → Tables
        hierarchy = self._build_hierarchy(blocks)

        doc = UnifiedDocument(
            id=self._generate_doc_id(filepath),
            source_type=SourceType.SPREADSHEET,
            source_path=str(filepath),
            blocks=blocks,
            hierarchy=hierarchy,
            metadata=metadata,
            full_text=self._extract_full_text(blocks),
            keywords=[],
        )

        logger.info(f"Extracted {len(blocks)} blocks from spreadsheet")
        return doc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _generate_doc_id(self, filepath: Path) -> str:
        return hashlib.md5(str(filepath).encode()).hexdigest()

    def _generate_block_id(self) -> str:
        self.block_counter += 1
        return f"xls-block-{self.block_counter}"

    # ------------------------------------------------------------------
    # Excel (openpyxl)
    # ------------------------------------------------------------------
    def _extract_openpyxl(self, filepath: Path) -> tuple[List[BaseBlock], DocumentMetadata]:
        wb = load_workbook(filepath, data_only=False, keep_links=False)
        blocks: List[BaseBlock] = []

        for ws in wb.worksheets:
            table_block = self._openpyxl_sheet_to_table(ws)
            if table_block:
                blocks.append(table_block)

        # Images
        for ws in wb.worksheets:
            for img in ws._images:
                img_bytes = img.ref
                mime, _ = mimetypes.guess_type(img.path)
                b64 = base64.b64encode(img_bytes).decode()
                data_uri = f"data:{mime or 'image/png'};base64,{b64}"
                blocks.append(
                    ImageBlock(
                        id=self._generate_block_id(),
                        type=BlockType.IMAGE,
                        content="",
                        src=data_uri,
                        alt=img.path,
                        metadata=BlockMetadata(
                            attributes={"sheet": ws.title, "embedded": True}, confidence=1.0
                        ),
                    )
                )

        metadata = DocumentMetadata(
            format_metadata={
                "file_type": "xlsx",
                "creator": wb.properties.creator or "",
                "created": wb.properties.created,
                "modified": wb.properties.modified,
                "sheet_names": wb.sheetnames,
                "file_size": filepath.stat().st_size,
            }
        )
        return blocks, metadata

    def _openpyxl_sheet_to_table(self, ws) -> Optional[TableBlock]:
        cells: List[TableCell] = []
        headers: List[int] = []

        max_row = ws.max_row or 0
        max_col = ws.max_column or 0
        if max_row == 0 or max_col == 0:
            return None

        for r_idx, row in enumerate(ws.iter_rows(), start=0):
            for c_idx, cell in enumerate(row, start=0):
                value = self._cell_value(cell)
                rowspan, colspan = 1, 1
                if cell.coordinate in ws.merged_cells:
                    # compute merged bounds
                    rng = next(r for r in ws.merged_cells.ranges if cell.coordinate in r)
                    min_row, min_col, max_row_rng, max_col_rng = rng.bounds
                    rowspan = max_row_rng - min_row + 1
                    colspan = max_col_rng - min_col + 1
                cells.append(
                    TableCell(
                        row=r_idx,
                        col=c_idx,
                        content=value,
                        rowspan=rowspan,
                        colspan=colspan,
                    )
                )
            if r_idx == 0:
                headers.append(r_idx)

        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={},
            rows=max_row,
            cols=max_col,
            cells=cells,
            headers=headers,
            metadata=BlockMetadata(
                attributes={"sheet": ws.title, "source": "openpyxl"}, confidence=1.0
            ),
        )

    def _cell_value(self, cell: OpxCell) -> str:
        return str(cell.value) if cell.value is not None else ""

    # ------------------------------------------------------------------
    # ODS (odfpy)
    # ------------------------------------------------------------------
    def _extract_ods(self, filepath: Path) -> tuple[List[BaseBlock], DocumentMetadata]:
        doc = odf_load(str(filepath))
        blocks: List[BaseBlock] = []

        for table in doc.spreadsheet.getElementsByType(OdfTable):
            table_block = self._ods_sheet_to_table(table)
            if table_block:
                blocks.append(table_block)

        metadata = DocumentMetadata(
            format_metadata={
                "file_type": "ods",
                "sheets": len(doc.spreadsheet.getElementsByType(OdfTable)),
                "file_size": filepath.stat().st_size,
            }
        )
        return blocks, metadata

    def _ods_sheet_to_table(self, table: OdfTable) -> Optional[TableBlock]:
        rows = table.getElementsByType(TableRow)
        cells: List[TableCell] = []
        headers: List[int] = []

        for r_idx, row in enumerate(rows):
            ods_cells = row.getElementsByType(OdfCell)
            for c_idx, cell in enumerate(ods_cells):
                value = str(cell) if cell else ""
                rowspan = int(cell.getAttribute("numberrowsspanned") or 1)
                colspan = int(cell.getAttribute("numbercolumnsspanned") or 1)
                cells.append(
                    TableCell(
                        row=r_idx,
                        col=c_idx,
                        content=value,
                        rowspan=rowspan,
                        colspan=colspan,
                    )
                )
            if r_idx == 0:
                headers.append(r_idx)

        max_row = len(rows)
        max_col = max((c.col + c.colspan - 1 for c in cells), default=0) + 1
        if max_row == 0 or max_col == 0:
            return None

        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={},
            rows=max_row,
            cols=max_col,
            cells=cells,
            headers=headers,
            metadata=BlockMetadata(
                attributes={"sheet": table.getAttribute("name") or "Sheet"}, confidence=1.0
            ),
        )

    # ------------------------------------------------------------------
    # Hierarchy
    # ------------------------------------------------------------------
    def _build_hierarchy(self, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        root = HierarchyNode(id="root", title="Workbook", level=0, block_id="root", children=[])

        # Group by sheet
        sheets: Dict[str, List[BaseBlock]] = {}
        for b in blocks:
            # Add null check for metadata.attributes
            if b.metadata and b.metadata.attributes:
                sheet = b.metadata.attributes.get("sheet", "Sheet1")
            else:
                sheet = "Sheet1"
            sheets.setdefault(sheet, []).append(b)

        for sheet_name, sheet_blocks in sheets.items():
            sheet_node = HierarchyNode(
                id=f"sheet-{sheet_name}",
                title=sheet_name,
                level=1,
                block_id=f"sheet-{sheet_name}",
                parent_id="root",
                breadcrumb=["Workbook", sheet_name],
            )
            root.children.append(sheet_node)

        return root if root.children else None

    def _extract_full_text(self, blocks: List[BaseBlock]) -> str:
        return "\n".join(
            c.content
            for b in blocks
            if b.type == BlockType.TABLE and hasattr(b, "cells")
            for c in b.cells
        )


# ----------------------------------------------------------------------
# Quick self-test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile
    import os

    # Create minimal XLSX
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Demo"
    ws["A1"] = "Name"
    ws["B1"] = "Value"
    ws["A2"] = "Alice"
    ws["B2"] = 42

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        tmp = f.name

    doc = SpreadsheetProvider().extract_document(tmp)
    assert doc.source_type == SourceType.SPREADSHEET
    assert len(doc.blocks) >= 1
    os.unlink(tmp)
    print("✅ Spreadsheet native provider self-test passed")