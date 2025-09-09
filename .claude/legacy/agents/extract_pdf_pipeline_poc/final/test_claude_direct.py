#!/usr/bin/env python3
"""Test calling claude directly"""

import subprocess

claude_path = "/home/graham/.bun/bin/claude"

# Test 1: Check if file exists
import os
print(f"Claude path: {claude_path}")
print(f"Exists: {os.path.exists(claude_path)}")
print(f"Is file: {os.path.isfile(claude_path)}")
print(f"Is executable: {os.access(claude_path, os.X_OK)}")

# Test 2: Try to run it
print("\nTrying to run claude --help:")
result = subprocess.run([claude_path, "--help"], capture_output=True, text=True)
print(f"Return code: {result.returncode}")
print(f"Stdout: {result.stdout[:500] if result.stdout else 'No stdout'}")
print(f"Stderr: {result.stderr[:500] if result.stderr else 'No stderr'}")

# Test 3: Try a simple prompt
print("\nTrying claude -p with simple prompt:")
result2 = subprocess.run([claude_path, "-p", "Say just 'yes'"], capture_output=True, text=True)
print(f"Return code: {result2.returncode}")
print(f"Stdout: {result2.stdout[:500] if result2.stdout else 'No stdout'}")
print(f"Stderr: {result2.stderr[:500] if result2.stderr else 'No stderr'}")