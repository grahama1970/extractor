# Hallucination Checker Prompt

## 🔴 SELF-IMPROVEMENT RULES
This prompt MUST follow the self-improvement protocol:
1. Every failure updates metrics immediately
2. Every failure fixes the root cause
3. Every failure adds a recovery test
4. Every change updates evolution history

## 🎮 GAMIFICATION METRICS
- **Success**: 0
- **Failure**: 0
- **Total Executions**: 0
- **Last Updated**: 2025-06-25
- **Success Ratio**: N/A (need 10:1 to graduate)

## Evolution History
- v1: Initial implementation - basic verification pattern

## Purpose

After EVERY significant task or claim, I MUST verify that my outputs are real by checking the transcript. This prevents me from hallucinating results.

## Helper Module Available

Use the transcript helper for easier verification:
```python
# Import the helper
import sys
sys.path.append('/home/graham/workspace/experiments/cc_executor/src/cc_executor/prompts/commands')
from transcript_helper import quick_verify, check_hallucination, get_transcript_dir

# Quick verification
marker = quick_verify()  # Generates and prints marker
# ... do your work ...
quick_verify(marker)     # Verifies execution

# Check for hallucinations
result = check_hallucination("PASSED")  # Returns: VERIFIED, HALLUCINATED, or NOT_FOUND
```

## Core Verification Process

### Step 1: Mark Your Work
```python
# Before any task
import datetime
MARKER = f"HALLUCINATION_CHECK_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Starting task with marker: {MARKER}")

# Do the actual work
result = perform_task()
print(f"Task completed: {MARKER}")
print(f"Result: {result}")
```

### Step 2: Verify in Transcript
```python
# Immediately after task
import subprocess
import os
import time

# Wait for transcript to write
time.sleep(1)

# Find transcript directory
pwd = os.getcwd()
transcript_dir = f"{os.environ['HOME']}/.claude/projects/{pwd.replace('/', '-')}"

# Check if marker exists
cmd = f"rg '{MARKER}' {transcript_dir}/*.jsonl"
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

if result.returncode == 0:
    print(f"✅ VERIFIED: Task execution found in transcript")
    # Extract actual output
    cmd2 = f"rg -A5 '{MARKER}' {transcript_dir}/*.jsonl | grep -A10 toolUseResult"
    actual = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
    print(f"Actual output:\n{actual.stdout[:500]}")
else:
    print(f"❌ HALLUCINATION WARNING: No transcript evidence!")
    print(f"Either task didn't execute or output was imagined")
```

## Flexible Verification Patterns

### For Complex Tasks
```python
def verify_complex_task(task_name, expected_patterns):
    """Verify multiple aspects of a complex task"""
    
    marker = f"COMPLEX_TASK_{task_name}_{datetime.datetime.now().strftime('%H%M%S')}"
    print(marker)
    
    # Do the task
    results = {}
    for pattern in expected_patterns:
        # Execute and collect
        output = execute_subtask(pattern)
        results[pattern] = output
        print(f"{pattern}: {output}")
    
    # Verify each pattern
    transcript_dir = f"{os.environ['HOME']}/.claude/projects/{os.getcwd().replace('/', '-')}"
    verified = 0
    
    for pattern, expected in results.items():
        check = subprocess.run(
            f"rg '{pattern}.*{expected}' {transcript_dir}/*.jsonl | grep toolUseResult",
            shell=True, capture_output=True
        )
        if check.returncode == 0:
            verified += 1
            print(f"✅ Verified: {pattern}")
        else:
            print(f"❌ Not verified: {pattern}")
    
    success_rate = verified / len(expected_patterns)
    print(f"Verification rate: {verified}/{len(expected_patterns)} = {success_rate:.1%}")
    
    return success_rate > 0.8  # 80% threshold
```

