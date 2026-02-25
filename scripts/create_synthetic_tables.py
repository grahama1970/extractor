#!/usr/bin/env python3
"""Generate hundreds of synthetic PDFs with varied table styles.

Creates PDFs modeled after real-world table patterns:
- Bordered (full grid, thick box, inner-only) → lattice strategies
- Borderless (whitespace-separated, shaded bands) → stream strategies
- Merged cells (row spans, column spans, nested headers) → complex strategies
- Mixed (bordered + borderless on same page)

Each PDF has a known ground-truth expected strategy, enabling controlled
validation of the strategy classifier.
"""

import hashlib
import itertools
import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "pdfs" / "synthetic"
MANIFEST_PATH = OUTPUT_DIR / "manifest.jsonl"

# Seed for reproducibility
random.seed(42)

# ---------------------------------------------------------------------------
# Data pools — real-world content drawn from actual PDF patterns
# ---------------------------------------------------------------------------

DEFENSE_HEADERS = [
    ["Req ID", "Requirement", "Threshold", "Objective", "Verification"],
    ["CSCI", "Function", "Input", "Output", "Interface"],
    ["Test ID", "Procedure", "Expected Result", "Actual", "Status"],
    ["Parameter", "Requirement", "Allocation", "Margin", "Risk"],
    ["CDR Item", "Description", "Owner", "Due Date", "Priority"],
]

ENGINEERING_HEADERS = [
    ["Parameter", "Min", "Typ", "Max", "Unit"],
    ["Component", "Value", "Tolerance", "Package", "Qty"],
    ["Signal", "Direction", "Voltage", "Current", "Notes"],
    ["Register", "Offset", "Width", "Access", "Description"],
    ["Pin", "Name", "Function", "Type", "Default"],
]

SCIENTIFIC_HEADERS = [
    ["Method", "Precision", "Recall", "F1", "Accuracy"],
    ["Dataset", "Samples", "Classes", "Split", "Source"],
    ["Metric", "Baseline", "Ours", "Δ", "p-value"],
    ["Layer", "Params", "FLOPs", "Output", "Activation"],
    ["Experiment", "Config", "Result", "Std Dev", "Notes"],
]

FINANCIAL_HEADERS = [
    ["", "Q1", "Q2", "Q3", "Q4", "Total"],
    ["Account", "Budget", "Actual", "Variance", "% Var"],
    ["Category", "FY2024", "FY2025", "Change", "% Change"],
    ["Item", "Unit Cost", "Quantity", "Subtotal", "Tax"],
    ["Department", "Headcount", "Budget ($K)", "Spent ($K)", "Remaining"],
]

MEDICAL_HEADERS = [
    ["Patient ID", "Age", "Sex", "Diagnosis", "Treatment", "Outcome"],
    ["Drug", "Dose", "Route", "Frequency", "Duration"],
    ["Lab Test", "Result", "Unit", "Reference", "Flag"],
    ["Symptom", "Onset", "Severity", "Duration", "Resolution"],
]

LEGAL_HEADERS = [
    ["Clause", "Section", "Requirement", "Compliance", "Evidence"],
    ["Control ID", "Description", "Status", "Owner", "Review Date"],
    ["Regulation", "Applicability", "Gap", "Remediation", "Priority"],
]


def _random_defense_rows(n: int) -> List[List[str]]:
    reqs = [f"SRD-{i:03d}" for i in range(1, n + 1)]
    descs = [
        "Operating Temperature", "Shock Resistance", "Vibration (Random)",
        "EMI Susceptibility", "MTBF", "Weight", "Power Consumption",
        "Data Rate", "Humidity Tolerance", "Altitude Operation",
        "Salt Fog Resistance", "Thermal Shock", "Acoustic Noise",
        "RF Emission", "Grounding Impedance", "Connector Pull Force",
    ]
    thresholds = ["-40°C to +71°C", "40g 11ms", "7.7 grms", "MIL-STD-461G",
                  ">2000 hrs", "<15 kg", "<150W", "≥100 Mbps", "95% RH",
                  "70,000 ft", "5% NaCl 48hr", "-40/+71°C 100cy",
                  "<85 dBA", "-80 dBm/MHz", "<0.1Ω", ">50 N"]
    verifs = ["Test", "Analysis", "Inspection", "Demonstration", "Test/Analysis"]
    rows = []
    for i in range(n):
        rows.append([
            reqs[i % len(reqs)],
            descs[i % len(descs)],
            thresholds[i % len(thresholds)],
            random.choice(["Meets", "Exceeds", "TBD"]),
            random.choice(verifs),
        ])
    return rows


