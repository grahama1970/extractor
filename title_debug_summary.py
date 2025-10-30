#!/usr/bin/env python3
"""
Comprehensive debug summary for the "INFER: 0" title issue.

This script shows exactly what's happening and where the issue originates.
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import importlib
steps_module = importlib.import_module('extractor.pipeline.steps.06a_title_caption_enricher')
table_module = importlib.import_module('extractor.pipeline.steps.05_table_extractor')

# Extract key functions
e_enrich_tables = steps_module.enrich_tables
e_enrich_figures = steps_module.enrich_figures
# The function is private, we'll access it through the module's internal namespace
t_infer_title_with_scillm = getattr(table_module, '_infer_title_with_scillm', None)


def show_current_state():
    """Show the current environment and what's happening."""
    print("=" * 70)
    print("TITLE INFERENCE ISSUE - COMPREHENSIVE ANALYSIS")
    print("=" * 70)
    
    print(f"\nCurrent Environment:")
    env_vars = ["CHUTES_TEXT_MODEL", "CHUTES_API_BASE", "CHUTES_API_KEY", "STAGE05_LLM_INFER"]
    for var in env_vars:
        value = os.environ.get(var, "NOT SET")
        if value and len(value) > 30:
            value = value[:30] + "..."
        print(f"  {var}: {value}")
    
    print(f"\nKey Functions:")
    print(f"  1. require_scillm_env() - Checks if CHUTES_TEXT_MODEL is set")
    print(f"  2. _chutes_title_infer_struct() - 06a enricher inference")
    print(f"  3. _infer_title_with_scillm() - 05 table extractor inference")
    print(f"  4. STAGE05_LLM_INFER env var - Controls Stage 05 inference")


def demonstrate_issue():
    """Demonstrate exactly what's happening."""
    print(f"\n" + "=" * 50)
    print("ISSUE DEMONSTRATION")
    print("=" * 50)
    
    # Save original state
    original_env = os.environ.get("CHUTES_TEXT_MODEL")
    original_stage05 = os.environ.get("STAGE05_LLM_INFER")
    
    print(f"\nSCENARIO 1: CHUTES_TEXT_MODEL is NOT set (current issue)")
    print("-" * 50)
    
    # Remove CHUTES_TEXT_MODEL to simulate the issue
    if "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]
    
    # Test require_scillm_env
    from extractor.pipeline.utils.preflight import require_scillm_env
    ok, reason = require_scillm_env()
    print(f"require_scillm_env() -> ok={ok}, reason='{reason}'")
    
    # Test 06a enricher inference
    sample_context = "Header: A | B | C\nSamples:\n1 | 2 | 3"
    result = steps_module._chutes_title_infer_struct(sample_context)
    print(f"_chutes_title_infer_struct() -> {result}")
    
    # Test 05 table extractor inference
    if t_infer_title_with_scillm:
        stage05_result = t_infer_title_with_scillm(sample_context)
        print(f"_infer_title_with_scillm() -> {stage05_result}")
    else:
        print(f"_infer_title_with_scillm() -> Function not available (private)")
        stage05_result = None
    
    print(f"\nResult: NO INFERENCE HAPPENS")
    print(f"The functions return None, so no 'INFER:' titles are generated.")
    
    print(f"\nSCENARIO 2: CHUTES_TEXT_MODEL is set but STAGE05_LLM_INFER is off")
    print("-" * 50)
    
    # Set CHUTES_TEXT_MODEL but keep STAGE05_LLM_INFER off
    os.environ["CHUTES_TEXT_MODEL"] = "test-model"
    os.environ["STAGE05_LLM_INFER"] = "0"
    
    ok, reason = require_scillm_env()
    print(f"require_scillm_env() -> ok={ok}, reason='{reason}'")
    
    result = steps_module._chutes_title_infer_struct(sample_context)
    print(f"_chutes_title_infer_struct() -> {result}")
    
    if t_infer_title_with_scillm:
        stage05_result = t_infer_title_with_scillm(sample_context)
        print(f"_infer_title_with_scillm() -> {stage05_result}")
    else:
        print(f"_infer_title_with_scillm() -> Function not available (private)")
        stage05_result = None
    
    print(f"\nResult: 06a enricher would work, but 05 extractor is disabled")
    
    print(f"\nSCENARIO 3: Both are enabled (but we'll use invalid API)")
    print("-" * 50)
    
    os.environ["STAGE05_LLM_INFER"] = "1"
    os.environ["CHUTES_API_BASE"] = "https://invalid-api.example.com"
    os.environ["CHUTES_API_KEY"] = "invalid-key"
    
    result = steps_module._chutes_title_infer_struct(sample_context, timeout=2.0)
    print(f"_chutes_title_infer_struct() -> {result}")
    
    if t_infer_title_with_scillm:
        stage05_result = t_infer_title_with_scillm(sample_context, timeout=2.0)
        print(f"_infer_title_with_scillm() -> {stage05_result}")
    else:
        print(f"_infer_title_with_scillm() -> Function not available (private)")
        stage05_result = None
    
    print(f"\nResult: Both would attempt inference but fail due to invalid API")
    
    # Restore original state
    if original_env is not None:
        os.environ["CHUTES_TEXT_MODEL"] = original_env
    elif "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]
        
    if original_stage05 is not None:
        os.environ["STAGE05_LLM_INFER"] = original_stage05
    elif "STAGE05_LLM_INFER" in os.environ:
        del os.environ["STAGE05_LLM_INFER"]


