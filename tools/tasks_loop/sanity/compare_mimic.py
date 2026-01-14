#!/usr/bin/env python3
"""
sanity/compare_mimic.py - Verify Structural Parity between Original and Mimic PDF.

Usage:
    python sanity/compare_mimic.py --original path/to/orig.pdf --mimic path/to/mimic.pdf
"""

import sys
import argparse
from pathlib import Path
import json
import logging

# Add tools/tasks_loop to path to import scanner
TASKS_LOOP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASKS_LOOP_DIR / "utils"))

from fixture_scanner import PDFScanner

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("compare_mimic")

def scan_pdf(path: Path) -> dict:
    if not path.exists():
        logger.error(f"File not found: {path}")
        sys.exit(1)
    
    scanner = PDFScanner(path)
    scanner.analyze_styles()
    scanner.convert()
    return scanner.get_spec()

def compare_specs(orig_spec: dict, mimic_spec: dict):
    orig_secs = orig_spec["sections"]
    mimic_secs = mimic_spec["sections"]
    
    logger.info(f"Original Sections: {len(orig_secs)}")
    logger.info(f"Mimic Sections:    {len(mimic_secs)}")
    
    # 1. Section Count
    if len(orig_secs) != len(mimic_secs):
        logger.error(f"❌ Section count mismatch! {len(orig_secs)} vs {len(mimic_secs)}")
        sys.exit(1)
        
    # 2. Section Titles (Fuzzy)
    mismatches = 0
    for i, (o, m) in enumerate(zip(orig_secs, mimic_secs)):
        # Mimic might have random text if we didn't preserve titles, 
        # but fixture_scanner normally preserves titles for headers.
        o_title = o["title"].strip()
        m_title = m["title"].strip()
        
        # Check if identical (ideal) mimic preserves title text
        if o_title != m_title:
             logger.warning(f"⚠️ Title Mismatch [{i}]: '{o_title}' vs '{m_title}'")
             mismatches += 1
    
    if mismatches == 0:
        logger.info("✅ All Section Titles Match exactly.")
    else:
        logger.info(f"ℹ️  {mismatches} title differences (expected if using lorem output for headers, but headers should be text)")

    # 3. Content item counts (Just info)
    o_content = sum(len(s.get("content", [])) for s in orig_secs)
    m_content = sum(len(s.get("content", [])) for s in mimic_secs)
    logger.info(f"Content Items: {o_content} (Original) vs {m_content} (Mimic)")
    
    print("\n✅ MIMIC STRUCTURE VERIFIED")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--mimic", required=True, type=Path)
    args = parser.parse_args()
    
    logger.info(f"Comparing:")
    logger.info(f"  Orig:  {args.original}")
    logger.info(f"  Mimic: {args.mimic}")
    
    s1 = scan_pdf(args.original)
    s2 = scan_pdf(args.mimic)
    
    compare_specs(s1, s2)

if __name__ == "__main__":
    main()
