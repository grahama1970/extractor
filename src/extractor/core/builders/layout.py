"""
Module: layout.py

External Dependencies:
- surya: [Documentation URL]
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from typing import Annotated, List, Optional, Any
import os

try:
    from surya.layout import LayoutPredictor  # type: ignore
    from surya.layout.schema import LayoutResult, LayoutBox  # type: ignore
except Exception:  # pragma: no cover
    LayoutPredictor = Any  # type: ignore
    LayoutResult = Any  # type: ignore
    LayoutBox = Any  # type: ignore
from loguru import logger

from extractor.core.builders import BaseBuilder
from extractor.core.providers.pdf import PdfProvider
from extractor.core.schema import BlockTypes
from extractor.core.schema.document import Document
from extractor.core.schema.groups.page import PageGroup
from extractor.core.schema.polygon import PolygonBox
from extractor.core.schema.registry import get_block_class
from extractor.core.settings import settings


class LayoutBuilder(BaseBuilder):
    """
    A builder for performing layout detection on PDF pages and merging the results into the document.
    """

    layout_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the layout model.",
        "Default is None, which will use the default batch size for the model.",
    ] = None
    force_layout_block: Annotated[
        str,
        "Skip layout and force every page to be treated as a specific block type.",
    ] = None
    disable_tqdm: Annotated[
        bool,
        "Disable tqdm progress bars.",
    ] = False

    def __init__(self, layout_model: Optional[LayoutPredictor] = None, config=None):
        self.layout_model = layout_model

        super().__init__(config)

    def __call__(self, document: Document, provider: PdfProvider):
        if self.force_layout_block is not None:
            # Assign the full content of every page to a single layout type
            layout_results = self.forced_layout(document.pages)
        else:
            if self.layout_model is None:
                # Offline/minimal mode: emit Figure blocks using embedded images from provider
                for p in document.pages:
                    try:
                        p.layout_sliced = False
                    except Exception:
                        pass
                self.add_embedded_images(document.pages, provider)
                return
            else:
                layout_results = self.surya_layout(document.pages)
                if layout_results and all(r is None for r in layout_results):
                    # nothing to add
                    return
                self.add_blocks_to_pages(document.pages, layout_results)

    def get_batch_size(self):
        if self.layout_batch_size is not None:
            return self.layout_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        return 6

    def add_embedded_images(self, pages: List[PageGroup], provider: PdfProvider):
        """
        Emit Figure blocks using embedded image rectangles from the provider.
        Coordinates from provider are already in page space; no rescaling needed.
        """
        for idx, page in enumerate(pages):
            try:
                rects = provider.get_embedded_image_rects(idx)
            except Exception as _e:
                logger.debug(f"get_embedded_image_rects unavailable: {_e}")
                rects = []

            for r in rects:
                # Normalize (x0, y0, x1, y1)
                if hasattr(r, "x0"):
                    bbox = (r.x0, r.y0, r.x1, r.y1)
                elif isinstance(r, (list, tuple)) and len(r) == 4:
                    bbox = (r[0], r[1], r[2], r[3])
                elif isinstance(r, dict) and all(k in r for k in ("x0", "y0", "x1", "y1")):
                    bbox = (r["x0"], r["y0"], r["x1"], r["y1"])
                else:
                    continue

                block_cls = get_block_class(BlockTypes.Figure)
                layout_block = page.add_block(block_cls, PolygonBox.from_bbox(bbox))
                layout_block.top_k = {BlockTypes.Figure: 1.0}
                layout_block.confidence = 0.99
                page.add_structure(layout_block)

            # Ensure non-empty containers
            if page.structure is None:
                page.structure = []
            if page.children is None:
                page.children = []

    def forced_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
        layout_results = []
        for page in pages:
            layout_results.append(
                LayoutResult(
                    image_bbox=page.polygon.bbox,
                    bboxes=[
                        LayoutBox(
                            label=self.force_layout_block,
                            position=0,
                            top_k={self.force_layout_block: 1},
                            polygon=page.polygon.polygon,
                        ),
                    ],
                    sliced=False,
                )
            )
        return layout_results

    def surya_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
        self.layout_model.disable_tqdm = self.disable_tqdm
        layout_results = self.layout_model(
            [p.get_image(highres=False) for p in pages], batch_size=int(self.get_batch_size())
        )
        return layout_results

    def add_blocks_to_pages(self, pages: List[PageGroup], layout_results: List[LayoutResult]):
        for page, layout_result in zip(pages, layout_results):
            layout_page_size = PolygonBox.from_bbox(layout_result.image_bbox).size
            provider_page_size = page.polygon.size
            page.layout_sliced = (
                layout_result.sliced
            )  # This indicates if the page was sliced by the layout model
            # Debug: print all unique labels from Surya
            unique_labels = set(bbox.label for bbox in layout_result.bboxes)
            logger.debug(f"Surya detected labels on page {page.page_id}: {unique_labels}")

            for bbox in sorted(layout_result.bboxes, key=lambda x: x.position):
                # Log SectionHeader detection
                if bbox.label == "SectionHeader":
                    logger.debug(f"Processing SectionHeader at position {bbox.position}")

                # Map label to BlockTypes enum (handle case differences)
                try:
                    block_type = BlockTypes[bbox.label]
                except KeyError:
                    # Handle label mapping issues
                    label_map = {
                        "Section-header": "SectionHeader",
                        "Section header": "SectionHeader",
                        # Add other mappings as needed
                    }
                    mapped_label = label_map.get(bbox.label, bbox.label)
                    try:
                        block_type = BlockTypes[mapped_label]
                    except KeyError:
                        print(f"WARNING: Unknown block type '{bbox.label}', skipping")
                        continue

                block_cls = get_block_class(block_type)
                layout_block = page.add_block(block_cls, PolygonBox(polygon=bbox.polygon))
                layout_block.polygon = layout_block.polygon.rescale(
                    layout_page_size, provider_page_size
                )
                layout_block.top_k = {
                    BlockTypes[label]: prob for (label, prob) in bbox.top_k.items()
                }
                layout_block.confidence = bbox.confidence  # Add the confidence score from Surya
                page.add_structure(layout_block)

            # Ensure page has non-empty structure
            if page.structure is None:
                page.structure = []

            # Ensure page has non-empty children
            if page.children is None:
                page.children = []
