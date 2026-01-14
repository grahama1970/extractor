#!/usr/bin/env bash
set -euo pipefail

# preflight.sh
#
# Purpose:
# - Run sanity checks *before* implementing tasks or running deterministic contract loops.
# - Includes both deterministic sanity (e.g., Camelot fixture extraction) and
#   semi-deterministic sanity (e.g., SciLLM/Chutes LLM calls).
#
# IMPORTANT:
# - Semi-deterministic sanity checks MUST NOT be called from verify_task*.sh (deterministic verifiers).
# - This script is intended for human/agent preflight runs.

# Select which checks to run by setting env vars:
#   PREFLIGHT_DET="S3" PREFLIGHT_SEMI="S5" ./preflight.sh
#
# Defaults:
PREFLIGHT_DET="${PREFLIGHT_DET:-S3}"
PREFLIGHT_SEMI="${PREFLIGHT_SEMI:-S5}"

run_det() {
  case "$1" in
    S3) bash sanity/S3_camelot_extract_fixture.sh ;;
    S4) python3 tools/table_count.py fixtures/camelot_fixture.pdf ;;
    *) echo "WARN: unknown deterministic sanity id: $1" >&2 ;;
  esac
}

run_semi() {
  case "$1" in
    S5) bash sanity/S5_scillm_min_call.sh ;;
    *) echo "WARN: unknown semi-deterministic sanity id: $1" >&2 ;;
  esac
}

echo "== preflight (deterministic) =="
for id in $PREFLIGHT_DET; do
  echo "-- $id --"
  run_det "$id"
done

echo ""
echo "== preflight (semi-deterministic) =="
for id in $PREFLIGHT_SEMI; do
  echo "-- $id --"
  run_semi "$id"
done

echo ""
echo "PREFLIGHT_STATUS=OK"
