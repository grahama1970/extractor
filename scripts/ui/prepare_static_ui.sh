#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <pipeline_results_dir> <tabbed_dir>"
  echo "Example: $0 data/results/pipeline_multi/bht_cv32a65x prototypes/tabbed"
  exit 1
fi

PIPE_DIR="$1"
TABBED_DIR="$2"
UI_SRC="$PIPE_DIR/ui/blocks_full.json"
VERIFY_SRC="$PIPE_DIR/05_table_extractor/verify"

if [ ! -f "$UI_SRC" ]; then
  echo "ERROR: $UI_SRC not found. Run pipeline first."
  exit 2
fi

mkdir -p "$TABBED_DIR/public/ui"
cp "$UI_SRC" "$TABBED_DIR/public/ui/blocks_full.json"

if [ -d "$VERIFY_SRC" ]; then
  mkdir -p "$TABBED_DIR/public/05_table_extractor/verify"
  rsync -a --delete "$VERIFY_SRC"/ "$TABBED_DIR/public/05_table_extractor/verify"/
  echo "Copied verify directory."
else
  echo "No verify dir found at $VERIFY_SRC (skipping)."
fi

echo "Static UI assets prepared in $TABBED_DIR/public"