def _random_engineering_rows(n: int) -> List[List[str]]:
    params = [
        "Input Voltage", "Output Current", "Ripple", "Efficiency",
        "Dropout Voltage", "Quiescent Current", "Line Regulation",
        "Load Regulation", "PSRR", "Thermal Resistance", "Junction Temp",
        "Operating Temp", "Switching Freq", "Output Capacitance",
    ]
    units = ["V", "mA", "mV", "%", "mV", "µA", "%/V", "%/A", "dB", "°C/W",
             "°C", "°C", "kHz", "µF"]
    rows = []
    for i in range(n):
        mn = round(random.uniform(0.1, 50), 2)
        typ = round(mn * random.uniform(1.0, 1.3), 2)
        mx = round(typ * random.uniform(1.0, 1.5), 2)
        rows.append([params[i % len(params)], str(mn), str(typ), str(mx),
                      units[i % len(units)]])
    return rows


def _random_scientific_rows(n: int) -> List[List[str]]:
    methods = [
        "BERT-base", "RoBERTa-large", "GPT-2", "T5-small", "XLNet",
        "ALBERT", "DeBERTa", "ELECTRA", "Longformer", "BigBird",
        "DistilBERT", "BART", "Pegasus", "Reformer",
    ]
    rows = []
    for i in range(n):
        p = round(random.uniform(0.60, 0.99), 3)
        r = round(random.uniform(0.55, 0.98), 3)
        f1 = round(2 * p * r / (p + r + 1e-9), 3)
        acc = round(random.uniform(0.70, 0.99), 3)
        rows.append([methods[i % len(methods)], str(p), str(r), str(f1), str(acc)])
    return rows


def _random_financial_rows(n: int) -> List[List[str]]:
    items = [
        "Revenue", "COGS", "Gross Profit", "R&D", "Sales & Marketing",
        "G&A", "Operating Income", "Interest", "Tax", "Net Income",
        "EBITDA", "Depreciation", "Amortization", "CapEx",
    ]
    rows = []
    for i in range(n):
        vals = [f"${random.randint(10, 500)}.{random.randint(0,9)}M" for _ in range(4)]
        pct = f"{random.choice(['+','-'])}{random.randint(1,30)}.{random.randint(0,9)}%"
        rows.append([items[i % len(items)]] + vals + [pct])
    return rows


def _random_medical_rows(n: int) -> List[List[str]]:
    drugs = ["Aspirin", "Metformin", "Lisinopril", "Atorvastatin", "Amoxicillin",
             "Omeprazole", "Losartan", "Gabapentin", "Hydrochlorothiazide", "Amlodipine"]
    routes = ["PO", "IV", "IM", "SC", "Topical"]
    freqs = ["QD", "BID", "TID", "QID", "PRN", "Q8H", "Q12H"]
    rows = []
    for i in range(n):
        rows.append([
            drugs[i % len(drugs)],
            f"{random.choice([50,100,200,250,500])} mg",
            random.choice(routes),
            random.choice(freqs),
            f"{random.randint(3,30)} days",
        ])
    return rows


