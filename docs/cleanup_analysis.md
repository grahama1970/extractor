# Marker Project Cleanup Analysis

## Files to Move/Archive/Delete

### 1. Stray Test Files in Root (Move to tests/)
- `test_basic_rl.py`
- `test_basic_rl_fixed.py`
- `test_basic_rl_v2.py`
- `test_marker_benchmark.py`
- `test_rl_correct.py`

### 2. Test JSON Files in Root (Archive or Delete)
These appear to be test result files that should be in test_results/ or archived:
- `001_final_tests.json`
- `001_test1.json`
- `001_tests.json`
- `002_test1.json`
- `002_tests.json`
- `003_test1.json`
- `003_tests.json`
- `004_core_tests.json`
- `004_integration_tests.json`
- `004_processor_tests.json`
- `004_verification_tests.json`

### 3. Scripts in Root (Move to appropriate locations)
- `quick_start_rl.py` - Move to examples/ or scripts/
- `sparta_extractor.py` - Move to scripts/ or examples/

### 4. Shell Scripts in Root
- `setup_claude_comms_repo.sh` - Move to scripts/

### 5. Configuration Files (Keep in root)
These should stay in root:
- `marker_mcp.json`
- `marker_mcp_full.json`
- `requirements.json`
- `.mcp.json`
- `pyproject.toml`
- `pytest.ini`
- `uv.lock`

### 6. Duplicate Test Directories
- `test/` directory should be merged into `tests/` or deleted
  - Contains: test_rl_integration*.py files

### 7. Large Archive Directory
The `archive/` directory contains many old files that could be cleaned up:
- Old logs in `archive/logs/`
- Old test files in `archive/old_tests/`
- Debug scripts in `archive/debug_scripts/`
- Analysis documents in `archive/analysis_docs/`

### 8. Temporary Outputs
- `archive/temp_outputs/` - Can likely be deleted
- `conversion_results/` - Check if needed, otherwise archive
- `debug_output/` - Contains many PDF page images, check if needed

### 9. Documentation Redundancy
The docs directory has been reorganized but still contains 86 files. Consider:
- Consolidating similar reports
- Archiving completed task documentation
- Removing duplicate guides

### 10. Data Directory Cleanup
- `data/debug_samples/` - Archive old debug samples
- `data/latex_to_md.sh` - Move to scripts/

### 11. Logs Directory
- `logs/` in root - Contains old logs that could be archived
- Multiple log files scattered in archive/logs/

### 12. Message Directories
- `messages/from_arangodb/` - Check if empty, delete if so
- `messages/to_arangodb/` - Check if empty, delete if so

### 13. Repos Directory
The `repos/` directory contains full clones of other projects:
- `camelot/`
- `label-studio/`
- `marker/`
- `unsloth/`
Consider if these are needed or should be git submodules

### 14. Duplicate Examples
Check for redundancy between:
- `examples/`
- `archive/debug_scripts/`
- Various test files

## Recommended Actions

1. **Create archive branch**: Before cleanup, create a branch to preserve current state
2. **Move test files**: All test*.py files in root should go to tests/
3. **Archive old results**: Move JSON test results to archive/test_results/
4. **Consolidate scripts**: Move loose scripts to scripts/ directory
5. **Clean empty directories**: Remove empty message directories
6. **Archive old logs**: Move all .log files to archive/logs/
7. **Review repos/**: Determine if full repo clones are needed
8. **Merge test/ into tests/**: Consolidate test directories
9. **Clean debug outputs**: Archive or delete old debug outputs
10. **Document cleanup**: Update README with new structure

## Priority Items

### High Priority (Affects code organization)
1. Move Python test files from root to tests/
2. Move scripts from root to scripts/
3. Merge test/ directory into tests/
4. Archive test JSON files

### Medium Priority (Cleanup)
1. Archive old logs
2. Clean empty directories
3. Organize debug outputs
4. Review and clean archive/

### Low Priority (Nice to have)
1. Consolidate documentation
2. Review repos/ directory
3. Clean up examples/
