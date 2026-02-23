"""
Module: unified_document.py
Purpose: Define unified JSON document schema for all file types

This module defines the universal document structure that all format extractors
must output. This ensures consistent JSON structure regardless of input format
(PDF, HTML, DOCX, PPTX, XLSX, XML, etc.) for seamless ArangoDB integration.

External Dependencies:
- pydantic: https://docs.pydantic.dev/latest/

Example Usage:
>>> from extractor.core.schema.unified_document import UnifiedDocument
>>> doc = UnifiedDocument(
...     source_type="html",
...     metadata={"title": "Sample Document"},
...     blocks=[...],
...     hierarchy={...}
... )
>>> json_output = doc.model_dump_json()
"""

from typing import List, Dict, Any, Optional, Union, Literal
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class BlockType(str, Enum):
    """Enumeration of all possible block types across formats"""

    # Text blocks
    TEXT = "text"
    HEADING = "heading"
    PARAGRAPH = "paragraph"

    # Structural blocks
    TABLE = "table"
    LIST = "list"
    LISTITEM = "listitem"

    # Media blocks
    IMAGE = "image"
    FIGURE = "figure"
    CHART = "chart"

    # Code blocks
    CODE = "code"
    EQUATION = "equation"
    FORMULA = "formula"  # For Excel formulas

    # Form blocks
    FORM = "form"
    FORMFIELD = "formfield"

    # Document-specific blocks
    FOOTNOTE = "footnote"
    PAGEHEADER = "pageheader"
    PAGEFOOTER = "pagefooter"
    TOC = "toc"
    REFERENCE = "reference"

    # Format-specific blocks
    SLIDE = "slide"  # PowerPoint
    SPEAKERNOTES = "speakernotes"  # PowerPoint
    COMMENT = "comment"  # Word/PowerPoint
    REVISION = "revision"  # Word track changes
    ANIMATION = "animation"  # PowerPoint
    WORKSHEET = "worksheet"  # Excel
    CELL = "cell"  # Excel
    PIVOTTABLE = "pivottable"  # Excel

    # HTML-specific
    HTMLELEMENT = "htmlelement"
    STYLE = "style"
    SCRIPT = "script"

    # XML-specific
    XMLELEMENT = "xmlelement"
    CDATA = "cdata"

    # Generic
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    """Enumeration of supported source file types"""

    PDF = "pdf"
    HTML = "html"
    DOCX = "docx"
    DOC = "doc"
    ODT = "odt"
    PPTX = "pptx"
    PPT = "ppt"
    ODP = "odp"
    XLSX = "xlsx"
    XLS = "xls"
    ODS = "ods"
    SPREADSHEET = "spreadsheet"
    XML = "xml"
    EPUB = "epub"
    MD = "markdown"
    RST = "rst"
    TXT = "text"
    JSON = "json"
    IMAGE = "image"
    UNKNOWN = "unknown"


class BlockMetadata(BaseModel):
    """Metadata common to all blocks"""

    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    page_number: Optional[int] = Field(None, description="Page number (if applicable)")
    bbox: Optional[List[float]] = Field(None, description="Bounding box [x0, y0, x1, y1]")
    style: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Style information")
    attributes: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional attributes"
    )
    source_id: Optional[str] = Field(None, description="ID from source format")
    language: Optional[str] = Field(None, description="Detected language code")


class BaseBlock(BaseModel):
    """Base class for all content blocks"""

    # Keep enums accessible via `.value` while JSON dumps stay stringified
    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(..., description="Unique block identifier")
    type: BlockType = Field(..., description="Type of content block")
    content: Union[str, Dict[str, Any], List[Any]] = Field(..., description="Block content")
    metadata: BlockMetadata = Field(default_factory=BlockMetadata)
    parent_id: Optional[str] = Field(None, description="Parent block ID for hierarchy")
    children_ids: List[str] = Field(default_factory=list, description="Child block IDs")


class TableCell(BaseModel):
    """Table cell structure"""

    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    content: str
    style: Optional[Dict[str, Any]] = None


class TableBlock(BaseBlock):
    """Specialized block for tables"""

    type: Literal[BlockType.TABLE] = BlockType.TABLE
    rows: int
    cols: int
    cells: List[TableCell]
    headers: Optional[List[int]] = Field(None, description="Row indices that are headers")


class FormulaBlock(BaseBlock):
    """Specialized block for formulas (Excel, equations)"""

    type: Literal[BlockType.FORMULA] = BlockType.FORMULA
    formula_text: str
    calculated_value: Optional[Any] = None
    cell_reference: Optional[str] = None  # For Excel
    dependencies: Optional[List[str]] = None  # Cell references this formula depends on


