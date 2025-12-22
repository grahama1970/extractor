#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "[update_scillm] repo root: $ROOT"

if [ ! -d "$ROOT/../litellm" ]; then
  echo "[update_scillm] ../litellm not found; aborting" >&2
  exit 1
fi

echo "[update_scillm] pulling ../litellm"
git -C "$ROOT/../litellm" pull --ff-only

echo "[update_scillm] reinstalling editable into current venv"
uv pip install -e "$ROOT/../litellm"

echo "[update_scillm] done"
