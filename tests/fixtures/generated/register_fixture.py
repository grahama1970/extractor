#!/usr/bin/env python3
"""Register a new fixture from /debug-pdf, /debug-table, or /fixture-tricky.

Usage:
    python register_fixture.py <pdf_path> --name <name> --source <skill> [options]

Example:
    python register_fixture.py /tmp/gauntlet.pdf \
        --name "gauntlet-false-positives" \
        --source "fixture-tricky" \
        --should-have-no-tables \
        --tags "false-positive,gauntlet"

This script:
1. Copies the PDF to tests/fixtures/generated/
2. Updates manifest.yaml with the fixture metadata
3. The fixture becomes part of the test suite automatically
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

FIXTURE_DIR = Path(__file__).parent
MANIFEST_FILE = FIXTURE_DIR / "manifest.yaml"


def load_manifest() -> dict:
    """Load existing manifest or create empty one."""
    if MANIFEST_FILE.exists():
        return yaml.safe_load(MANIFEST_FILE.read_text()) or {"fixtures": []}
    return {"fixtures": []}


def save_manifest(manifest: dict) -> None:
    """Save manifest to YAML."""
    MANIFEST_FILE.write_text(yaml.dump(manifest, default_flow_style=False, sort_keys=False))


def register_fixture(
    pdf_path: Path,
    name: str,
    source: str,
    expected_table_count: int | None = None,
    should_have_no_tables: bool = False,
    max_fragmentation: int | None = None,
    test_sections: bool = False,
    expected_section_count: int | None = None,
    test_profile: bool = False,
    expected_domain: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None,
) -> Path:
    """Register a fixture and copy it to the fixtures directory."""

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Generate filename from name
    safe_name = name.replace(" ", "_").replace("-", "_").lower()
    filename = f"{safe_name}.pdf"
    dest_path = FIXTURE_DIR / filename

    # Copy PDF
    shutil.copy2(pdf_path, dest_path)
    print(f"Copied: {pdf_path} -> {dest_path}")

    # Build fixture entry
    entry = {
        "name": name,
        "filename": filename,
        "source_skill": source,
        "registered_at": datetime.utcnow().isoformat(),
        "tags": tags or [],
    }

    if description:
        entry["description"] = description

    # Table extraction expectations
    if should_have_no_tables:
        entry["should_have_no_tables"] = True
    elif expected_table_count is not None:
        entry["expected_table_count"] = expected_table_count

    if max_fragmentation is not None:
        entry["max_fragmentation"] = max_fragmentation

    # Section expectations
    if test_sections:
        entry["test_sections"] = True
        if expected_section_count is not None:
            entry["expected_section_count"] = expected_section_count

    # Profile expectations
    if test_profile:
        entry["test_profile"] = True
        if expected_domain:
            entry["expected_domain"] = expected_domain

    # Update manifest
    manifest = load_manifest()

    # Remove existing entry with same name if exists
    manifest["fixtures"] = [f for f in manifest["fixtures"] if f["name"] != name]
    manifest["fixtures"].append(entry)

    save_manifest(manifest)
    print(f"Registered fixture: {name}")
    print(f"Manifest updated: {MANIFEST_FILE}")

    return dest_path


def main():
    """Register a testing fixture with specified PDF path and options."""
    parser = argparse.ArgumentParser(description="Register a fixture for testing")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF file")
    parser.add_argument("--name", required=True, help="Fixture name")
    parser.add_argument("--source", required=True, choices=["debug-pdf", "debug-table", "fixture-tricky", "manual"],
                        help="Source skill that generated this fixture")
    parser.add_argument("--expected-table-count", type=int, help="Expected number of tables")
    parser.add_argument("--should-have-no-tables", action="store_true",
                        help="Fixture should detect NO tables (false positive test)")
    parser.add_argument("--max-fragmentation", type=int, help="Maximum allowed fragmentation percentage")
    parser.add_argument("--test-sections", action="store_true", help="Enable section detection testing")
    parser.add_argument("--expected-section-count", type=int, help="Expected section count")
    parser.add_argument("--test-profile", action="store_true", help="Enable profile detection testing")
    parser.add_argument("--expected-domain", help="Expected domain (scientific, engineering, etc.)")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--description", help="Description of what this fixture tests")

    args = parser.parse_args()

    tags = args.tags.split(",") if args.tags else None

    try:
        register_fixture(
            pdf_path=args.pdf_path,
            name=args.name,
            source=args.source,
            expected_table_count=args.expected_table_count,
            should_have_no_tables=args.should_have_no_tables,
            max_fragmentation=args.max_fragmentation,
            test_sections=args.test_sections,
            expected_section_count=args.expected_section_count,
            test_profile=args.test_profile,
            expected_domain=args.expected_domain,
            tags=tags,
            description=args.description,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
