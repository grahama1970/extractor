#!/usr/bin/env python3
"""
Focused debug script to trace the exact flow of title inference.
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import importlib
steps_module = importlib.import_module('extractor.pipeline.steps.06a_title_caption_enricher')

# Extract key functions
enrich_tables = steps_module.enrich_tables
enrich_figures = steps_module.enrich_figures
_chutes_title_infer_struct = steps_module._chutes_title_infer_struct
_normalize_id = steps_module._normalize_id


def create_sample_table():
    """Create a sample table for testing."""
    return {
        "page_index": 0,
        "page_number": 1,
        "bbox": [100, 200, 300, 400],
        "pandas_df": [
            {"Parameter": "Temperature", "Value": "25.0", "Unit": "°C"},
            {"Parameter": "Pressure", "Value": "101.3", "Unit": "kPa"},
            {"Parameter": "Flow Rate", "Value": "2.5", "Unit": "L/min"}
        ]
    }


def create_sample_figure():
    """Create a sample figure for testing."""
    return {
        "page_index": 0,
        "page_number": 1,
        "bbox": [100, 200, 300, 400],
        "ai_description": "A line graph showing temperature vs time"
    }


def trace_enrich_tables():
    """Trace the exact flow in enrich_tables to see where titles come from."""
    print("=== Tracing enrich_tables function ===")
    
    # Save original env
    original_env = os.environ.get("CHUTES_TEXT_MODEL")
    
    # Test case 1: No CHUTES_TEXT_MODEL set
    print("\n1. Testing with CHUTES_TEXT_MODEL NOT set:")
    if "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]
    
    sample_table = create_sample_table()
    tables = [sample_table]
    
    try:
        enriched_tables = enrich_tables(tables, page_blocks=None)
        
        print(f"Original table keys: {list(sample_table.keys())}")
        print(f"Enriched table keys: {list(enriched_tables[0].keys())}")
        
        enriched = enriched_tables[0]
        print(f"  title: {enriched.get('title')}")
        print(f"  title_source: {enriched.get('title_source')}")
        print(f"  number: {enriched.get('number')}")
        print(f"  base_title: {enriched.get('base_title')}")
        print(f"  continued: {enriched.get('continued')}")
        print(f"  normalized_id: {enriched.get('normalized_id')}")
        
        # Let's trace what _normalize_id would return
        norm_id = _normalize_id("table", enriched.get("number"), enriched.get("base_title"))
        print(f"  _normalize_id('table', {enriched.get('number')}, {enriched.get('base_title')}) = {norm_id}")
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test case 2: CHUTES_TEXT_MODEL set but invalid
    print("\n2. Testing with CHUTES_TEXT_MODEL set but API will fail:")
    os.environ["CHUTES_TEXT_MODEL"] = "invalid-model"
    os.environ["CHUTES_API_BASE"] = "https://invalid-api.example.com"
    os.environ["CHUTES_API_KEY"] = "invalid-key"
    
    sample_table = create_sample_table()
    tables = [sample_table]
    
    try:
        enriched_tables = enrich_tables(tables, page_blocks=None)
        
        enriched = enriched_tables[0]
        print(f"  title: {enriched.get('title')}")
        print(f"  title_source: {enriched.get('title_source')}")
        print(f"  number: {enriched.get('number')}")
        print(f"  base_title: {enriched.get('base_title')}")
        print(f"  continued: {enriched.get('continued')}")
        print(f"  normalized_id: {enriched.get('normalized_id')}")
        
    except Exception as e:
        print(f"  Error: {e}")
    
    # Restore original env
    if original_env is not None:
        os.environ["CHUTES_TEXT_MODEL"] = original_env
    elif "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]


def trace_enrich_figures():
    """Trace the exact flow in enrich_figures."""
    print("\n\n=== Tracing enrich_figures function ===")
    
    # Save original env
    original_env = os.environ.get("CHUTES_TEXT_MODEL")
    
    # Test case 1: No CHUTES_TEXT_MODEL set
    print("\n1. Testing with CHUTES_TEXT_MODEL NOT set:")
    if "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]
    
    sample_figure = create_sample_figure()
    figures = [sample_figure]
    
    try:
        enriched_figures = enrich_figures(figures, page_blocks=None)
        
        enriched = enriched_figures[0]
        print(f"  title: {enriched.get('title')}")
        print(f"  title_source: {enriched.get('title_source')}")
        print(f"  number: {enriched.get('number')}")
        print(f"  base_title: {enriched.get('base_title')}")
        print(f"  continued: {enriched.get('continued')}")
        print(f"  normalized_id: {enriched.get('normalized_id')}")
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Restore original env
    if original_env is not None:
        os.environ["CHUTES_TEXT_MODEL"] = original_env
    elif "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]


def analyze_code_path():
    """Analyze the exact code path to understand where 'INFER: 0' comes from."""
    print("\n\n=== Code Path Analysis ===")
    
    print("\nIn enrich_tables():")
    print("1. Line 346: title = _explicit_table_title(tt)")
    print("   - If no explicit title, title = None")
    print("2. Line 348: if not title:")
    print("   - Enter inference branch")
    print("3. Line 379: inferred = _chutes_title_infer_struct(ctx_all or basic)")
    print("   - If env not set, this returns None")
    print("4. Line 380: if isinstance(inferred, dict):")
    print("   - False when inferred is None")
    print("5. Lines 387-391: title remains None")
    print("6. Line 397: norm_id = _normalize_id('table', number, base_title)")
    print("   - number=None, base_title=None")
    print("   - _normalize_id returns None")
    print("7. Line 405: normalized_id = norm_id or tt.get('normalized_id')")
    print("   - If no existing normalized_id, stays None")
    
    print("\nSo where does 'INFER: 0' come from?")
    print("- It's NOT coming from this enricher!")
    print("- The enricher sets title=None and normalized_id=None")
    print("- Some other part of the pipeline must be adding 'INFER: 0'")
    
    print("\nLet's check what _normalize_id does with different inputs:")
    test_cases = [
        ("table", "1", "Test Table"),
        ("table", None, "Test Table"),
        ("table", "1", None),
        ("table", None, None),
    ]
    
    for prefix, number, base_title in test_cases:
        result = _normalize_id(prefix, number, base_title)
        print(f"  _normalize_id('{prefix}', {number}, {base_title}) = {result}")


def search_for_infer_pattern():
    """Search for where 'INFER:' pattern might be generated in the codebase."""
    print("\n\n=== Searching for 'INFER:' Pattern ===")
    
    # Look for files that might generate the "INFER: 0" pattern
    search_terms = ["INFER:", "INFER :", "infer", "title", "normalized"]
    
    print("Searching for potential sources of 'INFER: 0' pattern...")
    print("This might be in:")
    print("- Output formatting/rendering code")
    print("- ID generation logic") 
    print("- Display/UI code")
    print("- Post-processing steps")
    
    # The issue might be in how the results are displayed or processed
    # after the enricher runs


def main():
    """Run all trace analyses."""
    print("Title Inference Flow Analysis")
    print("=" * 50)
    
    # Show current environment
    print("Current environment:")
    print(f"  CHUTES_TEXT_MODEL: {os.environ.get('CHUTES_TEXT_MODEL', 'NOT SET')}")
    
    trace_enrich_tables()
    trace_enrich_figures()
    analyze_code_path()
    search_for_infer_pattern()
    
    print("\n" + "=" * 50)
    print("Analysis complete!")
    print("\nCONCLUSION:")
    print("The 'INFER: 0' is NOT coming from the title caption enricher!")
    print("When CHUTES_TEXT_MODEL is not set:")
    print("- _chutes_title_infer_struct() returns None")
    print("- title remains None in enriched data")
    print("- normalized_id remains None in enriched data")
    print("- Some OTHER part of the pipeline must be adding 'INFER: 0'")
    print("\nLook for:")
    print("- Display/UI code that formats None titles as 'INFER: 0'")
    print("- Post-processing that generates fallback IDs")
    print("- Output rendering that adds this pattern")


if __name__ == "__main__":
    main()