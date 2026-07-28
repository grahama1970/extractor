#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="${CI_CORE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
ARTIFACT_ROOT="${CI_CORE_ARTIFACT_ROOT:-$ROOT/local/artifacts/ci_core/$RUN_ID}"
CLEAN_VENV="${CI_CORE_CLEAN_VENV:-/tmp/extractor-clean-$RUN_ID}"
SKILL_DIR="${EXTRACTOR_SKILL_DIR:-$ROOT/.skills/skills/extractor}"

mkdir -p "$ARTIFACT_ROOT"
cd "$ROOT"

unset CHUTES_API_KEY CHUTES_TEXT_MODEL CHUTES_VLM_MODEL SCILLM_API_BASE
unset OPENAI_API_KEY OPENAI_BASE_URL ANTHROPIC_API_KEY GOOGLE_API_KEY
unset ARANGO_HOST ARANGO_PORT ARANGO_USER ARANGO_USERNAME ARANGO_PASS ARANGO_PASSWORD
unset ARANGO_DATABASE REDIS_HOST REDIS_PORT REDIS_PASSWORD
unset VIRTUAL_ENV

uv sync --frozen --group dev

uv run python -c "import extractor; import extractor.cli_app"

uv run pytest --collect-only -q \
  | tee "$ARTIFACT_ROOT/pytest_collect.log"

uv run pytest -q \
  tests/contracts/test_universal_extract_contract.py \
  tests/contracts/test_pdf_routes_to_pdf_oxide.py \
  tests/contracts/test_pdf_oxide_result_mapping.py \
  tests/contracts/test_tau_only_model_boundary.py \
  tests/contracts/test_tau_enrichment_receipt.py \
  tests/contracts/test_extraction_status_contract.py \
  tests/contracts/test_required_artifact_failure.py \
  tests/contracts/test_stub_is_not_success.py \
  tests/contracts/test_recovery_preserves_source.py \
  tests/contracts/test_recovery_derived_artifact.py \
  tests/contracts/test_noop_repair_is_rejected.py \
  tests/contracts/test_agent_skill_wrapper.py \
  tests/contracts/test_console_entrypoint.py \
  tests/contracts/test_dependency_boundaries.py \
  tests/contracts/test_clean_install_contract.py \
  | tee "$ARTIFACT_ROOT/contract_tests.log"

rm -rf dist
uv build --wheel \
  | tee "$ARTIFACT_ROOT/uv_build.log"

rm -rf "$CLEAN_VENV"
python -m venv "$CLEAN_VENV"
"$CLEAN_VENV/bin/python" -m pip install --upgrade pip \
  | tee "$ARTIFACT_ROOT/pip_upgrade.log"
"$CLEAN_VENV/bin/python" -m pip install dist/extractor-*.whl \
  | tee "$ARTIFACT_ROOT/wheel_install.log"

"$CLEAN_VENV/bin/extractor" extract \
  data/input/twins/preset_twin/preset_twin.pdf \
  --out "$ARTIFACT_ROOT/clean_pdf" \
  --offline \
  --format json > "$ARTIFACT_ROOT/clean_pdf_result.json"

"$CLEAN_VENV/bin/extractor" extract \
  data/input/twins/preset_twin/preset_twin.docx \
  --out "$ARTIFACT_ROOT/clean_docx" \
  --offline \
  --format json > "$ARTIFACT_ROOT/clean_docx_result.json"

"$CLEAN_VENV/bin/python" - "$ARTIFACT_ROOT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for name in ["clean_pdf_result.json", "clean_docx_result.json"]:
    payload = json.loads((root / name).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "extractor.result.v1", name
    assert payload["status"] in {"complete", "degraded"}, payload["status"]
    assert payload["source_sha256"], name
    assert payload["artifacts"], name
PY

if [[ -x "$SKILL_DIR/run.sh" ]]; then
  EXTRACTOR_COMMAND="$CLEAN_VENV/bin/extractor" \
  EXTRACTOR_ROOT="$ROOT" \
  bash "$SKILL_DIR/run.sh" \
    data/input/twins/preset_twin/preset_twin.pdf \
    --out "$ARTIFACT_ROOT/clean_skill_pdf" \
    --offline \
    --format json > "$ARTIFACT_ROOT/clean_skill_pdf_result.json"

  "$CLEAN_VENV/bin/python" - "$ARTIFACT_ROOT/clean_skill_pdf_result.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["schema_version"] == "extractor.result.v1"
assert payload["status"] in {"complete", "degraded"}
assert payload["diagnostics"]["extra"]["offline"] is True
PY
else
  echo "Missing skill wrapper at $SKILL_DIR" | tee "$ARTIFACT_ROOT/skill_wrapper_missing.log"
  exit 1
fi

echo "ci_core artifacts: $ARTIFACT_ROOT"
