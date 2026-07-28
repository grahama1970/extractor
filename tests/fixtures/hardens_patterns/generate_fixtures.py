#!/usr/bin/env python3
"""Generate synthetic fixture PDFs reproducing HARDENS fragmentation patterns.

Patterns discovered via /debug-pdf analysis of HARDENS_ML22326A307:
  1. Code listing tables (68.8% of high-frag): tall-thin, line numbers, source code
  2. Sparse content tables: <50% cells filled, wrapped content
  3. Large spec tables: 65+ rows x 7+ columns, newlines/NBSP in cells
  4. Multi-column wide tables: 8-22 columns, index/ToC style

Each fixture is a minimal PDF that reproduces one pattern to test
extractor strategy selection and fragmentation scoring.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

OUT_DIR = Path(__file__).parent


def make_code_listing_fixture(path: Path) -> None:
    """Pattern 1: Tall-thin code listing table with line numbers and borders.

    HARDENS pages 93-173: 47-68 rows x 2-6 columns.
    stream_default fragments because code lines wrap across cells.
    Lattice should win because clear borders exist.
    """
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Code Listing Table — Fixture", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    # Simulate VHDL/SystemVerilog code listing like HARDENS
    code_lines = [
        ("Line", "Signal Name", "Direction", "Type", "Description"),
        ("1", "clk_i", "in", "std_logic", "System clock input"),
        ("2", "rst_n_i", "in", "std_logic", "Active-low\nasynchronous reset"),
        ("3", "data_valid_o", "out", "std_logic", "Data valid\u00a0output flag"),
        ("4", "bht_update_i", "in", "std_logic_vector\n(31 downto 0)", "Branch history\ntable update"),
        ("5", "bht_predi ction_o", "out", "std_logic_vector\n(1 downto 0)", "Branch prediction\u00a0output"),
        ("6", "execute_en_i", "in", "std_logic", "EXECU TE enable"),
        ("7", "subsyste m_sel_i", "in", "std_logic_vector\n(3 downto 0)", "Subsyste m\nselect input"),
        ("8", "addr_bus_o", "out", "std_logic_vector\n(31 downto 0)", "Address bus output"),
        ("9", "data_bus_io", "inout", "std_logic_vector\n(63 downto 0)", "Bidirectional\ndata bus"),
        ("10", "irq_pending_o", "out", "std_logic", "Interrupt request\npending flag"),
        ("11", "cache_flush_i", "in", "std_logic", "Cache flush\u00a0request"),
        ("12", "mem_ready_i", "in", "std_logic", "Memory ready\nstatus signal"),
        ("13", "write_back_o", "out", "std_logic", "Write-back\u00a0enable"),
        ("14", "pipeline_stall_i", "in", "std_logic", "Pipeline stall\nrequest input"),
        ("15", "branch_taken_o", "out", "std_logic", "Branch taken\nindicator"),
        ("16", "pc_next_o", "out", "std_logic_vector\n(31 downto 0)", "Next program\ncounter value"),
        ("17", "debug_mode_i", "in", "std_logic", "Debug mode\u00a0enable"),
        ("18", "trace_valid_o", "out", "std_logic", "Trace buffer\nvalid output"),
        ("19", "exception_o", "out", "std_logic_vector\n(4 downto 0)", "Exception\nvector output"),
        ("20", "csr_addr_i", "in", "std_logic_vector\n(11 downto 0)", "CSR address\ninput bus"),
    ]

    # Extend to ~50 rows to match HARDENS pattern
    for i in range(21, 51):
        code_lines.append((
            str(i),
            f"signal_{i}_reg",
            "in" if i % 2 == 0 else "out",
            "std_logic_vector\n(7 downto 0)" if i % 3 == 0 else "std_logic",
            f"Signal {i}\ndescripti on" if i % 4 == 0 else f"Signal {i} description",
        ))

    t = Table(code_lines, colWidths=[0.5 * inch, 1.2 * inch, 0.6 * inch, 1.5 * inch, 2.0 * inch])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(t)

    doc.build(elements)


def make_sparse_content_fixture(path: Path) -> None:
    """Pattern 2: Sparse content table with <50% cells filled.

    HARDENS pages 139, 155, 162: wrapped content with many empty cells.
    Fragmentation inflated by empty cell grid.
    """
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Sparse Content Table — Fixture", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    headers = ("Req ID", "Title", "Category", "Priority", "Status", "Notes", "Trace")
    rows = [headers]

    # Sparse data — many cells empty, some with wrapped text
    sparse_data = [
        ("REQ-001", "System Clock", "Hardware", "Critical", "", "", ""),
        ("", "", "", "", "Verified", "See section\n4.2.1 for\ndetails", ""),
        ("REQ-002", "Reset Logic", "", "High", "", "", "HARDENS-\n042"),
        ("", "Active-low\u00a0asynchronous", "Hardware", "", "Open", "", ""),
        ("REQ-003", "", "Software", "", "", "Pending\nreview", ""),
        ("", "Interrupt\nHandler", "", "Medium", "", "", "HARDENS-\n105"),
        ("REQ-004", "Memory\u00a0Protection", "", "", "Draft", "", ""),
        ("", "", "Security", "Critical", "", "Cross-reference\nwith NIST\u00a0SP-800", ""),
        ("REQ-005", "", "", "", "", "", ""),
        ("", "Watchdog\nTimer", "Hardware", "High", "Verified", "", "HARDENS-\n203"),
    ]

    # Extend to 40+ rows
    for i in range(6, 41):
        if i % 3 == 0:
            rows.append((f"REQ-{i:03d}", f"Requirement\n{i}", "", "", "", "", ""))
        elif i % 3 == 1:
            rows.append(("", "", "Category\u00a0{0}".format(i % 5), "", "Open", "", ""))
        else:
            rows.append(("", "", "", "", "", f"Note\nfor item {i}", f"TRACE-\n{i:03d}"))

    rows.extend(sparse_data)

    t = Table(rows, colWidths=[0.7 * inch, 1.0 * inch, 0.8 * inch, 0.7 * inch, 0.6 * inch, 1.2 * inch, 0.7 * inch])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(t)

    doc.build(elements)


def make_large_spec_fixture(path: Path) -> None:
    """Pattern 3: Large spec table with 65+ rows x 8 columns.

    HARDENS page 155 (frag=42, 520 cells): spec text with wrapped content.
    Non-breaking spaces and newlines within cells drive fragmentation.
    """
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Large Specification Table — Fixture", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    headers = ("ID", "Req", "Type", "Class", "Priority", "Status", "Trace", "Notes")
    rows = [headers]

    for i in range(1, 66):
        row = (
            f"S{i:03d}",
            f"The system shall\nprovide capability\u00a0{i}" if i % 5 == 0
            else f"Requirement {i}",
            "Functional" if i % 3 == 0 else ("Safety" if i % 3 == 1 else "Performance"),
            f"Class\u00a0{(i % 4) + 1}",
            "Critical" if i % 7 == 0 else ("High" if i % 3 == 0 else "Medium"),
            "Verified" if i % 4 == 0 else ("Open" if i % 4 == 1 else ""),
            f"TRACE-{i:03d}" if i % 2 == 0 else "",
            f"See section\n{i // 10 + 1}.{i % 10}" if i % 6 == 0
            else (f"Note {i}\nwith\u00a0NBSP" if i % 8 == 0 else ""),
        )
        rows.append(row)

    t = Table(rows, colWidths=[
        0.5 * inch, 1.3 * inch, 0.7 * inch, 0.6 * inch,
        0.6 * inch, 0.6 * inch, 0.7 * inch, 1.2 * inch,
    ])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(t)

    doc.build(elements)


def make_wide_multicol_fixture(path: Path) -> None:
    """Pattern 4: Multi-column wide table with 15+ columns.

    HARDENS pages 7-9 (frag=32, 176 cells): 8x22 index/ToC style.
    Many columns cause wrapping and empty cells.
    """
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.3 * inch, rightMargin=0.3 * inch)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Wide Multi-Column Table — Fixture", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    ncols = 15
    headers = tuple(f"Col\u00a0{i+1}" for i in range(ncols))
    rows = [headers]

    for r in range(30):
        row = []
        for c in range(ncols):
            if (r + c) % 4 == 0:
                row.append(f"Sec\n{r+1}.{c+1}")
            elif (r + c) % 4 == 1:
                row.append(f"Pg\u00a0{r * 10 + c}")
            elif (r + c) % 4 == 2:
                row.append("")
            else:
                row.append(f"Item\n{r}-{c}")
        rows.append(tuple(row))

    col_w = 0.48 * inch
    t = Table(rows, colWidths=[col_w] * ncols)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
    ]))
    elements.append(t)

    doc.build(elements)


def main() -> None:
    """Generate all PDF test fixtures."""
    make_code_listing_fixture(OUT_DIR / "fixture_code_listing.pdf")
    print(f"Created: fixture_code_listing.pdf")

    make_sparse_content_fixture(OUT_DIR / "fixture_sparse_content.pdf")
    print(f"Created: fixture_sparse_content.pdf")

    make_large_spec_fixture(OUT_DIR / "fixture_large_spec.pdf")
    print(f"Created: fixture_large_spec.pdf")

    make_wide_multicol_fixture(OUT_DIR / "fixture_wide_multicol.pdf")
    print(f"Created: fixture_wide_multicol.pdf")

    print("\nAll 4 HARDENS-pattern fixtures generated.")


if __name__ == "__main__":
    main()
