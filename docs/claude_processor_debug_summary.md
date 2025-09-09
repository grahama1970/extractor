# Claude Processor Debug Summary

## Date: 2025-08-04

## Overview
Successfully debugged and fixed the `claude_processor.py` utility to ensure reliable subprocess calls to Claude CLI with proper error handling, PATH management, and authentication.

## Issues Fixed

### 1. Windows Compatibility
- **Problem**: `os.setsid` not available on Windows
- **Fix**: Made `preexec_fn` conditional - only set on Unix systems
- **Impact**: ClaudeProcessor now works on both Unix and Windows

### 2. Unicode Decode Errors
- **Problem**: Potential crashes when subprocess output contains non-UTF8 characters
- **Fix**: Added `errors='replace'` to all decode operations
- **Impact**: Robust handling of any output encoding

### 3. BrokenPipeError Handling
- **Problem**: Process could exit before consuming stdin, causing BrokenPipeError
- **Fix**: Wrapped stdin operations in try/except block with appropriate warning
- **Impact**: Graceful handling of early process termination

### 4. PIL Dependency Removal
- **Problem**: Unnecessary PIL dependency in working_usage function
- **Fix**: Removed PIL usage, tests skip if images not found
- **Impact**: Reduced dependencies, cleaner test execution

### 5. Hardcoded Paths
- **Problem**: Used hardcoded `/home/username` paths
- **Fix**: Changed to use `Path.home()` for portability
- **Impact**: Works across different users and systems

### 6. Authentication Issue (Critical)
- **Problem**: Claude CLI failed with "Invalid API key" despite using `--dangerously-skip-permissions`
- **Root Cause**: `ANTHROPIC_API_KEY` environment variable was being passed to subprocess
- **Fix**: Added `self.env.pop("ANTHROPIC_API_KEY", None)` to remove API key from subprocess environment
- **Impact**: ClaudeProcessor now works correctly with credentials.json authentication

### 7. Node.js PATH Issue
- **Problem**: Claude CLI requires Node.js but it wasn't in PATH
- **Fix**: Added correct Node.js path (`/home/graham/.nvm/versions/node/v22.15.0/bin`)
- **Impact**: Claude CLI can execute properly

## Test Results

All tests now pass with 100% success rate:
- ✓ Simple text prompt ("What is 2+2?" → "4")
- ✓ Single image analysis (panda image → detailed description)
- ✓ Multiple image comparison (panda vs parrots → comparison)
- ✓ JSON response extraction (structured output with validation)

## Key Learnings

1. **Authentication**: The `--dangerously-skip-permissions` flag requires `ANTHROPIC_API_KEY` to be unset, not just empty
2. **PATH Management**: Comprehensive PATH setup is critical for subprocess execution
3. **Stream Draining**: Essential to prevent 64KB buffer deadlocks in async subprocess handling
4. **Error Messages**: Clear, actionable error messages help debugging significantly

## Code Quality Improvements

- Added comprehensive agent instructions at file header
- Created `ClaudeCallReport` class for detailed call tracking and reporting
- Enhanced logging with command details and PATH information
- Robust JSON extraction using `clean_json_string` utility
- Proper error categorization and helpful error messages

## Usage

```python
from utils.claude_processor import ClaudeProcessor

# Initialize processor
processor = ClaudeProcessor()

# Make a call
response = await processor.call_claude("Your prompt here")

# Batch processing
results = await processor.process_batch([
    {"prompt": "First prompt"},
    {"prompt": "Second prompt"}
], concurrency=10)
```

## Files Modified
- `/home/graham/workspace/experiments/extractor/src/extractor/pipeline/poc/utils/claude_processor.py`

## Dependencies
- No new dependencies added
- Removed PIL dependency from tests
- Uses existing `json_utils.clean_json_string` for robust JSON handling