class ImageBlock(BaseBlock):
    """Specialized block for images"""

    type: Literal[BlockType.IMAGE] = BlockType.IMAGE
    src: str = Field(..., description="Image source (URL, base64, or file path)")
    alt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None


class FormFieldBlock(BaseBlock):
    """Specialized block for form fields"""

    type: Literal[BlockType.FORMFIELD] = BlockType.FORMFIELD
    field_type: str  # text, checkbox, radio, select, etc.
    name: Optional[str] = None
    value: Optional[Any] = None
    options: Optional[List[str]] = None  # For select/radio fields
    required: bool = False


class HierarchyNode(BaseModel):
    """Node in the document hierarchy tree"""

    id: str
    title: str
    level: int
    block_id: str  # Reference to the actual block
    children: List["HierarchyNode"] = Field(default_factory=list)
    parent_id: Optional[str] = None
    breadcrumb: List[str] = Field(default_factory=list, description="Path from root")


class DocumentMetadata(BaseModel):
    """Document-level metadata"""

    title: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    language: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None

    # Format-specific metadata
    format_metadata: Dict[str, Any] = Field(default_factory=dict)

    # Extraction metadata
    extraction_date: datetime = Field(default_factory=datetime.now)
    extraction_method: str = "marker"
    extraction_version: Optional[str] = None

    # File metadata
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    mime_type: Optional[str] = None


class UnifiedDocument(BaseModel):
    """
    Unified document structure for all file types.
    This is the standard output format for all Marker extractors.
    """

    model_config = ConfigDict(use_enum_values=False, populate_by_name=True)

    # Core fields
    id: str = Field(..., description="Unique document identifier")
    source_type: SourceType = Field(..., description="Original file format")
    source_path: Optional[str] = Field(None, description="Path to source file")

    # Content
    blocks: List[Union[BaseBlock, TableBlock, FormulaBlock, ImageBlock, FormFieldBlock]] = Field(
        default_factory=list, description="All content blocks in document order"
    )

    # Structure
    hierarchy: Optional[HierarchyNode] = Field(
        None, description="Document hierarchy tree (sections, chapters, etc.)"
    )

    # Metadata
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)

    # Relationships
    relationships: List[Dict[str, Any]] = Field(
        default_factory=list, description="Relationships between blocks (references, links, etc.)"
    )

    # Search optimization
    full_text: Optional[str] = Field(None, description="Concatenated text for search")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")

    # ArangoDB compatibility (using alias for underscore fields)
    arango_key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    arango_collection: str = Field(
        "documents", alias="_collection", description="Target ArangoDB collection"
    )

    @classmethod
    def from_artifacts(cls, results_root: Union[str, Path]) -> "UnifiedDocument":
        """
        Reconstruct a UnifiedDocument from pipeline artifact JSONs (S04, S05, S06).

        Args:
            results_root: Path to the pipeline results directory

        Returns:
            UnifiedDocument: The reconstructed document
        """
        results_root = Path(results_root)

        # 1. Load Sections & Blocks (S04)
        sections_path = results_root / "04_section_builder" / "json_output" / "04_sections.json"
        sections_data = {}
        if sections_path.exists():
            with sections_path.open("r", encoding="utf-8") as f:
                import json

                sections_data = json.load(f)

        # 2. Load Tables (S05)
        tables_path = results_root / "05c_table_merger" / "json_output" / "05c_tables.json"
        if not tables_path.exists():
            tables_path = results_root / "05_table_extractor" / "json_output" / "05_tables.json"

        tables_data = {"tables": []}
        if tables_path.exists():
            with tables_path.open("r", encoding="utf-8") as f:
                import json

                tables_data = json.load(f)

        # 3. Load Figures (S06)
        figures_path = results_root / "06b_figure_describer" / "json_output" / "06b_figures.json"
        if not figures_path.exists():
            figures_path = results_root / "06_figure_extractor" / "json_output" / "06_figures.json"

        figures_data = {"figures": []}
        if figures_path.exists():
            with figures_path.open("r", encoding="utf-8") as f:
                import json

                figures_data = json.load(f)

        # --- Assemble blocks ---
        blocks = []

        # Add sections and their blocks in order
        for section in sections_data.get("sections", []):
            for b in section.get("blocks", []):
                metadata = BlockMetadata(
                    page_number=b.get("page"),
                    bbox=b.get("bbox"),
                )
                blocks.append(
                    BaseBlock(
                        id=b.get("id"),
                        type=b.get("block_type", "text"),
                        content=b.get("text", ""),
                        metadata=metadata,
                        parent_id=section.get("id"),
                    )
                )

        # Add Tables
        for t in tables_data.get("tables", []):
            cells = []
            if "cells" in t:
                cells = [TableCell(**c) for c in t["cells"]]

            blocks.append(
                TableBlock(
                    id=t.get("id") or t.get("table_id"),
                    rows=t.get("rows", 0),
                    cols=t.get("cols", 0),
                    cells=cells,
                    headers=t.get("headers"),
                    content=t.get("llm_title") or t.get("title") or "Table",
                    metadata=BlockMetadata(page_number=t.get("page_index", 0), bbox=t.get("bbox")),
                )
            )

        # Add Figures
        for f in figures_data.get("figures", []):
            blocks.append(
                ImageBlock(
                    id=f.get("figure_id") or f.get("id"),
                    src=f.get("image_path", ""),
                    alt=f.get("ai_description") or f.get("llm_description") or f.get("title") or "",
                    content=f.get("llm_title") or f.get("title") or "Figure",
                    metadata=BlockMetadata(page_number=f.get("page", 0), bbox=f.get("bbox")),
                )
            )

        full_text = "\n".join([str(b.content) for b in blocks if isinstance(b.content, str)])

        return cls(
            id=str(results_root.name),
            source_type=SourceType.PDF,
            blocks=blocks,
            metadata=DocumentMetadata(title=str(results_root.stem)),
            full_text=full_text,
        )

    def to_arangodb(self) -> Dict[str, Any]:
        """Convert to ArangoDB-compatible format"""
        # Use by_alias=True to get the underscore fields
        # Use mode='json' to ensure datetime serialization
        data = self.model_dump(by_alias=True, mode="json")
        # The _key field might be missing due to exclude_none behavior
        # Let's explicitly add it if arango_key was set
        if self.arango_key is not None:
            data["_key"] = self.arango_key
        elif "_key" in data and data["_key"] is None:
            # Remove None _key
            data.pop("_key")
        return data

    def ensure_arango_key(self, equivalence_id: str | None = None) -> None:
        """
        Ensure this document has a stable Arango _key.

        If an equivalence_id is provided (e.g., doc_set_id:revision), prefer it;
        otherwise derive a stable key from the internal id.
        """
        if self.arango_key:
            return
        import hashlib

        basis = (equivalence_id or self.id or "document").encode("utf-8")
        self.arango_key = hashlib.sha1(basis).hexdigest()[:40]

    def get_text_content(self) -> str:
        """Extract all text content from blocks"""
        text_parts = []
        for block in self.blocks:
            if hasattr(block, "content") and isinstance(block.content, str):
                text_parts.append(block.content)
        return "\n".join(text_parts)

    def get_blocks_by_type(self, block_type: BlockType) -> List[BaseBlock]:
        """Get all blocks of a specific type"""
        return [b for b in self.blocks if b.type == block_type]

    def build_hierarchy_from_headings(self) -> HierarchyNode:
        """Build hierarchy from heading blocks"""
        # Implementation for auto-generating hierarchy
        # This will be implemented in the hierarchy builder task
        pass


