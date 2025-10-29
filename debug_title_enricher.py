#!/usr/bin/env python3
"""
Debug script for title caption enricher issues.

This script helps diagnose why the _chutes_title_infer_struct function
is returning "INFER: 0" results instead of proper titles.
"""

import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extractor.pipeline.utils.preflight import require_scillm_env
from extractor.pipeline.utils.response_utils import normalize_json_content
import importlib
steps_module = importlib.import_module('extractor.pipeline.steps.06a_title_caption_enricher')
_chutes_title_infer_struct = steps_module._chutes_title_infer_struct


def test_require_scillm_env() -> None:
    """Test the require_scillm_env function under different conditions."""
    print("=== Testing require_scillm_env() ===")
    
    # Save original env
    original_env = {
        "CHUTES_API_BASE": os.environ.get("CHUTES_API_BASE"),
        "CHUTES_API_KEY": os.environ.get("CHUTES_API_KEY"), 
        "CHUTES_TEXT_MODEL": os.environ.get("CHUTES_TEXT_MODEL"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL"),
    }
    
    # Test 1: No environment set
    print("\n1. Testing with no CHUTES environment:")
    for key in ["CHUTES_API_BASE", "CHUTES_API_KEY", "CHUTES_TEXT_MODEL", "OPENAI_API_KEY", "OPENAI_BASE_URL"]:
        if key in os.environ:
            del os.environ[key]
    
    ok, reason = require_scillm_env()
    print(f"   Result: ok={ok}, reason='{reason}'")
    
    # Test 2: Only CHUTES_API_BASE set
    print("\n2. Testing with only CHUTES_API_BASE set:")
    os.environ["CHUTES_API_BASE"] = "https://api.example.com"
    if "CHUTES_API_KEY" in os.environ:
        del os.environ["CHUTES_API_KEY"]
    if "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]
    
    ok, reason = require_scillm_env()
    print(f"   Result: ok={ok}, reason='{reason}'")
    
    # Test 3: CHUTES_API_BASE and CHUTES_API_KEY set, but no CHUTES_TEXT_MODEL
    print("\n3. Testing with CHUTES_API_BASE and CHUTES_API_KEY set, but no CHUTES_TEXT_MODEL:")
    os.environ["CHUTES_API_BASE"] = "https://api.example.com"
    os.environ["CHUTES_API_KEY"] = "test-key"
    if "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]
    
    ok, reason = require_scillm_env()
    print(f"   Result: ok={ok}, reason='{reason}'")
    
    # Test 4: All required environment set
    print("\n4. Testing with all required environment set:")
    os.environ["CHUTES_API_BASE"] = "https://api.example.com"
    os.environ["CHUTES_API_KEY"] = "test-key"
    os.environ["CHUTES_TEXT_MODEL"] = "test-model"
    
    ok, reason = require_scillm_env()
    print(f"   Result: ok={ok}, reason='{reason}'")
    
    # Test 5: Check if OPENAI env vars are properly unset
    print("\n5. Testing OPENAI environment variable handling:")
    os.environ["OPENAI_API_KEY"] = "should-be-removed"
    os.environ["OPENAI_BASE_URL"] = "should-be-removed"
    
    ok, reason = require_scillm_env()
    print(f"   Result: ok={ok}, reason='{reason}'")
    print(f"   OPENAI_API_KEY in env: {'OPENAI_API_KEY' in os.environ}")
    print(f"   OPENAI_BASE_URL in env: {'OPENAI_BASE_URL' in os.environ}")
    
    # Restore original env
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]


