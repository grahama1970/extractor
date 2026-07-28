#!/usr/bin/env python3
"""Cell-level accuracy validator for synthetic PDF extraction.

Replays the synthetic PDF generator's random sequence (seed=42) to reconstruct
ground truth cell data, then compares against S11 structural.json outputs.

Usage:
    python scripts/validate_cell_accuracy.py [--output-dir PATH] [--domain DOMAIN]
"""

import csv
import io
import itertools
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Reproduce the EXACT data generation from create_synthetic_tables.py
# (same pools, same functions, same call order)
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
    """Generate random defense requirement rows with sequential IDs."""
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
    """Generate random engineering parameter rows."""
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
    """Generate random scientific method performance rows."""
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
    """Generate random financial data rows with specified number of entries."""
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
    """Generate random medical rows with drug names, routes, and frequencies."""
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
    """Generate random legal rows with control, version, and status data."""
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

BORDERED_STYLES_KEYS = ["full_grid", "thin_grid", "box_only"]
BORDERLESS_STYLES_KEYS = ["borderless_plain", "borderless_zebra", "borderless_topbot", "horizontal_only"]

HEADER_COLORS = [
    "#2c3e50", "#1a5276", "#154360", "#0e6655", "#4a235a",
    "#1b2631", "#7b241c", "#1b4f72", "#0b5345", "#6c3483",
    "#283747", "#1a237e", "#004d40", "#b71c1c", "#1565c0",
]


def _apply_merge_col_span(data: list) -> list:
    """Replay _add_column_span data mutation (no style cmds needed)."""
    ncols = len(data[0])
    mid = ncols // 2
    span_row = [""] * ncols
    span_row[0] = "Group A"
    span_row[mid] = "Group B"
    data.insert(0, span_row)
    return data


def _apply_merge_row_span(data: list) -> list:
    """Replay _add_row_span data mutation."""
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
    return new_data


def _apply_merge_nested_header(data: list) -> list:
    """Replay _add_nested_header data mutation."""
    ncols = len(data[0])
    if ncols < 4:
        return data
    top = [""] * ncols
    top[0] = data[0][0]  # keep first col label
    for i in range(1, ncols - 1, 2):
        top[i] = f"Metric {(i+1)//2}"
    data.insert(0, top)
    return data


MERGE_FUNS = {
    "none": lambda d: d,
    "col_span": _apply_merge_col_span,
    "row_span": _apply_merge_row_span,
    "nested_header": _apply_merge_nested_header,
}


def _gen_single_table_data(domain: str, border_style: str, merge_pattern: str,
                           n_rows: int) -> Dict:
    """Generate cell data for a single table (consumes random state identically)."""
    headers_pool, row_gen = DOMAIN_GENERATORS[domain]
    header = random.choice(headers_pool)
    rows = row_gen(n_rows)
    data = [header] + rows

    # Consume random state for border style (same as original)
    if border_style in BORDERED_STYLES_KEYS:
        _ = random.choice(HEADER_COLORS)  # consumed by _style_full_grid etc.

    # Apply merge pattern (modifies data in-place)
    data = MERGE_FUNS[merge_pattern](data)

    return {"cells": data, "n_rows": len(data), "n_cols": len(data[0]) if data else 0}


def _gen_multi_table_data(domain: str, border_styles: List[str],
                          merge_patterns: List[str],
                          n_rows_per_table: int = 8) -> Dict:
    """Generate cell data for multi-table PDF (consumes random state identically)."""
    all_tables_gt = []
    for bs, mp in zip(border_styles, merge_patterns):
        td = _gen_single_table_data(domain, bs, mp, n_rows_per_table)
        all_tables_gt.append(td["cells"])
    return {"cells": all_tables_gt, "n_tables": len(all_tables_gt)}


