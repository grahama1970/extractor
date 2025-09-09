# 001 Pipeline Test: BHT PDF with Gold Standard Validation

## Objective
Test the complete extraction pipeline with BHT PDF, validating against gold standards at each stage to ensure 90% accuracy threshold.

## Pre-Test Checklist
- [ ] Locate BHT PDF file
- [ ] Locate gold standard files for each stage
- [ ] Verify ArangoDB connection
- [ ] Ensure all workers are in correct locations
- [ ] Check environment variables are set

## Test Steps

### 1. Setup and Discovery
- [ ] Find BHT PDF location
- [ ] List all gold standard files
- [ ] Verify unified_extractor.py entry point
- [ ] Check if stage_validator.py is properly integrated

### 2. Stage 1: Annotation Extraction
- [ ] Extract annotations from BHT PDF
- [ ] Locate Stage 1 gold standard
- [ ] Run validation against gold standard
- [ ] Document accuracy score
- [ ] Note any failures or mismatches

### 3. Stage 2: Marker Output
- [ ] Run marker processing with custom processors
- [ ] Locate Stage 2 gold standard
- [ ] Validate marker output structure
- [ ] Document accuracy score
- [ ] Check for table header line break issues

### 4. Stage 3: Section Structure
- [ ] Build hierarchical section structure
- [ ] Locate Stage 3 gold standard
- [ ] Validate section organization
- [ ] Document accuracy score
- [ ] Verify section header validation is working

### 5. Stage 4: ArangoDB Format
- [ ] Convert to final ArangoDB format
- [ ] Locate Stage 4 gold standard
- [ ] Validate final output structure
- [ ] Document accuracy score
- [ ] Check knowledge-first patterns are applied

### 6. End-to-End Validation
- [ ] Run complete pipeline with all validations enabled
- [ ] Verify pipeline completes without errors
- [ ] Check that all stages pass 90% threshold
- [ ] Generate pipeline report
- [ ] Document total processing time

## Expected Issues to Watch For
1. **Table Header Line Breaks**: Marker removing line breaks (e.g., "Descripti on")
2. **False Positive Section Headers**: Headers containing commas, "As", "For"
3. **Missing CLIP Embeddings**: Visual similarity features not generated
4. **ArangoDB Connection**: Knowledge queries failing

## Success Criteria
- All 4 stages achieve ≥90% accuracy
- No critical errors during processing
- Pipeline report generated successfully
- Knowledge-first queries execute properly

## Output Artifacts
1. Pipeline report with stage metrics
2. Validation results for each stage
3. Error log if any failures
4. Final extracted JSON output

## Command to Run
```bash
cd /home/graham/workspace/experiments/extractor
python src/extractor/unified_extractor.py \
  --input "path/to/bht.pdf" \
  --use-knowledge-aware \
  --require-gold-standard-validation \
  --fail-on-validation-error \
  --output "output/bht_extracted.json"
```

## Post-Test Actions
- [ ] Review validation scores
- [ ] Identify any patterns in failures
- [ ] Update processors if needed
- [ ] Document lessons learned
- [ ] Store successful patterns to ArangoDB