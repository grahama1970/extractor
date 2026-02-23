#!/usr/bin/env python
"""Smoke test: Stage 08 Lean4 theorem proving via scillm direct mode.

This tests the complete proving path:
  extractor -> scillm.extras.providers.certainly_prove_iter
    -> scillm.integrations.certainly -> lean4_prover.certainly_min
    -> lean_runner container

Prerequisites:
  - lean_runner container running (docker ps | grep lean_runner)
  - OPENROUTER_API_KEY set
  - scillm[certainly] installed

Usage:
  uv run python scripts/smokes/pipeline/smoke_stage08_lean4_prove.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import typer
from dotenv import find_dotenv, load_dotenv

app = typer.Typer(add_completion=False, help="Smoke: Stage 08 Lean4 proving")


def check_prerequisites() -> list[str]:
    """Check prerequisites and return list of issues."""
    issues = []

    # Check OPENROUTER_API_KEY
    if not os.getenv("OPENROUTER_API_KEY"):
        issues.append("OPENROUTER_API_KEY not set")

    # Check lean_runner container
    import subprocess

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=lean_runner", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    if "lean_runner" not in result.stdout:
        issues.append(
            "lean_runner container not running (start with: make lean-runner-up in lean4 repo)"
        )

    # Check certainly is available
    try:
        from scillm.integrations.certainly import is_available

        if not is_available():
            issues.append(
                "certainly package not available (install with: pip install scillm[certainly])"
            )
    except ImportError:
        issues.append("scillm.integrations.certainly not found")

    return issues


@app.command()
def main(
    skip_impossible: bool = typer.Option(
        False, "--skip-impossible", help="Skip impossible proof test"
    ),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Proof timeout in seconds"),
):
    """Test Lean4 theorem proving integration."""
    load_dotenv(find_dotenv(usecwd=True) or None)

    # Check prerequisites
    issues = check_prerequisites()
    if issues:
        typer.echo("Prerequisites not met:", err=True)
        for issue in issues:
            typer.echo(f"  - {issue}", err=True)
        raise SystemExit(1)

    # Add src to path for imports
    sys.path.insert(0, os.path.abspath("src"))

    from scillm.integrations.certainly import prove_requirement

    results = {"tests": [], "ok": True}

    async def run_tests():
        nonlocal results

        # Test 1: Simple provable requirement
        typer.echo("Test 1: Proving 'n + 1 > n for natural numbers'...")
        try:
            result = await prove_requirement(
                requirement="Prove that for any natural number n, n + 1 > n",
                tactics=["simp", "omega"],
                num_candidates=2,
                compile_timeout_s=timeout,
            )
            test1_ok = result.get("ok", False)
            results["tests"].append(
                {
                    "name": "simple_provable",
                    "ok": test1_ok,
                    "requirement": "n + 1 > n",
                    "lean_code": (
                        result.get("best", {}).get("lean4", "")[:200] if test1_ok else None
                    ),
                    "error": (
                        None
                        if test1_ok
                        else result.get("error") or result.get("diagnosis", {}).get("diagnosis")
                    ),
                }
            )
            if test1_ok:
                typer.echo("  PASS: Proof found")
            else:
                typer.echo(f"  FAIL: {result.get('error') or 'No proof found'}", err=True)
                results["ok"] = False
        except Exception as e:
            typer.echo(f"  ERROR: {e}", err=True)
            results["tests"].append({"name": "simple_provable", "ok": False, "error": str(e)})
            results["ok"] = False

        # Test 2: Impossible proof (should fail gracefully)
        if not skip_impossible:
            typer.echo("Test 2: Proving '2 + 2 = 5' (should fail)...")
            try:
                result = await prove_requirement(
                    requirement="Prove that 2 + 2 = 5",
                    tactics=["simp"],
                    num_candidates=1,
                    compile_timeout_s=timeout,
                )
                test2_ok = result.get("ok", False) is False  # We expect failure
                has_diagnosis = bool(result.get("diagnosis"))
                results["tests"].append(
                    {
                        "name": "impossible_proof",
                        "ok": test2_ok and has_diagnosis,
                        "expected_failure": True,
                        "actually_failed": not result.get("ok", False),
                        "has_diagnosis": has_diagnosis,
                    }
                )
                if test2_ok and has_diagnosis:
                    typer.echo("  PASS: Correctly failed with diagnosis")
                else:
                    typer.echo("  FAIL: Expected failure with diagnosis", err=True)
                    results["ok"] = False
            except Exception as e:
                typer.echo(f"  ERROR: {e}", err=True)
                results["tests"].append({"name": "impossible_proof", "ok": False, "error": str(e)})
                results["ok"] = False

        # Test 3: Empty requirement (should fail fast)
        typer.echo("Test 3: Empty requirement (should fail fast)...")
        try:
            result = await prove_requirement(
                requirement="",
                tactics=[],
                num_candidates=1,
            )
            test3_ok = (
                result.get("ok", False) is False and "empty" in result.get("error", "").lower()
            )
            results["tests"].append(
                {
                    "name": "empty_requirement",
                    "ok": test3_ok,
                    "expected_failure": True,
                    "error": result.get("error"),
                }
            )
            if test3_ok:
                typer.echo("  PASS: Correctly rejected empty requirement")
            else:
                typer.echo("  FAIL: Should reject empty requirement", err=True)
                results["ok"] = False
        except Exception as e:
            typer.echo(f"  ERROR: {e}", err=True)
            results["tests"].append({"name": "empty_requirement", "ok": False, "error": str(e)})
            results["ok"] = False

    asyncio.run(run_tests())

    # Save results
    outdir = Path("scripts/artifacts")
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "stage08_lean4_prove.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    passed = sum(1 for t in results["tests"] if t.get("ok"))
    total = len(results["tests"])
    typer.echo(f"\nResults: {passed}/{total} tests passed")

    if not results["ok"]:
        raise SystemExit(1)

    typer.echo("OK: Lean4 proving integration working")


if __name__ == "__main__":
    app()
