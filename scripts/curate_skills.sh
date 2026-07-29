#!/usr/bin/env bash
set -euo pipefail

PROJECT="${PROJECT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SKILLS_SRC="${PI_SKILLS_ROOT:-$HOME/workspace/experiments/pi-mono/.pi/skills}"
SKILLS_DST="$PROJECT/.claude/skills"

# Remove blanket symlink
rm -f "$SKILLS_DST"

# Create curated directory
mkdir -p "$SKILLS_DST"

# Only project-relevant skills
SKILLS=(
  # Core pipeline
  memory
  review-pdf
  extractor
  extractor-quality-check
  learn-datalake
  table-lab
  create-figure
  figure-lab
  create-table
  create-table-classifier
  debug-pdf
  pdf-lab
  corpus-report
  # Agent essentials
  agent-inbox
  assess
  ask
  cleanup
  data-audit
  project-state
  monitor-skills
  handoff
  create-context
  dogpile
  # Dev tooling
  best-practices-react
  best-practices-python
  review-design
  assistant
  scillm
)

for skill in "${SKILLS[@]}"; do
  if [ -d "$SKILLS_SRC/$skill" ]; then
    ln -s "$SKILLS_SRC/$skill" "$SKILLS_DST/$skill"
    echo "  linked: $skill"
  else
    echo "  MISSING: $skill"
  fi
done

echo ""
echo "Curated $(ls "$SKILLS_DST" | wc -l) skills (down from 200+)"