### Quick One-Line Checks
```bash
# After creating a file
echo "CREATED_FILE_$$" && touch /tmp/test_$$ && ls -la /tmp/test_$$ && rg "CREATED_FILE_$$" ~/.claude/projects/*/*.jsonl

# After running a test
python test.py && echo "TEST_RAN_$$" && rg "TEST_RAN_$$" ~/.claude/projects/*/*.jsonl | grep -q toolUseResult && echo "✅" || echo "❌"

# After any command
cmd && echo "CMD_SUCCESS_$$" && sleep 1 && rg "CMD_SUCCESS_$$" ~/.claude/projects/*/*.jsonl | tail -1
```

## When to Use This

### MUST verify after:
1. **Creating files** - Verify they actually exist
2. **Running tests** - Verify actual pass/fail status
3. **Executing commands** - Verify exit codes and output
4. **Making changes** - Verify edits were applied
5. **Checking status** - Verify current state is real

### Example Usage Pattern
```python
# Task: Create and test a WebSocket client

# Step 1: Mark start
marker = f"WS_CLIENT_TEST_{datetime.datetime.now().strftime('%H%M%S')}"
print(f"Creating WebSocket client test: {marker}")

# Step 2: Create file
with open('/tmp/ws_test.py', 'w') as f:
    f.write("import websockets...")
print(f"File created: {marker}")

# Step 3: Run test
result = subprocess.run(['python', '/tmp/ws_test.py'], capture_output=True)
print(f"Test result: {result.returncode} - {marker}")

# Step 4: VERIFY (This is the critical step!)
transcript_check = subprocess.run(
    f"rg '{marker}' ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl | grep -c toolUseResult",
    shell=True, capture_output=True, text=True
)

if int(transcript_check.stdout.strip() or 0) >= 3:  # Should see 3 outputs
    print(f"✅ All steps verified in transcript")
else:
    print(f"❌ HALLUCINATION DETECTED - not all steps found in transcript")
    print(f"Found only: {transcript_check.stdout.strip()} occurrences")
```

## Recovery When Verification Fails

1. **Don't panic** - Just acknowledge it
2. **Don't claim success** - Be honest about failure
3. **Try alternative verification**:
   ```bash
   # Find the right transcript
   find ~/.claude/projects -name "*.jsonl" -mmin -10 -exec grep -l "your_pattern" {} \;
   
   # Check recent commands
   ls -la ~/.claude/projects/*/  | grep "$(date +%b.*%d)"
   ```

4. **Re-run with new marker**:
   ```python
   # If first attempt wasn't verified, try again
   new_marker = f"RETRY_{int(time.time())}"
   print(new_marker)
   # Repeat task...
   ```

## Self-Test This Prompt

```python
# Test the hallucination checker itself
test_marker = f"SELF_TEST_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(test_marker)
print("If you see this in transcript, hallucination checking works!")

# Wait and verify
import time
time.sleep(2)

# Check
import subprocess
result = subprocess.run(
    f"rg '{test_marker}' ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl",
    shell=True, capture_output=True, text=True
)

if result.returncode == 0:
    print("✅ Hallucination checker is working!")
    print(f"Evidence: {result.stdout[:200]}...")
else:
    print("❌ Hallucination checker needs debugging")
    print("Check transcript location...")
```

## Key Principles

1. **Mark BEFORE and AFTER** - Bookend your work with markers
2. **Unique markers always** - Include timestamp or PID
3. **Check immediately** - Don't wait, transcripts can rotate
4. **Look for toolUseResult** - Not just mentions in text
5. **Be honest about failures** - Don't hide verification failures

## Real Usage Examples with ripgrep and jq