def replay_ground_truth() -> Dict[str, Dict]:
    """Replay the exact random sequence from generate_all() to get ground truth cells.

    Returns dict mapping filename -> {cells: [[...]], n_rows, n_cols, ...}
    """
    random.seed(42)

    domains = list(DOMAIN_GENERATORS.keys())
    all_bordered = list(BORDERED_STYLES_KEYS)
    all_borderless = list(BORDERLESS_STYLES_KEYS)
    all_merges = list(MERGE_FUNS.keys())
    row_counts = [5, 8, 12, 15, 20]

    gt = {}
    idx = 0

    # Part 1: Single-table bordered
    for domain, bs, mp, nrows in itertools.product(
        domains, all_bordered, all_merges, row_counts
    ):
        idx += 1
        name = f"synth_{idx:04d}_{domain}_{bs}_{mp}_{nrows}r.pdf"
        td = _gen_single_table_data(domain, bs, mp, nrows)
        gt[name] = {**td, "domain": domain, "border_style": bs,
                    "merge_pattern": mp, "multi_table": False}

    # Part 1: Single-table borderless
    for domain, bs, mp, nrows in itertools.product(
        domains, all_borderless, all_merges, row_counts
    ):
        idx += 1
        name = f"synth_{idx:04d}_{domain}_{bs}_{mp}_{nrows}r.pdf"
        td = _gen_single_table_data(domain, bs, mp, nrows)
        gt[name] = {**td, "domain": domain, "border_style": bs,
                    "merge_pattern": mp, "multi_table": False}

    # Part 2: Mixed-style multi-table
    for domain in domains:
        for _ in range(5):
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
            td = _gen_multi_table_data(domain, styles_list, merges_list)
            gt[name] = {**td, "domain": domain, "multi_table": True}

    # Part 3: Multi-table same-style
    for domain in domains:
        for bs in all_bordered:
            idx += 1
            n_tables = random.randint(3, 5)
            merges = [random.choice(all_merges) for _ in range(n_tables)]
            name = f"synth_{idx:04d}_{domain}_multi_{bs}_{n_tables}t.pdf"
            td = _gen_multi_table_data(domain, [bs] * n_tables, merges)
            gt[name] = {**td, "domain": domain, "multi_table": True}

        for bs in all_borderless:
            idx += 1
            n_tables = random.randint(3, 5)
            merges = [random.choice(all_merges) for _ in range(n_tables)]
            name = f"synth_{idx:04d}_{domain}_multi_{bs}_{n_tables}t.pdf"
            td = _gen_multi_table_data(domain, [bs] * n_tables, merges)
            gt[name] = {**td, "domain": domain, "multi_table": True}

    # Part 4: Edge cases
    for domain in domains[:3]:  # defense, engineering, scientific
        for bs in [random.choice(all_bordered), random.choice(all_borderless)]:
            idx += 1
            name = f"synth_{idx:04d}_{domain}_tall_30r_{bs}.pdf"
            td = _gen_single_table_data(domain, bs, "none", 30)
            gt[name] = {**td, "domain": domain, "border_style": bs,
                        "merge_pattern": "none", "multi_table": False}

        for mp in ["col_span", "row_span", "nested_header"]:
            for bs in [random.choice(all_bordered), random.choice(all_borderless)]:
                idx += 1
                name = f"synth_{idx:04d}_{domain}_merge_{mp}_{bs}.pdf"
                td = _gen_single_table_data(domain, bs, mp, 12)
                gt[name] = {**td, "domain": domain, "border_style": bs,
                            "merge_pattern": mp, "multi_table": False}

    return gt


# ---------------------------------------------------------------------------
# Cell-level comparison
# ---------------------------------------------------------------------------

def normalize_cell(val: str) -> str:
    """Normalize cell value for comparison."""
    if not val:
        return ""
    val = val.strip()
    # Normalize unicode dashes/chars
    val = val.replace("\u2014", "-").replace("\u2013", "-")
    val = val.replace("\u2265", ">=").replace("\u2264", "<=")
    val = val.replace("\u00b0", "°")
    val = val.replace("\u00b5", "µ")
    # PDF font encoding artifacts: ≥ often extracted as ‡ (U+2021)
    val = val.replace("\u2021", ">=")
    # ≤ sometimes extracted as † (U+2020)
    val = val.replace("\u2020", "<=")
    # Normalize whitespace
    val = " ".join(val.split())
    return val


TITLE_KEYWORDS = {"Synthetic", "box_only", "full_grid", "thin_grid",
                  "borderless_plain", "borderless_zebra", "borderless_topbot",
                  "horizontal_only", "col_span", "row_span", "nested_header"}


