#!/usr/bin/env python3
"""
Test calling claude through shell to inherit environment
"""

import subprocess
import os

def call_claude_with_shell():
    """Call claude using shell=True to inherit shell environment."""
    prompt = "What is 2+2? Reply with just the number."
    
    # Method 1: Using shell=True with full command
    print("Method 1: shell=True")
    cmd = f'claude -p "{prompt}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"Return code: {result.returncode}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")
    
    # Method 2: Using explicit shell invocation
    print("\nMethod 2: explicit zsh")
    result2 = subprocess.run(
        ["/usr/bin/zsh", "-c", f'claude -p "{prompt}"'],
        capture_output=True,
        text=True,
        env=os.environ.copy()
    )
    print(f"Return code: {result2.returncode}")
    print(f"Stdout: {result2.stdout}")
    print(f"Stderr: {result2.stderr}")
    
    # Method 3: Source profile first
    print("\nMethod 3: source profile")
    cmd3 = f'source ~/.zshrc 2>/dev/null; claude -p "{prompt}"'
    result3 = subprocess.run(
        ["/usr/bin/zsh", "-c", cmd3],
        capture_output=True,
        text=True
    )
    print(f"Return code: {result3.returncode}")
    print(f"Stdout: {result3.stdout}")
    print(f"Stderr: {result3.stderr}")

if __name__ == "__main__":
    call_claude_with_shell()