# Model update forward refs to handle recursive HierarchyNode
HierarchyNode.model_rebuild()


def validate_unified_schema(document: Dict[str, Any]) -> bool:
    """
    Validate that a document conforms to the unified schema

    Args:
        document: Dictionary representation of a document

    Returns:
        bool: True if valid, raises exception if invalid
    """
    try:
        UnifiedDocument(**document)
        return True
    except Exception as e:
        raise ValueError(f"Document does not conform to unified schema: {e}")


if __name__ == "__main__":
    # Test the unified schema with sample data
    sample_doc = UnifiedDocument(
        id="test-doc-001",
        source_type=SourceType.HTML,
        blocks=[
            BaseBlock(
                id="block-1",
                type=BlockType.HEADING,
                content="Sample Document",
                metadata=BlockMetadata(confidence=0.95, attributes={"level": 1}),
            ),
            BaseBlock(
                id="block-2",
                type=BlockType.PARAGRAPH,
                content="This is a test paragraph.",
                parent_id="block-1",
            ),
            TableBlock(
                id="block-3",
                type=BlockType.TABLE,
                content={},
                rows=2,
                cols=2,
                cells=[
                    TableCell(row=0, col=0, content="Header 1"),
                    TableCell(row=0, col=1, content="Header 2"),
                    TableCell(row=1, col=0, content="Data 1"),
                    TableCell(row=1, col=1, content="Data 2"),
                ],
            ),
        ],
        metadata=DocumentMetadata(title="Sample Document", author="Test Author", language="en"),
    )

    # Test JSON serialization
    json_output = sample_doc.model_dump_json(indent=2)
    print(" Unified schema validation passed")
    print(f"Sample JSON output:\n{json_output[:500]}...")

    # Test ArangoDB conversion
    arango_doc = sample_doc.to_arangodb()
    assert "_key" not in arango_doc or arango_doc.get("_key") is None
    assert "blocks" in arango_doc
    print(" ArangoDB conversion passed")
