#!/usr/bin/env python3
"""
auto_tune.py - Agentic Repair Loop

Analyzes discrepancy between EXPECTED (Ground Truth) and ACTUAL (Pipeline Output).
Proposes configuration changes to fix the drift.

Usage:
    python tools/tasks_loop/auto_tune.py <fixture_path> [--apply]
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any, List


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text())


def analyze_table_failure(fixture_dir: Path, expected: Dict, actual: Dict) -> List[str]:
    proposals = []

    # 1. Count Mismatch
    exp_tables = [i for i in expected.get("content", []) if i.get("type", "").lower() == "table"]

    # Actual tables usually in data/results/pipeline/05_table_extractor/json_output
    # But for now we might rely on s10 output or direct validation metrics
    # Simplified logic: If we have 0 Actual Tables but Expected > 0

    # Check if we can find the 05 output
    results_dir = (
        fixture_dir.parent.parent.parent
        / "data"
        / "results"
        / "pipeline"
        / "05_table_extractor"
        / "json_output"
        / "05_tables.json"
    )
    actual_tables = []
    if results_dir.exists():
        actual_tables = load_json(results_dir).get("tables", [])

    cnt_exp = len(exp_tables)
    cnt_act = len(actual_tables)

    if cnt_exp > cnt_act:
        proposals.append(
            f"[Table] Expected {cnt_exp} tables, found {cnt_act}. Try increasing line_scale (Config Key: camelot.line_scale -> 20)"
        )
    elif cnt_act > cnt_exp:
        proposals.append(
            f"[Table] Found {cnt_act} tables, expected {cnt_exp}. Try increasing text_heavy_threshold (Config Key: heuristics.avg_words -> 6.0)"
        )

    return proposals


def analyze_requirement_failure(fixture_dir: Path, expected: Dict, actual: Dict) -> List[str]:
    proposals = []

    exp_reqs = [i for i in expected.get("content", []) if "req" in i.get("type", "").lower()]

    # Actual requirements in s08 output
    results_dir = (
        fixture_dir.parent.parent.parent
        / "data"
        / "results"
        / "pipeline"
        / "08_extract_requirements"
        / "json_output"
        / "08_requirements.json"
    )
    actual_reqs = []
    actual_ids = set()
    if results_dir.exists():
        actual_reqs = load_json(results_dir).get("requirements", [])
        actual_ids = {r.get("id") for r in actual_reqs if r.get("id")}

    for req in exp_reqs:
        rid = req.get("id")
        if rid and rid not in actual_ids:
            # Missed Requirement
            prefix = rid.split("-")[0] + "-" if "-" in rid else rid[:3]
            proposals.append(
                f"[Req] Missed ID {rid}. Suggest adding prefix '{prefix}' to domain_patterns.yml id_prefixes"
            )

    return proposals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path, help="Path to fixture directory")
    parser.add_argument("--apply", action="store_true", help="Apply fixes (Interactive)")
    args = parser.parse_args()

    if not args.fixture.exists():
        print(f"Error: {args.fixture} not found")
        sys.exit(1)

    # Load Truth
    expected_path = args.fixture / "source_expected.json"
    if not expected_path.exists():
        print(f"Error: Ground Truth {expected_path} not found")
        sys.exit(1)

    expected = load_json(expected_path)
    actual = {}  # TODO: Load aggregate actuals

    print(f"Analyzing {args.fixture.name}...")

    fixes = []
    fixes.extend(analyze_table_failure(args.fixture, expected, actual))
    fixes.extend(analyze_requirement_failure(args.fixture, expected, actual))

    if not fixes:
        print("✅ No tuning suggestions found. Pipeline seems aligned.")
        return

    print("\n⚠️  Suggested Fixes:")
    for i, fix in enumerate(fixes):
        print(f"{i+1}. {fix}")

    if args.apply:
        print("\n🔧 Applying fixes to SPEC.md...")

        spec_path = args.fixture / "SPEC.md"
        if not spec_path.exists():
            print(f"Error: No SPEC.md found at {spec_path}")
            sys.exit(1)

        # Read current SPEC
        content = spec_path.read_text()

        # Parse YAML frontmatter
        if not content.startswith("---"):
            print("Error: SPEC.md must have YAML frontmatter")
            sys.exit(1)

        parts = content.split("---", 2)
        if len(parts) < 3:
            print("Error: Invalid SPEC.md format")
            sys.exit(1)

        frontmatter = yaml.safe_load(parts[1])
        body = parts[2]

        # Ensure config section exists
        if "config" not in frontmatter:
            frontmatter["config"] = {}
        if "requirement_patterns" not in frontmatter["config"]:
            frontmatter["config"]["requirement_patterns"] = {}

        # Apply fixes based on suggestions
        patterns = frontmatter["config"]["requirement_patterns"]

        for fix in fixes:
            if "[Req] Missed ID" in fix and "prefix" in fix:
                # Extract prefix from suggestion
                import re

                match = re.search(r"prefix '([^']+)'", fix)
                if match:
                    prefix = match.group(1)
                    if "id_prefixes" not in patterns:
                        patterns["id_prefixes"] = []
                    if prefix not in patterns["id_prefixes"]:
                        patterns["id_prefixes"].append(prefix)
                        print(f"  ✅ Added id_prefix: {prefix}")

            elif "[Table]" in fix and "line_scale" in fix:
                # Add camelot config
                if "camelot" not in frontmatter["config"]:
                    frontmatter["config"]["camelot"] = {}
                frontmatter["config"]["camelot"]["line_scale"] = 20
                print("  ✅ Set camelot.line_scale: 20")

        # Write updated SPEC
        with open(spec_path, "w") as f:
            f.write("---\n")
            yaml.dump(frontmatter, f, sort_keys=False)
            f.write("---")
            f.write(body)

        print(f"\n✅ Updated {spec_path}")
        print("Run compile_contracts.py to regenerate contracts.")


if __name__ == "__main__":
    main()
