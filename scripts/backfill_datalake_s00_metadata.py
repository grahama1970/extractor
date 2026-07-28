#!/usr/bin/env python3
"""Backfill existing datalake_docs with S00 profile metadata.

Scans the corpus for 00_profile_detector/profile.json files, extracts S00
metadata fields, and upserts them into ArangoDB datalake_docs documents.

Handles two key formats:
- Old SPARTA batch: _key = slug (16-char hex, e.g., "047ca6ef3556a930")
- New S10 pipeline: _key = f"doc_{md5(slug)}"

Usage:
    python scripts/backfill_datalake_s00_metadata.py /mnt/storage12tb/extractor_corpus
    python scripts/backfill_datalake_s00_metadata.py /mnt/storage12tb/extractor_corpus --dry-run
    python scripts/backfill_datalake_s00_metadata.py /mnt/storage12tb/extractor_corpus --insert-missing
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arango import ArangoClient  # noqa: E402


def get_memory_db():
    """Connect to the memory database using the same env vars as S10."""
    hosts = os.getenv("ARANGO_HOST") or os.getenv("ARANGO_URL", "http://localhost:8529")
    if not hosts.startswith("http"):
        hosts = f"http://{hosts}:{os.getenv('ARANGO_PORT', '8529')}"
    db_name = os.getenv("MEMORY_ARANGO_DB", "memory")
    user = os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASSWORD") or os.getenv("ARANGO_PASS", "openSesame")

    client = ArangoClient(hosts=hosts)
    return client.db(db_name, username=user, password=password)


def extract_s00_fields(profile: dict) -> dict:
    """Extract S00 metadata fields from a profile.json dict."""
    elements = profile.get("elements", {}) or {}
    hierarchy = profile.get("hierarchy", {}) or {}
    layout = profile.get("layout", {}) or {}

    return {
        "page_count": profile.get("page_count", 0),
        "domain": str(profile.get("domain") or "unknown"),
        "file_size_mb": float(profile.get("file_size_mb") or 0),
        "table_count": int(elements.get("estimated_table_count") or 0),
        "table_pages": int(elements.get("table_pages") or 0),
        "has_tables": bool(elements.get("tables", False)),
        "has_figures": bool(elements.get("figures", False)),
        "image_pages": int(elements.get("image_pages") or 0),
        "has_formulas": bool(elements.get("formulas", False)),
        "has_requirements": bool(elements.get("requirements", False)),
        "section_estimate": int(
            hierarchy.get("estimated_sections") or elements.get("estimated_section_count") or 0
        ),
        "layout_columns": int(layout.get("columns") or 1),
        "detected_preset": str(profile.get("detected_preset") or ""),
    }


def find_profiles(corpus_dir: Path):
    """Find all profile.json files in the corpus."""
    for profile_path in corpus_dir.rglob("00_profile_detector/profile.json"):
        yield profile_path


def main():
    """Backfill datalake_docs with S00 metadata from the specified corpus."""
    parser = argparse.ArgumentParser(description="Backfill datalake_docs with S00 metadata")
    parser.add_argument("corpus_dir", type=Path, help="Path to extractor corpus")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be updated")
    parser.add_argument("--insert-missing", action="store_true",
                        help="Insert new docs for profiles not yet in ArangoDB")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of docs to process")
    args = parser.parse_args()

    corpus_dir = args.corpus_dir.resolve()
    if not corpus_dir.is_dir():
        print(f"ERROR: {corpus_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    if not args.dry_run:
        db = get_memory_db()
        if not db.has_collection("datalake_docs"):
            print("ERROR: datalake_docs collection does not exist", file=sys.stderr)
            sys.exit(1)
        col = db.collection("datalake_docs")

        # Load all existing keys for fast lookup
        existing_keys = set()
        cursor = db.aql.execute("FOR d IN datalake_docs RETURN d._key")
        for key in cursor:
            existing_keys.add(key)
        print(f"Existing datalake_docs: {len(existing_keys)}")
    else:
        col = None
        existing_keys = set()

    profiles = list(find_profiles(corpus_dir))
    print(f"Found {len(profiles)} profile.json files in {corpus_dir}")

    updated = 0
    inserted = 0
    skipped = 0
    missing = 0
    errors = 0

    for i, profile_path in enumerate(profiles):
        if args.limit and (updated + inserted + skipped + missing) >= args.limit:
            break

        try:
            profile = json.loads(profile_path.read_text())
        except Exception as e:
            print(f"  ERROR reading {profile_path}: {e}")
            errors += 1
            continue

        # The run dir containing 00_profile_detector
        run_dir = profile_path.parent.parent
        slug = run_dir.name
        source_file = profile.get("source_file") or profile.get("file") or str(run_dir)

        s00_fields = extract_s00_fields(profile)

        # Try both key formats:
        # 1. Old format: _key = slug (for old SPARTA batch docs)
        # 2. New format: _key = f"doc_{md5(slug)}"
        old_key = slug
        new_key = f"doc_{hashlib.md5(slug.encode()).hexdigest()}"

        if args.dry_run:
            print(f"  WOULD UPSERT {new_key} (slug={slug}): pages={s00_fields['page_count']}, "
                  f"tables={s00_fields['table_count']}, domain={s00_fields['domain']}")
            updated += 1
            continue

        try:
            # Check old key first (existing 164 docs)
            if old_key in existing_keys:
                col.update({"_key": old_key, **s00_fields})
                updated += 1
            elif new_key in existing_keys:
                col.update({"_key": new_key, **s00_fields})
                updated += 1
            elif args.insert_missing:
                # Insert new doc with S00 metadata
                doc = {
                    "_key": new_key,
                    "source": source_file,
                    "path": str(run_dir),
                    "full_text": "",
                    "entities": [],
                    "source_meta": {
                        "title": Path(source_file).name,
                        "backfilled": True,
                    },
                    "content_type": "canon",
                    **s00_fields,
                }
                col.insert(doc, overwrite=True)
                inserted += 1
            else:
                missing += 1

            total = updated + inserted
            if total > 0 and total % 1000 == 0:
                print(f"  Progress: {updated} updated, {inserted} inserted, "
                      f"{skipped} skipped, {missing} not in ArangoDB, {errors} errors")
        except Exception as e:
            print(f"  ERROR on {slug}: {e}")
            errors += 1

    print(f"\nDone: {updated} updated, {inserted} inserted, "
          f"{skipped} skipped, {missing} not in ArangoDB, {errors} errors")


if __name__ == "__main__":
    main()
