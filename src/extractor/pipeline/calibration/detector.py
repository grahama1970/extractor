"""Element detection with font/style metadata.

Extracts headers, tables, and figures from PDF pages with rich style information
for pattern learning during calibration.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF (optional — regression testing only)
except ImportError:
    fitz = None  # type: ignore[assignment]


@dataclass
class FontInfo:
    """Font/style information for text elements."""

    name: str = ""
    size: float = 0.0
    color: str = "#000000"
    is_bold: bool = False
    is_italic: bool = False
    flags: int = 0


@dataclass
class DetectedElement:
    """A detected element with style metadata."""

    element_type: str  # "header", "table", "figure", "text"
    bbox: list[float]  # [x0, y0, x1, y1]
    page_num: int
    element_idx: int
    text: str = ""
    font_info: FontInfo | None = None
    confidence: float = 0.5
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectorConfig:
    """Configuration for element detection."""

    detect_headers: bool = True
    detect_tables: bool = True
    detect_figures: bool = True
    min_header_size: float = 11.0
    header_patterns: list[str] = field(
        default_factory=lambda: [
            r"^\d+(\.\d+)*\s+[A-Z]",  # Section numbers: 1.2.3 Title
            r"^[A-Z][A-Z\s]+$",  # ALL CAPS
            r"^Chapter\s+\d+",  # Chapter N
            r"^Section\s+\d+",  # Section N
        ]
    )
    disabled_types: set[str] = field(default_factory=set)


class ElementDetector:
    """Detect elements with style metadata from PDF pages."""

    def __init__(self, config: DetectorConfig | None = None):
        """Initialize detector with config.

        Args:
            config: Detection configuration. Uses defaults if not provided.
        """
        self.config = config or DetectorConfig()
        self._compiled_patterns = [re.compile(p) for p in self.config.header_patterns]

    def detect_page(self, page: fitz.Page, page_num: int) -> list[DetectedElement]:
        """Detect all elements on a page.

        Args:
            page: PyMuPDF page object.
            page_num: Page number in document.

        Returns:
            List of detected elements with metadata.
        """
        elements: list[DetectedElement] = []
        element_idx = 0

        # Get text blocks with style info
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])

        # Detect headers
        if self.config.detect_headers and "header" not in self.config.disabled_types:
            headers = self._detect_headers(blocks, page_num, element_idx)
            element_idx += len(headers)
            elements.extend(headers)

        # Detect tables
        if self.config.detect_tables and "table" not in self.config.disabled_types:
            tables = self._detect_tables(page, blocks, page_num, element_idx)
            element_idx += len(tables)
            elements.extend(tables)

        # Detect figures
        if self.config.detect_figures and "figure" not in self.config.disabled_types:
            figures = self._detect_figures(page, blocks, page_num, element_idx)
            elements.extend(figures)

        return elements

    def detect_document(
        self, pdf_path: str | Path, page_numbers: list[int] | None = None
    ) -> dict[int, list[DetectedElement]]:
        """Detect elements in a document.

        Args:
            pdf_path: Path to PDF file.
            page_numbers: Specific pages to analyze. None means all pages.

        Returns:
            Dictionary mapping page numbers to detected elements.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        results: dict[int, list[DetectedElement]] = {}

        pages_to_scan = page_numbers if page_numbers else range(len(doc))

        for page_num in pages_to_scan:
            if page_num < 0 or page_num >= len(doc):
                continue
            page = doc[page_num]
            elements = self.detect_page(page, page_num)
            if elements:
                results[page_num] = elements

        doc.close()
        return results

    def _detect_headers(
        self, blocks: list[dict], page_num: int, start_idx: int
    ) -> list[DetectedElement]:
        """Detect header elements from text blocks."""
        headers: list[DetectedElement] = []
        element_idx = start_idx

        for block in blocks:
            if block.get("type") != 0:  # Not text block
                continue

            for line in block.get("lines", []):
                # Get the dominant span for this line
                spans = line.get("spans", [])
                if not spans:
                    continue

                # Combine spans into line text
                line_text = "".join(s.get("text", "") for s in spans).strip()
                if not line_text:
                    continue

                # Get font info from first span (usually representative)
                span = spans[0]
                font_info = self._extract_font_info(span)

                # Check if this looks like a header
                confidence, reasoning = self._score_header(line_text, font_info)

                if confidence >= 0.5:  # Threshold for detection
                    bbox = list(line["bbox"])
                    headers.append(
                        DetectedElement(
                            element_type="header",
                            bbox=bbox,
                            page_num=page_num,
                            element_idx=element_idx,
                            text=line_text,
                            font_info=font_info,
                            confidence=confidence,
                            reasoning=reasoning,
                        )
                    )
                    element_idx += 1

        return headers

    def _detect_tables(
        self, page: fitz.Page, blocks: list[dict], page_num: int, start_idx: int
    ) -> list[DetectedElement]:
        """Detect table elements using structure analysis."""
        tables: list[DetectedElement] = []
        element_idx = start_idx

        # Method 1: Check for grid-like text block arrangements
        text_blocks = [b for b in blocks if b.get("type") == 0]

        # Group blocks by approximate y position (rows)
        y_groups: dict[int, list[dict]] = {}
        for block in text_blocks:
            y_key = round(block["bbox"][1] / 10) * 10
            if y_key not in y_groups:
                y_groups[y_key] = []
            y_groups[y_key].append(block)

        # Find rows with multiple columns (potential table rows)
        table_rows = [
            (y, blocks) for y, blocks in y_groups.items() if len(blocks) >= 3  # At least 3 columns
        ]

        if len(table_rows) >= 2:  # At least 2 rows
            # Calculate bounding box of table
            all_blocks = [b for _, blocks in table_rows for b in blocks]
            x0 = min(b["bbox"][0] for b in all_blocks)
            y0 = min(b["bbox"][1] for b in all_blocks)
            x1 = max(b["bbox"][2] for b in all_blocks)
            y1 = max(b["bbox"][3] for b in all_blocks)

            # Extract sample text
            sample_text = ""
            for _, row_blocks in sorted(table_rows)[:3]:
                row_text = " | ".join(
                    "".join(
                        s.get("text", "")
                        for line in b.get("lines", [])
                        for s in line.get("spans", [])
                    ).strip()
                    for b in sorted(row_blocks, key=lambda x: x["bbox"][0])
                )
                sample_text += row_text + "\n"

            rows = len(table_rows)
            cols = max(len(blocks) for _, blocks in table_rows)

            tables.append(
                DetectedElement(
                    element_type="table",
                    bbox=[x0, y0, x1, y1],
                    page_num=page_num,
                    element_idx=element_idx,
                    text=sample_text.strip(),
                    confidence=0.7,
                    reasoning=f"Detected grid structure: {rows} rows x {cols} columns",
                    metadata={"rows": rows, "cols": cols, "has_borders": False},
                )
            )
            element_idx += 1

        # Method 2: Check for tables via drawings/lines (bordered tables)
        drawings = page.get_drawings()
        if drawings:
            # Look for rectangular patterns
            rects = [d for d in drawings if d.get("rect")]
            if len(rects) >= 4:  # Multiple rectangles could be table cells
                x0 = min(d["rect"][0] for d in rects)
                y0 = min(d["rect"][1] for d in rects)
                x1 = max(d["rect"][2] for d in rects)
                y1 = max(d["rect"][3] for d in rects)

                # Only add if not overlapping with previous detection
                is_new = True
                for existing in tables:
                    if self._bbox_overlap(existing.bbox, [x0, y0, x1, y1]) > 0.5:
                        is_new = False
                        existing.metadata["has_borders"] = True
                        existing.confidence = 0.85
                        existing.reasoning += " (bordered)"
                        break

                if is_new:
                    tables.append(
                        DetectedElement(
                            element_type="table",
                            bbox=[x0, y0, x1, y1],
                            page_num=page_num,
                            element_idx=element_idx,
                            text="[bordered table]",
                            confidence=0.8,
                            reasoning="Detected bordered table structure",
                            metadata={"has_borders": True},
                        )
                    )

        return tables

    def _detect_figures(
        self, page: fitz.Page, blocks: list[dict], page_num: int, start_idx: int
    ) -> list[DetectedElement]:
        """Detect figure/image elements."""
        figures: list[DetectedElement] = []
        element_idx = start_idx

        # Method 1: Embedded images
        image_list = page.get_images()
        for img_idx, img in enumerate(image_list):
            xref = img[0]
            # Get image bbox
            img_rects = page.get_image_rects(xref)
            for rect in img_rects:
                bbox = list(rect)

                # Look for nearby caption
                caption = self._find_caption(blocks, bbox)

                figures.append(
                    DetectedElement(
                        element_type="figure",
                        bbox=bbox,
                        page_num=page_num,
                        element_idx=element_idx,
                        text=caption or f"[Image {img_idx + 1}]",
                        confidence=0.9,
                        reasoning="Embedded image detected",
                        metadata={"xref": xref, "has_caption": bool(caption)},
                    )
                )
                element_idx += 1

        # Method 2: Image blocks
        for block in blocks:
            if block.get("type") == 1:  # Image block
                bbox = list(block["bbox"])

                # Check if already detected
                is_new = True
                for existing in figures:
                    if self._bbox_overlap(existing.bbox, bbox) > 0.5:
                        is_new = False
                        break

                if is_new:
                    caption = self._find_caption(blocks, bbox)
                    figures.append(
                        DetectedElement(
                            element_type="figure",
                            bbox=bbox,
                            page_num=page_num,
                            element_idx=element_idx,
                            text=caption or "[Image block]",
                            confidence=0.85,
                            reasoning="Image block detected",
                            metadata={"has_caption": bool(caption)},
                        )
                    )
                    element_idx += 1

        return figures

    def _extract_font_info(self, span: dict) -> FontInfo:
        """Extract font information from a text span."""
        flags = span.get("flags", 0)
        color_int = span.get("color", 0)

        # Convert color int to hex
        if isinstance(color_int, int):
            color_hex = f"#{color_int:06x}"
        else:
            color_hex = "#000000"

        return FontInfo(
            name=span.get("font", ""),
            size=span.get("size", 0),
            color=color_hex,
            is_bold=bool(flags & 16),  # Bold flag
            is_italic=bool(flags & 2),  # Italic flag
            flags=flags,
        )

    def _score_header(self, text: str, font_info: FontInfo) -> tuple[float, str]:
        """Score how likely text is a header.

        Returns:
            Tuple of (confidence, reasoning).
        """
        reasons = []
        score = 0.0

        # Check font size
        if font_info.size >= self.config.min_header_size:
            score += 0.3
            reasons.append(f"Large font ({font_info.size:.1f}pt)")

        # Check bold
        if font_info.is_bold:
            score += 0.2
            reasons.append("Bold text")

        # Check patterns
        for pattern in self._compiled_patterns:
            if pattern.match(text):
                score += 0.4
                reasons.append("Matches header pattern")
                break

        # Check all caps (but not too long)
        if text.isupper() and len(text) < 50:
            score += 0.1
            reasons.append("All caps")

        # Penalize very long text (unlikely header)
        if len(text) > 100:
            score -= 0.2
            reasons.append("Too long for header")

        # Penalize if ends with punctuation that's not colon
        if text and text[-1] in ".!?":
            score -= 0.1

        return max(0, min(1, score)), "; ".join(reasons) if reasons else "No header indicators"

    def _find_caption(self, blocks: list[dict], figure_bbox: list[float]) -> str | None:
        """Find caption text near a figure."""
        figure_bottom = figure_bbox[3]

        for block in blocks:
            if block.get("type") != 0:
                continue

            block_top = block["bbox"][1]

            # Check if block is just below figure
            if 0 < block_top - figure_bottom < 30:
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")

                text = text.strip()
                # Check if it looks like a caption
                if re.match(r"^(Figure|Fig\.?|Image|Diagram)\s*\d*", text, re.IGNORECASE):
                    return text

        return None

    def _bbox_overlap(self, bbox1: list[float], bbox2: list[float]) -> float:
        """Calculate overlap ratio between two bboxes."""
        x0 = max(bbox1[0], bbox2[0])
        y0 = max(bbox1[1], bbox2[1])
        x1 = min(bbox1[2], bbox2[2])
        y1 = min(bbox1[3], bbox2[3])

        if x0 >= x1 or y0 >= y1:
            return 0.0

        intersection = (x1 - x0) * (y1 - y0)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])

        if area1 == 0 or area2 == 0:
            return 0.0

        return intersection / min(area1, area2)


def detect_elements(
    pdf_path: str | Path,
    page_numbers: list[int] | None = None,
    disabled_types: set[str] | None = None,
) -> dict[int, list[DetectedElement]]:
    """Convenience function to detect elements in a PDF.

    Args:
        pdf_path: Path to PDF file.
        page_numbers: Specific pages to analyze. None means all pages.
        disabled_types: Element types to skip (e.g., {"figure"}).

    Returns:
        Dictionary mapping page numbers to detected elements.
    """
    config = DetectorConfig()
    if disabled_types:
        config.disabled_types = disabled_types
    detector = ElementDetector(config)
    return detector.detect_document(pdf_path, page_numbers)
