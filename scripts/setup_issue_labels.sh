#!/usr/bin/env bash
set -euo pipefail
if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install GitHub CLI: https://cli.github.com/" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "gh CLI not authenticated. Run: gh auth login" >&2
  exit 1
fi

create_label(){
  local name="$1"; local color="$2"; local desc="$3"
  gh label create "$name" --color "$color" --description "$desc" 2>/dev/null || gh label edit "$name" --color "$color" --description "$desc" >/dev/null
}

create_label "micro-brief" "6f42c1" "Small, feel-first UI change"
create_label "status:proposed" "c2e0c6" "Proposed"
create_label "status:in-progress" "fef2c0" "In progress"
create_label "status:verify" "bfdadc" "Ready to verify"
create_label "status:done" "d4c5f9" "Completed"

echo "Labels ensured."
