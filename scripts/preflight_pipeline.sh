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

: "${CHUTES_API_BASE:?Set CHUTES_API_BASE}" >/dev/null
: "${CHUTES_API_KEY:?Set CHUTES_API_KEY}" >/dev/null
echo "CHUTES env OK"
echo "== Preflight OK =="