def test_normalize_json_content() -> None:
    """Test the normalize_json_content function with various inputs."""
    print("\n\n=== Testing normalize_json_content() ===")
    
    # Test cases
    test_cases = [
        # Case 1: None response
        {"name": "None response", "response": None, "expected_raw": "", "expected_obj": None},
        
        # Case 2: Empty dict
        {"name": "Empty dict", "response": {}, "expected_raw": "", "expected_obj": None},
        
        # Case 3: Valid JSON string response
        {
            "name": "Valid JSON string", 
            "response": {"choices": [{"message": {"content": '{"title": "Test Title", "number": "1"}'}}]},
            "expected_raw": '{"title": "Test Title", "number": "1"}',
            "expected_obj": {"title": "Test Title", "number": "1"}
        },
        
        # Case 4: JSON object directly in content
        {
            "name": "JSON object in content",
            "response": {"choices": [{"message": {"content": {"title": "Direct JSON", "number": "2"}}}]},
            "expected_raw": '{"title": "Direct JSON", "number": "2"}',
            "expected_obj": {"title": "Direct JSON", "number": "2"}
        },
        
        # Case 5: Malformed JSON
        {
            "name": "Malformed JSON",
            "response": {"choices": [{"message": {"content": '{"title": "Broken", number: invalid}'}}]},
            "expected_raw": '{"title": "Broken", number: invalid}',
            "expected_obj": None  # Should fail to parse
        },
        
        # Case 6: Simple string content
        {
            "name": "Simple string",
            "response": {"choices": [{"message": {"content": "Just a string"}}]},
            "expected_raw": "Just a string",
            "expected_obj": None
        }
    ]
    
    for case in test_cases:
        print(f"\n{case['name']}:")
        try:
            raw_text, json_obj = normalize_json_content(case["response"])
            print(f"   Raw text: '{raw_text}'")
            print(f"   JSON obj: {json_obj}")
            print(f"   Expected raw: '{case['expected_raw']}'")
            print(f"   Expected obj: {case['expected_obj']}")
            
            # Check if results match expectations
            raw_match = raw_text == case["expected_raw"]
            obj_match = json_obj == case["expected_obj"]
            print(f"   ✓ Raw match: {raw_match}")
            print(f"   ✓ Obj match: {obj_match}")
            
        except Exception as e:
            print(f"   ✗ Error: {e}")


