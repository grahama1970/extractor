#!/usr/bin/env bash
set -euo pipefail

echo "== Preflight: tools and env =="
command -v gs >/dev/null 2>&1 || { echo "Ghostscript (gs) not found. Install it." >&2; exit 2; }

python - <<'PY'
import sys
ok=1
try:
    import fitz  # PyMuPDF
except Exception as e:
    print("PyMuPDF (fitz) not importable:", e); ok=0
try:
    from camelot import io as _cio
except Exception as e:
    print("Camelot not importable:", e); ok=0
print("Python deps OK" if ok else "Python deps missing")
sys.exit(0 if ok else 3)
PY

# Only require CHUTES/OpenAI when figure descriptions (or any LLM) are explicitly enabled
FIGURE_DESC="${FIGURE_DESC:-1}"
case "${FIGURE_DESC,,}" in
  1|true|yes)
    : "${CHUTES_API_BASE:?Set CHUTES_API_BASE for VLM figure descriptions}" >/dev/null
    : "${CHUTES_API_KEY:?Set CHUTES_API_KEY for VLM figure descriptions}" >/dev/null
    if [[ "${CHUTES_API_BASE}" != *"/v1" ]]; then
      echo "CHUTES_API_BASE must end with /v1 (e.g., https://api.chutes.ai/v1)" >&2
      exit 2
    fi
    echo "CHUTES env OK (figure descriptions enabled)"
    echo "Checking CHUTES /models connectivity..."
    if ! curl -sSf -H "Authorization: Bearer ${CHUTES_API_KEY}" "${CHUTES_API_BASE}/models" >/dev/null; then
      echo "CHUTES /models check failed. Verify CHUTES_API_BASE and CHUTES_API_KEY." >&2
      exit 2
    fi
    echo "CHUTES /models reachable" ;;
  *)
    echo "CHUTES env not required (FIGURE_DESC=${FIGURE_DESC})" ;;
esac
echo "== Preflight OK =="
