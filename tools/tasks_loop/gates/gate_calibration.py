#!/usr/bin/env python3
"""Flight check gate for calibration sessions.

Validates a calibration session meets quality thresholds before preset generation.

Usage:
    python gate_calibration.py --session-id <session_id>

Exit codes:
    0: PASS - All checks pass
    1: FAIL - One or more checks failed
"""

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class FlightCheckResult:
    """Result of flight check validation."""

    passed: bool
    checks: dict[str, bool]
    stats: dict[str, Any]
    missing: list[str]
    message: str


def run_flight_check(session_key: str) -> FlightCheckResult:
    """Run flight check on a calibration session.

    Checks:
    1. Minimum examples (>=20)
    2. Accuracy threshold (>=90%)
    3. All element types have >=3 examples
    4. At least one pattern per type (optional)

    Args:
        session_key: Session key to validate.

    Returns:
        FlightCheckResult with pass/fail status.
    """
    from extractor.pipeline.calibration import (
        CalibrationSchema,
        FeedbackHandler,
        PatternLearner,
    )

    schema = CalibrationSchema()
    session = schema.get_session(session_key)

    if not session:
        return FlightCheckResult(
            passed=False,
            checks={},
            stats={},
            missing=["session_not_found"],
            message=f"Session '{session_key}' not found",
        )

    handler = FeedbackHandler(schema)
    stats = handler.get_session_stats(session_key)

    # Run checks
    checks = {
        "min_examples": stats["reviewed"] >= 20,
        "accuracy_threshold": stats["accuracy"] >= 90.0,
        "has_headers": stats["by_type"].get("header", {}).get("reviewed", 0) >= 3,
        "has_tables": stats["by_type"].get("table", {}).get("reviewed", 0) >= 3,
        "has_figures": stats["by_type"].get("figure", {}).get("reviewed", 0) >= 3,
    }

    # Check for patterns (optional but recommended)
    preset_id = session.get("preset_id", session_key)
    learner = PatternLearner(schema)
    patterns = learner.get_active_patterns(preset_id)

    checks["has_patterns"] = len(patterns) > 0

    # Determine pass/fail
    required_checks = [
        "min_examples",
        "accuracy_threshold",
        "has_headers",
        "has_tables",
        "has_figures",
    ]
    all_required_pass = all(checks[c] for c in required_checks)

    missing = [name for name in required_checks if not checks[name]]

    if all_required_pass:
        message = "All flight checks passed!"
    else:
        message = f"Flight check failed: {', '.join(missing)}"

    return FlightCheckResult(
        passed=all_required_pass,
        checks=checks,
        stats={
            "reviewed": stats["reviewed"],
            "accuracy": stats["accuracy"],
            "by_type": stats["by_type"],
            "patterns": len(patterns),
        },
        missing=missing,
        message=message,
    )


def format_flight_check(result: FlightCheckResult) -> str:
    """Format flight check result for display.

    Args:
        result: FlightCheckResult to format.

    Returns:
        Formatted string.
    """
    lines = ["Flight Check Results:", ""]

    for check_name, passed in result.checks.items():
        status = "✔" if passed else "✗"
        display_name = check_name.replace("_", " ").title()
        lines.append(f"  {status} {display_name}")

    lines.append("")
    lines.append(f"FLIGHT CHECK: {'PASS' if result.passed else 'FAIL'}")

    if not result.passed:
        lines.append("")
        lines.append(f"Missing: {', '.join(result.missing)}")

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Calibration flight check gate")
    parser.add_argument("--session-id", required=True, help="Session ID to validate")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = run_flight_check(args.session_id)

    if args.json:
        output = {
            "passed": result.passed,
            "checks": result.checks,
            "stats": result.stats,
            "missing": result.missing,
            "message": result.message,
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_flight_check(result))

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
