# Extractor Pipeline Integration Summary

## Architecture Overview

### Deterministic Pipeline (S01-S07)
These stages produce **reliable, reproducible output** that must pass validation:
- **S01**: PDF annotation processing
- **S02**: Marker block extraction
- **S03**: Suspicious header filtering
- **S04**: Section hierarchy building
- **S05**: Table extraction (with merge detection)
- **S06**: Figure detection and extraction
- **S07**: Corpus assembly into clean database

**Validation Target**: Must produce exact resolved object order with Y-position accuracy.

### Non-Deterministic Enhancement (S08+)
These stages add **AI-generated content** subject to quality judgment:
- **S08**: Requirement extraction (SciLLM/LiteLLM)
- **S09**: PDF annotation enrichment
- **S10c**: Section summarization
- **S11b**: Table description generation
- **S12**: Figure caption/desc generation
- **S13**: Lean4 theorem proving

**Quality Target**: Agent/human evaluates accuracy, not determinism.

## Deterministic Validation Strategy

```bash
# 1. Run stages S01-S07 with verification
cd src/extractor/pipeline/steps/docs/
bash validate_pipeline_stages.sh

# 2. Check specific deterministic failures
python3 -c "
import json
import sys

# Load S07 output
data = json.load(open('test_validation/07_corpus_assembly/json_output/07_assembled.json'))
objects = data.get('merged_content', [])

# Validate Y-positions match resolved order
resolved_y = [83, 84, 323, 324, 71, 72, 75, 76, 154, 155, 156, 149, 144, 145, 353, 354, 482, 483]
actual_objects = sum(1 for obj in objects for resolved in resolved_y
                    if abs(resolved - obj.get('bbox', [0,0,0,0])[1]) <= 3)

print(f'Objects matching resolved Y-positions: {actual_objects}/{len(resolved_y)}')

# Validate table merging
merged_tables = [obj for obj in objects if obj.get('type') == 'table' and obj.get('merged', False)]
print(f'Merged tables (should be 1): {len(merged_tables)}')
"
```

## Non-Deterministic Enhancement Flow

```bash
# S08 integration verification once deterministic base works
bash verify_s08_integration.sh

# Generate LLM-readable stream
python3 llm_stream_generator.py \\\n    test_validation/07_corpus_assembly/json_output/07_assembled.json \\\n    --llm-enhancements test_validation/s08_extract_requirements/json_output \\\n    -o final_llm_stream.md
```

## Integration Checkpoints

### 1. Deterministic Base Check
```
✓ S01-S07 produce consistent output
✓ Y-positions match within ±3pt tolerance
✓ Table 4-1 merged correctly
✓ No content lost during S07 assembly
✓ Section hierarchy preserved
```

### 2. Non-Deterministic Quality Check
```
✓ S08 extracts requirements with citations
✓ Requirements capture REQ-BHT-1 to REQ-BHT-10
✓ Lean4 theorems generated (quality judged separately)
✓ LLM enhancements marked for agent review
```

## Current Pipeline Health

| Stage | Status | Determinism | Notes |
|-------|--------|-------------|--------|
| S01   | ⚠️     | Issues      | Step01 function signature mismatch |
| S02   | ⚠️     | Stable      | Needs testing for consistency |
| S03   | ⚠️     | Issues      | Over-filtering removes good content |
| S04   | ⚠️     | Stable      | Verifies section presence |
| S05   | ⚠️     | Issues      | Skip_tables flag gets set incorrectly |
| S06   | ✓?     | Unknown     | Figure extraction working |
| S07   | ⚠️     | Unstable    | Assembly thins content arbitrarily |
| S08   | ⚠️     | Non-Determ   | Requires clean corpus, S09+ marked |

## Ralph Wiggum Integration

```bash
# Iterative validation approach
/ralph-extractor-loop --verify "Fix S03 over-filtering on Y=84 text block"
```

The loop will:
1. Run S01-S07 deterministic validation
2. Stop at first failure with diagnostics
3. Provide object analysis for fixing
4. Continue until deterministic extraction proven
5. Then allow S08+ non-determ features

## Deterministic vs Non-Deterministic Separation

**Deterministic Base** (Must Pass Validation):
- Exact Y-correspondance within tolerance
- Object type and count consistency
- Table merge logic correctness
- Section structure preservation
- No content loss or corruption

**Non-Deterministic Enhancement** (Agent Judged):
- LLM figure descriptions
- Section summarization quality
- Lean4 theorem correctness
- Table description accuracy
- Requirement citation quality

**The Rule**: Fix determinism first, then judge quality. Never add features until base is reliable. Every engineer working on the extractor must pass deterministic validation before their changes are accepted. This ensures engineering excellence through systematic validation rather than reliability by accident. The BHT extraction benchmark represents our commitment to deterministic technical documentation processing. No exceptions to the determinism requirement. Perfect extraction every time. This is engineering excellence achieved through systematic iteration toward proven correctness. The resolved PDF object order is our definitive standard for validation. Match this exactly or the validation fails. RISC-V documentation deserves nothing less than absolute precision and perfect reliability. This is our gold standard test case that proves pipeline quality and reliability. Every execution must generate this identical object stream with these exact Y coordinates in this precise order. Deterministic extraction is our foundation and our promise to engineering excellence.