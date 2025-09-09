#!/usr/bin/env python3
"""Test Claude CLI authentication methods."""

import subprocess
import os
from pathlib import Path

def test_claude_with_different_auth():
    """Test various authentication approaches for Claude CLI."""
    
    # Test 1: Default environment
    print("Test 1: Default environment")
    result = subprocess.run(
        ["/home/graham/.bun/bin/bun", "/home/graham/.bun/bin/claude", "-p", "test"],
        capture_output=True,
        text=True
    )
    print(f"Exit code: {result.returncode}")
    print(f"Stdout: {result.stdout[:200]}")
    print(f"Stderr: {result.stderr[:200]}")
    print()
    
    # Test 2: With --dangerously-skip-permissions
    print("Test 2: With --dangerously-skip-permissions")
    result = subprocess.run(
        ["/home/graham/.bun/bin/bun", "/home/graham/.bun/bin/claude", "-p", "--dangerously-skip-permissions", "test"],
        capture_output=True,
        text=True
    )
    print(f"Exit code: {result.returncode}")
    print(f"Stdout: {result.stdout[:200]}")
    print(f"Stderr: {result.stderr[:200]}")
    print()
    
    # Test 3: With ANTHROPIC_API_KEY unset
    print("Test 3: With ANTHROPIC_API_KEY unset")
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        ["/home/graham/.bun/bin/bun", "/home/graham/.bun/bin/claude", "-p", "--dangerously-skip-permissions", "test"],
        capture_output=True,
        text=True,
        env=env
    )
    print(f"Exit code: {result.returncode}")
    print(f"Stdout: {result.stdout[:200]}")
    print(f"Stderr: {result.stderr[:200]}")
    print()
    
    # Test 4: Check for credentials file
    print("Test 4: Check for credentials file")
    cred_file = Path.home() / ".claude" / ".credentials.json"
    print(f"Credentials file exists: {cred_file.exists()}")
    if cred_file.exists():
        print(f"Credentials file readable: {os.access(cred_file, os.R_OK)}")
    
    # Test 5: With HOME set to current user
    print("\nTest 5: With HOME explicitly set")
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env["HOME"] = str(Path.home())
    result = subprocess.run(
        ["/home/graham/.bun/bin/bun", "/home/graham/.bun/bin/claude", "-p", "--dangerously-skip-permissions", "test"],
        capture_output=True,
        text=True,
        env=env
    )
    print(f"Exit code: {result.returncode}")
    print(f"Stdout: {result.stdout[:200]}")
    print(f"Stderr: {result.stderr[:200]}")

if __name__ == "__main__":
    test_claude_with_different_auth()