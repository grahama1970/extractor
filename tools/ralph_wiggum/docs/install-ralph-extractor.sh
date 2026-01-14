#!/bin/bash
# NOTE: Legacy Ralph Wiggum loop installer.
# Current contract-loop docs live under tools/contract_loop/docs.

# Install extractor-specific Ralph Wiggum commands
# This creates a local installation that overrides the global ralph-wiggum plugin

set -euo pipefail

echo "📦 Installing Extractor-specific Ralph Wiggum commands..."
echo ""

# Get the extractor project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null && pwd)"
EXTRACTOR_ROOT="$(cd "$SCRIPT_DIR/../.." > /dev/null && pwd)"

echo "Extractor root: $EXTRACTOR_ROOT"
echo ""

# Create local Claude config if it doesn't exist
CLAUDE_LOCAL_DIR="$EXTRACTOR_ROOT/.claude/commands"
mkdir -p "$CLAUDE_LOCAL_DIR"

# Copy our custom ralph-wiggum command files
echo "→ Installing ralph-extractor-loop command..."
cp "$SCRIPT_DIR/ralph-extractor-loop.md" "$CLAUDE_LOCAL_DIR/ralph-extractor-loop.md"

echo "→ Installing extractor verification library..."
mkdir -p lib
if [[ -f "$SCRIPT_DIR/lib/extractor_verify.sh" ]]; then
    cp "$SCRIPT_DIR/lib/extractor_verify.sh" "lib/extractor_verify.sh"
    chmod +x "lib/extractor_verify.sh"
fi

# Create a wrapper script for local execution
cat > "$EXTRACTOR_ROOT/extractor-loop" <<EOF
#!/bin/bash
# Wrapper for extractor ralph loop with project context

# Change to extractor directory if not already there
if [[ "\$(basename "\$PWD")" != "extractor" ]]; then
    echo "Please run from extractor project root directory"
    exit 1
fi

# Run the actual ralph loop
bash scripts/ralph.sh "\$@"
EOF
chmod +x "$EXTRACTOR_ROOT/extractor-loop"

echo ""
echo "✅ Installation complete!"
echo ""
echo "🔧 USAGE:"
echo "   ./extractor-loop 'Fix S05 table extraction' --verify --max-iterations 10"
echo "   # or with the proper slash command:"
echo "   ./ralph-extractor-loop 'Improve S03 head detection' --verify"
echo ""
echo "📁 Files installed:"
echo "   - .claude/commands/ralph-extractor-loop.md"
if [[ -f "lib/extractor_verify.sh" ]]; then
  echo "   - lib/extractor_verify.sh"
fi
echo "   - $EXTRACTOR_ROOT/extractor-loop (wrapper)"
echo ""
echo "🎯 This installation provides:"
echo "   • DuckDB table schema validation"
echo "   • PDF reading order verification"
echo "   • GOAL.md assertion checking"
echo "   • Stage-specific smoke test integration"
echo "   • LLM enrichment field validation"
echo ""
echo "Note: Run from extractor project root for best results"
echo "      The loop will verify your changes against GOAL.md after each iteration"
