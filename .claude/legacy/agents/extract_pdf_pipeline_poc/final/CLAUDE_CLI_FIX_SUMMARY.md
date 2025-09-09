# Claude CLI Integration Fix Summary

## Problem
The PDF extraction pipeline (POC 07) was not actually calling Claude CLI - it was falling back to heuristics, causing incorrect classifications of table cells as section headers.

## Root Causes
1. **API Key Conflict**: ANTHROPIC_API_KEY environment variable must be unset for Claude CLI to use its own authentication
2. **Bun Wrapper Issue**: Calling claude through bun (`bun claude -p`) fails with "Invalid API key", but calling claude directly works
3. **PATH Setup**: Claude needs node.js in PATH to execute properly

## Solution
Updated `call_claude_cli_sync()` in poc_07_final_secure_pipeline.py:

1. **Unset ANTHROPIC_API_KEY**: `env.pop("ANTHROPIC_API_KEY", None)`
2. **Call claude directly**: Use `[claude_path, "-p", prompt]` instead of `[bun_path, claude_path, "-p", prompt]`
3. **Fix PATH**: Add both `/home/graham/.bun/bin` and node paths to environment

## Results
- Claude CLI now successfully analyzes blocks
- Correctly identifies garbled text as TableCell (not Text)
- Returns confidence scores and reasoning
- No more fallback to heuristics

## Test Output
```
2025-08-02 13:03:09 | INFO | Claude CLI analyzed 1 blocks
Analysis results: [{
    'uuid': 'test-001', 
    'correct_type': 'TableCell', 
    'confidence': 0.85, 
    'reasoning': 'Garbled OCR of table header cells containing column names (Signal/IO/Description/Type/connection)'
}]
```

The pipeline now makes real Claude calls as expected!