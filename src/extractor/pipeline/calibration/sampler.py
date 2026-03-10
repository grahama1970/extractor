"""Smart page sampling for calibration.

Selects representative pages from large PDFs for efficient human review:
- First and last pages (boundary conditions)
- Pages with detected tables (important elements)
- Pages with detected figures/images
- Random middle pages for coverage
"""

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF (optional — regression testing only)
except ImportError:
    fitz = None  # type: ignore[assignment]


@dataclass
class PageInfo:
    """Information about a sampled page."""

    page_num: int
    reason: str
    has_tables: bool = False
    has_figures: bool = False
    has_headers: bool = False
    text_length: int = 0


@dataclass
class SamplerConfig:
    """Configuration for page sampling."""

    min_pages: int = 10
    max_pages: int = 15
    include_first: bool = True
    include_last: bool = True
    prioritize_tables: bool = True
    prioritize_figures: bool = True
    random_seed: int | None = None


@dataclass
class SampleResult:
    """Result of page sampling."""

    pages: list[PageInfo] = field(default_factory=list)
    total_pages: int = 0
    pdf_path: str = ""

    @property
    def page_numbers(self) -> list[int]:
        """Get list of page numbers."""
        return [p.page_num for p in self.pages]


class PageSampler:
    """Smart page sampler for calibration."""

    def __init__(self, config: SamplerConfig | None = None):
        """Initialize sampler with config.

        Args:
            config: Sampling configuration. Uses defaults if not provided.
        """
        self.config = config or SamplerConfig()
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)

    def sample(self, pdf_path: str | Path) -> SampleResult:
        """Sample representative pages from a PDF.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            SampleResult with selected pages and metadata.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        result = SampleResult(total_pages=total_pages, pdf_path=str(pdf_path))

        # Analyze all pages
        page_analysis = self._analyze_pages(doc)

        # Select pages using priority system
        selected = self._select_pages(page_analysis, total_pages)

        result.pages = selected
        doc.close()

        return result

    def _analyze_pages(self, doc: fitz.Document) -> list[dict[str, Any]]:
        """Analyze all pages for content.

        Args:
            doc: PyMuPDF document.

        Returns:
            List of page analysis dictionaries.
        """
        analysis = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Get text blocks
            text_dict = page.get_text("dict")
            blocks = text_dict.get("blocks", [])

            # Analyze content
            has_tables = self._detect_tables(page, blocks)
            has_figures = self._detect_figures(page, blocks)
            has_headers = self._detect_headers(blocks)
            text_length = len(page.get_text())

            analysis.append(
                {
                    "page_num": page_num,
                    "has_tables": has_tables,
                    "has_figures": has_figures,
                    "has_headers": has_headers,
                    "text_length": text_length,
                }
            )

        return analysis

    def _detect_tables(self, page: fitz.Page, blocks: list[dict]) -> bool:
        """Detect if page likely contains tables.

        Uses heuristics: grid-like text blocks, tables annotation, etc.
        """
        # Check for table annotations
        for annot in page.annots() or []:
            if "table" in str(annot.info.get("content", "")).lower():
                return True

        # Check for grid-like structure (multiple blocks aligned)
        text_blocks = [b for b in blocks if b.get("type") == 0]  # Text blocks
        if len(text_blocks) >= 4:
            # Check for horizontal alignment (table rows)
            y_positions = [b["bbox"][1] for b in text_blocks]
            y_counts = {}
            for y in y_positions:
                # Round to nearest 5 for grouping
                y_rounded = round(y / 5) * 5
                y_counts[y_rounded] = y_counts.get(y_rounded, 0) + 1
            # If multiple blocks share y position, likely a table row
            if any(count >= 3 for count in y_counts.values()):
                return True

        return False

    def _detect_figures(self, page: fitz.Page, blocks: list[dict]) -> bool:
        """Detect if page contains figures/images."""
        # Check for image blocks
        for block in blocks:
            if block.get("type") == 1:  # Image block
                return True

        # Check for embedded images
        image_list = page.get_images()
        if image_list:
            return True

        return False

    def _detect_headers(self, blocks: list[dict]) -> bool:
        """Detect if page contains section headers."""
        for block in blocks:
            if block.get("type") != 0:  # Not text
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    # Check for header characteristics
                    flags = span.get("flags", 0)
                    size = span.get("size", 0)
                    text = span.get("text", "").strip()

                    # Bold text (flag 16) or large text
                    is_bold = flags & 16
                    is_large = size >= 12

                    # Section number pattern (e.g., "1.2" or "3.1.1")
                    import re

                    has_section_num = bool(re.match(r"^\d+(\.\d+)*\s+", text))

                    if (is_bold or is_large) and has_section_num:
                        return True

        return False

    def _select_pages(self, analysis: list[dict[str, Any]], total_pages: int) -> list[PageInfo]:
        """Select pages based on priority.

        Priority order:
        1. First page (always)
        2. Last page (always)
        3. Pages with tables
        4. Pages with figures
        5. Random middle pages to fill quota
        """
        selected: list[PageInfo] = []
        used_pages: set[int] = set()

        # 1. First page
        if self.config.include_first and total_pages > 0:
            info = analysis[0]
            selected.append(
                PageInfo(
                    page_num=0,
                    reason="first_page",
                    has_tables=info["has_tables"],
                    has_figures=info["has_figures"],
                    has_headers=info["has_headers"],
                    text_length=info["text_length"],
                )
            )
            used_pages.add(0)

        # 2. Last page
        if self.config.include_last and total_pages > 1:
            last_idx = total_pages - 1
            if last_idx not in used_pages:
                info = analysis[last_idx]
                selected.append(
                    PageInfo(
                        page_num=last_idx,
                        reason="last_page",
                        has_tables=info["has_tables"],
                        has_figures=info["has_figures"],
                        has_headers=info["has_headers"],
                        text_length=info["text_length"],
                    )
                )
                used_pages.add(last_idx)

        # 3. Pages with tables
        if self.config.prioritize_tables:
            table_pages = [
                a for a in analysis if a["has_tables"] and a["page_num"] not in used_pages
            ]
            # Take up to 5 table pages, spread across document
            table_pages_to_add = min(5, len(table_pages), self.config.max_pages - len(selected))
            if table_pages_to_add > 0 and table_pages:
                step = max(1, len(table_pages) // table_pages_to_add)
                for i in range(0, len(table_pages), step):
                    if len(selected) >= self.config.max_pages:
                        break
                    if table_pages[i]["page_num"] not in used_pages:
                        info = table_pages[i]
                        selected.append(
                            PageInfo(
                                page_num=info["page_num"],
                                reason="has_tables",
                                has_tables=True,
                                has_figures=info["has_figures"],
                                has_headers=info["has_headers"],
                                text_length=info["text_length"],
                            )
                        )
                        used_pages.add(info["page_num"])

        # 4. Pages with figures
        if self.config.prioritize_figures:
            figure_pages = [
                a for a in analysis if a["has_figures"] and a["page_num"] not in used_pages
            ]
            # Take up to 3 figure pages
            figure_pages_to_add = min(3, len(figure_pages), self.config.max_pages - len(selected))
            if figure_pages_to_add > 0 and figure_pages:
                step = max(1, len(figure_pages) // figure_pages_to_add)
                for i in range(0, len(figure_pages), step):
                    if len(selected) >= self.config.max_pages:
                        break
                    if figure_pages[i]["page_num"] not in used_pages:
                        info = figure_pages[i]
                        selected.append(
                            PageInfo(
                                page_num=info["page_num"],
                                reason="has_figures",
                                has_tables=info["has_tables"],
                                has_figures=True,
                                has_headers=info["has_headers"],
                                text_length=info["text_length"],
                            )
                        )
                        used_pages.add(info["page_num"])

        # 5. Random middle pages to reach minimum
        available_pages = [a for a in analysis if a["page_num"] not in used_pages]

        while len(selected) < self.config.min_pages and available_pages:
            # Pick random page
            idx = random.randint(0, len(available_pages) - 1)
            info = available_pages.pop(idx)
            selected.append(
                PageInfo(
                    page_num=info["page_num"],
                    reason="random_sample",
                    has_tables=info["has_tables"],
                    has_figures=info["has_figures"],
                    has_headers=info["has_headers"],
                    text_length=info["text_length"],
                )
            )
            used_pages.add(info["page_num"])

        # Sort by page number
        selected.sort(key=lambda p: p.page_num)

        return selected


def sample_pages(
    pdf_path: str | Path,
    min_pages: int = 10,
    max_pages: int = 15,
    seed: int | None = None,
) -> SampleResult:
    """Convenience function to sample pages from a PDF.

    Args:
        pdf_path: Path to PDF file.
        min_pages: Minimum pages to sample.
        max_pages: Maximum pages to sample.
        seed: Random seed for reproducibility.

    Returns:
        SampleResult with selected pages.
    """
    config = SamplerConfig(min_pages=min_pages, max_pages=max_pages, random_seed=seed)
    sampler = PageSampler(config)
    return sampler.sample(pdf_path)
