#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="${EXTRACTOR_SKILL_DIR:-$ROOT/.skills/skills/extractor}"

cd "$ROOT"

EXTRACTOR_SKILL_DIR="$SKILL_DIR" \
uv run pytest -q tests/contracts/test_agent_skill_wrapper.py

EXTRACTOR_ROOT="$ROOT" \
bash "$SKILL_DIR/sanity.sh"
