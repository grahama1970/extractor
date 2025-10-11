"""
Module: __init__.py
Description: Package initialization and exports

External Dependencies:
- PIL: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- pdftext: [Documentation URL]
- marker: [Documentation URL]
- weasyprint: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from functools import lru_cache
from typing import List, Optional, Dict, Any

from PIL import Image
from pydantic import BaseModel

try:
    from pdftext.schema import Reference  # type: ignore
except Exception:  # pragma: no cover - optional dependency in minimal/offline mode
    class Reference:  # type: ignore
        ...

from extractor.core.logger import configure_logging
from extractor.core.schema.polygon import PolygonBox
from extractor.core.schema.text import Span
from extractor.core.schema.text.line import Line
from extractor.core.settings import settings
from extractor.core.util import assign_config

configure_logging()


class Char(BaseModel):
    char: str
    polygon: PolygonBox
    char_idx: int


class ProviderOutput(BaseModel):
    line: Line
    spans: List[Span]
    chars: Optional[List[List[Char]]] = None

    @property
    def raw_text(self):
        return "".join(span.text for span in self.spans)

    def __hash__(self):
        # Include spans text in hash to avoid collision on identical bboxes
        spans_text = "".join(span.text for span in self.spans)
        return hash((tuple(self.line.polygon.bbox), spans_text))

    def merge(self, other: "ProviderOutput"):
        # Use Pydantic's built-in copy method instead of deepcopy
        new_output = self.model_copy(deep=True)
        other_copy = other.model_copy(deep=True)

        new_output.spans.extend(other_copy.spans)
        if new_output.chars is not None and other_copy.chars is not None:
            new_output.chars.extend(other_copy.chars)
        elif other_copy.chars is not None:
            new_output.chars = other_copy.chars

        new_output.line.polygon = new_output.line.polygon.merge([other_copy.line.polygon])
        return new_output


ProviderPageLines = Dict[int, List[ProviderOutput]]


class BaseProvider:
    def __init__(self, filepath: str, config: Optional[BaseModel | Dict[str, Any]] = None):
        assign_config(self, config)
        self.filepath = filepath

    def __len__(self):
        """Return the number of pages/items in this provider.

        Returns:
            int: Number of pages or items

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement __len__")

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        """Get images for the specified page indices at given DPI.

        Args:
            idxs: List of page indices to render
            dpi: DPI for image rendering

        Returns:
            List of PIL Image objects

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_images")

    def get_page_bbox(self, idx: int) -> PolygonBox | None:
        """Get the bounding box for a specific page.

        Args:
            idx: Page index

        Returns:
            PolygonBox or None if page doesn't exist

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_page_bbox")

    def get_page_lines(self, idx: int) -> List["ProviderOutput"]:
        """Get text lines for a specific page.

        Args:
            idx: Page index

        Returns:
            List of ProviderOutput objects

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_page_lines")

    def get_page_refs(self, idx: int) -> List[Reference]:
        """Get references for a specific page.

        Args:
            idx: Page index

        Returns:
            List of Reference objects

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_page_refs")

    def __enter__(self):
        return self

    @staticmethod
    @lru_cache(maxsize=1)
    def get_font_css():
        """Get cached CSS configuration for fonts.

        Returns:
            CSS object for weasyprint

        Raises:
            ValueError: If font settings are not properly configured
        """
        from weasyprint import CSS
        from weasyprint.text.fonts import FontConfiguration

        # Validate font settings
        if not hasattr(settings, "FONT_PATH") or not settings.FONT_PATH:
            raise ValueError("FONT_PATH setting is required but not configured")
        if not hasattr(settings, "FONT_NAME") or not settings.FONT_NAME:
            raise ValueError("FONT_NAME setting is required but not configured")

        font_config = FontConfiguration()
        css = CSS(
            string=f"""
            @font-face {{
                font-family: GoNotoCurrent-Regular;
                src: url({settings.FONT_PATH});
                font-display: swap;
            }}
            body {{
                font-family: {settings.FONT_NAME.split(".")[0]}, sans-serif;
                font-variant-ligatures: none;
                font-feature-settings: "liga" 0;
                text-rendering: optimizeLegibility;
            }}
            """,
            font_config=font_config,
        )
        return css
