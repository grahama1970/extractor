# Additional Cleanup - August 16, 2025

## Additional Files Cleaned

After the initial cleanup, found and cleaned additional loose files:

### POC Simplified Directory
**Location:** `src/extractor/pipeline/poc_simplified/`

**Removed:**
- `01_annotation_processor copy.py` - Duplicate file
- `03_knn_suspicious_detector.py` - Should be in pipeline subdirectory
- Test scripts: `test_annotations.py`, `run_full_test.sh`, `run_pipeline.py`
- Utility scripts: `fix_pipeline_stages.py`
- Output files: `stage_*.json`, `stage_*.log`, `*.png`
- `pipeline_test.log`

**Kept:**
- `README.md`
- `requirements.txt`

### Pipeline Directory
**Location:** `src/extractor/pipeline/poc_simplified/pipeline/`

**Removed:**
- All test output files: `test_*.json`, `test_*.log`
- Stage output files: `stage_*.json`, `stage_*.log`

**Kept:**
- Essential pipeline scripts (00-14_*.py)
- `gold_standard_output.json` - Important reference
- `sample_stage_07_output.json` - Example output

### Root Directory
**Location:** Project root

**Removed:**
- `claude_subprocess_example.png`
- `critical_lessons_subprocess_path.json`
- `extracted_blocks_old.json`
- `extractor_output.log`
- Output images: `page_1_table_1.png`, `page_2_table_1.png`, `section_visual_2.png`
- Stage outputs: `stage_*.json`, `stage_*.log`
- `test_multipage_visual_result.json`

### Other Directories
**Removed:**
- `src/extractor/conversion_results/` - Moved entire directory with test outputs

## Summary

These additional cleanups removed:
- ~50 more loose files
- Test outputs that should be in tmp/
- Duplicate and misplaced scripts
- PNG images and JSON outputs in wrong locations

All files were moved to `.archive/poc_simplified_cleanup_20250816/` for preservation.

The project structure is now much cleaner with:
- Pipeline scripts in their proper directory
- No loose output files cluttering directories
- Clear separation between code and generated outputs