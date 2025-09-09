#!/usr/bin/env python3
"""
Test the complete pipeline with ACTUAL problematic headers (FRONT, END, STEM).
This demonstrates the real issue and proves the solution works.
"""
import asyncio
import json
from pathlib import Path

# Test POCs with problematic data
async def test_pipeline():
    print("=== TESTING PIPELINE WITH PROBLEMATIC HEADERS ===\n")
    
    # 1. Create test data with the EXACT problem
    test_blocks = [
        {
            "block_type": "Text",
            "text": "This is normal paragraph text before the table.",
            "bbox": [70, 100, 500, 120],
            "page": 1
        },
        {
            "block_type": "SectionHeader",  # WRONG! This is a table cell
            "text": "FRONT",
            "bbox": [200, 150, 250, 165],
            "page": 1
        },
        {
            "block_type": "SectionHeader",  # WRONG! This is a table cell
            "text": "END",
            "bbox": [260, 150, 300, 165],
            "page": 1
        },
        {
            "block_type": "SectionHeader",  # WRONG! This is a table cell
            "text": "STEM",
            "bbox": [310, 150, 360, 165],
            "page": 1
        },
        {
            "block_type": "SectionHeader",  # WRONG! This is a table cell
            "text": "SUBSY",
            "bbox": [370, 150, 420, 165],
            "page": 1
        },
        {
            "block_type": "Table",
            "text": "Table data rows below headers",
            "bbox": [200, 170, 420, 250],
            "page": 1
        },
        {
            "block_type": "SectionHeader",  # CORRECT - this is a real header
            "text": "2.3 Methodology",
            "bbox": [70, 300, 300, 320],
            "page": 1,
            "font_size": 16,
            "font_weight": 700
        }
    ]
    
    print("INPUT BLOCKS:")
    print(f"Total blocks: {len(test_blocks)}")
    print(f"Misclassified as SectionHeader: {sum(1 for b in test_blocks if b['block_type'] == 'SectionHeader')}")
    for b in test_blocks:
        if b['block_type'] == 'SectionHeader':
            print(f"  - '{b['text']}' (type: {b['block_type']})")
    
    # 2. Run POC 01 - Add UUIDs
    print("\n--- RUNNING POC 01: Add UUIDs ---")
    from poc_01_marker_extraction import add_uuids_to_blocks
    blocks_with_uuids = add_uuids_to_blocks(test_blocks)
    print(f"✓ Added UUIDs to {len(blocks_with_uuids)} blocks")
    
    # 3. Run POC 02 - Detect suspicious headers
    print("\n--- RUNNING POC 02: Detect Suspicious Headers ---")
    from poc_02_relabel_suspicious import identify_suspicious_blocks, is_likely_real_header
    
    suspicious = identify_suspicious_blocks(blocks_with_uuids)
    print(f"✓ Found {len(suspicious)} suspicious headers:")
    
    for s in suspicious:
        print(f"\n  Block: '{s['text']}'")
        print(f"  Score: {s['suspicion_score']:.2f}")
        print(f"  Reasons: {', '.join(s['suspicion_reasons'])}")
        print(f"  Is likely real header: {is_likely_real_header(s['text'])}")
    
    # 4. Show what SHOULD happen
    print("\n--- EXPECTED CORRECTIONS ---")
    expected_corrections = {
        "FRONT": "TableCell",
        "END": "TableCell", 
        "STEM": "TableCell",
        "SUBSY": "TableCell",
        "2.3 Methodology": "SectionHeader"  # Should remain unchanged
    }
    
    print("\nExpected results:")
    for text, expected_type in expected_corrections.items():
        current = next((b for b in blocks_with_uuids if b['text'] == text), None)
        if current:
            print(f"  '{text}': {current['block_type']} → {expected_type}")
    
    # 5. Verify detection accuracy
    print("\n--- VERIFICATION ---")
    detected_garbage = {s['text'] for s in suspicious}
    expected_garbage = {"FRONT", "END", "STEM", "SUBSY"}
    
    print(f"✓ Correctly detected: {detected_garbage & expected_garbage}")
    print(f"✗ Missed: {expected_garbage - detected_garbage}")
    print(f"✗ False positives: {detected_garbage - expected_garbage}")
    
    success = detected_garbage == expected_garbage
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}: Detection accuracy = {len(detected_garbage & expected_garbage)}/{len(expected_garbage)}")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(test_pipeline())
    exit(0 if success else 1)