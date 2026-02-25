#!/usr/bin/env python3
"""Batch re-extract S05 (Table Extractor) on all corpus PDFs.

Re-runs S05 with the corrected fragmentation scoring so that stored
fragmentation_score values and strategy selections reflect the latest
metrics.py changes (stopword filter, CamelCase check, etc.).

Usage:
    python scripts/batch_s05_reextract.py [--dry-run] [--max N] [--timeout SECS]
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

CORPUS_ROOT = Path(os.getenv(
    "CORPUS_ROOT",
    "/mnt/storage12tb/extractor_corpus",
))
RESULTS_DIR = CORPUS_ROOT / "results"


def _timeout_for_pdf(pdf_dir: Path, default: int = 600) -> int:
    """Estimate timeout based on page count from S00 profile."""
    profile = pdf_dir / "00_profile_detector" / "json_output" / "00_profile.json"
    if profile.exists():
        try:
            data = json.loads(profile.read_text())
            pages = data.get("page_count", 0)
            if pages > 100:
                return max(default, pages * 10)  # ~10s per page for large docs
        except Exception:
            pass
    return default


def run_batch(dry_run: bool = False, max_pdfs: int = 0, timeout: int = 600):
    from extractor.pipeline.steps.s05_table_extractor import run as s05_run

    pdf_dirs = sorted(
        d for d in RESULTS_DIR.iterdir()
        if d.is_dir()
        and (d / "04_section_builder" / "json_output" / "04_sections.json").exists()
    )
    total = len(pdf_dirs)
    if max_pdfs > 0:
        pdf_dirs = pdf_dirs[:max_pdfs]
        total = len(pdf_dirs)

    print(f"=== S05 Batch Re-Extraction ===")
    print(f"Corpus: {RESULTS_DIR}")
    print(f"PDFs to process: {total}")
    print(f"Default timeout: {timeout}s")
    if dry_run:
        print("DRY RUN — no extraction will happen")
    print()

    succeeded = 0
    failed = 0
    skipped = 0
    total_time = 0.0

    for i, pdf_dir in enumerate(pdf_dirs, 1):
        name = pdf_dir.name
        s04_json = pdf_dir / "04_section_builder" / "json_output" / "04_sections.json"
        pdf_subdir = pdf_dir / "01_annotation_processor"

        if not pdf_subdir.exists():
            print(f"[{i}/{total}] {name}: SKIP (no 01_annotation_processor)")
            skipped += 1
            continue

        pdf_timeout = _timeout_for_pdf(pdf_dir, timeout)

        if dry_run:
            print(f"[{i}/{total}] {name}: would re-extract (timeout={pdf_timeout}s)")
            continue

        print(f"[{i}/{total}] {name}...", end=" ", flush=True)
        t0 = time.monotonic()

        try:
            # Use alarm for hard timeout
            def _alarm_handler(signum, frame):
                raise TimeoutError(f"S05 exceeded {pdf_timeout}s timeout")

            old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
            signal.alarm(pdf_timeout)

            s05_run(
                input_json=s04_json,
                pdf_dir=pdf_subdir,
                output_dir=pdf_dir,
            )

            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

            elapsed = time.monotonic() - t0
            total_time += elapsed

            # Read result for summary
            tables_json = pdf_dir / "05_table_extractor" / "json_output" / "05_tables.json"
            ntables = 0
            total_frag = 0
            if tables_json.exists():
                data = json.loads(tables_json.read_text())
                ntables = len(data.get("tables", []))
                total_frag = sum(
                    t.get("fragmentation_score", 0) for t in data.get("tables", [])
                )

            print(f"OK ({elapsed:.1f}s, {ntables} tables, frag={total_frag})")
            succeeded += 1

        except TimeoutError as e:
            signal.alarm(0)
            elapsed = time.monotonic() - t0
            total_time += elapsed
            print(f"TIMEOUT ({elapsed:.0f}s)")
            failed += 1

        except Exception as e:
            signal.alarm(0)
            elapsed = time.monotonic() - t0
            total_time += elapsed
            err = str(e)[:80]
            print(f"FAIL ({elapsed:.1f}s): {err}")
            failed += 1

    print()
    print(f"=== Summary ===")
    print(f"Processed: {succeeded + failed + skipped}/{total}")
    print(f"Succeeded: {succeeded}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Total time: {total_time/60:.1f} min")
    if succeeded > 0:
        print(f"Avg time per PDF: {total_time/succeeded:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Batch S05 re-extraction")
    parser.add_argument("--dry-run", action="store_true", help="Just list PDFs")
    parser.add_argument("--max", type=int, default=0, help="Max PDFs to process (0=all)")
    parser.add_argument("--timeout", type=int, default=600, help="Default timeout per PDF (s)")
    args = parser.parse_args()
    run_batch(dry_run=args.dry_run, max_pdfs=args.max, timeout=args.timeout)


if __name__ == "__main__":
    main()
