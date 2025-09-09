# Claude API Fix Plan - FAIL FAST Implementation

## Root Cause Analysis

### 1. Authentication Issue
The Claude processor is using `--dangerously-skip-permissions` flag (line 630) which requires:
- NO `ANTHROPIC_API_KEY` in environment
- Valid `~/.claude/.credentials.json` file
- The processor is removing `ANTHROPIC_API_KEY` (line 235) but this might not be enough

### 2. Error Handling Issue  
All POC scripts are **continuing after Claude failures** instead of failing fast:

**POC 03 Example (lines 1390-1391):**
```python
else:
    logger.error(f"Batch {idx} failed: {batch_result['error']}")
    # CONTINUES PROCESSING! This is WRONG!
```

## Immediate Fixes Required

### Fix 1: Update Claude Processor Authentication

```python
# In claude_processor.py __init__ method:

# Option A: Use API key mode (more reliable)
if os.getenv("ANTHROPIC_API_KEY"):
    # Remove --dangerously-skip-permissions when API key is present
    self.use_api_key_mode = True
else:
    # Use credentials.json mode
    self.use_api_key_mode = False
    self.env.pop("ANTHROPIC_API_KEY", None)

# In call_claude method:
cmd = [self.claude_bin, '-p']
if not self.use_api_key_mode:
    cmd.append('--dangerously-skip-permissions')
```

### Fix 2: Implement FAIL FAST in All POCs

**POC 01 - Extract Annotations:**
```python
# After Claude timeout
except TimeoutError:
    logger.error("CRITICAL: Claude API timeout - cannot continue without AI analysis")
    raise RuntimeError("Pipeline cannot function without Claude API response")
```

**POC 03 - Identify Suspicious Blocks:**
```python
# After batch processing
failed_batches = [r for r in batch_results if not r['success']]
if failed_batches:
    errors = [f"Batch {r['index']}: {r['error']}" for r in failed_batches]
    raise RuntimeError(f"Claude API failed for {len(failed_batches)} batches:\n" + "\n".join(errors))
```

**POC 05 - Fix Section JSON:**
```python
# After max retries
if not response:
    raise RuntimeError(f"Claude API failed after {max_retries} attempts - cannot enhance sections")
```

### Fix 3: Add Pre-flight Check

Create a simple test before running the pipeline:

```python
async def verify_claude_working():
    """Verify Claude API is working before starting pipeline."""
    try:
        processor = ClaudeProcessor()
        response = await processor.call_claude("Say 'OK' if you're working", timeout=10)
        if "OK" not in response:
            raise ValueError(f"Unexpected response: {response}")
        logger.info("✓ Claude API verified working")
        return True
    except Exception as e:
        logger.error(f"Claude API verification failed: {e}")
        raise RuntimeError("Cannot start pipeline - Claude API not working")
```

## Testing the Fix

1. **Test Claude CLI directly:**
```bash
# With API key
export ANTHROPIC_API_KEY=your_key
claude -p "Test"

# Without API key (credentials.json)
unset ANTHROPIC_API_KEY
claude -p --dangerously-skip-permissions "Test"
```

2. **Debug the exact error:**
```python
# Add more debugging to claude_processor.py
logger.debug(f"Command: {' '.join(cmd)}")
logger.debug(f"Environment ANTHROPIC_API_KEY: {'SET' if 'ANTHROPIC_API_KEY' in self.env else 'UNSET'}")
logger.debug(f"Credentials file exists: {Path.home() / '.claude' / '.credentials.json').exists()}")
```

## Summary

The pipeline MUST:
1. **Fix authentication** - Either use API key OR credentials.json, not a broken mix
2. **Fail immediately** when Claude doesn't respond
3. **Verify Claude works** before starting any processing
4. **Provide clear error messages** about what's wrong

Without these fixes, the pipeline is just pretending to work while producing garbage output.