def _random_legal_rows(n: int) -> List[List[str]]:
    controls = [f"AC-{i}" for i in range(1, 30)]
    statuses = ["Implemented", "Planned", "Partial", "Not Applicable"]
    priorities = ["High", "Medium", "Low", "Critical"]
    rows = []
    for i in range(n):
        rows.append([
            controls[i % len(controls)],
            f"3.{random.randint(1,13)}.{random.randint(1,10)}",
            f"Control requirement {i+1}",
            random.choice(statuses),
            random.choice(priorities),
        ])
    return rows


DOMAIN_GENERATORS = {
    "defense": (DEFENSE_HEADERS, _random_defense_rows),
    "engineering": (ENGINEERING_HEADERS, _random_engineering_rows),
    "scientific": (SCIENTIFIC_HEADERS, _random_scientific_rows),
    "financial": (FINANCIAL_HEADERS, _random_financial_rows),
    "medical": (MEDICAL_HEADERS, _random_medical_rows),
    "legal": (LEGAL_HEADERS, _random_legal_rows),
}

# ---------------------------------------------------------------------------
# Border style definitions
# ---------------------------------------------------------------------------

def _style_full_grid(header_color: str = "#2c3e50") -> List[tuple]:
    """Full grid with thick outer box — classic bordered table."""
    return [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1.5, colors.black),
        ("BOX", (0, 0), (-1, -1), 2.5, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]


def _style_thin_grid(header_color: str = "#34495e") -> List[tuple]:
    """Thin grid lines — lighter bordered table."""
    return [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]


def _style_box_only(header_color: str = "#1a5276") -> List[tuple]:
    """Outer box + header line only — semi-bordered."""
    return [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 1.5, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]


def _style_borderless_plain() -> List[tuple]:
    """No borders at all — pure whitespace separation."""
    return [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#cccccc")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]


def _style_borderless_zebra() -> List[tuple]:
    """No grid lines but alternating row shading — common in scientific papers."""
    return [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]


def _style_borderless_topbot() -> List[tuple]:
    """Top and bottom rules only — classic scientific/APA style."""
    return [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]


def _style_horizontal_only() -> List[tuple]:
    """Horizontal rules between rows, no vertical lines."""
    return [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8f8")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]


# Bordered styles → expect lattice strategies
BORDERED_STYLES = {
    "full_grid": _style_full_grid,
    "thin_grid": _style_thin_grid,
    "box_only": _style_box_only,
}

# Borderless styles → expect stream strategies
BORDERLESS_STYLES = {
    "borderless_plain": _style_borderless_plain,
    "borderless_zebra": _style_borderless_zebra,
    "borderless_topbot": _style_borderless_topbot,
    "horizontal_only": _style_horizontal_only,
}

HEADER_COLORS = [
    "#2c3e50", "#1a5276", "#154360", "#0e6655", "#4a235a",
    "#1b2631", "#7b241c", "#1b4f72", "#0b5345", "#6c3483",
    "#283747", "#1a237e", "#004d40", "#b71c1c", "#1565c0",
]

# ---------------------------------------------------------------------------
# Merged cell patterns
# ---------------------------------------------------------------------------

def _add_column_span(style_cmds: list, data: list) -> list:
    """Add column-spanning header row (e.g., category grouping above the real header)."""
    ncols = len(data[0])
    mid = ncols // 2
    span_row = [""] * ncols
    span_row[0] = "Group A"
    span_row[mid] = "Group B"
    data.insert(0, span_row)
    style_cmds.append(("SPAN", (0, 0), (mid - 1, 0)))
    style_cmds.append(("SPAN", (mid, 0), (ncols - 1, 0)))
    style_cmds.append(("ALIGN", (0, 0), (-1, 0), "CENTER"))
    style_cmds.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#555555")))
    style_cmds.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.white))
    return data


