#!/usr/bin/env python3
"""
run_all_gates.py - Simple orchestrator for tasks_loop gate scripts.

Usage:
    python tools/tasks_loop/run_all_gates.py [--stop-on-fail] [--gate PATTERN]

Exit codes:
    0 = All gates passed
    1 = One or more gates failed
    42 = A gate requested clarification (human input needed)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CLARIFY_EXIT = 42
ROOT = Path(__file__).resolve().parents[2]
GATES_DIR = Path(__file__).resolve().parent / "gates"


def discover_gates(pattern: str | None = None) -> list[Path]:
    """Find all gate_*.py files in the tasks_loop directory."""
    gates = sorted(GATES_DIR.glob("gate_*.py"))
    if pattern:
        gates = [g for g in gates if pattern in g.name]
    return gates


def run_gate(gate_path: Path) -> int:
    """Run a single gate script. Returns exit code."""
    print(f"\n{'='*60}")
    print(f"GATE: {gate_path.name}")
    print(f"{'='*60}")

    result = subprocess.run(
        [sys.executable, str(gate_path)],
        cwd=ROOT,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT / "src")},
    )

    if result.returncode == 0:
        print(f"✅ PASS: {gate_path.name}")
    elif result.returncode == CLARIFY_EXIT:
        print(f"❓ CLARIFY: {gate_path.name} (needs human input)")
    else:
        print(f"❌ FAIL: {gate_path.name} (exit={result.returncode})")

    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all gate scripts.")
    parser.add_argument(
        "--stop-on-fail",
        "-s",
        action="store_true",
        help="Stop on first failure (default: run all gates).",
    )
    parser.add_argument(
        "--gate",
        "-g",
        type=str,
        default=None,
        help="Only run gates matching this pattern (e.g. 's05').",
    )
    args = parser.parse_args()

    gates = discover_gates(args.gate)
    if not gates:
        print("No gate scripts found.")
        return 0

    print(f"Found {len(gates)} gate(s): {[g.name for g in gates]}")

    results: dict[str, int] = {}
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=False,
    ) as progress:
        task = progress.add_task("[cyan]Running Gates...", total=len(gates))

        for gate in gates:
            progress.update(task, description=f"[cyan]Running {gate.name}...")
            # Capture output to avoid breaking progress bar layout
            # (In a real implementation we might pipe stdout, but for now we let it print
            # above the bar or just accept the interleave)

            rc = run_gate(gate)
            results[gate.name] = rc
            progress.advance(task)

            if rc == CLARIFY_EXIT:
                print(f"\n⚠️  Gate {gate.name} requires clarification. Stopping.")
                return CLARIFY_EXIT

            if rc != 0 and args.stop_on_fail:
                print(f"\n⚠️  Stopping due to failure in {gate.name}")
                return 1

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for r in results.values() if r == 0)
    failed = sum(1 for r in results.values() if r != 0)
    for name, rc in results.items():
        status = "✅" if rc == 0 else "❌"
        print(f"  {status} {name}")

    print(f"\nPassed: {passed}/{len(results)}, Failed: {failed}/{len(results)}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
