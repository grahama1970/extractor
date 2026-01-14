# Extractor Project - Deterministic Extraction Target

## Objective
Extract `BHT_CV32A65X_with_requirements_noannots.pdf` to produce deterministic output
matching the resolved object order below.

## Test Fixtures
`data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf`

## Resolved PDF Object Order (Ground Truth)

```markdown
## --- Page 1 ---
[SECTION] (Order: Page 1 (Y=83))
# 4.1.5.4. BHT (Branch History Table) submodule

[TEXT] (Order: Page 1 (Y=84))
BHT is implemented as a memory which is composed of BHTDepth configuration parameter entries...

[FIGURE] (Order: Page 1 (Y=323))
(BHT state machine diagram)

[TEXT] (Order: Page 1 (Y=324))
When a branch instruction is pre-decoded by instr_scan submodule...

## --- Page 2 ---
[TABLE] (Order: Page 2 (Y=71))
```csv
Signal,IO,Description,Connection,Type
clk_i,in,Subsystem Clock,SUBSYSTEM,logic
vpc_i,in,Virtual PC,CACHE,logic[CVA6Cfg.VLEN-1:0]
bht_update_i,in,Update bht with resolved address,EXECUTE,bht_update_t
bht_prediction_o,out,Prediction from bht,FRONT END,ariane_pkg::bht_prediction_t[CVA6Cfg.INSTR_PER_FETCH-1:0]
```

[TEXT] (Order: Page 2 (Y=72))
- debug_mode_i input is tied to 0

## --- Page 3 ---
[SECTION] (Order: Page 3 (Y=75))
# 4.1.5.4.1. REQUIREMENTS (Simulated)

[TEXT] (Order: Page 3 (Y=76))
This simulated section provides formal, hardware-oriented requirements...
[Contains REQ-BHT-1 through REQ-BHT-10]

## --- Page 4 ---
[SECTION] (Order: Page 4 (Y=75))
# 4.1.5. TABLE MERGE SCENARIOS (Simulated)

[TEXT] (Order: Page 4 (Y=76))
This simulated section mirrors the BHT section formatting...

[SECTION] (Order: Page 4 (Y=154))
# Mergeable Tables:

[TEXT] (Order: Page 4 (Y=155))
Table 4-1. BHT Prediction Outcomes (Part 1)

[TABLE] (Order: Page 4 (Y=156))
PC Range,Outcome,Count,Accuracy
0x8000_0000-0x8000_00FF,taken,124,91.2%
...6 more rows

## --- Page 5 ---
[SECTION] (Order: Page 5 (Y=75))
# 4.1.5. TABLE MERGE SCENARIOS (Simulated) - Continued

[TEXT] (Order: Page 5 (Y=76))
Continuation of Table 4-1: The rows below are part of the same dataset...

[TABLE] (Order: Page 5 (Y=144))
PC Range,Outcome,Count,Accuracy (continued rows: Y=147-213)
[Same table structure with 8 more rows]

[TABLE] (Order: Page 5 (Y=353))
Signal,Description,Width
[TABLE 4-2 - Separate table]

[TABLE] (Order: Page 5 (Y=482))
Parameter,Value,Notes
[TABLE 4-3 - Separate table]
```

## Critical Determinism Requirements

1. **Exact Y-position sequence** (±3 px tolerance)
   - Objects must appear in exact vertical order as resolved
   - Page boundaries at Y=595.276 (612pt height - margins)
   - No missing objects between resolved Y-positions

2. **Table merging logic**
   - Table 4-1 spans pages 4 (Y=156) and 5 (Y=144) -> must be merged
   - Table 4-2 (page 5, Y=353) and 4-3 (page 5, Y=482) stay separate

3. **Section hierarchy preservation**
   - Section 4.1.5.4 must be parent of 4.1.5.4.1
   - Section titles must match exactly (including spaces/punctuation)
   - No hallucinated sections

4. **Spatial coordinate integrity**
   - All objects must have valid bounding boxes
   - Page transitions preserve reading order
   - Text blocks do not split mid-sentence

5. **Content completeness**
   - REQ-BHT-1 through REQ-BHT-10 are present
   - Technical terms (BHT, VPC, saturating, prediction) preserved
   - RISC-V signal names preserved

## Failure Points to Monitor

- S03: Over-aggressive filtering removes legitimate blocks
- S05: skip_tables flag gets set, bypassing extraction
- S07: assembly thins content (lost objects)
- Y-coordinates drift between runs on identical PDF
- Table merging logic fails on continuation detection

## Success Criteria

The extractor is considered reliable when:

1. All validations pass on the same PDF with no code changes
2. Multiple runs produce identical missing/detected object lists
3. Y-positions maintain exact sequence within tolerance
4. Table 4-1 is merged; tables 4-2/4-3 remain separate
5. No content is dropped without explicit logging
6. All critical BHT specifications are present in output

## Contract Loop Integration

Deterministic validation (stop at first failing step):

```bash
python tools/contract_loop/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture tools/contract_loop/adapters/extractor/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode deterministic
```

Use this loop to identify the first failing step and tighten the contract until
this deterministic target is achieved on repeated runs.
