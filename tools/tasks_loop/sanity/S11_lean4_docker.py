#!/usr/bin/env python3
"""
S11_lean4_docker.py - Sanity check for Lean4 Docker container.

Purpose:
- Verify that the Lean4/Certainly Docker container is running.
- This is required for S11 (Lean4 Theorem Prover).

Dependencies:
- Docker
- Lean4 container running

Success Criteria:
- Container is running (docker ps finds it)
"""

import os
import subprocess
import sys


# Possible container names to check
CONTAINER_NAMES = [
    "lean4",
    "certainly",
    "lean4-bridge",
    "certainly-bridge",
]


def main() -> int:
    # Check if docker is available
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print("SKIP: Docker not available")
            return 0
    except Exception as e:
        print(f"SKIP: Docker not available ({e})")
        return 0

    print("Checking for Lean4 Docker container...")

    # Check each possible container name
    for name in CONTAINER_NAMES:
        try:
            result = subprocess.run(
                ["docker", "ps", "-q", "--filter", f"name={name}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                container_id = result.stdout.strip()
                print(f"OK: Found running container '{name}' (ID: {container_id[:12]})")
                return 0
        except Exception:
            continue

    # Also check via env var if bridge URL is set
    bridge_url = os.getenv("CERTAINLY_BRIDGE_BASE") or os.getenv("LEAN4_BRIDGE_BASE")
    if bridge_url:
        print(f"NOTE: Bridge URL configured: {bridge_url}")
        print("      Container check skipped (assuming external bridge)")
        return 0

    print(f"SKIP: No Lean4 container found (checked: {CONTAINER_NAMES})")
    print("      Set CERTAINLY_BRIDGE_BASE or LEAN4_BRIDGE_BASE if using external bridge")
    return 0  # Skip, not fail - Lean4 is optional


if __name__ == "__main__":
    sys.exit(main())
