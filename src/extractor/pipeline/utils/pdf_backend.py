"""
Unified PDF backend — dispatches to pdf_oxide or PyMuPDF.

Feature flags control which backend handles each operation.
Flip flags one at a time as pdf_oxide gains parity, run smoke tests, then move on.

Usage:
    from extractor.pipeline.utils.pdf_backend import open_pdf, BackendDoc

    with open_pdf("/path/to.pdf") as doc:
        text = doc.extract_text(0)
        spans = doc.extract_spans(0)
        img_bytes = doc.render_page(0, dpi=150)
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

# ---------------------------------------------------------------------------
# Feature flags — set via env or flip here during migration
# Values: "oxide", "pymupdf", "auto" (try oxide, fall back to pymupdf)
# ---------------------------------------------------------------------------
_env = os.environ.get

BACKEND_OPEN = _env("PDF_BACKEND_OPEN", "auto")
BACKEND_TEXT = _env("PDF_BACKEND_TEXT", "auto")
BACKEND_RENDER = _env("PDF_BACKEND_RENDER", "auto")  # oxide has rendering since Phase 1.5
BACKEND_ANNOTATIONS = _env("PDF_BACKEND_ANNOTATIONS", "auto")  # oxide has read + write since Phase 1.6
BACKEND_IMAGES = _env("PDF_BACKEND_IMAGES", "auto")
BACKEND_MANIPULATE = _env("PDF_BACKEND_MANIPULATE", "auto")  # oxide has delete/move/duplicate/merge since Phase 2.3
BACKEND_METADATA = _env("PDF_BACKEND_METADATA", "auto")  # oxide has get_info since Phase 1.8
BACKEND_TABLES = _env("PDF_BACKEND_TABLES", "auto")
BACKEND_SAVE = _env("PDF_BACKEND_SAVE", "auto")
BACKEND_SEARCH = _env("PDF_BACKEND_SEARCH", "auto")

# Shadow mode: run both backends and log divergences >5%
BACKEND_SHADOW = _env("PDF_BACKEND_SHADOW", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Lazy imports — only load what we need
# ---------------------------------------------------------------------------
_fitz = None
_pdf_oxide = None


def _get_fitz():
    """Perform get fitz operation."""
    global _fitz
    if _fitz is None:
        import fitz
        _fitz = fitz
    return _fitz


def _get_oxide():
    """Perform get oxide operation."""
    global _pdf_oxide
    if _pdf_oxide is None:
        import pdf_oxide
        _pdf_oxide = pdf_oxide
    return _pdf_oxide


def _use_oxide(flag: str) -> bool:
    """Decide whether to use oxide for a given feature flag."""
    if flag == "oxide":
        return True
    if flag == "pymupdf":
        return False
    # "auto" — try oxide, catch ImportError
    try:
        _get_oxide()
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
@dataclass
class Rect:
    """Minimal rectangle — compatible with both backends.

    Stores as (x0, y0, x1, y1) like PyMuPDF convention.
    """
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def intersects(self, other: Rect) -> bool:
        return not (self.x1 < other.x0 or other.x1 < self.x0
                    or self.y1 < other.y0 or other.y1 < self.y0)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)

    @classmethod
    def from_fitz(cls, r) -> Rect:
        """From fitz.Rect."""
        return cls(r.x0, r.y0, r.x1, r.y1)

    @classmethod
    def from_oxide_media_box(cls, box: tuple) -> Rect:
        """From pdf_oxide page_media_box (llx, lly, urx, ury)."""
        return cls(box[0], box[1], box[2], box[3])


@dataclass
class Span:
    """Text span with font info — normalized from either backend."""
    text: str
    bbox: Rect
    font_name: str = ""
    font_size: float = 0.0
    is_bold: bool = False
    is_italic: bool = False
    color: int = 0  # RGB packed int


@dataclass
class TextBlock:
    """Block of text — closest to PyMuPDF get_text('dict') block."""
    bbox: Rect
    lines: list[list[Span]] = field(default_factory=list)
    block_type: int = 0  # 0=text, 1=image


@dataclass
class ImageInfo:
    """Extracted image metadata + bytes."""
    width: int
    height: int
    bbox: Optional[Rect] = None
    data: Optional[bytes] = None
    format: str = "png"


@dataclass
class Annotation:
    """Normalized annotation."""
    subtype: str
    rect: Rect
    contents: str = ""
    author: str = ""
    color: Optional[tuple] = None


@dataclass
class TableResult:
    """Extracted table."""
    bbox: Rect
    rows: list[list[str]] = field(default_factory=list)
    col_count: int = 0
    row_count: int = 0


# ---------------------------------------------------------------------------
# Unified document wrapper
# ---------------------------------------------------------------------------
class BackendDoc:
    """Unified PDF document — wraps either backend transparently."""

    def __init__(self, path: str | Path, *, prefer_oxide: bool = True):
        """Perform init operation."""
        self._path = str(path)
        self._fitz_doc = None
        self._oxide_doc = None

        # Open with preferred backend
        if prefer_oxide and _use_oxide(BACKEND_OPEN):
            try:
                self._oxide_doc = _get_oxide().PdfDocument(self._path)
            except Exception:
                self._fitz_doc = _get_fitz().open(self._path)
        else:
            self._fitz_doc = _get_fitz().open(self._path)

    @classmethod
    def from_bytes(cls, data: bytes, *, prefer_oxide: bool = True) -> "BackendDoc":
        """Create a BackendDoc from raw PDF bytes (Phase 1.2)."""
        doc = cls.__new__(cls)
        doc._path = ""
        doc._fitz_doc = None
        doc._oxide_doc = None

        if prefer_oxide and _use_oxide(BACKEND_OPEN):
            try:
                doc._oxide_doc = _get_oxide().PdfDocument.from_bytes(data)
                return doc
            except Exception:
                pass
        doc._fitz_doc = _get_fitz().open(stream=data, filetype="pdf")
        return doc

    @property
    def is_encrypted(self) -> bool:
        """Check if the document is encrypted (Phase 1.3)."""
        if self._oxide_doc:
            try:
                return self._oxide_doc.is_encrypted
            except Exception:
                pass
        if self._fitz_doc:
            return self._fitz_doc.is_encrypted
        return False

    def close(self):
        """Perform close operation."""
        if self._fitz_doc:
            self._fitz_doc.close()
            self._fitz_doc = None
        self._oxide_doc = None

    def __enter__(self):
        """Perform enter operation."""
        return self

    def __exit__(self, *args):
        """Perform exit operation."""
        self.close()

    # -- Properties --

    @property
    def page_count(self) -> int:
        """Perform page count operation."""
        if self._oxide_doc:
            return self._oxide_doc.page_count()
        return self._ensure_fitz().page_count

    def page_rect(self, page_num: int) -> Rect:
        """Perform page rect operation."""
        if self._oxide_doc:
            box = self._oxide_doc.page_media_box(page_num)
            return Rect.from_oxide_media_box(box)
        page = self._ensure_fitz()[page_num]
        return Rect.from_fitz(page.rect)

    # -- Text extraction --

    def extract_text(self, page_num: int) -> str:
        """Plain text extraction."""
        if self._oxide_doc and _use_oxide(BACKEND_TEXT):
            return self._oxide_doc.extract_text(page_num)
        page = self._ensure_fitz()[page_num]
        return page.get_text()

    def extract_spans(self, page_num: int) -> list[Span]:
        """Span-level extraction with font info."""
        if self._oxide_doc and _use_oxide(BACKEND_TEXT):
            raw = self._oxide_doc.extract_spans(page_num)
            return [
                Span(
                    text=s.text,
                    bbox=Rect(s.bbox[0], s.bbox[1], s.bbox[2], s.bbox[3]),
                    font_name=s.font_name,
                    font_size=s.font_size,
                    is_bold=s.is_bold,
                    is_italic=s.is_italic,
                )
                for s in raw
            ]
        # PyMuPDF fallback — extract from dict mode
        page = self._ensure_fitz()[page_num]
        data = page.get_text("dict")
        spans = []
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for s in line.get("spans", []):
                    bbox = s.get("bbox", (0, 0, 0, 0))
                    spans.append(Span(
                        text=s.get("text", ""),
                        bbox=Rect(*bbox),
                        font_name=s.get("font", ""),
                        font_size=s.get("size", 0.0),
                        is_bold="Bold" in s.get("font", ""),
                        is_italic="Italic" in s.get("font", ""),
                        color=s.get("color", 0),
                    ))
        return spans

    def extract_text_dict(self, page_num: int) -> dict:
        """PyMuPDF-compatible get_text('dict') structure.

        Returns nested {blocks: [{lines: [{spans: [...]}]}]} dict.
        Uses oxide's native extract_text_dict() when available (Phase 1.1).
        """
        if self._oxide_doc and _use_oxide(BACKEND_TEXT):
            try:
                return self._oxide_doc.extract_text_dict(page_num)
            except Exception:
                pass  # fall through to fitz
        if self._fitz_doc is None:
            try:
                self._fitz_doc = _get_fitz().open(self._path)
            except ImportError:
                pass
        if self._fitz_doc:
            return self._ensure_fitz()[page_num].get_text("dict")
        raise NotImplementedError(
            "get_text('dict') not available — install PyMuPDF or pdf_oxide"
        )

    def extract_words(self, page_num: int) -> list[dict]:
        """Word-level extraction."""
        if self._oxide_doc and _use_oxide(BACKEND_TEXT):
            raw = self._oxide_doc.extract_words(page_num)
            return [
                {
                    "text": w.text,
                    "bbox": (w.bbox[0], w.bbox[1], w.bbox[2], w.bbox[3]),
                    "font_name": w.font_name,
                    "font_size": w.font_size,
                }
                for w in raw
            ]
        page = self._ensure_fitz()[page_num]
        return [
            {"text": w[4], "bbox": w[:4]}
            for w in page.get_text("words")
        ]

    # -- Rendering --

    def render_page(self, page_num: int, *, dpi: int = 150,
                    fmt: str = "png") -> bytes:
        """Render page to image bytes."""
        if self._oxide_doc and _use_oxide(BACKEND_RENDER):
            try:
                return self._oxide_doc.render_page(page_num, dpi=dpi, format=fmt)
            except Exception:
                pass  # fall through to fitz
        fitz = _get_fitz()
        page = self._ensure_fitz()[page_num]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes(fmt)

    def render_page_clipped(self, page_num: int, clip: Rect, *,
                            dpi: int = 150, fmt: str = "png") -> bytes:
        """Render a clipped region of a page."""
        if self._oxide_doc and _use_oxide(BACKEND_RENDER):
            try:
                return self._oxide_doc.render_page_clipped(
                    page_num,
                    (clip.x0, clip.y0, clip.x1, clip.y1),
                    dpi=dpi, format=fmt,
                )
            except Exception:
                pass  # fall through to fitz
        fitz = _get_fitz()
        page = self._ensure_fitz()[page_num]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        clip_rect = fitz.Rect(clip.x0, clip.y0, clip.x1, clip.y1)
        pix = page.get_pixmap(matrix=mat, clip=clip_rect)
        return pix.tobytes(fmt)

    # -- Annotations --

    def _ensure_fitz(self):
        """Lazy-load fitz doc when oxide can't handle something."""
        if self._fitz_doc is None:
            self._fitz_doc = _get_fitz().open(self._path)
        return self._fitz_doc

    def get_annotations(self, page_num: int) -> list[Annotation]:
        """Read annotations from a page."""
        if self._oxide_doc and _use_oxide(BACKEND_ANNOTATIONS):
            raw = self._oxide_doc.get_annotations(page_num)
            return [
                Annotation(
                    subtype=a.get("subtype", ""),
                    rect=Rect(*a["rect"]) if "rect" in a else Rect(0, 0, 0, 0),
                    contents=a.get("contents", ""),
                    author=a.get("author", ""),
                )
                for a in raw
            ]
        page = self._ensure_fitz()[page_num]
        annots = []
        for annot in page.annots():
            r = annot.rect
            annots.append(Annotation(
                subtype=annot.type[1] if annot.type else "",
                rect=Rect(r.x0, r.y0, r.x1, r.y1),
                contents=annot.info.get("content", ""),
                author=annot.info.get("title", ""),
            ))
        return annots

    # -- Images --

    def extract_images(self, page_num: int) -> list[ImageInfo]:
        """Extract images from a page."""
        if self._oxide_doc and _use_oxide(BACKEND_IMAGES):
            raw = self._oxide_doc.extract_image_bytes(page_num)
            return [
                ImageInfo(
                    width=img.get("width", 0),
                    height=img.get("height", 0),
                    data=img.get("data"),
                    format=img.get("format", "png"),
                )
                for img in raw
            ]
        page = self._ensure_fitz()[page_num]
        images = []
        for img_info in page.get_images():
            xref = img_info[0]
            try:
                pix = _get_fitz().Pixmap(self._fitz_doc, xref)
                images.append(ImageInfo(
                    width=pix.width,
                    height=pix.height,
                    data=pix.tobytes("png"),
                    format="png",
                ))
            except Exception:
                pass
        return images

    # -- Tables --

    def extract_tables(self, page_num: int) -> list[TableResult]:
        """Extract tables from a page."""
        if self._oxide_doc and _use_oxide(BACKEND_TABLES):
            raw = self._oxide_doc.extract_tables(page_num)
            results = []
            for t in raw:
                bbox_raw = t.get("bbox", (0, 0, 0, 0))
                rows = []
                for row in t.get("rows", []):
                    cells = [c.get("text", "") for c in row.get("cells", [])]
                    rows.append(cells)
                results.append(TableResult(
                    bbox=Rect(*bbox_raw),
                    rows=rows,
                    col_count=t.get("col_count", 0),
                    row_count=t.get("row_count", 0),
                ))
            return results
        # PyMuPDF doesn't have native table extraction — return empty
        # (extractor uses camelot for tables, not fitz)
        return []

    # -- Search --

    def search_text(self, pattern: str, *, page_num: Optional[int] = None,
                    max_results: int = 100) -> list[dict]:
        """Search for text pattern."""
        if self._oxide_doc and _use_oxide(BACKEND_SEARCH):
            if page_num is not None:
                return self._oxide_doc.search_page(page_num, pattern,
                                                   max_results=max_results)
            return self._oxide_doc.search(pattern, max_results=max_results)
        # PyMuPDF search
        results = []
        pages = [page_num] if page_num is not None else range(self.page_count)
        for pn in pages:
            page = self._ensure_fitz()[pn]
            for rect in page.search_for(pattern):
                results.append({
                    "page": pn,
                    "x": rect.x0, "y": rect.y0,
                    "width": rect.width, "height": rect.height,
                })
                if len(results) >= max_results:
                    return results
        return results

    # -- Metadata --

    def metadata(self) -> dict:
        """Read document metadata."""
        if self._oxide_doc and _use_oxide(BACKEND_METADATA):
            try:
                info = self._oxide_doc.get_info()
                return dict(info) if info else {}
            except Exception:
                # Fall back to XMP if get_info not available
                try:
                    xmp = self._oxide_doc.xmp_metadata()
                    if xmp:
                        return {
                            "title": xmp.get("dc_title", ""),
                            "author": xmp.get("dc_creator", ""),
                            "subject": xmp.get("dc_description", ""),
                            "keywords": xmp.get("dc_subject", ""),
                            "creator": xmp.get("xmp_creator_tool", ""),
                            "producer": xmp.get("pdf_producer", ""),
                        }
                except Exception:
                    pass
        return self._ensure_fitz().metadata or {}

    # -- Save --

    def save(self, path: str | Path):
        """Save document."""
        if self._oxide_doc and _use_oxide(BACKEND_SAVE):
            # oxide requires page() to be called first to init editor
            self._oxide_doc.page(0)
            self._oxide_doc.save(str(path))
            return
        self._ensure_fitz().save(str(path))

    # -- Merge --

    def merge_from(self, other_path: str | Path):
        """Append pages from another PDF."""
        if self._oxide_doc and _use_oxide(BACKEND_SAVE):
            self._oxide_doc.merge_from(str(other_path))
            return
        other = _get_fitz().open(str(other_path))
        self._ensure_fitz().insert_pdf(other)
        other.close()

    # -- Drawing (Phase 2.1) --

    def draw_rect(self, page_num: int, x: float, y: float,
                  width: float, height: float, *,
                  color: tuple = (0, 0, 0), fill: tuple | None = None,
                  line_width: float = 1.0):
        """Draw a rectangle on a page."""
        if self._oxide_doc and _use_oxide(BACKEND_MANIPULATE):
            self._oxide_doc.draw_rect(page_num, x, y, width, height,
                                       color=color, fill=fill,
                                       line_width=line_width)
            return
        fitz = _get_fitz()
        page = self._ensure_fitz()[page_num]
        shape = page.new_shape()
        r = fitz.Rect(x, y, x + width, y + height)
        shape.draw_rect(r)
        shape.finish(color=color, fill=fill, width=line_width)
        shape.commit()

    def draw_line(self, page_num: int, x1: float, y1: float,
                  x2: float, y2: float, *,
                  color: tuple = (0, 0, 0), line_width: float = 1.0):
        """Draw a line on a page."""
        if self._oxide_doc and _use_oxide(BACKEND_MANIPULATE):
            self._oxide_doc.draw_line(page_num, x1, y1, x2, y2,
                                       color=color, line_width=line_width)
            return
        fitz = _get_fitz()
        page = self._ensure_fitz()[page_num]
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x1, y1), fitz.Point(x2, y2))
        shape.finish(color=color, width=line_width)
        shape.commit()

    def draw_circle(self, page_num: int, cx: float, cy: float,
                    radius: float, *,
                    color: tuple = (0, 0, 0), fill: tuple | None = None,
                    line_width: float = 1.0):
        """Draw a circle on a page."""
        if self._oxide_doc and _use_oxide(BACKEND_MANIPULATE):
            self._oxide_doc.draw_circle(page_num, cx, cy, radius,
                                         color=color, fill=fill,
                                         line_width=line_width)
            return
        fitz = _get_fitz()
        page = self._ensure_fitz()[page_num]
        shape = page.new_shape()
        shape.draw_circle(fitz.Point(cx, cy), radius)
        shape.finish(color=color, fill=fill, width=line_width)
        shape.commit()

    def insert_text(self, page_num: int, x: float, y: float, text: str, *,
                    font_size: float = 12.0, color: tuple = (0, 0, 0)):
        """Insert text at a position on a page."""
        if self._oxide_doc and _use_oxide(BACKEND_MANIPULATE):
            self._oxide_doc.insert_text(page_num, x, y, text,
                                         font_size=font_size, color=color)
            return
        page = self._ensure_fitz()[page_num]
        page.insert_text((x, y), text, fontsize=font_size, color=color)

    def insert_textbox(self, page_num: int, x: float, y: float,
                       width: float, height: float, text: str, *,
                       font_size: float = 12.0, color: tuple = (0, 0, 0)):
        """Insert text in a bounding box with word-wrap."""
        if self._oxide_doc and _use_oxide(BACKEND_MANIPULATE):
            self._oxide_doc.insert_textbox(page_num, x, y, width, height,
                                            text, font_size=font_size,
                                            color=color)
            return
        fitz = _get_fitz()
        page = self._ensure_fitz()[page_num]
        r = fitz.Rect(x, y - height, x + width, y)
        page.insert_textbox(r, text, fontsize=font_size, color=color)

    # -- Rawdict extraction (Phase 2.4) --

    def extract_text_rawdict(self, page_num: int) -> dict:
        """Extract text with per-character bounding boxes.

        Like extract_text_dict() but each span includes a 'chars' key.
        """
        if self._oxide_doc and _use_oxide(BACKEND_TEXT):
            try:
                return self._oxide_doc.extract_text_rawdict(page_num)
            except Exception:
                pass
        return self._ensure_fitz()[page_num].get_text("rawdict")

    # -- Page manipulation (Phase 2.3) --

    def delete_page(self, index: int):
        """Delete a page by index."""
        if self._oxide_doc and _use_oxide(BACKEND_MANIPULATE):
            self._oxide_doc.delete_page(index)
            return
        self._ensure_fitz().delete_page(index)

    def move_page(self, from_idx: int, to_idx: int):
        """Move a page."""
        if self._oxide_doc and _use_oxide(BACKEND_MANIPULATE):
            self._oxide_doc.move_page(from_idx, to_idx)
            return
        self._ensure_fitz().move_page(from_idx, to_idx)

    def duplicate_page(self, index: int) -> int:
        """Duplicate a page, returning the new page index."""
        if self._oxide_doc and _use_oxide(BACKEND_MANIPULATE):
            return self._oxide_doc.duplicate_page(index)
        self._ensure_fitz().copy_page(index)
        return self._ensure_fitz().page_count - 1

    # -- Incremental save (Phase 2.6) --

    def save_incremental(self, path: str | Path):
        """Save as incremental update (preserves encryption, appends changes)."""
        if self._oxide_doc and _use_oxide(BACKEND_SAVE):
            self._oxide_doc.save_incremental(str(path))
            return
        self._ensure_fitz().save(str(path), incremental=True,
                                  encryption=_get_fitz().PDF_ENCRYPT_KEEP)

    # -- Raw backend access (escape hatch for migration) --

    @property
    def fitz_doc(self):
        """Access underlying fitz.Document — for code not yet migrated."""
        if self._fitz_doc is None:
            self._fitz_doc = _get_fitz().open(self._path)
        return self._fitz_doc

    @property
    def oxide_doc(self):
        """Access underlying pdf_oxide.PdfDocument."""
        if self._oxide_doc is None:
            self._oxide_doc = _get_oxide().PdfDocument(self._path)
        return self._oxide_doc


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------
@contextmanager
def open_pdf(path: str | Path, *, prefer_oxide: bool = True) -> Iterator[BackendDoc]:
    """Open a PDF with the unified backend.

    Usage:
        with open_pdf("doc.pdf") as doc:
            text = doc.extract_text(0)
    """
    doc = BackendDoc(path, prefer_oxide=prefer_oxide)
    try:
        yield doc
    finally:
        doc.close()