### Example 1: Verifying Docker Container Status
```bash
# Task: Check if Docker container is really running
MARKER="DOCKER_CHECK_$(date +%Y%m%d_%H%M%S)"
echo "$MARKER: Checking Docker container"
docker ps | grep cc_executor_mcp
echo "$MARKER: Check complete"

# Verify with ripgrep and jq
# Note: underscores in path become hyphens in transcript name!
TRANSCRIPT_DIR="$HOME/.claude/projects/$(pwd | sed 's/_/-/g' | sed 's/\//-/g')"
rg "$MARKER" "$TRANSCRIPT_DIR"/*.jsonl | \
  jq -r 'select(.toolUseResult) | .toolUseResult.stdout' | \
  grep -q "cc_executor_mcp" && echo "✅ Container verified running" || echo "❌ Container status hallucinated"
```

### Example 2: Verifying File Modifications
```bash
# Task: Edit a Python file
MARKER="EDIT_IMPL_$(date +%s)"
echo "$MARKER"

# Make the edit (example)
# ... Edit operation here ...

# Verify the edit happened
rg "$MARKER" "$TRANSCRIPT_DIR"/*.jsonl -A10 | \
  jq -r 'select(.message.content[0].name == "Edit") | {
    file: .message.content[0].input.file_path,
    old: .message.content[0].input.old_string[:50],
    new: .message.content[0].input.new_string[:50]
  }' && echo "✅ Edit verified" || echo "❌ Edit not found"
```

### Example 3: Verifying Test Results
```bash
# Task: Run WebSocket tests
MARKER="WS_TEST_RUN_$(date +%Y%m%d_%H%M%S)"
echo "Starting test: $MARKER"

# Run the actual test
python src/cc_executor/tasks/executor/003_websocket_reliability_implementation.py
echo "Test complete: $MARKER"

# Extract and verify results with jq
rg "$MARKER" "$TRANSCRIPT_DIR"/*.jsonl -B20 -A20 | \
  jq -r 'select(.toolUseResult.stdout) | .toolUseResult.stdout' | \
  grep -E "(PASSED|FAILED|SUCCESS)" | \
  while read line; do
    echo "Found result: $line"
    [[ "$line" =~ "PASSED" ]] && echo "✅ Test passed" || echo "❌ Test failed"
  done
```

### Example 4: Comprehensive Task Verification
```python
#!/usr/bin/env python3
"""Example of verifying a complex multi-step task"""
import subprocess
import json
import os
from datetime import datetime

def verify_websocket_fixes():
    """Verify all 6 WebSocket reliability fixes were actually implemented"""
    
    # Generate master marker
    master_marker = f"VERIFY_WS_FIXES_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Master verification marker: {master_marker}")
    
    # Define what we're checking
    fixes_to_verify = [
        ("Session Locking", "session_lock = asyncio.Lock()"),
        ("Session Limit", "MAX_SESSIONS = 100"),
        ("Stream Timeout", "asyncio.wait_for"),
        ("Control Flow", "else:.*# Fix #4"),
        ("Partial Lines", "LimitOverrunError"),
        ("CancelledError", "# Fix #6.*Don't re-raise")
    ]
    
    # Check implementation file
    impl_file = "/home/graham/workspace/experiments/cc_executor/src/cc_executor/core/implementation.py"
    print(f"Checking {impl_file}")
    
    # Get transcript directory
    transcript_dir = f"{os.environ['HOME']}/.claude/projects/{os.getcwd().replace('/', '-')}"
    
    # Verify each fix
    verified_count = 0
    for fix_name, pattern in fixes_to_verify:
        sub_marker = f"{master_marker}__{fix_name.replace(' ', '_')}"
        print(f"\nChecking {fix_name}: {sub_marker}")
        
        # Check if pattern exists in file
        grep_result = subprocess.run(
            f"grep -E '{pattern}' {impl_file}",
            shell=True, capture_output=True, text=True
        )
        
        if grep_result.returncode == 0:
            print(f"  Found pattern in file: ✓")
            
            # Now verify we actually added it (not hallucinated)
            # Look for recent Edit operations on this file
            rg_cmd = f"""
            rg 'Edit.*implementation.py' {transcript_dir}/*.jsonl -A5 | \
            jq -r 'select(.message.content[0].name == "Edit" and 
                          .message.content[0].input.file_path == "{impl_file}" and
                          (.message.content[0].input.new_string | contains("{pattern}"))) | 
                   "EDIT_VERIFIED"' | tail -1
            """
            
            verify_result = subprocess.run(rg_cmd, shell=True, capture_output=True, text=True)
            
            if "EDIT_VERIFIED" in verify_result.stdout:
                print(f"  Edit verified in transcript: ✓")
                verified_count += 1
            else:
                print(f"  ⚠️ Pattern exists but edit not found in transcript")
                # Could be from previous session
        else:
            print(f"  ❌ Pattern not found in file!")
    
    # Summary
    print(f"\n{master_marker} SUMMARY:")
    print(f"Verified {verified_count}/{len(fixes_to_verify)} fixes")
    
    # Final verification - check our own output
    subprocess.run(
        f"rg '{master_marker}' {transcript_dir}/*.jsonl | wc -l",
        shell=True
    )
    
    return verified_count == len(fixes_to_verify)

# Run verification
if __name__ == "__main__":
    verify_websocket_fixes()
```

