# Pipeline Renaming Summary

## Changes Made

### File Renames
1. **Production Pipeline** (now POC 01-06):
   - POC 01-05: Unchanged (core extraction pipeline)
   - POC 08 → POC 06: `poc_08_export_to_arangodb.py` → `poc_06_export_to_arangodb.py`

2. **Testing/Validation Tools** (separate from production):
   - POC 06 → `poc_06_validate_against_gold_standards.py` (was deep section analysis)
   - POC 07 → `poc_07_test_analysis_fixes.py` (was fix sections from analysis)

3. **Gold Standards Updated**:
   - `poc_08_gold_standard_export_arangodb.json` → `poc_06_gold_standard_export_arangodb.json`
   - `poc_08_gold_standard_export_original.json` → `poc_06_gold_standard_export_original.json`

## New Pipeline Structure

### Production Pipeline (6 steps)
```
1. poc_01_extract_annotations.py      - Learn from human annotations
2. poc_02_marker_extraction.py         - Extract raw content
3. poc_03_identify_suspicious_blocks.py - Fix misclassified blocks
4. poc_04_create_section_json.py       - Build initial sections
5. poc_05_fix_section_json_enhanced.py - Fix section hierarchy
6. poc_06_export_to_arangodb.py        - Export to database (FINAL)
```

### Testing/Validation Tools
```
- poc_06_validate_against_gold_standards.py - Compare against known-good results
- poc_07_test_analysis_fixes.py              - Test improvement strategies
- poc_09_annotations_to_arangodb.py          - Utility for managing annotations
```

## Benefits of This Structure

1. **Clear Production Path**: Steps 1-6 form a clean, sequential pipeline
2. **Separated Testing**: Validation tools are clearly marked as non-production
3. **No Confusion**: Users won't accidentally run validation on production PDFs
4. **Proper Naming**: Files now accurately reflect their purpose
5. **Maintainable**: Easy to understand which files are for what purpose

## Usage

### Production (for any PDF):
```bash
python poc_02_marker_extraction.py extract document.pdf
python poc_03_identify_suspicious_blocks.py clean outputs/poc_02_output.json
python poc_04_create_section_json.py create outputs/poc_03_output.json
python poc_05_fix_section_json_enhanced.py fix outputs/poc_04_output.json --pdf document.pdf
python poc_06_export_to_arangodb.py export outputs/poc_05_output.json document.pdf
```

### Testing (only for test documents with gold standards):
```bash
# Validate extraction quality
python poc_06_validate_against_gold_standards.py analyze outputs/poc_05_output.json

# Test fix strategies
python poc_07_test_analysis_fixes.py apply outputs/validation_results/
```

## Migration Notes

- All internal references updated to reflect new names
- README.md updated with clear production vs testing distinction
- Gold standard files renamed to match
- No functional changes - only naming for clarity