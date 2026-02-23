"""
Add a '(Simulated)' hardware-specific requirements section as a new page 3
to a given PDF. The content is tailored to the BHT (Branch History Table)
context present in the CV32A65X document.

Usage (from repo root):
  python scripts/add_simulated_requirements_page.py \
    --input src/extractor/pipeline/poc_simplified/input/BHT_CV32A65X_marked.pdf \
    --output src/extractor/pipeline/poc_simplified/input/BHT_CV32A65X_marked_with_requirements.pdf

Requires: PyMuPDF (pip install pymupdf)
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    import fitz  # PyMuPDF
except Exception as e:  # fail fast with clear guidance
    raise SystemExit(
        "PyMuPDF (package 'pymupdf') is required. Install with: pip install pymupdf\n"
        f"Import error: {e}"
    )


def _rgb_from_int(n: int) -> tuple[float, float, float]:
    r = (n >> 16) & 0xFF
    g = (n >> 8) & 0xFF
    b = n & 0xFF
    return (r / 255.0, g / 255.0, b / 255.0)


def infer_section_header_style(doc: "fitz.Document") -> dict:
    """Infer font name, size, and color from the existing '4.1.5.4 ... BHT' header.
    Fallback to Helvetica 16pt black if not found or not usable.
    """
    style = {"fontname": "Helvetica", "fontsize": 16.0, "color": (0, 0, 0)}
    try:
        for i in range(min(3, doc.page_count)):
            pg = doc.load_page(i)
            d = pg.get_text("dict")
            for block in d.get("blocks", []):
                for line in block.get("lines", []):
                    text_line = "".join(span.get("text", "") for span in line.get("spans", []))
                    if "4.1.5.4" in text_line and "BHT" in text_line:
                        # use the largest span on the line
                        spans = line.get("spans", [])
                        if not spans:
                            continue
                        s = max(spans, key=lambda sp: sp.get("size", 0))
                        fontname = s.get("font", style["fontname"]) or style["fontname"]
                        fontsize = float(s.get("size", style["fontsize"]))
                        color_int = int(s.get("color", 0))
                        color = _rgb_from_int(color_int) if color_int else style["color"]
                        # Prefer the detected font; if it's Arial on a system without it,
                        # Helvetica is the closest base-14 substitute.
                        resolved_font = fontname if fontname else style["fontname"]
                        if resolved_font.lower().startswith("arial"):
                            resolved_font = "Helvetica"
                        return {"fontname": resolved_font, "fontsize": fontsize, "color": color}
    except Exception:
        pass
    return style


def infer_body_text_style(doc: "fitz.Document", header_style: dict) -> dict:
    """Infer predominant body text font/size/color from the first pages.
    Excludes the header style line; chooses the most frequent span style.
    Returns {fontname, fontsize, color, leading} with reasonable fallbacks.
    """
    from collections import Counter

    # fallbacks
    style = {
        "fontname": "Helvetica",
        "fontsize": 10.5,
        "color": (0, 0, 0),
        "leading": 1.28,
    }

    counts = Counter()
    color_map = {}
    for i in range(min(3, doc.page_count)):
        pg = doc.load_page(i)
        dct = pg.get_text("dict")
        for block in dct.get("blocks", []):
            for line in block.get("lines", []):
                text_line = "".join(span.get("text", "") for span in line.get("spans", []))
                # skip header lines similar to the section header
                if (
                    "4.1.5.4" in text_line and "BHT" in text_line
                ) or text_line.strip().lower().startswith("section header"):
                    continue
                for sp in line.get("spans", []):
                    fn = sp.get("font") or style["fontname"]
                    sz = float(sp.get("size") or style["fontsize"])
                    col = sp.get("color")
                    key = (fn, round(sz, 1))
                    counts[key] += 1
                    if key not in color_map and isinstance(col, int):
                        color_map[key] = _rgb_from_int(col)

    if counts:
        (fn, sz), _ = counts.most_common(1)[0]
        fn_low = fn.lower()
        # Map common non-base14 fonts to base-14 substitutes
        if fn_low.startswith("arial") or "calibri" in fn_low or "noto sans" in fn_low:
            mapped = "Helvetica"
        elif "times" in fn_low:
            mapped = "Times-Roman"
        elif "courier" in fn_low or "mono" in fn_low:
            mapped = "Courier"
        else:
            mapped = "Helvetica"
        style["fontname"] = mapped
        style["fontsize"] = float(sz)
        style["color"] = color_map.get((fn, sz), style["color"])

    # crude leading estimate: typical 1.2–1.35; if small sizes, up a bit
    if style["fontsize"] <= 10.0:
        style["leading"] = 1.33
    elif style["fontsize"] >= 11.5:
        style["leading"] = 1.22
    else:
        style["leading"] = 1.28
    return style


def build_requirements_text() -> str:
    # Exact section title as requested, include (Simulated)
    title = "4.1.5.4.1. REQUIREMENTS (Simulated)"

    intro = (
        "This simulated section provides formal, hardware-oriented requirements for the "
        "Branch History Table (BHT) described in Section 4.1.5.4. The BHT uses two-bit "
        "saturating counters indexed by the lower bits of the Virtual PC (VPC), is "
        "updated upon branch resolution in the execute stage, and provides predictions "
        "to the front end."
    )

    # Formal 'shall' requirements; ASCII hyphens to avoid bullet rendering issues
    reqs = [
        "REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i. The width of VPC_i shall match CVA6Cfg.VLEN.",
        "REQ-BHT-2: Each BHT entry shall contain a two-bit saturating counter that encodes taken/not-taken and shall saturate at its limits.",
        "REQ-BHT-3: The BHT shall accept update information from the execute stage (bht_update_i) including the branch PC and resolved outcome, and shall update the corresponding counter accordingly.",
        "REQ-BHT-4: The BHT shall provide a prediction output (bht_prediction_o) aligned with the front-end fetch group width (CVA6Cfg.INSTR_PER_FETCH).",
        "REQ-BHT-5: The BHT shall not be flushed by pipeline events. Only rst_ni shall initialize internal state.",
        "REQ-BHT-6: The subsystem clock clk_i and asynchronous active-low reset rst_ni shall be the only clock/reset inputs required for BHT operation.",
        "REQ-BHT-7: When a branch is pre-decoded by the instr_scan submodule, the BHT shall indicate whether a VPC_i address hits and shall return the taken/not-taken prediction to the front end in the same fetch cycle when available.",
        "REQ-BHT-8: In cv32a65x configuration, flush_bp_i shall be tied to 0. When DebugEn is False, debug_mode_i shall be tied to 0 and shall not appear as an external port.",
        "REQ-BHT-9: All signal widths and types exposed by the BHT interfaces shall be consistent with the configuration package definitions (e.g., CVA6Cfg.VLEN and any package enums used by prediction/update types).",
        "REQ-BHT-10: The prediction datapath shall not introduce structural hazards with instruction fetch; updates from the execute stage shall not stall front-end prediction availability.",
    ]

    # Conditional forms, kept flat for text extraction; use ASCII hyphens
    conditional_blocks = [
        (
            "When bht_update_i.valid is True:",
            [
                "The BHT shall locate the entry indexed by the provided VPC and shall increment or decrement the two-bit counter based on the resolved outcome (taken/not-taken).",
                "The update shall saturate at the counter bounds and shall not invalidate other entries.",
            ],
        ),
        (
            "When a fetch request presents VPC_i:",
            [
                "If the indexed entry exists, the BHT shall return the current prediction in bht_prediction_o aligned to the fetch slot.",
                "If the indexed entry does not exist, the BHT shall return a default not-taken prediction (unless otherwise configured).",
            ],
        ),
        (
            "When rst_ni is asserted low:",
            [
                "The BHT shall initialize internal state without flushing entries during normal operation; only reset causes initialization.",
            ],
        ),
        (
            "When DebugEn is False:",
            [
                "debug_mode_i shall be tied to 0 and shall not be exposed as an active functional input.",
            ],
        ),
    ]

    disclaimer = "Note: This page is simulated test content to validate PDF processing and does not alter the authoritative hardware specification."

    # Build single text block with ASCII hyphens to ensure robust extraction
    # Also include the title at the top of the body so text extractors capture it.
    lines = [title, "", intro, "", "Formal Requirements:"]
    for r in reqs:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("Conditional Requirements:")
    for hdr, items in conditional_blocks:
        lines.append(hdr)
        for it in items:
            lines.append(f"- {it}")
        lines.append("")
    lines.append(disclaimer)
    return "\n".join(lines)


def add_page_3(input_pdf: Path, output_pdf: Path) -> None:
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

    doc = fitz.open(input_pdf.as_posix())
    header_style = infer_section_header_style(doc)
    body_style = infer_body_text_style(doc, header_style)
    try:
        # Insert a new page at index 2 (third page for 0-based indexing)
        new_page = doc.new_page(pno=2, width=612, height=792)  # Letter size

        # Margins and layout
        left, top, right, bottom = 54, 72, 612 - 54, 792 - 72  # 3/4" margins
        title_rect = fitz.Rect(left, top, right, top + 30)
        body_rect = fitz.Rect(left, top + 36, right, bottom)

        text = build_requirements_text()

        # Draw title using inferred header style
        title = text.split("\n", 1)[0]
        new_page.insert_textbox(
            title_rect,
            title,
            fontsize=header_style["fontsize"],
            fontname=header_style["fontname"],
            align=fitz.TEXT_ALIGN_LEFT,
            color=header_style["color"],
        )

        # Draw a thin line under the title
        new_page.draw_line((left, top + 32), (right, top + 32), color=(0, 0, 0), width=0.5)

        # Manual text layout for robust extraction and to avoid overflow issues
        body_text = text.split("\n", 1)[1] if "\n" in text else ""

        def wrap_lines(
            para: str, max_width: float, fontname: str, fontsize: float, indent: float = 0.0
        ) -> list[str]:
            if not para:
                return [""]
            words = para.split(" ")
            lines: list[str] = []
            cur: list[str] = []
            for w in words:
                trial = (" ".join(cur + [w])).strip()
                if not trial:
                    cur.append(w)
                    continue
                width = fitz.get_text_length(trial, fontname=fontname, fontsize=fontsize)
                if width <= max_width:
                    cur.append(w)
                else:
                    if cur:
                        lines.append(" ".join(cur))
                        cur = [w]
                    else:
                        # single very long word: force break
                        lines.append(w)
                        cur = []
            if cur:
                lines.append(" ".join(cur))
            return lines or [""]

        # Determine a font size that fits the available height
        max_width = body_rect.x1 - body_rect.x0
        fontsize = body_style["fontsize"]
        line_leading = body_style["leading"]  # line height multiplier

        paragraphs = body_text.splitlines()

        def count_lines_for_size(size: float) -> int:
            total = 0
            for p in paragraphs:
                total += len(wrap_lines(p, max_width, body_style["fontname"], size, indent=0.0))
            return total

        available_height = body_rect.y1 - body_rect.y0
        # Try sizes 11.0 down to 9.0
        # try around inferred size
        size_candidates = [fontsize, fontsize - 0.5, fontsize + 0.5, fontsize - 1.0]
        for size in [s for s in size_candidates if s > 8.0]:
            lines = count_lines_for_size(size)
            if lines * (size * line_leading) <= available_height:
                fontsize = size
                break

        # Draw lines
        y = body_rect.y0
        for p in paragraphs:
            is_bullet = p.strip().startswith("-")
            indent_x = 14.0 if is_bullet else 0.0
            ptext = p[1:].strip() if is_bullet else p
            wrapped = wrap_lines(
                ptext, max_width - indent_x, body_style["fontname"], fontsize, indent=indent_x
            )
            for line in wrapped:
                if y + fontsize > body_rect.y1:
                    break
                new_page.insert_text(
                    fitz.Point(body_rect.x0 + indent_x, y),
                    line,
                    fontsize=fontsize,
                    fontname=body_style["fontname"],
                    color=body_style["color"],
                )
                y += fontsize * line_leading
            if y + fontsize > body_rect.y1:
                break

        # Append additional simulated section with tables
        add_simulated_tables_section(doc, header_style, body_style)

        # Save as a copy
        doc.save(output_pdf.as_posix())
    finally:
        doc.close()


def add_simulated_tables_section(
    doc: "fitz.Document", header_style: dict, body_style: dict
) -> None:
    """Append a new '(Simulated)' section 4.1.6 including tables that
    demonstrate merge vs. non-merge scenarios. Creates one or more pages at end.
    """
    # Create first page of this section
    page = doc.new_page(width=612, height=792)

    left, top, right, bottom = 54, 72, 612 - 54, 792 - 72
    title_rect = fitz.Rect(left, top, right, top + 30)
    body_rect = fitz.Rect(left, top + 44, right, bottom)

    def draw_title(p: "fitz.Page", text: str):
        p.insert_textbox(
            title_rect,
            text,
            fontsize=header_style["fontsize"],
            fontname=header_style["fontname"],
            align=fitz.TEXT_ALIGN_LEFT,
            color=header_style["color"],
        )
        p.draw_line((left, top + 32), (right, top + 32), color=(0, 0, 0), width=0.5)

    def wrap_lines(para: str, max_width: float, fontname: str, fontsize: float) -> list[str]:
        if not para:
            return [""]
        words = para.split(" ")
        lines: list[str] = []
        cur: list[str] = []
        for w in words:
            trial = (" ".join(cur + [w])).strip()
            if not trial:
                cur.append(w)
                continue
            width = fitz.get_text_length(trial, fontname=fontname, fontsize=fontsize)
            if width <= max_width:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                    cur = [w]
                else:
                    lines.append(w)
                    cur = []
        if cur:
            lines.append(" ".join(cur))
        return lines or [""]

    def draw_paragraph(
        p: "fitz.Page", rect: fitz.Rect, text: str, fontsize: float | None = None
    ) -> float:
        max_width = rect.x1 - rect.x0
        y = rect.y0
        fontsize = fontsize or body_style["fontsize"]
        line_leading = body_style["leading"]
        for para in text.splitlines():
            is_bullet = para.strip().startswith("-")
            indent_x = 14.0 if is_bullet else 0.0
            ptxt = para[1:].strip() if is_bullet else para
            lines = wrap_lines(ptxt, max_width - indent_x, body_style["fontname"], fontsize)
            for line in lines:
                if y + fontsize > rect.y1:
                    return y
                p.insert_text(
                    fitz.Point(rect.x0 + indent_x, y),
                    line,
                    fontsize=fontsize,
                    fontname=body_style["fontname"],
                    color=body_style["color"],
                )
                y += fontsize * line_leading
            y += fontsize * 0.3  # paragraph spacing
        return y

    def draw_table(
        p: "fitz.Page",
        x0: float,
        y0: float,
        col_widths: list[float],
        row_heights: list[float],
        cells: list[list[str]],
        caption: str | None = None,
        fontsize: float | None = None,
    ) -> float:
        y = y0
        fontsize = fontsize or max(9.0, body_style["fontsize"] - 0.5)
        # caption above table
        if caption:
            p.insert_text(
                fitz.Point(x0, y),
                caption,
                fontsize=body_style["fontsize"],
                fontname=body_style["fontname"],
                color=body_style["color"],
            )
            y += 14

        # draw grid
        total_width = sum(col_widths)
        total_height = sum(row_heights)
        # outer border
        p.draw_rect(
            fitz.Rect(x0, y, x0 + total_width, y + total_height), color=(0, 0, 0), width=0.7
        )
        # vertical lines
        cx = x0
        for w in col_widths[:-1]:
            cx += w
            p.draw_line((cx, y), (cx, y + total_height), color=(0, 0, 0), width=0.5)
        # horizontal lines
        cy = y
        for h in row_heights[:-1]:
            cy += h
            p.draw_line((x0, cy), (x0 + total_width, cy), color=(0, 0, 0), width=0.5)

        # cell content
        cy = y
        for r, rh in enumerate(row_heights):
            cx = x0
            for c, cw in enumerate(col_widths):
                if r < len(cells) and c < len(cells[r]):
                    txt = cells[r][c]
                else:
                    txt = ""
                # small padding
                tx = cx + 6
                ty = cy + rh * 0.65  # baseline near bottom of cell
                p.insert_text(
                    fitz.Point(tx, ty),
                    txt,
                    fontsize=fontsize,
                    fontname=body_style["fontname"],
                    color=body_style["color"],
                )
                cx += cw
            cy += rh

        return y + total_height + 10  # return next y

    # Content for the new section
    # Corrected numbering: 4.1.6 per spec
    draw_title(page, "4.1.6. TABLE MERGE SCENARIOS (Simulated)")
    y = body_rect.y0
    y = draw_paragraph(
        page,
        fitz.Rect(body_rect.x0, y, body_rect.x1, body_rect.y1),
        (
            "This simulated section mirrors the BHT section formatting and introduces two table scenarios "
            "to exercise table-merge logic: (1) a logically single table split across pages that should be merged; "
            "and (2) two independent tables that should not be merged."
        ),
        fontsize=10.5,
    )
    y += 6

    # Mergeable: Table 4-1 (Part 1) on this page
    page.insert_text(
        fitz.Point(body_rect.x0, y),
        "Mergeable Tables:",
        fontsize=11.5,
        fontname="Helvetica",
        color=(0, 0, 0),
    )
    y += 16
    table_left = body_rect.x0
    col_widths = [180, 100, 80, 100]
    row_heights = [18] + [18] * 6
    cells = [
        ["PC Range", "Outcome", "Count", "Accuracy"],
        ["0x8000_0000-0x8000_00FF", "taken", "124", "91.2%"],
        ["0x8000_0100-0x8000_01FF", "not-taken", "98", "88.4%"],
        ["0x8000_0200-0x8000_02FF", "taken", "206", "93.7%"],
        ["0x8000_0300-0x8000_03FF", "taken", "151", "89.6%"],
        ["0x8000_0400-0x8000_04FF", "not-taken", "74", "86.1%"],
        ["0x8000_0500-0x8000_05FF", "taken", "132", "92.0%"],
    ]
    y = draw_table(
        page,
        table_left,
        y,
        col_widths,
        row_heights,
        cells,
        caption="Table 4-1. BHT Prediction Outcomes (Part 1)",
    )

    y = draw_paragraph(
        page,
        fitz.Rect(body_rect.x0, y, body_rect.x1, body_rect.y1),
        (
            "Paragraph for Table 4-1: This table summarizes a subset of BHT prediction statistics. "
            "The continuation appears on the next page and should be merged with this part."
        ),
        fontsize=10.0,
    )

    # Next page: continuation (mergeable part 2)
    page2 = doc.new_page(width=612, height=792)
    # Continuation page uses the same corrected section number
    draw_title(page2, "4.1.6. TABLE MERGE SCENARIOS (Simulated) - Continued")
    body2 = fitz.Rect(left, top + 44, right, bottom)
    y2 = body2.y0
    y2 = draw_paragraph(
        page2,
        fitz.Rect(body2.x0, y2, body2.x1, body2.y1),
        "Continuation of Table 4-1: The rows below are part of the same dataset and should be merged.",
        fontsize=10.0,
    )
    row_heights2 = [18] * 7
    cells2 = [
        ["0x8000_0600-0x8000_06FF", "not-taken", "67", "85.2%"],
        ["0x8000_0700-0x8000_07FF", "taken", "189", "94.1%"],
        ["0x8000_0800-0x8000_08FF", "taken", "203", "92.7%"],
        ["0x8000_0900-0x8000_09FF", "not-taken", "81", "87.5%"],
        ["0x8000_0A00-0x8000_0AFF", "taken", "117", "90.6%"],
        ["0x8000_0B00-0x8000_0BFF", "taken", "176", "91.4%"],
        ["0x8000_0C00-0x8000_0CFF", "not-taken", "72", "84.9%"],
    ]
    y2 = draw_table(
        page2,
        body2.x0,
        y2,
        col_widths,
        row_heights2,
        cells2,
        caption="Table 4-1. BHT Prediction Outcomes (Continued)",
    )
    y2 = draw_paragraph(
        page2,
        fitz.Rect(body2.x0, y2, body2.x1, body2.y1),
        "Paragraph for Table 4-1 (continued): Additional rows belong to the same logical table.",
        fontsize=10.0,
    )

    # Non-mergeable: two independent tables on the same page with clear separation
    page2.insert_text(
        fitz.Point(body2.x0, y2 + 8),
        "Non-Mergeable Tables:",
        fontsize=11.5,
        fontname="Helvetica",
        color=(0, 0, 0),
    )
    y2 += 28
    y2 = draw_paragraph(
        page2,
        fitz.Rect(body2.x0, y2, body2.x1, body2.y1),
        (
            "Table 4-2 and Table 4-3 are distinct datasets and shall not be merged. Each is preceded by its own paragraph."
        ),
        fontsize=10.0,
    )

    # Table 4-2
    col_w_small = [210, 180, 110]
    row_h_small = [18] + [18] * 4
    cells_42 = [
        ["Signal", "Description", "Width"],
        ["clk_i", "Subsystem clock", "1"],
        ["rst_ni", "Async reset (active-low)", "1"],
        ["vpc_i", "Virtual PC input", "CVA6Cfg.VLEN"],
        ["bht_prediction_o", "Prediction vector", "CVA6Cfg.INSTR_PER_FETCH"],
    ]
    y2 = draw_table(
        page2,
        body2.x0,
        y2,
        col_w_small,
        row_h_small,
        cells_42,
        caption="Table 4-2. Interface Signals",
    )
    y2 = draw_paragraph(
        page2,
        fitz.Rect(body2.x0, y2, body2.x1, body2.y1),
        "Paragraph for Table 4-2: Interface-level information unrelated to Table 4-3.",
        fontsize=10.0,
    )

    # Table 4-3
    cells_43 = [
        ["Parameter", "Value", "Notes"],
        ["BHTDepth", "1024", "Configurable"],
        ["CounterType", "2-bit saturating", "Standard"],
        ["DefaultPrediction", "not-taken", "On miss"],
        ["FlushPolicy", "none", "Per spec"],
    ]
    y2 = draw_table(
        page2,
        body2.x0,
        y2,
        col_w_small,
        row_h_small,
        cells_43,
        caption="Table 4-3. BHT Parameters",
    )
    draw_paragraph(
        page2,
        fitz.Rect(body2.x0, y2, body2.x1, body2.y1),
        "Paragraph for Table 4-3: Parameter summary distinct from interface signals above.",
        fontsize=10.0,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Insert simulated hardware requirements as page 3 of a PDF"
    )
    parser.add_argument("--input", required=True, help="Path to input PDF")
    parser.add_argument("--output", required=True, help="Path to output PDF")
    parser.add_argument(
        "--header-font-file", help="Optional path to header font (TTF/OTF) to embed", default=None
    )
    parser.add_argument(
        "--body-font-file", help="Optional path to body font (TTF/OTF) to embed", default=None
    )
    args = parser.parse_args(argv)

    input_pdf = Path(args.input).resolve()
    output_pdf = Path(args.output).resolve()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    add_page_3(input_pdf, output_pdf)
    print(f"Wrote: {output_pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
