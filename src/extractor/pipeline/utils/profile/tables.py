"""Table region estimation via line drawings for Stage-00 profile detection.

Fast table region estimation using PyMuPDF line drawings.  Scans all pages
for horizontal/vertical line segments that indicate table gridlines.  Groups
them into distinct table regions per page.

Inputs: PDF path
Outputs: Dict with estimated_table_count, table_pages_drawing, density, max
Failure: Returns zero-count dict if fitz unavailable or PDF unreadable
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from loguru import logger

try:
    import fitz
    _HAVE_FITZ = True
except ImportError:
    _HAVE_FITZ = False

# Table region detection thresholds
MIN_TABLE_LINES = 4
LINE_TOLERANCE = 2.0


def _empty_result() -> Dict[str, Any]:
    return {
        "estimated_table_count": 0, "table_pages_drawing": 0,
        "table_density_top10": [], "max_tables_per_page": 0,
    }


def estimate_table_regions(pdf_path: Path) -> Dict[str, Any]:
    """Fast table region estimation using PyMuPDF line drawings.

    O(pages) but very fast (~100ms even for 1000+ page documents)
    because it only reads drawing commands, not text content.

    Returns:
        {
            "estimated_table_count": int,
            "table_pages_drawing": int,
            "table_density_top10": list,
            "max_tables_per_page": int,
        }
    """
    if not _HAVE_FITZ:
        return _empty_result()

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return _empty_result()

    total_regions = 0
    pages_with_tables = 0
    max_per_page = 0
    density: list[tuple[int, int]] = []

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            drawings = page.get_drawings()

            h_lines: list[tuple[float, float, float]] = []
            v_lines: list[tuple[float, float, float]] = []
            for d in drawings:
                for item in d.get("items", []):
                    if item[0] == "l":
                        p1, p2 = item[1], item[2]
                        dx = abs(p1.x - p2.x)
                        dy = abs(p1.y - p2.y)
                        if dy < LINE_TOLERANCE and dx > 10:
                            h_lines.append((min(p1.y, p2.y), min(p1.x, p2.x), max(p1.x, p2.x)))
                        elif dx < LINE_TOLERANCE and dy > 10:
                            v_lines.append((min(p1.x, p2.x), min(p1.y, p2.y), max(p1.y, p2.y)))

            if len(h_lines) < MIN_TABLE_LINES or len(v_lines) < 2:
                continue

            h_widths = [x2 - x1 for _, x1, x2 in h_lines]
            page_width = page.rect.width
            if h_widths and page_width > 0:
                if max(h_widths) < page_width * 0.25:
                    continue

            if h_widths:
                mean_width = sum(h_widths) / len(h_widths)
                if mean_width > 0:
                    std_width = (sum((w - mean_width) ** 2 for w in h_widths) / len(h_widths)) ** 0.5
                    if std_width / mean_width > 0.6:
                        continue

            v_xs = sorted([x for x, _, _ in v_lines])
            if len(v_xs) >= 2:
                x_clusters: list[tuple[float, int]] = []
                for x in v_xs:
                    matched = False
                    for i, (cx, count) in enumerate(x_clusters):
                        if abs(x - cx) < 5.0:
                            x_clusters[i] = ((cx * count + x) / (count + 1), count + 1)
                            matched = True
                            break
                    if not matched:
                        x_clusters.append((x, 1))

                if len(x_clusters) > 20:
                    continue
                if sum(1 for _, count in x_clusters if count >= 2) < 2:
                    continue

            h_ys = sorted(set(round(y, 0) for y, _, _ in h_lines))
            if not h_ys:
                continue

            region_count = 1
            for i in range(1, len(h_ys)):
                if h_ys[i] - h_ys[i - 1] > 30:
                    region_count += 1

            pages_with_tables += 1
            total_regions += region_count
            max_per_page = max(max_per_page, region_count)
            if region_count > 0:
                density.append((page_num, region_count))
    finally:
        doc.close()

    density.sort(key=lambda x: x[1], reverse=True)

    return {
        "estimated_table_count": total_regions,
        "table_pages_drawing": pages_with_tables,
        "table_density_top10": density[:10],
        "max_tables_per_page": max_per_page,
    }
