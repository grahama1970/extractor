#!/usr/bin/env bash
# Minimal local dev loop: format → lint → type → tests → optional stage smoke
# Usage examples:
#   K_FILTER="table|figure" ./scripts/devloop.sh
#   RUN_STAGES="01 02 03 04 05 06 07" PDF_PATH="/absolute/path/to/your.pdf" ./scripts/devloop.sh
#   RUN_STAGES="07" ./scripts/devloop.sh

set -euo pipefail

# Optional env:
#   K_FILTER   - pytest -k filter (e.g., "table|figure"); default runs all tests
#   RUN_STAGES - space-separated stages to smoke test (e.g., "01 02 03 04 05 06 07")
#   PDF_PATH   - required when RUN_STAGES includes 01

K_FILTER="${K_FILTER:-}"
RUN_STAGES="${RUN_STAGES:-}"
PDF_PATH="${PDF_PATH:-}"

echo "== Format =="
black -q src tests

echo "== Lint =="
ruff check src tests

echo "== Type =="
mypy src

echo "== Tests =="
if [[ -n "${K_FILTER}" ]]; then
  echo "pytest -k '${K_FILTER}'"
  pytest -q -k "${K_FILTER}"
else
  echo "pytest (all)"
  pytest -q
fi

if [[ -n "${RUN_STAGES}" ]]; then
  echo "== Stage smoke (${RUN_STAGES}) =="
  SMOKE_CMD=(python scripts/stage_smoke.py --stages "${RUN_STAGES}")
  if [[ -n "${PDF_PATH}" ]]; then
    SMOKE_CMD+=("--pdf" "${PDF_PATH}")
  fi
  echo ">> ${SMOKE_CMD[*]}"
  "${SMOKE_CMD[@]}"
fi

echo "== OK =="