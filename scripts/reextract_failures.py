#!/usr/bin/env python3
"""
Re-extract PDFs that failed in the continuous learning daemon.

Parses the daemon log for timeout failures and re-runs extraction
with improved timeout parameters and source-specific multipliers.

Usage:
    python scripts/reextract_failures.py --dry-run    # Show what would be done
    python scripts/reextract_failures.py              # Actually re-extract
    python scripts/reextract_failures.py --limit 100  # Process first 100 failures
"""
import json
import re
import subprocess
import sys
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from loguru import logger

LOG_FILE = Path.home() / ".pi" / "continuous-learning" / "daemon.log"
RESULTS_DIR = Path("/mnt/storage12tb/extractor_corpus/results")
EXTRACTOR_ROOT = Path(__file__).parent.parent


def parse_failures(log_file: Path) -> list[dict]:
    """Parse daemon log for failures."""
    failures = []
    seen = set()

    with open(log_file) as f:
        for line in f:
            if '"success": false' not in line:
                continue

            try:
                # Extract JSON from log line
                json_start = line.find("{")
                if json_start == -1:
                    continue
                data = json.loads(line[json_start:])

                pdf_path = data.get("pdf", "")
                error = data.get("error", "")

                # Skip duplicates
                if pdf_path in seen:
                    continue
                seen.add(pdf_path)

                if "Timeout" in error:
                    # Skip files inside results directories (shouldn't have been processed)
                    source = data.get("source", "unknown")
                    if source in ("01_annotation_processor", "results"):
                        continue
                    if "/results/" in pdf_path:
                        continue

                    failures.append({
                        "pdf": pdf_path,
                        "error": error,
                        "source": source,
                    })
            except json.JSONDecodeError:
                continue

    return failures


def get_source_timeout(source: str) -> int:
    """Get timeout for source type (matches daemon logic)."""
    SOURCE_MULTIPLIERS = {
        "arxiv": 2.5,
        "archive_org": 2.0,
        "ietf": 1.5,
        "defense": 1.3,
        "nasa": 1.3,
        "nist": 1.2,
    }
    base = 300  # seconds
    mult = SOURCE_MULTIPLIERS.get(source, 1.0)
    return int(base * mult)


def reextract_pdf(pdf_path: str, source: str, timeout: int) -> dict:
    """Re-extract a single PDF with improved timeout."""
    pdf = Path(pdf_path)
    if not pdf.exists():
        return {"pdf": pdf_path, "success": False, "error": "File not found"}

    output_dir = RESULTS_DIR / pdf.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "extractor.pipeline.cli",
        str(pdf),
        "--out", str(output_dir),
        "--fast-batch",        # Skip heavy LLM stages (summarizer, descriptions)
        "--skip-llm03",        # Skip VLM verification
        "--continue-on-error",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(EXTRACTOR_ROOT),
        )

        if proc.returncode == 0:
            return {"pdf": pdf_path, "success": True, "source": source, "timeout": timeout}
        else:
            return {"pdf": pdf_path, "success": False, "error": proc.stderr[:500], "source": source}

    except subprocess.TimeoutExpired:
        return {"pdf": pdf_path, "success": False, "error": f"Timeout after {timeout}s", "source": source}
    except Exception as e:
        return {"pdf": pdf_path, "success": False, "error": str(e), "source": source}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Re-extract failed PDFs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of PDFs to process")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--source", type=str, help="Only process failures from this source")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    logger.info(f"Parsing failures from {LOG_FILE}")
    failures = parse_failures(LOG_FILE)

    if args.source:
        failures = [f for f in failures if f["source"] == args.source]

    logger.info(f"Found {len(failures)} timeout failures")

    # Count by source
    by_source = Counter(f["source"] for f in failures)
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        timeout = get_source_timeout(source)
        logger.info(f"  {source}: {count} failures (new timeout: {timeout}s)")

    if args.limit:
        failures = failures[:args.limit]
        logger.info(f"Processing first {args.limit} failures")

    if args.dry_run:
        logger.info("Dry run - not actually processing")
        return

    # Process failures
    successful = 0
    still_failed = 0
    results = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for failure in failures:
            timeout = get_source_timeout(failure["source"])
            future = executor.submit(reextract_pdf, failure["pdf"], failure["source"], timeout)
            futures[future] = failure

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result["success"]:
                successful += 1
                logger.info(f"SUCCESS: {Path(result['pdf']).name}")
            else:
                still_failed += 1
                logger.warning(f"FAILED: {Path(result['pdf']).name} - {result.get('error', 'unknown')[:80]}")

    logger.info("=" * 60)
    logger.info(f"Re-extraction complete:")
    logger.info(f"  Successful: {successful}/{len(failures)} ({100*successful/len(failures):.1f}%)")
    logger.info(f"  Still failed: {still_failed}")

    # Save results
    results_file = Path.home() / ".pi" / "continuous-learning" / "reextract_results.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "total": len(failures),
            "successful": successful,
            "still_failed": still_failed,
            "results": results,
        }, f, indent=2)
    logger.info(f"Results saved to {results_file}")


if __name__ == "__main__":
    main()
