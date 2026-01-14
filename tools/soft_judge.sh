#!/usr/bin/env bash
set -euo pipefail

if ! command -v codex >/dev/null 2>&1; then
  echo "ERROR: codex CLI not found on PATH." >&2
  exit 2
fi

OUT="soft_judge.txt"
echo "Writing advisory feedback to $OUT"

codex exec --sandbox read-only --ask-for-approval never "
Review:
- src/contacts.py:normalize_contacts
- tools/contacts_cli.py

Return:
- readability score 0-10
- 3 concise improvements

Be brief.
" > "$OUT" 2>&1 || true

echo "Done (advisory)."