def find_infer_zero_source():
    """Find where 'INFER: 0' actually comes from."""
    print(f"\n" + "=" * 50)
    print("FINDING THE SOURCE OF 'INFER: 0'")
    print("=" * 50)
    
    print(f"\nSearching the codebase for 'INFER: 0' pattern...")
    
    # Search for the pattern
    import subprocess
    result = subprocess.run([
        "grep", "-r", "INFER.*0", "src/", "--include=*.py"
    ], capture_output=True, text=True)
    
    if result.stdout:
        print(f"Found patterns:")
        print(result.stdout)
    else:
        print(f"No exact 'INFER: 0' patterns found in Python code.")
    
    # Search more broadly
    result = subprocess.run([
        "grep", "-r", "INFER:", "src/", "--include=*.py", "-n"
    ], capture_output=True, text=True)
    
    if result.stdout:
        print(f"\nAll 'INFER:' patterns in source code:")
        print(result.stdout)
    
    # Check if it's in output files
    print(f"\nChecking recent output files...")
    output_dirs = [
        "data/results/pipeline",
        "data/output", 
        "tmp",
        "artifacts"
    ]
    
    for dir_path in output_dirs:
        path = Path(dir_path)
        if path.exists():
            json_files = list(path.rglob("*.json"))[:5]  # Check first 5 JSON files
            if json_files:
                print(f"\nChecking {dir_path} for 'INFER: 0' patterns...")
                for json_file in json_files:
                    try:
                        with open(json_file) as f:
                            content = f.read()
                            if "INFER: 0" in content:
                                print(f"  Found 'INFER: 0' in {json_file}")
                                # Show context
                                lines = content.split('\n')
                                for i, line in enumerate(lines):
                                    if "INFER: 0" in line:
                                        start = max(0, i-2)
                                        end = min(len(lines), i+3)
                                        print(f"    Context around line {i+1}:")
                                        for j in range(start, end):
                                            marker = ">>> " if j == i else "    "
                                            print(f"{marker}{lines[j]}")
                                break
                    except Exception as e:
                        continue


def analyze_stage05_vs_stage06a():
    """Compare Stage 05 vs Stage 06a behavior."""
    print(f"\n" + "=" * 50)
    print("STAGE 05 vs STAGE 06a COMPARISON")
    print("=" * 50)
    
    print(f"\nStage 05 Table Extractor:")
    print(f"- Function: _infer_title_with_scillm()")
    print(f"- Environment: STAGE05_LLM_INFER (default: '0' = OFF)")
    print(f"- When disabled: Returns None immediately")
    print(f"- When enabled: Attempts inference, may return 'INFER: <title>'")
    print(f"- Fallback: Uses header text or nearby text directly")
    
    print(f"\nStage 06a Title Caption Enricher:")
    print(f"- Function: _chutes_title_infer_struct()")
    print(f"- Environment: CHUTES_TEXT_MODEL (must be set)")
    print(f"- When not set: Returns None immediately")
    print(f"- When set: Attempts inference, returns structured data")
    print(f"- Fallback: Leaves title as None")
    
    print(f"\nThe Issue:")
    print(f"- You see 'INFER: 0' in output")
    print(f"- Stage 06a enricher sets title=None when CHUTES_TEXT_MODEL not set")
    print(f"- Stage 05 extractor only runs when STAGE05_LLM_INFER='1'")
    print(f"- The 'INFER: 0' must be coming from:")
    print(f"  1. Stage 05 extractor if STAGE05_LLM_INFER='1' and inference fails")
    print(f"  2. Post-processing that formats None titles as 'INFER: 0'")
    print(f"  3. Display/UI code that shows 'INFER: 0' for missing titles")
    print(f"  4. Some other pipeline step")


def provide_solution():
    """Provide the solution to fix the issue."""
    print(f"\n" + "=" * 50)
    print("SOLUTION")
    print("=" * 50)
    
    print(f"\nTo fix the 'INFER: 0' issue, you need to:")
    print(f"\n1. Set CHUTES_TEXT_MODEL environment variable:")
    print(f"   export CHUTES_TEXT_MODEL='your-model-name'")
    print(f"\n2. Or enable Stage 05 inference (if that's the source):")
    print(f"   export STAGE05_LLM_INFER='1'")
    print(f"\n3. Check your .env file and ensure it contains:")
    print(f"   CHUTES_TEXT_MODEL=moonshotai/Kimi-K2-Instruct-0905")
    print(f"   CHUTES_API_BASE=https://llm.chutes.ai/v1")
    print(f"   CHUTES_API_KEY=your-api-key")
    print(f"\n4. To debug further, check:")
    print(f"   - Recent output JSON files for 'INFER: 0' patterns")
    print(f"   - Display/UI code that might format None as 'INFER: 0'")
    print(f"   - Post-processing steps after the enricher")
    
    print(f"\nCurrent diagnosis:")
    current_model = os.environ.get("CHUTES_TEXT_MODEL", "NOT SET")
    stage05_infer = os.environ.get("STAGE05_LLM_INFER", "0")
    print(f"   CHUTES_TEXT_MODEL: {current_model}")
    print(f"   STAGE05_LLM_INFER: {stage05_infer}")
    
    if current_model == "NOT SET":
        print(f"   ✗ CHUTES_TEXT_MODEL is not set - this is the main issue!")
        print(f"   ✗ Stage 06a enricher cannot perform inference")
    else:
        print(f"   ✓ CHUTES_TEXT_MODEL is set")
        
    if stage05_infer == "1":
        print(f"   ⚠ Stage 05 inference is enabled - could be source of 'INFER: 0'")
    else:
        print(f"   ✓ Stage 05 inference is disabled")


def main():
    """Run the complete analysis."""
    show_current_state()
    demonstrate_issue()
    find_infer_zero_source()
    analyze_stage05_vs_stage06a()
    provide_solution()
    
    print(f"\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()