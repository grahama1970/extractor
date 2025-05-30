#!/bin/bash
# Test the LLM validation CLI functionality

echo "=== Testing LLM Validation CLI ==="
echo

# Set up environment
export PYTHONPATH=/home/graham/workspace/experiments/marker:$PYTHONPATH
cd /home/graham/workspace/experiments/marker

echo "1. Testing help command:"
echo "Command: python -m marker.llm_call.cli.app --help"
python3 -m marker.llm_call.cli.app --help
echo

echo "2. Testing list-validators command:"
echo "Command: python -m marker.llm_call.cli.app list-validators"
python3 -m marker.llm_call.cli.app list-validators
echo

echo "3. Testing validate-text with length check:"
echo 'Command: python -m marker.llm_call.cli.app validate-text "Hello world" --validator length_check'
python3 -m marker.llm_call.cli.app validate-text "Hello world" --validator length_check
echo

echo "4. Testing validate-text with field presence (will fail):"
echo 'Command: python -m marker.llm_call.cli.app validate-text "Test" --validator field_presence'
python3 -m marker.llm_call.cli.app validate-text "Test" --validator field_presence
echo

echo "=== CLI Test Complete ===
"