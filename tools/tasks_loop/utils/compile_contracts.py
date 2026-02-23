#!/usr/bin/env python3
"""
compile_contracts.py - Compile fixture SPEC.md (YAML frontmatter) into per-step contracts.

Usage:
    python utils/compile_contracts.py                    # All fixtures
    python utils/compile_contracts.py --fixture NAME    # Specific fixture

SPEC.md uses YAML frontmatter for easy/reliable parsing.
Contracts are generated per-step in fixtures/{name}/contracts/

MUST be run whenever any SPEC.md changes.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
TASKS_LOOP_DIR = SCRIPT_DIR.parent
FIXTURES_DIR = TASKS_LOOP_DIR / "fixtures"


def parse_yaml_frontmatter(content: str) -> Dict[str, Any]:
    """Extract and parse YAML frontmatter from markdown."""
    if not content.startswith("---"):
        raise ValueError("SPEC.md must start with YAML frontmatter (---)")

    # Split on --- to get frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SPEC.md frontmatter must end with ---")

    frontmatter = parts[1].strip()
    return yaml.safe_load(frontmatter)


def validate_spec(spec: Dict[str, Any]) -> bool:
    """Basic schema validation (until jsonschema is available)."""
    required = ["fixture", "pdf", "steps"]
    for field in required:
        if field not in spec:
            print(f"  ❌ Missing required field: {field}")
            return False
    return True


def compile_fixture(fixture_name: str) -> int:
    """Compile a fixture's SPEC.md into per-step contracts and runtime config."""
    fixture_dir = FIXTURES_DIR / fixture_name
    spec_file = fixture_dir / "SPEC.md"

    if not spec_file.exists():
        print(f"ERROR: SPEC.md not found at {spec_file}")
        return 1

    contracts_dir = fixture_dir / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)

    content = spec_file.read_text()

    try:
        spec = parse_yaml_frontmatter(content)
    except Exception as e:
        print(f"ERROR: Failed to parse YAML frontmatter: {e}")
        return 1

    print(f"\n== Fixture: {fixture_name} ==")

    # Validation
    if not validate_spec(spec):
        print("  ❌ Schema Validation Failed")
        return 1
    print("  ✅ Schema Validation Passed")

    # Compile Configuration (Intent)
    config = spec.get("config")
    if config:
        pdf_path = Path(spec.get("pdf", ""))
        pdf_name = pdf_path.stem
        # Maps to {pdf_name}_profile.json
        # S08 searches for this file relative to PDF or CWD.
        # We save it in the fixture dir (where the PDF usually is or mimicking struct)
        profile_path = fixture_dir / f"{pdf_name}_profile.json"
        profile_path.write_text(json.dumps(config, indent=2))
        print(f"  ✅ Compiled Config -> {profile_path.name}")

    steps = spec.get("steps", {})
    sanity_deps = spec.get("sanity_dependencies", {})

    print(f"  PDF: {spec.get('pdf', 'N/A')}")
    print(f"  Steps: {len(steps)}")

    known_steps = [
        "s00",
        "s01",
        "s02",
        "s03",
        "s04",
        "s04a",
        "s05",
        "s05b",
        "s05c",
        "s06",
        "s06b",
        "s07",
        "s08",
        "s09",
        "s10",
        "s14",
    ]

    # Merge specified steps with defaults for missing ones
    for step_id in known_steps:
        step_data = steps.get(step_id, {})

        contract = {
            "step": step_id,
            "fixture": fixture_name,
            "name": step_data.get("name", f"Auto-Generated {step_id.upper()}"),
            "output": step_data.get("output", ""),
            "format": step_data.get("format", []),
            "expected": step_data.get("expected", {}),
            "sanity": sanity_deps.get(step_id, []),
        }

        filepath = contracts_dir / f"{step_id}.json"
        filepath.write_text(json.dumps(contract, indent=2))

        status = "✅" if step_id in steps else "⚠️"
        print(f"    {status} {step_id}: {contract['name']}")

    return 0


def compile_all() -> int:
    """Compile all fixtures."""
    if not FIXTURES_DIR.exists():
        print("ERROR: fixtures/ directory not found")
        return 1

    fixtures = [d for d in FIXTURES_DIR.iterdir() if d.is_dir() and (d / "SPEC.md").exists()]

    if not fixtures:
        print("No fixtures with SPEC.md found")
        return 1

    for fixture_dir in fixtures:
        result = compile_fixture(fixture_dir.name)
        if result != 0:
            return result

    print(f"\n✅ Compiled {len(fixtures)} fixture(s)")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compile fixture specs into contracts")
    parser.add_argument("--fixture", help="Compile specific fixture only")
    args = parser.parse_args()

    if args.fixture:
        sys.exit(compile_fixture(args.fixture))
    else:
        sys.exit(compile_all())
