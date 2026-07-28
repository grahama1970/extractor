#!/usr/bin/env python3
"""Selective S05 re-extraction for high-fragmentation PDFs.

After debug-table tune-corpus generates hints, this script re-runs only
the S05 table extraction step on the worst fragmentation offenders,
so they can pick up the agent_tuned strategy from the new hints.

Usage:
    python scripts/rerun_s05_top_offenders.py [--top N] [--min-frag SCORE] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

CORPUS_ROOT = Path("/mnt/storage12tb/extractor_corpus")
RESULTS_DIR = CORPUS_ROOT / "results"


def find_fragmentation_offenders(min_frag: int = 50, top_n: int = 20) -> list[dict]:
    """Find PDFs with worst table fragmentation from existing S05 results."""
    entries = []

    for tables_file in RESULTS_DIR.glob("*/05_table_extractor/json_output/05_tables.json"):
        result_dir = tables_file.parent.parent.parent
        dir_name = result_dir.name

        try:
            data = json.loads(tables_file.read_text())
            tables = data.get("tables", [])
            total_frag = sum(
                t.get("fragmentation_score", 0)
                for t in tables
                if isinstance(t, dict)
            )
            table_count = len(tables)
            strategies = {}
            for t in tables:
                s = t.get("strategy", "unknown")
                strategies[s] = strategies.get(s, 0) + 1

            # Find the source PDF
            source_pdf = data.get("source_pdf", "")
            if not source_pdf:
                # Look for *_clean.pdf in 01_annotation_processor
                annot_dir = result_dir / "01_annotation_processor"
                pdfs = list(annot_dir.glob("*_clean.pdf"))
                source_pdf = str(pdfs[0]) if pdfs else ""

            entries.append({
                "dir": dir_name,
                "result_dir": str(result_dir),
                "total_frag": total_frag,
                "table_count": table_count,
                "strategies": strategies,
                "source_pdf": source_pdf,
                "has_agent_tuned": "agent_tuned" in strategies,
            })
        except Exception:
            continue

    # Filter and sort
    entries = [e for e in entries if e["total_frag"] >= min_frag]
    entries.sort(key=lambda x: x["total_frag"], reverse=True)
    return entries[:top_n]


def _read_s00_timeout(result_dir: str, table_count: int = 0, default: int = 900) -> int:
    """Read S00's estimated timeout from pipeline_context.json.

    Falls back to a heuristic based on known table count if pipeline_context
    was written before S00 had table estimation.
    """
    try:
        ctx_file = Path(result_dir) / "pipeline_context.json"
        if ctx_file.exists():
            ctx = json.loads(ctx_file.read_text())
            est = int(ctx.get("estimated_timeout_seconds", 0))
            # Check if S00 had table estimation (estimated_table_count present)
            if est > 0 and ctx.get("estimated_table_count", 0) > 0:
                return max(est, default)
    except Exception:
        pass
    # Fallback: 5 seconds per known table from S05 data + base
    if table_count > 0:
        return max(120 + table_count * 5, default)
    return default


def rerun_s05(entry: dict, dry_run: bool = False) -> bool:
    """Re-run S05 table extraction for a single PDF.

    Uses the S05 module's __main__ entry point which accepts --pipeline-dir.
    This re-runs ONLY the table extraction step, preserving all other pipeline outputs.
    Timeout is read from S00's estimated_timeout_seconds in pipeline_context.json.
    """
    result_dir = entry["result_dir"]

    # Verify prerequisites
    s4_json = Path(result_dir) / "04_section_builder" / "json_output" / "04_sections.json"
    if not s4_json.exists():
        print(f"  SKIP: missing S04 output at {s4_json}")
        return False

    cmd = [
        sys.executable, "-m", "extractor.pipeline.steps.s05_table_extractor",
        "--pipeline-dir", result_dir,
    ]

    if dry_run:
        print(f"  DRY-RUN: {' '.join(cmd)}")
        return True

    dir_name = Path(result_dir).name
    timeout = _read_s00_timeout(result_dir, table_count=entry.get("table_count", 0))
    print(f"  Running S05 on {dir_name}... (timeout={timeout}s / {timeout//60}min)")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent.parent),
            env={**__import__("os").environ, "CORPUS_ROOT": str(CORPUS_ROOT)},
        )
        if result.returncode == 0:
            print(f"  OK: S05 completed")
            return True
        else:
            print(f"  FAIL: exit code {result.returncode}")
            if result.stderr:
                for line in result.stderr.splitlines()[-5:]:
                    print(f"    {line}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: S05 exceeded {timeout}s ({timeout//60}min) limit")
        return False
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return False


def check_hints_available() -> bool:
    """Verify that table_hints.json exists and has hints."""
    hints_path = CORPUS_ROOT / "metadata" / "table_hints.json"
    if not hints_path.exists():
        print(f"WARNING: {hints_path} does not exist")
        print("Run debug-table tune-corpus first, then 'apply --to-corpus'")
        return False

    data = json.loads(hints_path.read_text())
    hint_count = len(data.get("hints", {}))
    print(f"Hints available: {hint_count} entries in {hints_path}")
    return hint_count > 0


def main():
    """Re-run S05 on worst fragmentation offenders."""
    parser = argparse.ArgumentParser(description="Re-run S05 on worst fragmentation offenders")
    parser.add_argument("--top", type=int, default=20, help="Number of top offenders to process")
    parser.add_argument("--min-frag", type=int, default=50, help="Minimum fragmentation score")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    print("=== Selective S05 Re-extraction ===\n")

    # Check prerequisites
    check_hints_available()

    # Find offenders
    offenders = find_fragmentation_offenders(min_frag=args.min_frag, top_n=args.top)
    if not offenders:
        print(f"No PDFs found with fragmentation >= {args.min_frag}")
        return

    print(f"\nFound {len(offenders)} PDFs with fragmentation >= {args.min_frag}:")
    print(f"{'#':>3s} {'Directory':55s} {'Frag':>6s} {'Tables':>7s} {'Agent?':>7s}")
    print("-" * 85)
    for i, e in enumerate(offenders, 1):
        agent = "YES" if e["has_agent_tuned"] else "no"
        print(f"{i:3d} {e['dir'][:55]:55s} {e['total_frag']:6d} {e['table_count']:7d} {agent:>7s}")

    if args.dry_run:
        print(f"\n[DRY-RUN] Would re-run S05 on {len(offenders)} PDFs")
    else:
        print(f"\nRe-running S05 on {len(offenders)} PDFs...")

    success = 0
    failed = 0
    for i, entry in enumerate(offenders, 1):
        print(f"\n[{i}/{len(offenders)}] {entry['dir']} (frag={entry['total_frag']})")
        if rerun_s05(entry, dry_run=args.dry_run):
            success += 1
        else:
            failed += 1

    print(f"\n=== Summary ===")
    print(f"Processed: {success + failed}")
    print(f"Success: {success}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
