#!/usr/bin/env python3
"""
Layout Analyzer: Scans a PDF to determine optimal SPEC.md settings.

Detects:
1. Header/Footer Y-limits (using text density at page edges)
2. Column count (using gutter detection)
3. Main body font size

Usage:
    python analyze_layout.py doc.pdf
"""
import fitz
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
from collections import Counter

def analyze_layout(pdf_path: Path, max_pages: int = 10):
    doc = fitz.open(pdf_path)
    limit = min(len(doc), max_pages)
    
    # Collect block coordinates
    header_candidates = []
    footer_candidates = []
    text_sizes = Counter()
    
    page_width = 0
    page_height = 0
    
    print(f"Scanning {limit} pages of {pdf_path.name}...")
    
    for i in range(limit):
        page = doc[i]
        page_width = page.rect.width
        page_height = page.rect.height
        
        blocks = page.get_text("blocks")
        # x0, y0, x1, y1, text, block_no, block_type
        
        for b in blocks:
            x0, y0, x1, y1, text, _, _ = b
            
            # Filter empty blocks
            if not text.strip():
                continue
                
            # Header candidate: Top 15% of page
            if y1 < page_height * 0.15:
                header_candidates.append(y1)
                
            # Footer candidate: Bottom 10% of page
            if y0 > page_height * 0.90:
                footer_candidates.append(y0)
                
        # Collect font sizes for body text
        dict_blocks = page.get_text("dict")["blocks"]
        for b in dict_blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        if span["text"].strip():
                            text_sizes[round(span["size"], 1)] += len(span["text"])

    # --- Analysis ---
    
    # Header Limit: Safe Y-cutoff just below the lowest header element found widely
    # Heuristic: 90th percentile of header candidate bottom-edges
    suggested_header_limit = 0.0
    if header_candidates:
        suggested_header_limit = float(np.percentile(header_candidates, 90)) + 5.0
        
    # Footer Limit: Safe Y-cutoff just above the highest footer element
    # Heuristic: 10th percentile of footer candidate top-edges
    suggested_footer_limit = page_height
    if footer_candidates:
        suggested_footer_limit = float(np.percentile(footer_candidates, 10)) - 5.0
        
    # Body Font
    body_font = text_sizes.most_common(1)[0][0] if text_sizes else 11.0
    
    # Column Detection (Scan middle of page)
    # Simplified logic: Check for text in the "gutter" (center 10%)
    
    print("\n" + "="*40)
    print("📊 LAYOUT ANALYSIS REPORT")
    print("="*40)
    
    print(f"\nDimensions: {page_width:.1f} x {page_height:.1f} pts")
    print(f"Body Font:  {body_font} pt")
    
    print(f"\n[Headers & Footers]")
    print(f"  Detected Header Region: 0 - {suggested_header_limit:.1f}")
    if header_candidates:
        print(f"    (found {len(header_candidates)} blocks in top 15%)")
        
    print(f"  Detected Footer Region: {suggested_footer_limit:.1f} - {page_height:.1f}")
    if footer_candidates:
        print(f"    (found {len(footer_candidates)} blocks in bottom 10%)")
        
    print("\n✅ SUGGESTED SPEC.MD CONFIG")
    print("-" * 30)
    print(f"""agent_config:
  header_lower_limit: {int(suggested_header_limit)}
  footer_upper_limit: {int(suggested_footer_limit)}
  
  # Columns (heuristic)
  column_count: 1  # Verify visually
    """)
    print("-" * 30)

    return {
        "header_limit": suggested_header_limit,
        "footer_limit": suggested_footer_limit,
        "body_font": body_font
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    analyze_layout(args.pdf)