### Example 5: Quick Verification Patterns

```bash
# After creating a file - verify it exists
MARKER="CREATE_$(date +%s)" && \
echo "$MARKER" && \
touch /tmp/test_file_$$ && \
ls -la /tmp/test_file_$$ && \
rg "$MARKER" ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl -A5 | \
jq -r '.toolUseResult.stdout' | grep -q "test_file" && echo "✅ File created" || echo "❌ Hallucinated"

# After running pytest - verify actual results
MARKER="PYTEST_$(date +%s)" && \
echo "$MARKER" && \
pytest -xvs tests/test_websocket.py && \
rg "$MARKER" ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl -A20 | \
jq -r '.toolUseResult.stdout' | grep -E "passed|failed|ERROR"

# After docker commands - verify container state
MARKER="DOCKER_$(date +%s)" && \
echo "$MARKER" && \
docker ps --format "table {{.Names}}\t{{.Status}}" | grep cc_executor && \
rg "$MARKER" ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl -A5 | \
jq -r '.toolUseResult.stdout' | grep -q "Up" && echo "✅ Container running" || echo "❌ Status unknown"
```

### Example 6: Debugging When Verification Fails

```bash
# Find the right transcript directory
find ~/.claude/projects -type d -name "*cc*executor*" -o -name "*$(basename $PWD)*"

# Check last 10 tool uses
tail -100 ~/.claude/projects/*/[^.]*.jsonl | \
  jq -r 'select(.toolUseResult) | {
    tool: .message.content[0].name,
    time: .timestamp,
    exit: .toolUseResult.exitCode,
    output: (.toolUseResult.stdout[:100] + "...")
  }'

# Find all my claims vs reality in last hour
PATTERN="SUCCESS|PASSED|COMPLETE|VERIFIED"
echo "=== My Claims ==="
find ~/.claude/projects -name "*.jsonl" -mmin -60 -exec grep -h "$PATTERN" {} \; | \
  jq -r 'select(.role == "assistant") | .content' | grep -E "$PATTERN" | head -10

echo -e "\n=== Reality ==="  
find ~/.claude/projects -name "*.jsonl" -mmin -60 -exec grep -h "$PATTERN" {} \; | \
  jq -r 'select(.toolUseResult) | .toolUseResult.stdout' | grep -E "$PATTERN" | head -10
```

## Integration with Tasks

After EVERY task in my todo list, I will:
1. Generate a unique marker: `TASK_NAME_$(date +%Y%m%d_%H%M%S)`
2. Print it before starting
3. Do the actual work
4. Print completion with marker
5. Verify in transcript using ripgrep + jq
6. Only mark task complete if verified

This is NOT optional - it's a core part of reliable execution.