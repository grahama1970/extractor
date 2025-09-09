#!/usr/bin/env python3
"""
Test calling claude with activated venv
"""

import subprocess
import os
from pathlib import Path

def call_claude_with_venv():
    """Call claude after activating the venv."""
    prompt = "What is 2+2? Reply with just the number."
    
    # Find project root and venv
    project_root = Path("/home/graham/workspace/experiments/extractor")
    venv_activate = project_root / ".venv/bin/activate"
    
    print(f"Project root: {project_root}")
    print(f"Venv activate script: {venv_activate}")
    print(f"Exists: {venv_activate.exists()}")
    
    # Method 1: Activate venv then call claude
    print("\nMethod 1: Activate venv in subprocess")
    cmd = f'source {venv_activate} && claude -p "{prompt}"'
    result = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True,
        cwd=str(project_root)
    )
    print(f"Return code: {result.returncode}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")
    
    # Method 2: Use venv python directly
    print("\nMethod 2: Check venv bin directory")
    venv_bin = project_root / ".venv/bin"
    claude_path = venv_bin / "claude"
    print(f"Looking for: {claude_path}")
    print(f"Exists: {claude_path.exists()}")
    
    if claude_path.exists():
        result2 = subprocess.run(
            [str(claude_path), "-p", prompt],
            capture_output=True,
            text=True
        )
        print(f"Return code: {result2.returncode}")
        print(f"Stdout: {result2.stdout}")
        print(f"Stderr: {result2.stderr}")
    
    # Method 3: List what's in venv/bin
    print("\nMethod 3: List venv/bin contents")
    if venv_bin.exists():
        items = list(venv_bin.glob("*"))
        print(f"Found {len(items)} items in venv/bin")
        claude_items = [i for i in items if 'claude' in i.name.lower()]
        if claude_items:
            print("Claude-related items:")
            for item in claude_items:
                print(f"  - {item.name}")
        else:
            print("No claude-related items found in venv/bin")

if __name__ == "__main__":
    call_claude_with_venv()