def _add_row_span(style_cmds: list, data: list) -> list:
    """Add row-spanning cells in first column (e.g., category grouping)."""
    if len(data) < 5:
        return data
    categories = ["Category A", "Category B", "Category C"]
    new_data = [data[0]]  # header
    body = data[1:]
    chunk = max(2, len(body) // len(categories))
    for ci, cat in enumerate(categories):
        start = ci * chunk
        end = min(start + chunk, len(body))
        if start >= len(body):
            break
        for ri, row in enumerate(body[start:end]):
            if ri == 0:
                new_data.append([cat] + row[1:])
            else:
                new_data.append([""] + row[1:])
        # Add SPAN for the category cell
        data_start = 1 + ci * chunk
        data_end = 1 + min((ci + 1) * chunk, len(body)) - 1
        if data_end > data_start:
            style_cmds.append(("SPAN", (0, data_start), (0, data_end)))
            style_cmds.append(("VALIGN", (0, data_start), (0, data_end), "MIDDLE"))
    return new_data


def _add_nested_header(style_cmds: list, data: list) -> list:
    """Add two-level header: top spans across groups, bottom has individual cols."""
    ncols = len(data[0])
    if ncols < 4:
        return data
    # Create top-level header spanning pairs
    top = [""] * ncols
    top[0] = data[0][0]  # keep first col label
    for i in range(1, ncols - 1, 2):
        top[i] = f"Metric {(i+1)//2}"
        style_cmds.append(("SPAN", (i, 0), (min(i + 1, ncols - 1), 0)))
    data.insert(0, top)
    style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")))
    style_cmds.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.white))
    style_cmds.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    style_cmds.append(("ALIGN", (0, 0), (-1, 0), "CENTER"))
    return data


MERGE_PATTERNS = {
    "none": lambda sc, d: d,
    "col_span": _add_column_span,
    "row_span": _add_row_span,
    "nested_header": _add_nested_header,
}

# ---------------------------------------------------------------------------
# PDF generators
# ---------------------------------------------------------------------------

def _col_widths(ncols: int, page_width: float = 6.5) -> List[float]:
    """Compute even column widths in inches."""
    w = page_width / ncols
    return [w * inch] * ncols


def create_single_table_pdf(
    path: Path,
    domain: str,
    border_style: str,
    merge_pattern: str,
    n_rows: int,
    pagesize=letter,
    title: str = "",
) -> Dict:
    """Create a single-table PDF. Returns metadata dict."""
    headers_pool, row_gen = DOMAIN_GENERATORS[domain]
    header = random.choice(headers_pool)
    rows = row_gen(n_rows)
    data = [header] + rows

    # Determine border style
    if border_style in BORDERED_STYLES:
        hcolor = random.choice(HEADER_COLORS)
        style_cmds = BORDERED_STYLES[border_style](hcolor)
        expected_strategy_family = "lattice"
    else:
        style_cmds = BORDERLESS_STYLES[border_style]()
        expected_strategy_family = "stream"

    # Apply merge pattern
    merge_fn = MERGE_PATTERNS[merge_pattern]
    data = merge_fn(style_cmds, data)

    # If merging with bordered → more complex, may need lattice_strong
    if merge_pattern != "none" and border_style in BORDERED_STYLES:
        expected_strategy_family = "lattice"

    doc = SimpleDocTemplate(str(path), pagesize=pagesize)
    styles = getSampleStyleSheet()
    story = []

    if not title:
        title = f"Synthetic {domain.title()} — {border_style} / {merge_pattern}"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))

    ncols = len(data[0])
    t = Table(data, colWidths=_col_widths(ncols))
    t.setStyle(TableStyle(style_cmds))
    story.append(t)

    doc.build(story)

    return {
        "filename": path.name,
        "domain": domain,
        "border_style": border_style,
        "merge_pattern": merge_pattern,
        "n_rows": n_rows,
        "n_cols": ncols,
        "expected_strategy_family": expected_strategy_family,
        "table_style": "bordered" if border_style in BORDERED_STYLES else "borderless",
        "ground_truth_cells": data,
    }