def parse_csv_to_cells(csv_text: str) -> List[List[str]]:
    """Parse CSV text into list of rows, each a list of cell strings.

    Skips:
    - Pandas index header rows (e.g., "0,1,2,3,4")
    - Title rows (e.g., ",Synthetic Scientific — ...")
    - Title continuation rows (e.g., ",,,col_span,,")
    """
    if not csv_text or not csv_text.strip():
        return []
    reader = csv.reader(io.StringIO(csv_text))
    raw_rows = list(reader)

    # Two-pass: identify title rows, then skip them
    skip_indices = set()
    in_title = False
    for i, row in enumerate(raw_rows):
        cleaned = [c.strip() for c in row]
        joined = " ".join(cleaned)

        # Skip pandas index header (all values are digit strings)
        non_empty = [c for c in cleaned if c]
        if non_empty and all(c.isdigit() for c in non_empty):
            skip_indices.add(i)
            continue

        # Title row contains "Synthetic" + em dash
        if "Synthetic" in joined and ("\u2014" in joined or "—" in joined or "-" in joined):
            skip_indices.add(i)
            in_title = True
            continue

        # Title continuation: row has mostly empty cells and contains a title keyword
        if in_title:
            empty_ratio = sum(1 for c in cleaned if not c) / len(cleaned) if cleaned else 0
            if empty_ratio >= 0.5 and any(kw in joined for kw in TITLE_KEYWORDS):
                skip_indices.add(i)
                continue
            in_title = False

        # Standalone title fragment: mostly empty row where the ONLY non-empty
        # values are title keywords (e.g., Camelot captures "col_span" or
        # "nested_header" from the PDF title as a separate row)
        if non_empty and len(non_empty) <= 2:
            empty_ratio = sum(1 for c in cleaned if not c) / len(cleaned) if cleaned else 0
            if empty_ratio >= 0.5:
                all_title_kw = all(
                    any(kw in v for kw in TITLE_KEYWORDS) for v in non_empty
                )
                if all_title_kw:
                    skip_indices.add(i)
                    continue

    rows = []
    for i, row in enumerate(raw_rows):
        if i in skip_indices:
            continue
        rows.append([c.strip() for c in row])

    # Merge category-label rows back into data rows (row_span fix)
    rows = _merge_category_label_rows(rows)
    return rows


def _strip_empty_cols(rows: List[List[str]]) -> List[List[str]]:
    """Remove columns that are entirely empty across all rows."""
    if not rows:
        return rows
    max_cols = max(len(r) for r in rows)
    # Pad rows to same length
    padded = [r + [""] * (max_cols - len(r)) for r in rows]
    # Find non-empty columns
    keep = []
    for ci in range(max_cols):
        if any(padded[ri][ci].strip() for ri in range(len(padded))):
            keep.append(ci)
    return [[r[ci] for ci in keep] for r in padded]


