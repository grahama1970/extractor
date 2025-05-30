#!/usr/bin/env python3
"""Test string corpus validation with CLI."""

import subprocess
import sys
import json
import os

# Set environment
env = os.environ.copy()
env["PYTHONPATH"] = "."

# Create a config file for the validator with the corpus
corpus_config = {
    "corpus": ["London", "Houston", "New York City"],
    "case_sensitive": False
}

# Save config to a temporary file
with open("/tmp/corpus_config.json", "w") as f:
    json.dump(corpus_config, f)

# Run the CLI command with no retries
result = subprocess.run([
    sys.executable, "-m", "marker.llm_call.cli.app", 
    "validate", 
    "What is the Capital of France?",
    "--validators", "string_corpus",
    "--max-retries", "1",  # Only try once
    "--debug"
], 
    capture_output=True, 
    text=True,
    env=env
)

print("=== CLI Output ===")
print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")
print("\n=== Expected Result ===")
print("The validation should FAIL because 'Paris' is not in the corpus [London, Houston, New York City]")