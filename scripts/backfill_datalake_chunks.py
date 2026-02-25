#!/usr/bin/env python3
"""Backfill datalake_chunks from existing extracted profiles.

Iterates through extracted_runs directories and calls sync_to_datalake()
for each profile that has assembled_content.json + flattened data.

This fixes the gap where extractions were run without --learn flag,
so sync_to_datalake() was never called.

Usage:
    python scripts/backfill_datalake_chunks.py [--limit N] [--dry-run] [--tables-only]
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Add extractor src to path
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Ensure SYNC_TO_MEMORY is enabled
os.environ["SYNC_TO_MEMORY"] = "1"


def find_all_run_dirs():
    """Find all extracted run directories across all locations."""
    dirs = []
    locations = [
        Path("/home/graham/workspace/experiments/pi-mono/.pi/skills/review-pdf/extracted_runs_staging"),
        Path("/home/graham/workspace/experiments/pi-mono/.pi/skills/review-pdf/extracted_runs"),
        Path("/mnt/storage12tb/skills/review-pdf/extracted_runs"),
    ]
    for loc in locations:
        if not loc.exists():
            continue
        for entry in loc.iterdir():
            target = entry.resolve() if entry.is_symlink() else entry
            if target.is_dir():
                dirs.append(target)
    # Deduplicate by resolved path
    seen = set()
    unique = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def build_doc_meta(run_dir: Path) -> dict | None:
    """Build doc_meta dict matching S10 expectations."""
    slug = run_dir.name
    doc_hash = hashlib.md5(slug.encode()).hexdigest()
    doc_key = f"doc_{doc_hash}"

    doc_meta = {
        "_key": doc_key,
        "filename": slug,
        "path": str(run_dir),
    }

    # Load S00 profile for metadata
    profile_path = run_dir / "00_profile_detector" / "profile.json"
    if profile_path.exists():
        try:
            s00 = json.loads(profile_path.read_text())
            elements = s00.get("elements", {})
            doc_meta["profile"] = {
                "page_count": s00.get("page_count", 0),
                "domain": s00.get("domain", "unknown"),
                "file_size_mb": s00.get("file_size_mb", 0),
                "table_count": elements.get("estimated_table_count", 0),
                "table_pages": elements.get("table_pages", 0),
                "has_tables": bool(elements.get("tables", False)),
                "has_figures": bool(elements.get("figures", False)),
                "image_pages": elements.get("image_pages", 0),
                "has_formulas": bool(elements.get("formulas", False)),
                "has_requirements": bool(elements.get("requirements", False)),
                "section_estimate": s00.get("hierarchy", {}).get("estimated_sections", 0),
                "layout_columns": s00.get("layout", {}).get("columns", 1),
                "detected_preset": s00.get("detected_preset", ""),
            }
        except Exception:
            pass

    return doc_meta, doc_key


def load_flattened_data(run_dir: Path) -> list | None:
    """Load flattened data from S10 output or build from assembled_content."""
    # Try pre-built flattened data first
    flat_path = run_dir / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if flat_path.exists():
        try:
            return json.loads(flat_path.read_text())
        except Exception:
            pass

    # Fall back to S11 structural.json
    structural_path = run_dir / "11_json_exporter" / "structural.json"
    if structural_path.exists():
        try:
            data = json.loads(structural_path.read_text())
            items = data if isinstance(data, list) else data.get("elements", data.get("sections", []))
            if isinstance(items, list) and items:
                return items
        except Exception:
            pass

    return None


def count_tables(data: list) -> int:
    """Count table entries in flattened data."""
    return sum(
        1 for item in data
        if (item.get("object_type", "") or item.get("type", "")).lower() == "table"
    )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max profiles to process (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Count without writing")
    parser.add_argument("--tables-only", action="store_true", help="Only process profiles with tables")
    args = parser.parse_args()

    print("Scanning extracted runs...")
    run_dirs = find_all_run_dirs()
    print(f"Found {len(run_dirs)} unique extracted run directories")

    # Filter to those with usable data
    candidates = []
    total_tables = 0
    for rd in run_dirs:
        flat_data = load_flattened_data(rd)
        if not flat_data:
            continue
        tables = count_tables(flat_data)
        if args.tables_only and tables == 0:
            continue
        candidates.append((rd, flat_data, tables))
        total_tables += tables

    print(f"Profiles with flattened data: {len(candidates)}")
    print(f"Total table chunks: {total_tables}")
    print(f"Profiles with tables: {sum(1 for _, _, t in candidates if t > 0)}")

    if args.dry_run:
        print("\n--dry-run: not writing to ArangoDB")
        # Show sample
        for rd, data, tables in candidates[:5]:
            print(f"  {rd.name}: {len(data)} items, {tables} tables")
        return

    # Import sync_to_datalake
    try:
        from extractor.pipeline.steps.s10_arangodb_exporter import sync_to_datalake
    except ImportError as e:
        print(f"ERROR: Cannot import s10_arangodb_exporter: {e}")
        print("Make sure extractor venv is active or PYTHONPATH includes src/")
        sys.exit(1)

    to_process = candidates[:args.limit] if args.limit > 0 else candidates
    processed = 0
    errors = 0
    t0 = time.time()

    for i, (rd, flat_data, tables) in enumerate(to_process):
        try:
            doc_meta, doc_key = build_doc_meta(rd)
            sync_to_datalake(doc_meta, flat_data, doc_key)
            processed += 1

            if (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                rate = processed / elapsed if elapsed > 0 else 0
                print(
                    f"  [{i+1}/{len(to_process)}] processed={processed} errors={errors} "
                    f"rate={rate:.1f}/s elapsed={elapsed:.0f}s"
                )
        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"  ERROR {rd.name}: {e}")

    elapsed = time.time() - t0
    print(f"\nBackfill complete:")
    print(f"  Processed: {processed}/{len(to_process)}")
    print(f"  Errors: {errors}")
    print(f"  Elapsed: {elapsed:.0f}s ({processed/elapsed:.1f}/s)" if elapsed > 0 else "")


if __name__ == "__main__":
    main()
