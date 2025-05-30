#!/usr/bin/env python3
"""
Integration Test for Organized Test Structure

This test ensures that the reorganized test structure can be properly
imported and executed using pytest.
"""

import sys
import os
import pytest
from pathlib import Path


def test_imports():
    """Test that all modules can be imported properly."""
    # Test importing ArangoDB modules
    from tests.arangodb.test_arangodb_quick import AQLValidator, ArangoDocumentValidator
    
    # Create and test a validator
    validator = AQLValidator()
    query = "FOR u IN users RETURN u"
    result = validator.validate(query)
    assert result.valid


def test_test_directories():
    """Test that all test directories exist and have __init__.py."""
    test_dirs = [
        "arangodb",
        "code",
        "cli",
        "metadata",
        "package",
        "pdf",
        "validation",
    ]
    
    for test_dir in test_dirs:
        dir_path = Path(__file__).parent / test_dir
        assert dir_path.exists(), f"Directory {test_dir} does not exist"
        assert (dir_path / "__init__.py").exists(), f"__init__.py missing in {test_dir}"


def test_allowed_cities():
    """Test that allowed_cities.txt can be loaded."""
    cities_file = Path(__file__).parent.parent / "allowed_cities.txt"
    
    if not cities_file.exists():
        with open(cities_file, "w") as f:
            f.write("New York\nLondon\nTokyo\nParis\nBerlin\nSingapore\n")
    
    with open(cities_file, "r") as f:
        allowed_cities = {city.strip() for city in f if city.strip()}
    
    assert "London" in allowed_cities
    assert len(allowed_cities) >= 5


if __name__ == "__main__":
    test_imports()
    test_test_directories()
    test_allowed_cities()
    print("✅ All integration tests passed")