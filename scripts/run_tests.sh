#!/bin/bash
"""
Run all Marker tests with proper organization
"""

echo "Running Marker Enhanced Tests..."
echo "==============================="

# Core tests
echo -e "\n1. Running core functionality tests..."
pytest tests/config/ tests/builders/ tests/converters/ tests/providers/ tests/renderers/ tests/schema/ tests/services/ -v

# Feature tests
echo -e "\n2. Running enhanced feature tests..."
pytest tests/features/ -v

# Integration tests
echo -e "\n3. Running integration tests..."
pytest tests/test_e2e_workflow.py tests/test_regression_marker.py -v

# Summary
echo -e "\n==============================="
echo "Test run complete!"