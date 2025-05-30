#!/usr/bin/env python3
"""Test the CLI with a real example."""

import subprocess
import sys

# Test with a simple prompt
result = subprocess.run([
    sys.executable, "-m", "marker.llm_call.cli.app", 
    "validate", 
    "Generate a Python function to calculate fibonacci numbers",
    "--validators", "python_syntax",
    "--validators", "content_quality", 
    "--debug"
], capture_output=True, text=True)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")