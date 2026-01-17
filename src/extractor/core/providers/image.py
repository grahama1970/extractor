"""
Module: image.py

Image provider with consistent API pattern.
Supports both initialization patterns for backwards compatibility:
  - Standard: ImageProvider().extract_document(filepath)
  - Legacy: ImageProvider(filepath).extract_document()

External Dependencies:
- PIL: https://pillow.readthedocs.io/
"""

from pathlib import Path
from typing import List, Optional, Any, Dict, Union
from PIL import Image

from extractor.core.providers import ProviderPageLines, BaseProvider, ProviderOutput
from extractor.core.providers.fetcher_bridge import ensure_local_source
from extractor.core.schema.polygon import PolygonBox
try:
    from pdftext.schema import Reference  # type: ignore
except Exception:  # pragma: no cover - optional dependency in minimal/offline mode
    class Reference:  # type: ignore
        ...


from extractor.core.schema.unified_document import (
    UnifiedDocument,
    BlockType,
    SourceType,
    ImageBlock,
    BlockMetadata,
    DocumentMetadata,
)


class ImageProvider(BaseProvider):
    """Image provider supporting both standard and legacy initialization patterns."""

    def __init__(self, filepath: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize ImageProvider.

        Args:
            filepath: Optional path to image file. If provided, loads immediately (legacy pattern).
                     If None, filepath must be provided to extract_document() (standard pattern).
            config: Optional configuration dictionary.
        """
        # Store config for later use
        self._config = config
        self._loaded = False
        self._filepath: Optional[str] = None
        self._image: Optional[Image.Image] = None
        self._image_count = 0
        self._page_lines: ProviderPageLines = {}
        self._page_range: List[int] = []
        self._page_bboxes: Dict[int, List[float]] = {}
        self._fetch_download = None

        # If filepath provided, load immediately (legacy pattern)
        if filepath is not None:
            self._load(filepath)
            # Call BaseProvider init with filepath for compatibility
            super().__init__(str(self._filepath), config)
        else:
            # Deferred loading (standard pattern)
            # Don't call BaseProvider.__init__ yet - will call in _load()
            pass

    def _load(self, filepath: Union[str, Path]) -> None:
        """Load image file and initialize state."""
        if self._loaded:
            return

        resolved_path, fetch_download = ensure_local_source(str(filepath))
        self._filepath = str(resolved_path)
        self._fetch_download = fetch_download

        # Open image and detect if it's multi-page (TIFF, GIF, etc.)
        self._image = Image.open(str(resolved_path))
        self._image_count = getattr(self._image, "n_frames", 1)
        self._page_lines = {i: [] for i in range(self._image_count)}
        self._page_range = list(range(self._image_count))

        # Calculate bboxes for each frame/page
        self._page_bboxes = {}
        for i in self._page_range:
            if self._image_count > 1:
                self._image.seek(i)
            self._page_bboxes[i] = [0.0, 0.0, float(self._image.size[0]), float(self._image.size[1])]

        self._loaded = True

    def extract_document(self, filepath: Optional[Union[str, Path]] = None) -> UnifiedDocument:
        """Extract image content to a UnifiedDocument.

        Args:
            filepath: Path to image file. Required if not provided in __init__.

        Returns:
            UnifiedDocument with image blocks.
        """
        # Handle standard pattern: filepath in extract_document
        if not self._loaded:
            if filepath is None:
                raise ValueError("filepath must be provided either in __init__ or extract_document()")
            self._load(filepath)

        blocks = []
        for i in range(self._image_count):
            blocks.append(ImageBlock(
                id=f"img_{i}",
                content="",  # Image content is binary, stored via src
                src=str(self._filepath),
                metadata=BlockMetadata(page_number=i + 1)
            ))

        return UnifiedDocument(
            id=Path(self._filepath).stem,
            source_type=SourceType.IMAGE,
            blocks=blocks,
            metadata=DocumentMetadata(title=Path(self._filepath).stem)
        )

    # Properties for backwards compatibility
    @property
    def filepath(self) -> Optional[str]:
        return self._filepath

    @property
    def image(self) -> Optional[Image.Image]:
        return self._image

    @property
    def image_count(self) -> int:
        return self._image_count

    @property
    def page_lines(self) -> ProviderPageLines:
        return self._page_lines

    @property
    def page_range(self) -> List[int]:
        return self._page_range

    @property
    def fetch_download(self):
        return self._fetch_download

    def __len__(self):
        return self._image_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._image is not None:
            self._image.close()

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        if not self._loaded:
            raise RuntimeError("Image not loaded. Call extract_document() first or provide filepath in __init__.")
        images = []
        for i in idxs:
            if self._image_count > 1:
                self._image.seek(i)
            # Create a copy to avoid issues with the original image
            img_copy = self._image.copy()
            images.append(img_copy)
        return images

    def get_page_bbox(self, idx: int) -> Optional[PolygonBox]:
        if not self._loaded:
            return None
        bbox = self._page_bboxes.get(idx)
        if bbox:
            return PolygonBox.from_bbox(bbox)
        return None

    def get_page_lines(self, idx: int) -> List[ProviderOutput]:
        """Image provider does not support text extraction"""
        return self._page_lines.get(idx, [])

    def get_page_refs(self, idx: int) -> List[Reference]:
        return []
