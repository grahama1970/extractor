"""
Module: image.py

External Dependencies:
- PIL: [Documentation URL]
- marker: [Documentation URL]
- pdftext: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from typing import List, Annotated, Optional
from PIL import Image

from extractor.core.providers import ProviderPageLines, BaseProvider
from extractor.core.schema.polygon import PolygonBox
from extractor.core.schema.text import Line
from pdftext.schema import Reference


class ImageProvider(BaseProvider):
    page_range: Annotated[
        Optional[List[int]],
        "The range of pages to process.",
        "Default is None, which will process all pages."
    ] = None

    image_count: int = 1

    def __init__(self, filepath: str, config=None):
        super().__init__(filepath, config)

        self.images = [Image.open(filepath)]
        self.page_lines: ProviderPageLines = {i: [] for i in range(self.image_count)}

        if self.page_range is None:
            self.page_range = range(self.image_count)

        assert max(self.page_range) < self.image_count and min(self.page_range) >= 0, \
            f"Invalid page range, values must be between 0 and {len(self.doc) - 1}.  Min of provided page range is {min(self.page_range)} and max is {max(self.page_range)}."

        self.page_bboxes = {i: [0, 0, self.images[i].size[0], self.images[i].size[1]] for i in self.page_range}

    def __len__(self):
        return self.image_count

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        return [self.images[i] for i in idxs]

    def get_page_bbox(self, idx: int) -> PolygonBox | None:
        bbox = self.page_bboxes[idx]
        if bbox:
            return PolygonBox.from_bbox(bbox)


    def get_page_lines(self, idx: int) -> List[Line]:
        return self.page_lines[idx]

    def get_page_refs(self, idx: int) -> List[Reference]:
        return []