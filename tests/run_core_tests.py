#!/usr/bin/env python3
"""
Module: run_core_tests.py
Description: Simple test runner for core extractor functionality

External Dependencies:
- None (uses standard library only)

Sample Input:
>>> python tests/run_core_tests.py

Expected Output:
>>> Summary of test results

Example Usage:
>>> python tests/run_core_tests.py
"""

import sys
import subprocess
from pathlib import Path


def run_test_file(test_file):
    """Run a single test file and return results."""
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "file": test_file.name,
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "file": test_file.name,
            "success": False,
            "output": "",
            "error": "Test timed out"
        }
    except Exception as e:
        return {
            "file": test_file.name,
            "success": False,
            "output": "",
            "error": str(e)
        }


def main():
    """Run core tests without pytest."""
    tests_dir = Path(__file__).parent
    
    print("🧪 Running Core Extractor Tests")
    print("=" * 50)
    
    # Core test files to run
    test_files = [
        tests_dir / "test_basic_functionality.py",
        tests_dir / "test_core_functionality.py",
        tests_dir / "test_honeypot.py",
        tests_dir / "integration" / "test_granger_pipeline.py"
    ]
    
    results = []
    
    for test_file in test_files:
        if test_file.exists():
            print(f"\n📋 Running {test_file.name}...")
            result = run_test_file(test_file)
            results.append(result)
            
            if result["success"]:
                print(f"✅ {result['file']} - PASSED")
                if result["output"]:
                    print(result["output"].strip())
            else:
                print(f"❌ {result['file']} - FAILED")
                if result["error"]:
                    print(f"Error: {result['error']}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    
    print(f"Total: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    
    if passed == total:
        print("\n✅ All core tests passed!")
        print("The extractor module is ready for Granger ecosystem integration.")
    else:
        print("\n❌ Some tests failed.")
        print("Please check the errors above.")
    
    # Exit with appropriate code
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())