#!/usr/bin/env python3
"""
Test that the test directory structure mirrors the source structure.
"""

import os
import time
from pathlib import Path


def test_structure_mirror():
    """Verify that test directory structure mirrors src/marker/ structure."""
    start_time = time.time()
    
    project_root = Path(__file__).parent.parent.parent
    src_dir = project_root / "src" / "marker"
    test_dir = project_root / "tests"
    
    # Core directories that should be mirrored
    expected_mirrors = {
        "cli": test_dir / "cli",
        "core": test_dir / "core",
        "mcp": test_dir / "mcp",
        "core/arangodb": test_dir / "core" / "arangodb",
        "core/builders": test_dir / "core" / "builders",
        "core/config": test_dir / "core" / "config",
        "core/converters": test_dir / "core" / "converters",
        "core/processors": test_dir / "core" / "processors",
        "core/providers": test_dir / "core" / "providers",
        "core/renderers": test_dir / "core" / "renderers",
        "core/schema": test_dir / "core" / "schema",
        "core/services": test_dir / "core" / "services",
    }
    
    missing_dirs = []
    found_dirs = []
    
    for src_path, expected_test_path in expected_mirrors.items():
        full_src_path = src_dir / src_path
        
        if full_src_path.exists() and full_src_path.is_dir():
            if expected_test_path.exists() and expected_test_path.is_dir():
                found_dirs.append(str(expected_test_path.relative_to(project_root)))
            else:
                missing_dirs.append(str(expected_test_path.relative_to(project_root)))
    
    duration = time.time() - start_time
    
    print(f"\nStructure Mirror Test Results:")
    print(f"Duration: {duration:.3f} seconds")
    print(f"Expected test directories: {len(expected_mirrors)}")
    print(f"Found directories: {len(found_dirs)}")
    print(f"Missing directories: {len(missing_dirs)}")
    
    if missing_dirs:
        print("\nMissing test directories:")
        for dir_path in missing_dirs:
            print(f"  - {dir_path}")
    
    # Check for test files in proper locations
    test_files_found = 0
    for test_path in [test_dir / "core", test_dir / "cli", test_dir / "mcp"]:
        if test_path.exists():
            test_files = list(test_path.rglob("test_*.py"))
            test_files_found += len(test_files)
    
    print(f"\nTest files found in mirrored structure: {test_files_found}")
    
    assert len(missing_dirs) == 0, f"Missing {len(missing_dirs)} expected test directories"
    assert test_files_found > 20, f"Only found {test_files_found} test files, expected more"
    # Structure verification is naturally very fast since it's just checking directories
    assert duration >= 0, f"Invalid test duration ({duration:.3f}s)"
    assert duration < 2.0, f"Structure test too slow ({duration:.3f}s), possible issue"


if __name__ == "__main__":
    print("Running structure verification test...")
    
    try:
        test_structure_mirror()
        print("✓ Structure mirror test passed")
    except AssertionError as e:
        print(f"✗ Structure mirror test failed: {e}")