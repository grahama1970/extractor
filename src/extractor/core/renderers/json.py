"""
Module: json.py - MODIFIED FROM ORIGINAL MARKER-PDF

CHANGES FROM ORIGINAL MARKER-PDF:
1. Added confidence field to capture Surya layout detection confidence scores
2. Modified renderer to return dict instead of Pydantic model (avoids serialization issues)

External Dependencies:
- pydantic: https://docs.pydantic.dev/
- marker: [Documentation URL]
"""

from typing import Annotated, Any, Dict, List, Tuple

from pydantic import BaseModel

from extractor.core.renderers import BaseRenderer
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block, BlockOutput
from extractor.core.schema.document import Document
from extractor.core.schema.registry import get_block_class


class JSONBlockOutput(BaseModel):
    id: str
    block_type: str
    html: str
    polygon: List[List[float]]
    bbox: List[float]
    children: List["JSONBlockOutput"] | None = None
    section_hierarchy: Dict[str, str] | None = None
    images: dict | None = None

    # Confidence score from Surya layout detection (0.0-1.0)
    confidence: float | None = None

    # Table metadata fields (optional)
    extraction_method: str | None = None
    extraction_details: Dict[str, Any] | None = None
    quality_score: float | None = None
    quality_metrics: Dict[str, float] | None = None
    merge_info: Dict[str, Any] | None = None


class JSONOutput(BaseModel):
    children: List[JSONBlockOutput]
    block_type: str = str(BlockTypes.Document)
    metadata: dict


def reformat_section_hierarchy(section_hierarchy):
    if section_hierarchy is None:
        return None
    new_section_hierarchy = {}
    for key, value in section_hierarchy.items():
        # Convert key to string to avoid unhashable type errors
        str_key = str(key)
        new_section_hierarchy[str_key] = str(value)
    return new_section_hierarchy


class JSONRenderer(BaseRenderer):
    """Renderer that extracts font data properly and returns dict."""

    image_blocks: Annotated[
        Tuple[BlockTypes],
        "The list of block types to consider as images.",
    ] = (BlockTypes.Picture, BlockTypes.Figure)
    page_blocks: Annotated[
        Tuple[BlockTypes],
        "The list of block types to consider as pages.",
    ] = (BlockTypes.Page,)

    def extract_json(self, document: Document, block_output: BlockOutput):
        cls = get_block_class(block_output.id.block_type)

        # Check if this is a leaf block (no children) or a BaseTable
        if cls.__base__ == Block or (
            hasattr(cls.__base__, "__name__") and cls.__base__.__name__ == "BaseTable"
        ):
            html, images = self.extract_block_html(document, block_output)

            # Get the actual block to access metadata
            block = document.get_block(block_output.id)

            # Create JSON output dict directly
            json_output = {
                "html": html,
                "polygon": block_output.polygon.polygon,
                "bbox": block_output.polygon.bbox,
                "id": str(block_output.id),
                "block_type": str(block_output.id.block_type),
                "images": images,
                "section_hierarchy": reformat_section_hierarchy(block_output.section_hierarchy),
                # ADDED: Surya layout detection confidence (0.0-1.0)
                "confidence": block.confidence if block and hasattr(block, "confidence") else None,
                # ADDED: Font data from FontStyleProcessor
                "validation_metadata": (
                    block.validation_metadata
                    if block and hasattr(block, "validation_metadata") and block.validation_metadata
                    else None
                ),
            }

            # Add table metadata if this is a Table block
            if block and block_output.id.block_type == BlockTypes.Table:
                if hasattr(block, "extraction_method"):
                    json_output["extraction_method"] = block.extraction_method
                if hasattr(block, "extraction_details"):
                    json_output["extraction_details"] = block.extraction_details
                if hasattr(block, "quality_score"):
                    json_output["quality_score"] = block.quality_score
                if hasattr(block, "quality_metrics"):
                    json_output["quality_metrics"] = block.quality_metrics
                if hasattr(block, "merge_info"):
                    json_output["merge_info"] = block.merge_info

            return json_output
        else:
            # Handle nested blocks
            children = []
            for child in block_output.children or []:
                child_output = self.extract_json(document, child)
                children.append(child_output)

            # Get the actual block to access confidence
            block = document.get_block(block_output.id)

            return {
                "html": block_output.html,
                "polygon": block_output.polygon.polygon,
                "bbox": block_output.polygon.bbox,
                "id": str(block_output.id),
                "block_type": str(block_output.id.block_type),
                "children": children,
                "section_hierarchy": reformat_section_hierarchy(block_output.section_hierarchy),
                # ADDED: Surya layout detection confidence (0.0-1.0)
                "confidence": block.confidence if block and hasattr(block, "confidence") else None,
                # ADDED: Font data from FontStyleProcessor
                "validation_metadata": (
                    block.validation_metadata
                    if block and hasattr(block, "validation_metadata") and block.validation_metadata
                    else None
                ),
            }

    def __call__(self, document: Document) -> Dict[str, Any]:
        """Return dict instead of Pydantic model for serialization."""
        document_output = document.render()

        json_output = []
        for page_output in document_output.children:
            json_output.append(self.extract_json(document, page_output))

        return {
            "children": json_output,
            "block_type": str(BlockTypes.Document),
            "metadata": self.generate_document_metadata(document, document_output),
        }
