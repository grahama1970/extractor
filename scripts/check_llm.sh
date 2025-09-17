#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (this script is in scripts/)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Activate venv and load .env if present
if [[ -d "$ROOT_DIR/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi
set -a
[[ -f "$ROOT_DIR/.env" ]] && source "$ROOT_DIR/.env"
set +a

# Prefer LITELLM_DEFAULT_MODEL for testing, fallback to LITELLM_MODEL, then a safe default
# Prefer LITELLM_DEFAULT_MODEL (project default), then DEFAULT_LITELLM_MODEL, then LITELLM_MODEL
MODEL="${LITELLM_DEFAULT_MODEL:-${DEFAULT_LITELLM_MODEL:-${LITELLM_MODEL:-gpt-4o-mini}}}"

# Optional: DEBUG=1 to include --wrap-json
ARGS=()
if [[ "${DEBUG:-}" != "" ]]; then
  case "${DEBUG,,}" in
    1|true|yes|y)
      ARGS+=(--wrap-json)
      ;;
  esac
fi

python "$ROOT_DIR/src/extractor/pipeline/utils/litellm_call.py" \
  sanity \
  --model "$MODEL" \
  "${ARGS[@]}" "$@"
