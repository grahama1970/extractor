# PDF Extraction Quick Reference

## Complete Pipeline in 10 Commands

```bash
# 1. Extract annotations from original PDF
extract-pipeline extract-annotations input.pdf -o /tmp/annotations.json

# 2. [AGENT TASK] Analyze annotations.json for semantic meaning

# 3. Create clean PDF without annotations
extract-pipeline create-clean-pdf input.pdf -o /tmp/clean.pdf

# 4. Check knowledge base for similar extractions
knowledge-architect search "pdf extraction patterns"

# 5. Run marker extraction with UUIDs
marker-pdf /tmp/clean.pdf --output /tmp/blocks.json

# 5.5a. Create batches if suspicious blocks exist
extract-pipeline create-batches /tmp/blocks.json -d /tmp/batches/

# 5.5b. [AGENT TASK] Spawn sub-agents using pdf_block_fixer_prompt.md

# 5.5c. Apply fixes from sub-agents
extract-pipeline apply-fixes /tmp/blocks.json /tmp/decisions.json -o /tmp/fixed.json

# 6. Build section nodes
extract-pipeline build-sections /tmp/fixed.json -o /tmp/sections.json

# 7a. Create section validation images
pdf-tools section-image input.pdf /tmp/sections.json -o /tmp/section_img.png

# 7b. Create table validation images  
pdf-tools table-image input.pdf /tmp/fixed.json -o /tmp/table_img.png

# 8. [AGENT TASK] Enhance sections using CONCURRENT sub-agents
# Split by type
jq '.sections[] | select(.type == "text")' /tmp/sections.json > /tmp/text_sections.json
jq '.sections[] | select(.type == "table")' /tmp/sections.json > /tmp/table_sections.json
jq '.sections[] | select(.type == "equation")' /tmp/sections.json > /tmp/equation_sections.json
jq '.sections[] | select(.type == "code")' /tmp/sections.json > /tmp/code_sections.json

# Spawn all sub-agents AT ONCE (concurrent execution)
# Then merge results:
jq -s '{"sections": add}' /tmp/enhanced_*.json > /tmp/enhanced.json

# 9. Validate against gold standard
extract-pipeline validate-extraction /tmp/enhanced.json --gold /tmp/gold.json

# 10. Store successful patterns
knowledge-architect store /tmp/enhanced.json --type "extraction_result"
```

## Key Commands Summary

| Stage | Command | Purpose |
|-------|---------|---------|
| 1 | `extract-pipeline extract-annotations` | Get PDF annotations with metadata |
| 3 | `extract-pipeline create-clean-pdf` | Remove annotation artifacts |
| 5 | `marker-pdf` | Extract blocks with marker |
| 5.5a | `extract-pipeline create-batches` | Batch suspicious blocks |
| 5.5c | `extract-pipeline apply-fixes` | Apply sub-agent decisions |
| 6 | `extract-pipeline build-sections` | Organize into sections |
| 7 | `pdf-tools section-image/table-image` | Create validation images |
| 8 | `extract-pipeline enhance-sections` | Semantic enhancement |
| 9 | `extract-pipeline validate-extraction` | Check accuracy |

## Agent Tasks (Not CLI)

- **Stage 2**: Interpret annotations semantically (read JSON, add meaning)
- **Stage 5.5b**: Spawn sub-agents for batch processing (use prompt template)
- **Stage 8**: Spawn CONCURRENT sub-agents for section enhancement:
  - `semantic-section-enhancer.md` → text sections
  - `table-structure-fixer.md` → table sections
  - `equation-formatter.md` → equation sections  
  - `code-block-enhancer.md` → code sections

## Tips

1. All paths should be absolute or start with `/tmp/`
2. Use `--help` on any command for options
3. Check intermediate outputs to verify each stage
4. Store successful runs in knowledge base for future reference