def create_multi_table_pdf(
    path: Path,
    domain: str,
    border_styles: List[str],
    merge_patterns: List[str],
    n_rows_per_table: int = 8,
    pagesize=letter,
) -> Dict:
    """Create PDF with multiple tables (possibly mixed styles)."""
    doc = SimpleDocTemplate(str(path), pagesize=pagesize)
    styles = getSampleStyleSheet()
    story = []

    has_bordered = any(s in BORDERED_STYLES for s in border_styles)
    has_borderless = any(s in BORDERLESS_STYLES for s in border_styles)

    if has_bordered and has_borderless:
        table_style_label = "mixed"
    elif has_bordered:
        table_style_label = "bordered"
    else:
        table_style_label = "borderless"

    story.append(Paragraph(
        f"Synthetic {domain.title()} — Multi-Table ({table_style_label})",
        styles["Title"],
    ))
    story.append(Spacer(1, 0.2 * inch))

    headers_pool, row_gen = DOMAIN_GENERATORS[domain]
    all_tables_gt = []

    for i, (bs, mp) in enumerate(zip(border_styles, merge_patterns)):
        story.append(Paragraph(f"Table {i + 1}", styles["Heading2"]))
        story.append(Spacer(1, 0.1 * inch))

        header = random.choice(headers_pool)
        rows = row_gen(n_rows_per_table)
        data = [header] + rows

        if bs in BORDERED_STYLES:
            hcolor = random.choice(HEADER_COLORS)
            style_cmds = BORDERED_STYLES[bs](hcolor)
        else:
            style_cmds = BORDERLESS_STYLES[bs]()

        merge_fn = MERGE_PATTERNS[mp]
        data = merge_fn(style_cmds, data)
        all_tables_gt.append(data)

        ncols = len(data[0])
        t = Table(data, colWidths=_col_widths(ncols))
        t.setStyle(TableStyle(style_cmds))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

    doc.build(story)

    return {
        "filename": path.name,
        "domain": domain,
        "border_styles": border_styles,
        "merge_patterns": merge_patterns,
        "n_tables": len(border_styles),
        "table_style": table_style_label,
        "ground_truth_cells": all_tables_gt,
    }


