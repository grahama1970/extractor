#!/usr/bin/env python3
"""
gate_s07b.py - Gate for S07b: Text Cleaner
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import run_gate, GateError


def checks(fixture_name: str):
    # Just verify merged_content exists and has data
    # (Strict content checks belong in specific fixture contracts if needed)

    # We need to find the DB. run_pipeline sets EXTRACTOR_OUTPUT_ROOT env var.
    import os

    results_dir = Path(os.environ.get("EXTRACTOR_OUTPUT_ROOT", "data/results/pipeline"))
    db_path = results_dir / "pipeline.duckdb"

    if not db_path.exists():
        raise GateError(
            "Database not found", expected="pipeline.duckdb", actual="missing", file=str(db_path)
        )

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        count = con.execute("SELECT count(*) FROM merged_content").fetchone()[0]
        if count == 0:
            raise GateError(
                "merged_content table is empty", expected=">0 rows", actual=0, file=str(db_path)
            )
        print(f"✅ merged_content rows: {count}")
    finally:
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()
    sys.exit(run_gate("S07b: Text Cleaner", lambda: checks(args.fixture)))
