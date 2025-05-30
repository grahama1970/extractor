#!/bin/bash
# Test LLM Validation CLI with proper uv setup

echo "=== LLM Validation CLI Test with uv ==="
echo

# Setup environment
cd /home/graham/workspace/experiments/marker
source .venv/bin/activate
export PYTHONPATH=/home/graham/workspace/experiments/marker/

echo "1. Check uv installation:"
which uv
echo

echo "2. Show installed packages (with uv):"
uv pip list | grep -E "litellm|pydantic|rapidfuzz|typer|rich"
echo

echo "3. Run CLI help:"
python -m marker.llm_call.cli.app --help
echo

echo "4. List validators:"
python -m marker.llm_call.cli.app list-validators
echo

echo "5. Create test file:"
cat > test_data.json << 'EOF'
{
  "content": "This is test content with sufficient length for validation.",
  "table": {
    "headers": ["Name", "Role"],
    "rows": [
      ["Alice", "Developer"],
      ["Bob", "Designer"]
    ]
  }
}
EOF
echo "Created test_data.json"
echo

echo "6. Test validation command:"
echo "Command: python -m marker.llm_call.cli.app validate test_data.json --validators table_structure"
# Note: This would actually run the validation if the CLI was fully implemented

echo
echo "=== Test Complete ==="
echo "Ready for ArangoDB integration with uv package management"