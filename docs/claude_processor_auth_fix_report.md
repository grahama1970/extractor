# ClaudeProcessor Authentication Fix Report

## Issue Summary

The `ClaudeProcessor` was failing with "Invalid API key" errors when using the `--dangerously-skip-permissions` flag, while direct subprocess calls to the Claude CLI were working fine.

## Root Cause

The issue was that `ClaudeProcessor` preserves the original environment variables when creating the subprocess, including `ANTHROPIC_API_KEY` if it's set. The `--dangerously-skip-permissions` flag requires that `ANTHROPIC_API_KEY` is **NOT** set in the environment, otherwise it fails with "Invalid API key" error.

## Key Differences Found

1. **Working test** (`test_claude_direct.py`):
   ```python
   env = os.environ.copy()
   env.pop("ANTHROPIC_API_KEY", None)  # Explicitly removes API key
   ```

2. **Failing code** (original `ClaudeProcessor`):
   ```python
   self.env = os.environ.copy()  # Preserves all env vars including ANTHROPIC_API_KEY
   ```

## Solution Implemented

Added code to explicitly remove `ANTHROPIC_API_KEY` from the environment in `ClaudeProcessor.__init__()`:

```python
# Setup comprehensive PATH to prevent "command not found" errors
self.env = os.environ.copy()

# CRITICAL: Remove ANTHROPIC_API_KEY when using --dangerously-skip-permissions
# This flag requires that ANTHROPIC_API_KEY is NOT set in the environment
self.env.pop("ANTHROPIC_API_KEY", None)
```

## Test Results

After implementing the fix:

1. ✓ **With fake API key**: ClaudeProcessor now works even when ANTHROPIC_API_KEY is set in the parent environment
2. ✓ **Normal operation**: Basic Claude calls work correctly
3. ✓ **Batch processing**: Concurrent batch processing works as expected

## Minor Issue Remaining

When using `--output-format json`, the Claude CLI returns a structured response with metadata:
```json
{
  "type": "result",
  "result": "```json\n{\n  \"status\": \"working\",\n  \"message\": \"ClaudeProcessor is fixed!\"\n}\n```",
  "usage": {...},
  ...
}
```

The JSON extraction logic needs to be updated to handle this format and extract the actual result from the `result` field.

## Lessons Learned

1. When using subprocess with environment variables, always be explicit about which variables should be passed through
2. The `--dangerously-skip-permissions` flag has specific requirements about environment state
3. Authentication mechanisms can conflict when multiple are present (API key vs Claude Code credentials)
4. Always test with various environment configurations to catch edge cases

## Files Modified

- `/home/graham/workspace/experiments/extractor/src/extractor/pipeline/poc/utils/claude_processor.py` - Added `env.pop("ANTHROPIC_API_KEY", None)`
- `/home/graham/workspace/experiments/extractor/src/extractor/pipeline/poc/__init__.py` - Temporarily commented out broken imports (separate issue)

## Verification Steps

To verify the fix works:
1. Set a fake API key: `export ANTHROPIC_API_KEY=sk-fake-key`
2. Run the ClaudeProcessor with any prompt
3. It should now work instead of failing with "Invalid API key"