"""
Module: test_basic_functionality.py
Description: Basic functionality tests that don't require full imports

External Dependencies:
- pytest: https://docs.pytest.org/

Sample Input:
>>> pytest.main([__file__, "-v"])

Expected Output:
>>> All tests should pass with correct project structure

Example Usage:
>>> pytest tests/test_basic_functionality.py -v
"""

import pytest
import sys
from pathlib import Path


def test_python_version():
    """Test Python version is correct."""
    # Check for Python 3.10 or higher
    assert sys.version_info[:2] >= (3, 10), f"Python 3.10+ required, got {sys.version_info[:2]}"


def test_project_structure():
    """Test project structure exists."""
    project_root = Path(__file__).parent.parent
    assert project_root.exists()
    assert (project_root / "src").exists()
    assert (project_root / "pyproject.toml").exists()
    

def test_basic_math():
    """Test basic functionality."""
    assert 2 + 2 == 4
    # Updated to check for extractor instead of marker
    assert "extractor" in str(Path(__file__).parent.parent)


def test_path_operations():
    """Test path operations work."""
    test_path = Path("test/file.pdf")
    assert test_path.suffix == ".pdf"
    assert test_path.stem == "file"


def test_extractor_module_structure():
    """Test that extractor module structure is correct."""
    project_root = Path(__file__).parent.parent
    extractor_path = project_root / "src" / "extractor"
    
    assert extractor_path.exists(), "extractor module directory missing"
    assert (extractor_path / "__init__.py").exists(), "extractor __init__.py missing"
    assert (extractor_path / "core").exists(), "extractor core module missing"
    assert (extractor_path / "cli").exists(), "extractor cli module missing"


if __name__ == "__main__":
    # Validation
    results = []
    results.append(("python_version", test_python_version()))
    results.append(("project_structure", test_project_structure()))
    results.append(("basic_math", test_basic_math()))
    results.append(("path_operations", test_path_operations()))
    results.append(("extractor_module", test_extractor_module_structure()))
    
    failed = [name for name, result in results if result is False]
    if failed:
        print(f"❌ Failed tests: {failed}")
        exit(1)
    else:
        print("✅ All basic functionality tests passed")
        exit(0)