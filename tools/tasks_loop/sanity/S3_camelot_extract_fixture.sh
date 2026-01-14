#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT"

PDF="fixtures/camelot_fixture.pdf"

if [[ ! -f "$PDF" ]]; then
  echo "ERROR: fixture PDF missing at $PDF" >&2
  echo "Hint: add a small table PDF fixture to fixtures/camelot_fixture.pdf" >&2
  exit 1
fi

python3 - <<'PY'
import sys
from pathlib import Path

pdf = Path("fixtures/camelot_fixture.pdf")
try:
    import camelot  # type: ignore
except Exception as e:
    print("ERROR: camelot import failed:", e, file=sys.stderr)
    print("Hint: install camelot + dependencies (often: pip install 'camelot-py[cv]')", file=sys.stderr)
    sys.exit(1)

try:
    tables = camelot.read_pdf(str(pdf), pages="1")
except Exception as e:
    print("ERROR: camelot.read_pdf failed:", e, file=sys.stderr)
    sys.exit(1)

if len(tables) < 1:
    print("ERROR: expected at least 1 table in fixture PDF", file=sys.stderr)
    sys.exit(1)

print("OK: S3_camelot_extract_fixture tables=", len(tables))
PY
