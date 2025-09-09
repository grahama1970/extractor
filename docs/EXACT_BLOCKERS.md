# Exact Blockers in PDF Extraction Pipeline

**Date**: 2025-07-31  
**Time**: 17:42 EDT  

## BLOCKER 1: Marker/convert_single.py Hangs Indefinitely

**Problem**: The marker PDF extraction process hangs and never completes.

**Command that hangs**:
```bash
python ../../src/extractor/core/scripts/convert_single.py clean.pdf --output_dir . --output_format json
```

**Evidence**:
- Process hangs after loading initial modules
- No output file is generated
- Process must be killed with timeout or Ctrl+C
- Last output before hang: "Initialized UnifiedClaudeService with database at /home/graham/.marker/claude_unified.db"

**Impact**: Stage 5 cannot complete, forcing use of fallback blocks.json

## BLOCKER 2: PostToolUse Hooks Don't Capture Environment Variables

**Problem**: The Claude Code environment variables are not populated in hooks.

**Current hook configuration**:
```json
"command": "bash -c 'echo \"[$(date)] cmd=$CLAUDE_CMD exit=$CLAUDE_EXIT_CODE\" >> \"$log_dir/commands.log\"'"
```

**Actual output**:
```
[Thu Jul 31 05:42:25 PM EDT 2025] cmd= exit=
```

**Expected output**:
```
[Thu Jul 31 05:42:25 PM EDT 2025] cmd=python -m extractor.core.processors... exit=0
```

**Impact**: Cannot automatically capture command outputs and exit codes for debugging

## BLOCKER 3: Validator Module Syntax Errors

**Problem**: Multiple validator modules have syntax errors preventing loading.

**Errors**:
1. `/validators/table.py`: Line 2 has invalid syntax (fixed)
2. `/validators/code.py`: "name 'code' is not defined"
3. `/validators/citation.py`: "invalid syntax (citation.py, line 3)"
4. `/validators/math.py`: "name 'math' is not defined"
5. `/validators/general.py`: "name 'general' is not defined"
6. `/validators/value.py`: "name 'value' is not defined"
7. `/validators/image.py`: "name 'image' is not defined"

**Impact**: LLM validation strategies cannot be loaded, may affect LLM-based enhancements

## Summary

Three distinct blockers exist:
1. **Critical**: Marker extraction hangs - prevents proper PDF content extraction
2. **Major**: Hook environment variables not populated - prevents automated logging
3. **Minor**: Validator modules have syntax errors - may affect LLM features

No workarounds are in place. The pipeline uses fallback data when marker fails, but this is not a workaround - it's missing the actual PDF content extraction.