def generate_all():
    """Generate the full synthetic corpus."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    idx = 0

    domains = list(DOMAIN_GENERATORS.keys())
    all_bordered = list(BORDERED_STYLES.keys())
    all_borderless = list(BORDERLESS_STYLES.keys())
    all_merges = list(MERGE_PATTERNS.keys())
    row_counts = [5, 8, 12, 15, 20]

    # -----------------------------------------------------------------------
    # Part 1: Single-table PDFs — all combinations of domain × style × merge
    # -----------------------------------------------------------------------
    print("=== Part 1: Single-table PDFs ===")

    # Bordered tables (all combos)
    for domain, bs, mp, nrows in itertools.product(
        domains, all_bordered, all_merges, row_counts
    ):
        idx += 1
        name = f"synth_{idx:04d}_{domain}_{bs}_{mp}_{nrows}r.pdf"
        path = OUTPUT_DIR / name
        meta = create_single_table_pdf(path, domain, bs, mp, nrows)
        meta["pdf_id"] = idx
        manifest.append(meta)

    print(f"  Generated {idx} bordered single-table PDFs")
    bordered_count = idx

    # Borderless tables (all combos)
    for domain, bs, mp, nrows in itertools.product(
        domains, all_borderless, all_merges, row_counts
    ):
        idx += 1
        name = f"synth_{idx:04d}_{domain}_{bs}_{mp}_{nrows}r.pdf"
        path = OUTPUT_DIR / name
        meta = create_single_table_pdf(path, domain, bs, mp, nrows)
        meta["pdf_id"] = idx
        manifest.append(meta)

    print(f"  Generated {idx - bordered_count} borderless single-table PDFs")
    single_count = idx

    # -----------------------------------------------------------------------
    # Part 2: Mixed-style PDFs (bordered + borderless on same page)
    # -----------------------------------------------------------------------
    print("=== Part 2: Mixed-style multi-table PDFs ===")

    for domain in domains:
        for _ in range(5):  # 5 mixed PDFs per domain
            idx += 1
            n_tables = random.randint(2, 4)
            styles_list = []
            merges_list = []
            for _ in range(n_tables):
                if random.random() < 0.5:
                    styles_list.append(random.choice(all_bordered))
                else:
                    styles_list.append(random.choice(all_borderless))
                merges_list.append(random.choice(all_merges))

            name = f"synth_{idx:04d}_{domain}_mixed_{n_tables}t.pdf"
            path = OUTPUT_DIR / name
            meta = create_multi_table_pdf(path, domain, styles_list, merges_list)
            meta["pdf_id"] = idx
            manifest.append(meta)

    print(f"  Generated {idx - single_count} mixed multi-table PDFs")
    mixed_count = idx

    # -----------------------------------------------------------------------
    # Part 3: Multi-table same-style PDFs (stress test: many tables per page)
    # -----------------------------------------------------------------------
    print("=== Part 3: Multi-table same-style PDFs ===")

    for domain in domains:
        # All-bordered multi-table
        for bs in all_bordered:
            idx += 1
            n_tables = random.randint(3, 5)
            name = f"synth_{idx:04d}_{domain}_multi_{bs}_{n_tables}t.pdf"
            path = OUTPUT_DIR / name
            merges = [random.choice(all_merges) for _ in range(n_tables)]
            meta = create_multi_table_pdf(path, domain, [bs] * n_tables, merges)
            meta["pdf_id"] = idx
            manifest.append(meta)

        # All-borderless multi-table
        for bs in all_borderless:
            idx += 1
            n_tables = random.randint(3, 5)
            name = f"synth_{idx:04d}_{domain}_multi_{bs}_{n_tables}t.pdf"
            path = OUTPUT_DIR / name
            merges = [random.choice(all_merges) for _ in range(n_tables)]
            meta = create_multi_table_pdf(path, domain, [bs] * n_tables, merges)
            meta["pdf_id"] = idx
            manifest.append(meta)

    print(f"  Generated {idx - mixed_count} same-style multi-table PDFs")

    # -----------------------------------------------------------------------
    # Part 4: Edge cases — very wide, very tall, single-row, single-col
    # -----------------------------------------------------------------------
    print("=== Part 4: Edge case PDFs ===")
    edge_start = idx

    for domain in domains[:3]:  # defense, engineering, scientific
        # Very tall table (30+ rows)
        for bs in [random.choice(all_bordered), random.choice(all_borderless)]:
            idx += 1
            name = f"synth_{idx:04d}_{domain}_tall_30r_{bs}.pdf"
            path = OUTPUT_DIR / name
            meta = create_single_table_pdf(path, domain, bs, "none", 30, pagesize=A4)
            meta["pdf_id"] = idx
            manifest.append(meta)

        # Table with all merge types
        for mp in ["col_span", "row_span", "nested_header"]:
            for bs in [random.choice(all_bordered), random.choice(all_borderless)]:
                idx += 1
                name = f"synth_{idx:04d}_{domain}_merge_{mp}_{bs}.pdf"
                path = OUTPUT_DIR / name
                meta = create_single_table_pdf(path, domain, bs, mp, 12)
                meta["pdf_id"] = idx
                manifest.append(meta)

    print(f"  Generated {idx - edge_start} edge case PDFs")

    # -----------------------------------------------------------------------
    # Write manifest
    # -----------------------------------------------------------------------
    with open(MANIFEST_PATH, "w") as f:
        for rec in manifest:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Summary
    bordered_total = sum(1 for m in manifest if m.get("table_style") == "bordered")
    borderless_total = sum(1 for m in manifest if m.get("table_style") == "borderless")
    mixed_total = sum(1 for m in manifest if m.get("table_style") == "mixed")

    print(f"\n{'='*60}")
    print(f"Total: {idx} synthetic PDFs generated in {OUTPUT_DIR}")
    print(f"  Bordered:   {bordered_total}")
    print(f"  Borderless: {borderless_total}")
    print(f"  Mixed:      {mixed_total}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    generate_all()
