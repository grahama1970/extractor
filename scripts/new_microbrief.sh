#!/usr/bin/env bash
set -euo pipefail
root_dir="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
dir="$root_dir/docs/microbriefs"
mkdir -p "$dir/images"

slug="${1:-}"
if [[ -z "$slug" ]]; then
  echo "Usage: $0 <slug-like-hud-attach>" >&2
  exit 1
fi

# Find next number
next=$(ls "$dir"/MB-*.md 2>/dev/null | sed -n 's/.*MB-\([0-9][0-9][0-9]\)-.*/\1/p' | sort -n | tail -n1)
if [[ -z "$next" ]]; then
  num=001
else
  num=$(printf "%03d" $((10#$next + 1)))
fi

file="$dir/MB-$num-$slug.md"
cat > "$file" <<EOF2
---
id: MB-$num
route: /main
section: TBD
status: proposed
owner: graham
created: $(date +%F)
---

# $slug

## Context

## Friction

## Target Feel

## Acceptance
- [ ] 
- [ ] 

## Verify (60–120s)
1) 
2) 

## Assets
- docs/microbriefs/images/MB-$num-1.png

## Out of Scope
- 
EOF2

echo "Created $file"
