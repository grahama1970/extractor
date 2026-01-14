#!/usr/bin/env python3
"""
generate_complex_fixture.py

Generates a synthetic, "messy" PDF fixture for stress-testing the extraction pipeline.
Also generates "Ground Truth" artifacts (MD/JSON) matching the generated content.
Driven by `tricky_pdf_elements.yml` configuration.

Usage:
    python generate_complex_fixture.py data/input/complex_fixture.pdf --config tricky_pdf_elements.yml
"""

import fitz  # PyMuPDF
import sys
import json
import yaml
from pathlib import Path

def create_messy_fixture(output_path: Path, config_path: Path = None):
    # Load Config
    config = {}
    if config_path and config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text())
            print(f"Loaded config from {config_path}")
        except Exception as e:
            print(f"Error loading config: {e}")
            
    # Defaults handled by get() calls or fallback logic
    
    doc = fitz.open()
    
    # Ground Truth Containers
    expected_data = [] 
    expected_md_lines = []
    
    # --- Page 1: Introduction & Ambiguity ---
    p1 = doc.new_page()
    
    # Header
    p1.insert_text((50, 50), "1. Introduction", fontsize=18, fontname="Helvetica-Bold")
    p1.insert_text((50, 80), "This document is a synthetic test fixture.", fontsize=11)
    
    expected_md_lines.append("# 1. Introduction")
    expected_md_lines.append("This document is a synthetic test fixture.\n")
    
    # Inject Ambiguous Headers from Config
    y = 110
    ambiguous_headers = config.get("ambiguous_headers", [])
    if not ambiguous_headers: # Default fallback
        ambiguous_headers = [{"text": "E = mc^2 is a famous equation."}]
        
    for item in ambiguous_headers:
        text = item.get("text", "")
        fontsize = item.get("size", 11)
        font = item.get("font", "Helvetica")
        
        p1.insert_text((50, y), text, fontsize=fontsize, fontname=font)
        expected_md_lines.append(text) # In MD, it's just text, NOT a header
        y += 20
    
    expected_md_lines.append("") # Spacer
        
    # Start Table
    y = max(y + 20, 200)
    p1.insert_text((50, y), "Table 1: System Data (Configured)", fontsize=10, fontname="Helvetica-Oblique")
    y += 20
    
    expected_md_lines.append("### Table 1: System Data (Configured)")
    
    # Table Header
    p1.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0))
    p1.insert_text((60, y+14), "ID", fontsize=10, color=(1,1,1))
    p1.insert_text((150, y+14), "Value", fontsize=10, color=(1,1,1))
    p1.insert_text((300, y+14), "Description", fontsize=10, color=(1,1,1))
    y += 20
    
    expected_md_lines.append("| ID | Value | Description |")
    expected_md_lines.append("|---|---|---|")
    
    table_rows = []
    
    # Rows 1-10
    false_header = config.get("tables", {}).get("false_header_text", "SECTION 5 START")
    
    for i in range(10):
        c1, c2 = f"R{i}", f"VAL_{i}"
        
        # Ambiguous data looking like header
        if i == 5:
             c3 = false_header # Trap!
             p1.insert_text((300, y+14), c3, fontsize=10) 
        else:
             c3 = f"Data row {i}"
             p1.insert_text((300, y+14), c3, fontsize=10)
             
        p1.insert_text((60, y+14), c1, fontsize=10)
        p1.insert_text((150, y+14), c2, fontsize=10)
        p1.draw_line((50, y+20), (550, y+20))
        y += 20
        
        row_obj = {"ID": c1, "Value": c2, "Description": c3}
        table_rows.append(row_obj)
        expected_md_lines.append(f"| {c1} | {c2} | {c3} |")
        
    p1.insert_text((50, y+20), "(Table continues on next page...)", fontsize=9, fontname="Helvetica-Oblique")
    expected_md_lines.append("*(Table continues on next page...)*\n")

    # --- Page 2: Table Continuation & Requirements ---
    p2 = doc.new_page()
    
    # Table Continuation Header
    y = 50
    p2.insert_text((50, y), "Table 1 (Continued)", fontsize=10, fontname="Helvetica-Oblique")
    y += 20
    p2.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0.8, 0.8, 0.8), fill=(0.8,0.8,0.8)) # Gray header
    p2.insert_text((60, y+14), "ID", fontsize=10)
    p2.insert_text((150, y+14), "Value", fontsize=10)
    p2.insert_text((300, y+14), "Description", fontsize=10)
    y += 20
    
    # Rows 10-15
    for i in range(10, 16):
        c1, c2, c3 = f"R{i}", f"VAL_{i}", f"Data row {i}"
        p2.insert_text((60, y+14), c1, fontsize=10)
        p2.insert_text((150, y+14), c2, fontsize=10)
        p2.insert_text((300, y+14), c3, fontsize=10)
        p2.draw_line((50, y+20), (550, y+20))
        y += 20
        
        row_obj = {"ID": c1, "Value": c2, "Description": c3}
        table_rows.append(row_obj)
        expected_md_lines.append(f"| {c1} | {c2} | {c3} |")
        
    # Add Table to Expected Data
    is_strict_table = config.get("tables", {}).get("strict_verification", False)
    
    # Serialize to CSV for verification
    import io
    import csv
    output = io.StringIO()
    if table_rows:
        writer = csv.DictWriter(output, fieldnames=table_rows[0].keys())
        writer.writeheader()
        writer.writerows(table_rows)
    csv_text = output.getvalue()

    expected_data.append({
        "id": "TBL-001",
        "type": "Table",
        "title": "Table 1: System Data (Configured)",
        "content": table_rows,
        "text": csv_text,  # CSV representation for fuzzy matching
        "strict_verification": is_strict_table
    })

    y += 50
    p2.insert_text((50, y), "(End of Table 1)", fontsize=9, fontname="Helvetica-Oblique")
    
    # --- Page 3: Requirements (Isolated) ---
    p3 = doc.new_page()
    p2 = p3 # Reuse p2 variable to minimize code changes downstream
    y = 50
    p2.insert_text((50, y), "2. Requirements", fontsize=18, fontname="Helvetica-Bold")
    y += 30
    
    expected_md_lines.append("\n# 2. Requirements")
    
    # Valid Requirements
    reqs = [
        ("REQ-SYN-001", "The system shall handle synthetic data."),
        ("REQ-SYN-002", "The system must ignore false headers.")
    ]
    
    for rid, rtext in reqs:
        full_text = f"{rid}: {rtext}"
        p2.insert_text((50, y), full_text, fontsize=11)
        y += 20
        
        expected_md_lines.append(f"- **{rid}**: {rtext}")
        expected_data.append({
            "id": rid,
            "type": "Requirement",
            "text": full_text
        })
        
    # False Positives from Config
    false_positives = config.get("false_positives", [])
    if false_positives:
        y += 10
        p2.insert_text((50, y), "Examples (Non-Normative):", fontsize=12, fontname="Helvetica-Bold")
        y += 20
        expected_md_lines.append("\n## Examples (Non-Normative)")
        
        for fp in false_positives:
            text = fp.get("text", "")
            p2.insert_text((50, y), text, fontsize=11, color=(0.3, 0.3, 0.3))
            y += 20
            # These are NOT added to expected_data because they SHOULD NOT be extracted (that's the test)
            expected_md_lines.append(text) # Just text in MD

    # Critical Content (Golden Data) from Profile
    critical_content = config.get("critical_content", [])
    if critical_content:
        y += 20
        p2.insert_text((50, y), "Critical Requirements:", fontsize=12, fontname="Helvetica-Bold")
        y += 20
        expected_md_lines.append("\n## Critical Requirements")
        
        for item in critical_content:
            rid = item.get("id")
            rtext = item.get("text")
            full_text = f"{rid}: {rtext}"
            
            p2.insert_text((50, y), full_text, fontsize=11, color=(0,0,0)) # Normal logic
            y += 20
            
            expected_md_lines.append(f"- **{rid}**: {rtext}")
            
            # Add to expected with STRICT flag
            expected_data.append({
                "id": rid,
                "type": item.get("type", "Requirement"),
                "text": rtext, # Use body only for strict check
                "strict_verification": item.get("strict_verification", True)
            })

    # "Boilerplate"
    y = 750
    noise_texts = config.get("text_noise", ["Copyright 2024"])
    for i, noise in enumerate(noise_texts):
        p2.insert_text((50, y + (i*10)), noise, fontsize=9, color=(0.5, 0.5, 0.5))

    # Save PDF
    doc.save(output_path)
    print(f"Generated PDF: {output_path}")
    
    # Save Markdown
    md_path = output_path.with_name(output_path.stem + "_expected.md")
    md_path.write_text("\n".join(expected_md_lines))
    print(f"Generated MD:  {md_path}")
    
    # Save JSON with Metrics
    output_obj = {
        "metrics": {
            "requirement_count": len([i for i in expected_data if i['type'] == 'Requirement']),
            "table_count": len([i for i in expected_data if i['type'] == 'Table']),
            "total_items": len(expected_data)
        },
        "content": expected_data
    }
    json_path = output_path.with_name(output_path.stem + "_expected.json")
    json_path.write_text(json.dumps(output_obj, indent=2))
    print(f"Generated JSON: {json_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="Output PDF path")
    parser.add_argument("--config", type=Path, help="Optional tricky_elements.yml config")
    args = parser.parse_args()
    
    create_messy_fixture(args.output, args.config)
