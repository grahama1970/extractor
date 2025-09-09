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

file="${1:-}"
if [[ -z "$file" ]]; then
  echo "Usage: $0 <path-to-markdown>" >&2
  exit 1
fi
[[ -f "$file" ]] || { echo "File not found: $file" >&2; exit 1; }

# Parse first non-empty line as title
title=$(awk 'NF {print; exit}' "$file")
# Extract metadata lines (optional)
assignees=$(awk -F': *' '/^Assignees:/ {print $2}' "$file" | tr -d '\r')
labels=$(awk -F': *' '/^Labels:/ {print $2}' "$file" | tr -d '\r')
milestone=$(awk -F': *' '/^Milestone:/ {print $2}' "$file" | tr -d '\r')

# Body is the entire file content
body=$(cat "$file")

args=(issue create --title "$title" --body "$body")

# Split labels by comma
if [[ -n "$labels" ]]; then
  IFS=',' read -ra L <<< "$labels"
  for lab in "${L[@]}"; do
    lab_trim=$(echo "$lab" | xargs)
    [[ -n "$lab_trim" ]] && args+=(--label "$lab_trim")
  done
fi

# Assignees
if [[ -n "$assignees" ]]; then
  IFS=',' read -ra A <<< "$assignees"
  for a in "${A[@]}"; do
    a_trim=$(echo "$a" | xargs)
    [[ -n "$a_trim" ]] && args+=(--assignee "$a_trim")
  done
fi

# Milestone
if [[ -n "$milestone" ]]; then
  args+=(--milestone "$milestone")
fi

# Prevent duplicates by checking for an open issue with same title
if gh issue list --state all --search "$title in:title" --json title | jq -e ".[] | select(.title==\"$title\")" >/dev/null 2>&1; then
  echo "Issue with identical title already exists; skipping create." >&2
  exit 0
fi

printf "Creating issue: %s\n" "$title" >&2
gh "${args[@]}"
