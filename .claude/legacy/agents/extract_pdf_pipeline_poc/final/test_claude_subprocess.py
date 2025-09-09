#!/usr/bin/env python3
"""
Simple test to prove we can call claude -p from Python using asyncio subprocess
"""

import asyncio
import sys

async def call_claude_async():
    """Call claude -p using asyncio subprocess."""
    prompt = "What is 2+2? Reply with just the number."
    
    print(f"Calling claude with prompt: {prompt}")
    
    # Create the subprocess
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Wait for it to complete and get output
    stdout, stderr = await proc.communicate()
    
    # Decode output
    stdout_text = stdout.decode() if stdout else ""
    stderr_text = stderr.decode() if stderr else ""
    
    print(f"Return code: {proc.returncode}")
    print(f"Stdout: {stdout_text}")
    print(f"Stderr: {stderr_text}")
    
    return stdout_text

async def main():
    """Main async function."""
    try:
        result = await call_claude_async()
        print(f"\nClaude responded: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())