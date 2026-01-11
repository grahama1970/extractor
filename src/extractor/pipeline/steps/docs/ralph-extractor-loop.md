---
description: "Start Ralph Wiggum loop with extractor-specific verification"
argument-hint: "TASK_DESCRIPTION [--verify] [--max-iterations N] [--quick-smoke]"
allowed-tools: ["Bash(${project}/src/extractor/pipeline/steps/docs/ralph-extractor-loop.sh)"]
hide-from-slash-command-tool: "true"
---

# Extractor Ralph Loop Command

Execute the setup script to initialize the Ralph loop with extractor-specific verification:

```!
"${project}/src/extractor/pipeline/steps/docs/ralph-extractor-loop.sh" $ARGUMENTS

# Extract and display verification mode
if [[ "$ARGUMENTS" == *"--verify"* ]]; then
  echo ""
  echo "═══════════════════════════════════════════════════════════════"
  echo "EXTRACTOR VERIFICATION MODE ACTIVE"
  echo "═══════════════════════════════════════════════════════════════"
  echo ""
  echo "Verification will check:"
  echo "  ✓ DuckDB table schemas match GOAL.md specifications"
  echo "  ✓ PDF objects ordered by reading order (page * 10000 + y0)"
  echo "  ✓ LLM enrichment fields populated (80%+ target)"
  echo "  ✓ All spatial coordinates valid (bounding boxes)"
  echo "  ✓ Requirements extraction from technical PDFs"
  echo "  ✓ Table/figure captions preserved with assets"
  echo ""
  echo "GOAL.md assertions will run after each iteration."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

# Check for --quick-smoke flag
if [[ "$ARGUMENTS" == *"--quick-smoke"* ]]; then
  echo ""
  echo "💨 Quick smoke test mode enabled - faster verification"
  echo "   (Full verification disabled for rapid iteration)"
fi

# Display stage navigation help
if [[ -f "$(pwd)/.claude/ralph-loop.local.md" ]]; then
  echo ""
  echo "🔧 STAGE NAVIGATION:"
  echo "  python scripts/run_stage.py --stage=05      # Run table extraction"
  echo "  python scripts/stage_smoke.py S05          # Test stage 05"
  echo "  duckdb extractor.duckdb                    # Inspect data"
  echo "  bash lib/extractor_verify.sh               # Manual verification"
fi
```

## Extractor Project Context

When working on the extractor project, this loop will:

1. **Preserve PDF Reading Order**: Text, tables, and figures must appear in correct visual sequence
2. **Validate Extracted Data**: DuckDB tables are checked against expected schemas
3. **Verify LLM Enrichment**: AI-generated summaries and metadata are validated
4. **Check Requirements**: Technical requirement extraction is verified against citations

## Critical Focus Areas

- **Section Hierarchy**: H1→H2→H3 nested correctly with parent_id relationships
- **Spatial Coordinates**: All blocks must have valid x0,y0,x1,y1 bounding boxes
- **Text Continuity**: No text blocks omitted in multi-column layouts
- **Table Integrity**: Merged tables spanning pages appear as single entities
- **Requirement IDs**: REQ-4.1.5-001 format extraction from BHT documents

## DuckDB Quick Queries

For manual inspection during development:

```sql
-- View reading order
SELECT page, type, sort_order, substr(content, 1, 80)
FROM merged_content
ORDER BY sort_order
LIMIT 20;

-- Check table extraction quality
SELECT page, csv_data IS NOT NULL as has_data, sort_order
FROM tables
ORDER BY sort_order;

-- Verify requirement extraction
SELECT req_id, substr(text, 1, 50), confidence
FROM requirements
WHERE req_id IS NOT NULL
ORDER BY page;
```

Please iterate on the task. The loop will:
1. Run your changes
2. Execute extractor verification (if --verify is set)
3. Report failures from GOAL.md assertions
4. Loop back with feedback for next iteration

**Note**: When `--verify` is active, the loop will only exit when ALL GOAL.md assertions pass and the DuckDB output meets the extractor project's deterministic criteria. Confirm this by outputting the completion promise when genuinely achieved. NEVER output false promises to escape the loop. The verification ensures accurate PDF extraction and structural integrity. Establis