#!/bin/bash
# S08 stop-hook diagnostics for Contract Loop runs.
# Usage: tools/contract_loop/adapters/extractor/docs/s08_stop_hook_feedback.sh [PIPELINE_DIR] [PDF_PATH]

set -euo pipefail

PIPELINE_DIR="${1:-data/results/pipeline_contract}"
PDF_PATH="${2:-data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf}"
DB_PATH="$PIPELINE_DIR/pipeline.duckdb"
export PIPELINE_DIR DB_PATH

printf "S08 stop-hook diagnostics\n"
printf "Pipeline dir: %s\n" "$PIPELINE_DIR"
printf "PDF path: %s\n\n" "$PDF_PATH"

if [[ ! -d "$PIPELINE_DIR" ]]; then
  printf "STOP_HOOK_FEEDBACK: pipeline dir not found: %s\n" "$PIPELINE_DIR"
  printf "Fix: run the Contract Loop at least through S07.\n"
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  printf "STOP_HOOK_FEEDBACK: pipeline.duckdb not found at %s\n" "$DB_PATH"
  printf "Fix: ensure S07 (duckdb ingest) completed successfully.\n"
  exit 1
fi

python - <<'PY'
from pathlib import Path
import os
import sys

try:
    import duckdb
except Exception as exc:
    print(f"STOP_HOOK_FEEDBACK: duckdb import failed: {exc}")
    print("Fix: ensure python env includes duckdb.")
    sys.exit(1)

pipe_dir = Path(os.environ["PIPELINE_DIR"])
db_path = Path(os.environ["DB_PATH"])

try:
    con = duckdb.connect(str(db_path), read_only=True)
except Exception as exc:
    print(f"STOP_HOOK_FEEDBACK: cannot open {db_path}: {exc}")
    print("Fix: re-run S07 to regenerate pipeline.duckdb.")
    sys.exit(1)

# Requirements table check
try:
    req_count = con.execute("SELECT count(*) FROM requirements").fetchone()[0]
except Exception as exc:
    print(f"STOP_HOOK_FEEDBACK: requirements table missing or unreadable: {exc}")
    print("Fix: run S08_extract_requirements and confirm it writes to DuckDB.")
    con.close()
    sys.exit(1)

print(f"Requirements rows: {req_count}")

if req_count == 0:
    print("STOP_HOOK_FEEDBACK: requirements table is empty")
    print("Fix: check LLM config, prompts, and section filtering in S08.")
    con.close()
    sys.exit(1)

# Sample requirements
rows = con.execute(
    "SELECT req_id, substr(text, 1, 120) FROM requirements ORDER BY created_at DESC NULLS LAST LIMIT 3"
).fetchall()
print("Sample requirements:")
for req_id, text in rows:
    rid = req_id or "(missing id)"
    print(f"  - {rid}: {text}")

con.close()
print("S08 diagnostics OK")
PY
