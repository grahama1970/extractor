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

from typing import List, Optional, Any, Dict
from PIL import Image

from extractor.core.providers import ProviderPageLines, BaseProvider, ProviderOutput
from extractor.core.providers.fetcher_bridge import ensure_local_source
from extractor.core.schema.polygon import PolygonBox
try:
    from pdftext.schema import Reference  # type: ignore
except Exception:  # pragma: no cover - optional dependency in minimal/offline mode
    class Reference:  # type: ignore
        ...


class ImageProvider(BaseProvider):
    def __init__(self, filepath: str, config: Optional[Dict[str, Any]] = None):
        resolved_path, fetch_download = ensure_local_source(filepath)
        super().__init__(str(resolved_path), config)
        self.fetch_download = fetch_download

        # Open image and detect if it's multi-page (TIFF, GIF, etc.)
        self.image = Image.open(str(resolved_path))
        self.image_count = getattr(self.image, "n_frames", 1)
        self.page_lines: ProviderPageLines = {i: [] for i in range(self.image_count)}

        # Convert to list for proper type checking
        self.page_range: List[int] = list(range(self.image_count))

        # Calculate bboxes for each frame/page
        self.page_bboxes: Dict[int, List[float]] = {}
        for i in self.page_range:
            if self.image_count > 1:
                self.image.seek(i)
            self.page_bboxes[i] = [0.0, 0.0, float(self.image.size[0]), float(self.image.size[1])]

    def __len__(self):
        return self.image_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if hasattr(self, "image") and self.image:
            self.image.close()

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        images = []
        for i in idxs:
            if self.image_count > 1:
                self.image.seek(i)
            # Create a copy to avoid issues with the original image
            img_copy = self.image.copy()
            images.append(img_copy)
        return images

    def get_page_bbox(self, idx: int) -> PolygonBox | None:
        bbox = self.page_bboxes.get(idx)
        if bbox:
            return PolygonBox.from_bbox(bbox)
        return None

    def get_page_lines(self, idx: int) -> List[ProviderOutput]:
        """Image provider does not support text extraction"""
        return self.page_lines[idx]

    def get_page_refs(self, idx: int) -> List[Reference]:
        return []