def _merge_category_label_rows(rows: List[List[str]]) -> List[List[str]]:
    """Fix category label placement for row_span tables.

    Camelot stream can't detect vertically merged cells.  Category labels
    ("Category A/B/C") appear either as standalone rows or merged with the
    wrong data row (roughly the visual center of the span instead of the
    first row).

    This function:
    1. Detects stream extraction via first data row having empty col 0
    2. Collects all labels (standalone or misplaced)
    3. Strips them out, calculates the correct chunk size
    4. Re-assigns each label to the first row of its chunk

    For lattice extraction (first data row already has a label), the
    labels are already correct and this function returns rows unchanged.
    """
    if len(rows) < 3:
        return rows

    # Collect standalone label rows: only col 0 has content, rest empty.
    # These are the definitive signal of row_span extraction issues.
    _CATEGORY_RE = {"Category A", "Category B", "Category C"}
    standalone_labels = []
    for i, row in enumerate(rows):
        if i == 0:
            continue
        non_empty = [v.strip() for v in row if v.strip()]
        if (len(non_empty) == 1 and row[0].strip()
                and len(row) > 1
                and all(not row[j].strip() for j in range(1, len(row)))):
            standalone_labels.append((i, row[0].strip()))

    # Also detect category labels merged with wrong data rows.
    # Only valid if: (a) first data row has empty col 0, AND
    # (b) the col 0 values match known category label patterns.
    merged_labels = []
    first_data_empty = len(rows) > 1 and not rows[1][0].strip()
    if first_data_empty and not standalone_labels:
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if row[0].strip() in _CATEGORY_RE:
                other_data = [v.strip() for v in row[1:] if v.strip()]
                if other_data:
                    merged_labels.append((i, row[0].strip()))

    all_labels = [(i, t, True) for i, t in standalone_labels] + \
                 [(i, t, False) for i, t in merged_labels]
    all_labels.sort(key=lambda x: x[0])

    if not all_labels:
        return rows

    # Remove standalone label rows, strip col 0 from misplaced rows
    standalone_set = {i for i, _, sa in all_labels if sa}
    merged_set = {i for i, _, sa in all_labels if not sa}

    clean = []
    for i, row in enumerate(rows):
        if i in standalone_set:
            continue
        if i in merged_set:
            new_row = list(row)
            new_row[0] = ""
            clean.append(new_row)
        else:
            clean.append(row)

    # Calculate chunk size and redistribute labels
    n_data = len(clean) - 1  # exclude header
    total = len(all_labels)
    if total == 0:
        return rows
    chunk = max(2, n_data // total)

    label_ptr = 0
    for i in range(1, len(clean)):
        if label_ptr >= total:
            break
        data_offset = i - 1
        if data_offset % chunk == 0 and not clean[i][0].strip():
            clean[i] = list(clean[i])
            clean[i][0] = all_labels[label_ptr][1]
            label_ptr += 1

    return clean


def _flatten_row_values(row: List[str]) -> List[str]:
    """Extract non-empty values from a row, preserving order."""
    return [v.strip() for v in row if v.strip()]


def compare_cells(gt_cells: List[List[str]], extracted_cells: List[List[str]],
                  merge_pattern: str = "none") -> Dict:
    """Compare ground truth cells against extracted cells.

    Uses value-set comparison per row to handle column shifts from merges.

    Returns:
        Dict with match counts and details
    """
    ext = extracted_cells

    # For merged tables, Camelot may add extra empty columns.
    # Compare by extracting non-empty values per row (order-preserving).
    total_gt_vals = 0
    matched = 0
    mismatched = 0
    missing = 0
    extra = 0
    mismatches = []

    n_rows = max(len(gt_cells), len(ext))
    for ri in range(n_rows):
        gt_row = gt_cells[ri] if ri < len(gt_cells) else []
        ext_row = ext[ri] if ri < len(ext) else []

        gt_vals = _flatten_row_values(gt_row)
        ext_vals = _flatten_row_values(ext_row)

        total_gt_vals += len(gt_vals)

        # Compare value by value (order matters)
        n_vals = max(len(gt_vals), len(ext_vals))
        for vi in range(n_vals):
            gt_val = normalize_cell(gt_vals[vi]) if vi < len(gt_vals) else ""
            ext_val = normalize_cell(ext_vals[vi]) if vi < len(ext_vals) else ""

            if not gt_val and not ext_val:
                continue

            if gt_val == ext_val:
                matched += 1
            elif not gt_val and ext_val:
                extra += 1
            elif gt_val and not ext_val:
                missing += 1
                mismatches.append((ri, vi, gt_val, ext_val))
            else:
                mismatched += 1
                mismatches.append((ri, vi, gt_val, ext_val))

    total_compared = matched + mismatched + missing
    accuracy = matched / total_compared if total_compared > 0 else 0.0

    return {
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
        "extra": extra,
        "total_gt_cells": total_gt_vals,
        "accuracy": accuracy,
        "mismatches": mismatches[:20],
    }


def find_s11_output(filename: str, output_base: Path) -> Optional[Path]:
    """Find S11 structural.json for a given PDF filename."""
    stem = filename.replace(".pdf", "")
    s11_path = output_base / stem / "11_json_exporter" / "structural.json"
    if s11_path.exists():
        return s11_path
    return None


def find_s05_output(filename: str, output_base: Path) -> Optional[Path]:
    """Find S05 05_tables.json for a given PDF filename."""
    stem = filename.replace(".pdf", "")
    s05_path = output_base / stem / "05_table_extractor" / "json_output" / "05_tables.json"
    if s05_path.exists():
        return s05_path
    return None


def extract_csv_from_s05(s05_path: Path) -> Optional[str]:
    """Extract CSV content from S05 05_tables.json.

    S05 stores tables with pandas_df (list of row-dicts keyed by column index)
    and sometimes a csv field. We reconstruct CSV from pandas_df for reliability.
    """
    with open(s05_path) as f:
        data = json.load(f)

    tables = data.get("tables", [])
    if not tables:
        return None

    table = tables[0]

    # Try pandas_df first (most reliable — actual cell data)
    pdf = table.get("pandas_df")
    if pdf and isinstance(pdf, list):
        # pdf is a list of dicts like {"0": "val", "1": "val", ...}
        # or {"Unnamed: 0": "val", "col_name": "val", ...}
        rows = []
        for row_dict in pdf:
            # Sort by key to preserve column order
            if all(k.isdigit() for k in row_dict.keys()):
                sorted_keys = sorted(row_dict.keys(), key=int)
            else:
                sorted_keys = list(row_dict.keys())
            vals = []
            for k in sorted_keys:
                v = row_dict[k]
                if v is None or (isinstance(v, float) and str(v) == "nan"):
                    vals.append("")
                else:
                    vals.append(str(v))
            rows.append(vals)

        # Convert to CSV string
        out = io.StringIO()
        writer = csv.writer(out)
        # Add column headers as first row
        if all(k.isdigit() for k in pdf[0].keys()):
            pass  # numeric keys — no header row needed
        else:
            sorted_keys = list(pdf[0].keys()) if not all(
                k.isdigit() for k in pdf[0].keys()
            ) else sorted(pdf[0].keys(), key=int)
            writer.writerow(sorted_keys)
        for row in rows:
            writer.writerow(row)
        return out.getvalue()

    # Fallback: csv field
    csv_text = table.get("csv", "")
    return csv_text if csv_text else None


def extract_csv_from_s11(s11_path: Path) -> Optional[str]:
    """Extract CSV content from S11 structural.json."""
    with open(s11_path) as f:
        data = json.load(f)

    for section in data.get("sections", []):
        for element in section.get("elements", []):
            if element.get("type") == "table":
                return element.get("content", "")
    return None


def main():
    """Validate cell-level accuracy and filter by domain if specified."""
    import argparse
    parser = argparse.ArgumentParser(description="Cell-level accuracy validator")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("/mnt/storage12tb/extractor_data/output/synthetic_validation"))
    parser.add_argument("--domain", type=str, default=None,
                        help="Filter to specific domain")
    parser.add_argument("--border-style", type=str, default=None,
                        help="Filter to specific border style (e.g., thin_grid)")
    parser.add_argument("--merge-pattern", type=str, default=None,
                        help="Filter to specific merge pattern (e.g., col_span)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--save-gt", type=Path, default=None,
                        help="Save ground truth to manifest with cells")
    parser.add_argument("--source", choices=["s05", "s11", "auto"], default="auto",
                        help="Data source: s05 (05_tables.json), s11 (structural.json), auto (s05 first)")
    args = parser.parse_args()

    print("Replaying ground truth generation (seed=42)...")
    gt = replay_ground_truth()
    print(f"  Generated ground truth for {len(gt)} PDFs")

    if args.save_gt:
        print(f"\nSaving ground truth to {args.save_gt}...")
        with open(args.save_gt, "w") as f:
            for name, data in gt.items():
                rec = {"filename": name, **data}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  Saved {len(gt)} records")

    # Filter to single-table only (multi-table is a different challenge)
    single_gt = {k: v for k, v in gt.items() if not v.get("multi_table")}
    print(f"\nValidating {len(single_gt)} single-table PDFs...")

    if args.domain:
        single_gt = {k: v for k, v in single_gt.items() if v["domain"] == args.domain}
        print(f"  Filtered to {len(single_gt)} {args.domain} PDFs")

    if args.border_style:
        single_gt = {k: v for k, v in single_gt.items()
                     if v.get("border_style") == args.border_style}
        print(f"  Filtered to {len(single_gt)} {args.border_style} PDFs")

    if args.merge_pattern:
        single_gt = {k: v for k, v in single_gt.items()
                     if v.get("merge_pattern") == args.merge_pattern}
        print(f"  Filtered to {len(single_gt)} {args.merge_pattern} PDFs")

    # Run validation
    # Track by domain AND by border_style x merge_pattern
    domain_stats = defaultdict(lambda: {"total": 0, "matched_cells": 0,
                                        "total_cells": 0, "perfect": 0,
                                        "failures": []})
    style_stats = defaultdict(lambda: {"total": 0, "matched_cells": 0,
                                       "total_cells": 0, "perfect": 0,
                                       "failures": []})
    overall_matched = 0
    overall_total = 0
    no_output = 0
    s05_used = 0
    s11_used = 0

    for filename, gt_data in sorted(single_gt.items()):
        # Find extraction output: try S05 first (freshest), then S11
        csv_text = None
        source_label = None

        if args.source in ("s05", "auto"):
            s05_path = find_s05_output(filename, args.output_dir)
            if s05_path:
                csv_text = extract_csv_from_s05(s05_path)
                if csv_text:
                    source_label = "s05"
                    s05_used += 1

        if csv_text is None and args.source in ("s11", "auto"):
            s11_path = find_s11_output(filename, args.output_dir)
            if s11_path:
                csv_text = extract_csv_from_s11(s11_path)
                if csv_text:
                    source_label = "s11"
                    s11_used += 1

        if csv_text is None:
            no_output += 1
            continue

        extracted_cells = parse_csv_to_cells(csv_text)
        result = compare_cells(gt_data["cells"], extracted_cells,
                               merge_pattern=gt_data.get("merge_pattern", "none"))

        domain = gt_data["domain"]
        bs = gt_data.get("border_style", "unknown")
        mp = gt_data.get("merge_pattern", "none")
        style_key = f"{bs}/{mp}"

        for stats_dict, key in [(domain_stats, domain), (style_stats, style_key)]:
            stats_dict[key]["total"] += 1
            stats_dict[key]["matched_cells"] += result["matched"]
            stats_dict[key]["total_cells"] += (result["matched"] + result["mismatched"] + result["missing"])
            if result["accuracy"] >= 0.99:
                stats_dict[key]["perfect"] += 1
            if result["accuracy"] < 0.90:
                stats_dict[key]["failures"].append(
                    (filename, f"accuracy={result['accuracy']:.1%}, "
                     f"mismatched={result['mismatched']}, missing={result['missing']}"))

        if args.verbose and result["accuracy"] < 0.99:
            print(f"\n  {filename} [{source_label}]: accuracy={result['accuracy']:.1%}")
            for ri, ci, gt_val, ext_val in result["mismatches"][:5]:
                print(f"    row={ri} col={ci}: GT='{gt_val}' EXT='{ext_val}'")

        overall_matched += result["matched"]
        overall_total += (result["matched"] + result["mismatched"] + result["missing"])

    # Print results
    print(f"\n{'='*70}")
    print(f"CELL-LEVEL ACCURACY REPORT")
    print(f"{'='*70}")
    print(f"Sources: S05={s05_used}, S11={s11_used}, not found={no_output}")
    print()

    # Domain breakdown
    print("BY DOMAIN:")
    for domain in sorted(domain_stats.keys()):
        ds = domain_stats[domain]
        cell_acc = ds["matched_cells"] / ds["total_cells"] if ds["total_cells"] > 0 else 0
        marker = " ✓" if cell_acc >= 0.95 else " ✗"
        print(f"  {domain:15s}  tables={ds['total']:4d}  "
              f"perfect={ds['perfect']:4d}  "
              f"cell_accuracy={cell_acc:.1%}{marker}  "
              f"({ds['matched_cells']}/{ds['total_cells']} cells)")
        if ds["failures"]:
            for fname, reason in ds["failures"][:3]:
                print(f"    FAIL: {fname} — {reason}")
            if len(ds["failures"]) > 3:
                print(f"    ... and {len(ds['failures']) - 3} more failures")

    # Border-style x merge-pattern breakdown
    print(f"\nBY BORDER_STYLE / MERGE_PATTERN:")
    for style_key in sorted(style_stats.keys()):
        ss = style_stats[style_key]
        cell_acc = ss["matched_cells"] / ss["total_cells"] if ss["total_cells"] > 0 else 0
        marker = " ✓" if cell_acc >= 0.95 else " ✗"
        print(f"  {style_key:35s}  tables={ss['total']:3d}  "
              f"cell_accuracy={cell_acc:.1%}{marker}  "
              f"({ss['matched_cells']}/{ss['total_cells']})")

    overall_acc = overall_matched / overall_total if overall_total > 0 else 0
    print(f"\n  {'OVERALL':15s}  cell_accuracy={overall_acc:.1%}  "
          f"({overall_matched}/{overall_total} cells)")
    print(f"{'='*70}")

    return 0 if overall_acc >= 0.95 else 1


if __name__ == "__main__":
    sys.exit(main())
