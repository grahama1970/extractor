#!/usr/bin/env python3
"""
gate_s11.py - Gate for Lean4 Infrastructure Verification

This gate validates that Lean4 theorem proving capability is available.
The actual pipeline step is s08_lean4_theorem_prover, but the sanity
scripts use "S11" naming for the Lean4 infrastructure.

Checks:
1. Lean4 Docker container is running OR
2. CERTAINLY_BRIDGE_BASE / LEAN4_BRIDGE_BASE env var is set

Exit codes:
- 0: Lean4 infrastructure verified
- 42: Lean4 not available (clarify - optional dependency)
- 1: Unexpected error

Usage: python gate_s11.py [--require]
  --require: Fail (exit 1) instead of clarify (exit 42) if Lean4 unavailable
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import run_gate, GateError

CONTAINER_NAMES = ["lean4", "certainly", "lean4-bridge", "certainly-bridge"]


def check_docker_container() -> str | None:
    """Check if any Lean4 container is running. Returns container name if found."""
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return None
    except Exception:
        return None

    for name in CONTAINER_NAMES:
        try:
            result = subprocess.run(
                ["docker", "ps", "-q", "--filter", f"name={name}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return name
        except Exception:
            continue
    return None


def check_bridge_url() -> str | None:
    """Check if bridge URL is configured via environment."""
    return (
        os.getenv("CERTAINLY_BRIDGE_BASE")
        or os.getenv("LEAN4_BRIDGE_BASE")
        or os.getenv("SCILLM_API_BASE")  # May include Lean4 endpoint
    )


def checks(require: bool = False):
    """Verify Lean4 infrastructure is available."""
    container = check_docker_container()
    bridge_url = check_bridge_url()

    if container:
        print(f"Found running container: {container}")
        return

    if bridge_url:
        print(f"Bridge URL configured: {bridge_url}")
        return

    # Lean4 not available
    msg = "Lean4 infrastructure not available"
    hint = "Start Docker container or set CERTAINLY_BRIDGE_BASE"

    if require:
        raise GateError(
            message=msg,
            expected="Docker container OR bridge URL",
            actual="neither found",
            hint=hint,
        )
    else:
        # Exit 42 = clarify (Lean4 is optional)
        print(f"CLARIFY: {msg}")
        print(f"HINT: {hint}")
        print("Lean4 proving is optional - pipeline works without it")
        sys.exit(42)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S11: Lean4 Infrastructure")
    parser.add_argument(
        "--require", action="store_true", help="Fail instead of clarify if Lean4 unavailable"
    )
    args = parser.parse_args()

    sys.exit(run_gate("S11: Lean4 Infrastructure", lambda: checks(require=args.require)))