def test_chutes_title_infer_struct() -> None:
    """Test the _chutes_title_infer_struct function with different environments."""
    print("\n\n=== Testing _chutes_title_infer_struct() ===")
    
    # Sample context that should produce a reasonable title
    sample_context = """
    Header: Parameter | Value | Unit
    Samples:
    Temperature | 25.0 | °C
    Pressure | 101.3 | kPa
    Flow Rate | 2.5 | L/min
    
    This table shows the operating conditions for the reactor system.
    """
    
    # Save original env
    original_env = {
        "CHUTES_API_BASE": os.environ.get("CHUTES_API_BASE"),
        "CHUTES_API_KEY": os.environ.get("CHUTES_API_KEY"), 
        "CHUTES_TEXT_MODEL": os.environ.get("CHUTES_TEXT_MODEL"),
        "RUN_RESULTS_DIR": os.environ.get("RUN_RESULTS_DIR"),
    }
    
    # Test 1: No environment (should return None)
    print("\n1. Testing with no CHUTES environment:")
    for key in ["CHUTES_API_BASE", "CHUTES_API_KEY", "CHUTES_TEXT_MODEL"]:
        if key in os.environ:
            del os.environ[key]
    
    try:
        result = _chutes_title_infer_struct(sample_context)
        print(f"   Result: {result}")
        print(f"   ✓ Expected None when environment not set: {result is None}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Partial environment (should return None)
    print("\n2. Testing with partial environment:")
    os.environ["CHUTES_API_BASE"] = "https://api.example.com"
    os.environ["CHUTES_API_KEY"] = "test-key"
    # Deliberately not setting CHUTES_TEXT_MODEL
    if "CHUTES_TEXT_MODEL" in os.environ:
        del os.environ["CHUTES_TEXT_MODEL"]
    
    try:
        result = _chutes_title_infer_struct(sample_context)
        print(f"   Result: {result}")
        print(f"   ✓ Expected None when TEXT_MODEL not set: {result is None}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Set up a test environment with results directory
    print("\n3. Setting up test environment with RUN_RESULTS_DIR:")
    test_results_dir = Path("/tmp/test_title_enricher")
    test_results_dir.mkdir(exist_ok=True)
    os.environ["RUN_RESULTS_DIR"] = str(test_results_dir)
    
    # We'll simulate the case where environment is set but model call fails
    os.environ["CHUTES_API_BASE"] = "https://invalid-api.example.com"
    os.environ["CHUTES_API_KEY"] = "invalid-key"
    os.environ["CHUTES_TEXT_MODEL"] = "invalid-model"
    
    try:
        result = _chutes_title_infer_struct(sample_context, timeout=2.0)
        print(f"   Result: {result}")
        print(f"   ✓ Expected None when API call fails: {result is None}")
        
        # Check if log files were created
        logs_dir = test_results_dir / "06a_title_caption_enricher" / "logs"
        if logs_dir.exists():
            print(f"   ✓ Log directory created: {logs_dir}")
            request_file = logs_dir / "last_request.json"
            response_file = logs_dir / "last_response.json"
            if request_file.exists():
                print(f"   ✓ Request log file exists")
                try:
                    request_data = json.loads(request_file.read_text())
                    print(f"   Request model: {request_data.get('model')}")
                    print(f"   Request messages count: {len(request_data.get('messages', []))}")
                except Exception as e:
                    print(f"   ✗ Error reading request log: {e}")
            if response_file.exists():
                print(f"   ✓ Response log file exists")
                try:
                    response_data = json.loads(response_file.read_text())
                    print(f"   Response: {response_data}")
                except Exception as e:
                    print(f"   ✗ Error reading response log: {e}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: Test with very short context
    print("\n4. Testing with minimal context:")
    minimal_context = "Header: A | B | C"
    try:
        result = _chutes_title_infer_struct(minimal_context, timeout=2.0)
        print(f"   Result: {result}")
        print(f"   ✓ Function handles minimal context")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Clean up
    import shutil
    if test_results_dir.exists():
        shutil.rmtree(test_results_dir)
    
    # Restore original env
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]


def analyze_inference_issue() -> None:
    """Analyze the specific issue with 'INFER: 0' results."""
    print("\n\n=== Analyzing 'INFER: 0' Issue ===")
    
    print("\nThe 'INFER: 0' results suggest that:")
    print("1. The _chutes_title_infer_struct function is returning None")
    print("2. The enrich_tables/enrich_figures functions are falling back to simple numbering")
    print("3. This happens when require_scillm_env() returns False")
    
    print("\nLooking at the code in enrich_tables():")
    print("- Line 379: inferred = _chutes_title_infer_struct(ctx_all or basic)")
    print("- Line 380-391: If inferred is dict, use title from inference")
    print("- If inferred is None (environment not set), title remains None")
    print("- Line 397: norm_id = _normalize_id('table', number, base_title)")
    print("- If no base_title, norm_id becomes None")
    print("- The 'INFER: 0' likely comes from elsewhere in the pipeline")
    
    print("\nThe issue is that when CHUTES_TEXT_MODEL is not set:")
    print("1. require_scillm_env() returns False")
    print("2. _chutes_title_infer_struct() returns None immediately")
    print("3. No actual inference happens")
    print("4. The 'INFER: 0' must be coming from a different part of the code")


def main() -> None:
    """Run all debug tests."""
    print("Title Caption Enricher Debug Script")
    print("=" * 50)
    
    # Show current environment
    print("Current environment:")
    chutes_vars = ["CHUTES_API_BASE", "CHUTES_API_KEY", "CHUTES_TEXT_MODEL", "CHUTES_AUTH_STYLE"]
    for var in chutes_vars:
        value = os.environ.get(var, "NOT SET")
        if value and len(value) > 20:
            value = value[:20] + "..."
        print(f"  {var}: {value}")
    
    # Run tests
    test_require_scillm_env()
    test_normalize_json_content()
    test_chutes_title_infer_struct()
    analyze_inference_issue()
    
    print("\n" + "=" * 50)
    print("Debug analysis complete!")
    print("\nKey findings:")
    print("1. The function returns None when CHUTES_TEXT_MODEL is not set")
    print("2. No actual inference happens without proper environment")
    print("3. The 'INFER: 0' results are likely coming from fallback logic elsewhere")
    print("4. Check if the pipeline has fallback title generation that uses simple numbering")


if __name__ == "__main__":
    main()