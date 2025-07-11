# Anti-Hallucination Verification Prompt

## 🔴 SELF-IMPROVEMENT RULES
This prompt MUST follow the self-improvement protocol:
1. Every failure updates metrics immediately
2. Every failure fixes the root cause
3. Every failure adds a recovery test
4. Every change updates evolution history

## 🎮 GAMIFICATION METRICS
- **Success**: 9
- **Failure**: 2
- **Total Executions**: 11
- **Last Updated**: 2025-06-25
- **Success Ratio**: 4.5:1 (need 10:1 to graduate)

## Evolution History
- v1: Initial implementation - basic marker checking
- v2: Added rg pattern matching for complex outputs
- v3: Fixed false positives by checking toolUseResult specifically
- v4: Added automatic transcript directory detection
- v5: Improved error handling for missing transcripts
- v6: Added reasonableness checks - verify outputs contain actual data, not just exit codes

## Purpose

Verify that Claude's claimed outputs actually exist in the transcript AND are reasonable (not empty, gibberish, or just exit codes), preventing hallucinations about execution results.

## Core Verification Pattern

```bash
#!/bin/bash
# Anti-hallucination verification script

# Generate unique marker
MARKER="MARKER_$(date +%Y%m%d_%H%M%S)_$$"
echo "$MARKER"

# Execute your actual code/test here
python your_script.py
echo "Test completed with marker: $MARKER"

# Verify in transcript (MUST happen)
TRANSCRIPT_DIR="$HOME/.claude/projects/$(pwd | sed 's/\//-/g')"
sleep 1  # Give transcript time to write

if rg -q "$MARKER" "$TRANSCRIPT_DIR"/*.jsonl 2>/dev/null; then
    echo "✅ VERIFIED: Execution confirmed in transcript"
    
    # Extract actual output
    rg -A5 -B5 "$MARKER" "$TRANSCRIPT_DIR"/*.jsonl | \
        jq -r '.toolUseResult.stdout // empty' 2>/dev/null | \
        grep -C3 "$MARKER"
else
    echo "❌ HALLUCINATION RISK: No transcript evidence found"
    echo "Checking alternate locations..."
    
    # Debug: Show available transcripts
    ls -la ~/.claude/projects/*/
    
    exit 1
fi
```

## Python Implementation

```python
#!/usr/bin/env python3
"""Anti-hallucination verification for Python scripts"""
import os
import sys
import time
import subprocess
import json
from datetime import datetime

def verify_execution(marker=None, expected_output=None):
    """Verify that code execution is real, not hallucinated"""
    
    # Generate marker if not provided
    if not marker:
        marker = f"MARKER_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    
    print(marker)
    
    # Get transcript directory
    pwd = os.getcwd()
    transcript_dir = f"{os.environ['HOME']}/.claude/projects/{pwd.replace('/', '-')}"
    
    # Wait for transcript to be written
    time.sleep(1)
    
    # Search for marker in transcript
    try:
        result = subprocess.run(
            ['rg', marker, f"{transcript_dir}/*.jsonl"],
            capture_output=True,
            text=True,
            shell=True
        )
        
        if result.returncode == 0:
            print(f"✅ VERIFIED: {marker} found in transcript")
            
            # Parse and verify expected output if provided
            if expected_output:
                found_expected = False
                for line in result.stdout.strip().split('\n'):
                    try:
                        # Extract JSON part after filename
                        json_str = line.split(':', 1)[1]
                        data = json.loads(json_str)
                        
                        if 'toolUseResult' in data:
                            stdout = data['toolUseResult'].get('stdout', '')
                            if expected_output in stdout:
                                found_expected = True
                                print(f"✅ Expected output verified: {expected_output[:50]}...")
                                break
                    except:
                        continue
                
                if not found_expected:
                    print(f"⚠️ Marker found but expected output missing: {expected_output}")
                    return False
            
            return True
        else:
            print(f"❌ NOT VERIFIED: {marker} not found in transcript")
            print(f"Transcript dir: {transcript_dir}")
            
            # Debug: Check if transcript exists
            if os.path.exists(transcript_dir):
                files = subprocess.run(['ls', '-la', transcript_dir], capture_output=True, text=True)
                print(f"Files in transcript dir:\n{files.stdout}")
            else:
                print("Transcript directory does not exist!")
            
            return False
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

# Usage example
if __name__ == "__main__":
    # Always start with verification marker
    marker = verify_execution()
    
    # Your actual code here
    print("Running WebSocket reliability test...")
    result = 42  # Your computation
    print(f"Result: {result}")
    
    # Verify with expected output
    if not verify_execution(marker, f"Result: {result}"):
        print("⚠️ WARNING: Execution may be hallucinated!")
        sys.exit(1)
```

## Quick One-Liners

```bash
# Instant verification
echo "MARKER_$$" && your_command && rg "MARKER_$$" ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl

# Check if something was really printed
rg "YOUR_EXPECTED_OUTPUT" ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl | jq -r '.toolUseResult.stdout' | grep -q "YOUR_EXPECTED_OUTPUT" && echo "✅ VERIFIED" || echo "❌ HALLUCINATED"

# Count claims vs reality
pattern="TEST PASSED"
claims=$(rg "$pattern" ~/.claude/projects/*/*.jsonl | grep -c '"role":"assistant"')
reality=$(rg "$pattern" ~/.claude/projects/*/*.jsonl | grep -c 'toolUseResult')
echo "Claims: $claims, Reality: $reality"
```

## Common Patterns

### For Test Results
```bash
# Verify test actually passed
MARKER="TEST_MARKER_$(date +%s)"
echo "$MARKER"
pytest your_test.py -v
echo "Tests complete: $MARKER"

# Check transcript
rg "$MARKER" ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl | grep -q "toolUseResult" && echo "✅ Tests verified" || echo "❌ Tests not found"
```

### For File Creation
```bash
# Verify file was actually created
FILE_PATH="/tmp/test_file_$$"
echo "Creating $FILE_PATH"
echo "content" > "$FILE_PATH"

# Double verification
ls -la "$FILE_PATH" 2>&1 | tee /tmp/verify_$$
rg "$FILE_PATH" ~/.claude/projects/$(pwd | sed 's/\//-/g')/*.jsonl | grep -q "toolUseResult"
```

## Failure Recovery

When verification fails:

1. **Check transcript location**:
   ```bash
   find ~/.claude/projects -name "*.jsonl" -mmin -5
   ```

2. **Debug what was actually executed**:
   ```bash
   tail -50 ~/.claude/projects/*/$(ls -t ~/.claude/projects/*/*.jsonl | head -1) | jq -r '.toolUseResult.stdout // empty'
   ```

3. **Force new marker and retry**:
   ```bash
   NEW_MARKER="RETRY_$(date +%s)_$$"
   echo "$NEW_MARKER" && your_command && sleep 2 && rg "$NEW_MARKER" ~/.claude/projects/*/*.jsonl
   ```

## Reasonableness Checks

After verifying a marker exists, also verify the output is reasonable:

### 1. For Usage Functions
```bash
# Bad: Only checking exit code
python module.py && echo "✅ Success"

# Good: Verify actual functionality
python module.py > /tmp/output.txt 2>&1
if grep -E "(Service:|Sessions:|Config:|Result:)" /tmp/output.txt; then
    echo "✅ Output contains expected data structures"
else
    echo "❌ Output missing expected content"
fi
```

### 2. For Test Results
```bash
# Bad: Just checking if tests ran
pytest && echo "✅ Tests passed"

# Good: Verify specific test outcomes
pytest -v | tee /tmp/pytest_output.txt
if grep -E "test_.*PASSED|[0-9]+ passed" /tmp/pytest_output.txt; then
    echo "✅ Tests actually executed and passed"
else
    echo "❌ No evidence of actual test execution"
fi
```

### 3. For JSON/API Responses
```bash
# Bad: Assuming valid JSON
curl http://localhost:8003/health

# Good: Parse and verify structure
RESPONSE=$(curl -s http://localhost:8003/health)
if echo "$RESPONSE" | jq -e '.status == "healthy" and .service and .version' >/dev/null; then
    echo "✅ Health check returns valid structure"
else
    echo "❌ Invalid or missing health response"
fi
```

### 4. For Process Operations
```bash
# Bad: Assuming process started
python start_process.py

# Good: Verify actual PID
OUTPUT=$(python process_manager.py)
if echo "$OUTPUT" | grep -E "PID=[0-9]+ PGID=[0-9]+"; then
    echo "✅ Process actually started with real PIDs"
else
    echo "❌ No evidence of process creation"
fi
```

### 5. Reasonableness Patterns
```bash
# Check for non-empty output
[ -s /tmp/output.txt ] || { echo "❌ Empty output file"; exit 1; }

# Check for expected patterns
grep -qE "(PASSED|SUCCESS|Result:|Created|Started)" /tmp/output.txt || \
    { echo "❌ Output missing success indicators"; exit 1; }

# Check against gibberish
if file /tmp/output.txt | grep -q "ASCII text"; then
    echo "✅ Output is readable text"
else
    echo "❌ Output contains binary/gibberish"
fi

# Verify reasonable data sizes
SIZE=$(wc -c < /tmp/output.txt)
if [ $SIZE -gt 50 ] && [ $SIZE -lt 1000000 ]; then
    echo "✅ Output size reasonable: $SIZE bytes"
else
    echo "❌ Suspicious output size: $SIZE bytes"
fi
```

## Key Rules

1. **ALWAYS use unique markers** - Include timestamp and PID
2. **VERIFY immediately after execution** - Don't wait
3. **Check toolUseResult specifically** - Not just any mention
4. **Handle missing transcripts gracefully** - They might be in different location
5. **Never claim success without verification** - Better to fail honestly
6. **Check output reasonableness** - Not just exit codes, verify actual content
7. **Look for expected patterns** - PIDs, session IDs, JSON structure, etc.
8. **Reject empty or gibberish** - Output should contain meaningful data

## Example: CC Executor Usage Verification

```bash
#!/bin/bash
# Verify all cc_executor modules produce reasonable output

MARKER="USAGE_VERIFY_$(date +%Y%m%d_%H%M%S)"
echo "$MARKER: Starting comprehensive usage verification"

# Test each module and verify reasonable output
for module in config models session_manager process_manager stream_handler websocket_handler main; do
    echo -e "\nTesting $module.py..."
    
    # Run and capture output
    python $module.py > /tmp/${module}_verify.txt 2>&1
    EXIT_CODE=$?
    
    # Check exit code
    if [ $EXIT_CODE -ne 0 ]; then
        echo "❌ $module.py failed with exit code $EXIT_CODE"
        continue
    fi
    
    # Check output exists and is non-empty
    if [ ! -s /tmp/${module}_verify.txt ]; then
        echo "❌ $module.py produced no output"
        continue
    fi
    
    # Module-specific reasonableness checks
    case $module in
        config)
            if grep -qE "(Service: cc_executor_mcp|Max Sessions: [0-9]+|Log Level:)" /tmp/${module}_verify.txt; then
                echo "✅ $module.py shows configuration values"
            else
                echo "❌ $module.py missing expected config data"
            fi
            ;;
        models)
            if grep -qE "(JSON-RPC Request:|jsonrpc.*2\.0|method.*execute)" /tmp/${module}_verify.txt; then
                echo "✅ $module.py generates valid JSON-RPC"
            else
                echo "❌ $module.py missing JSON-RPC structures"
            fi
            ;;
        session_manager)
            if grep -qE "(Created session-[0-9]|Active sessions: [0-9]+/[0-9]+)" /tmp/${module}_verify.txt; then
                echo "✅ $module.py manages sessions"
            else
                echo "❌ $module.py missing session management"
            fi
            ;;
        process_manager)
            if grep -qE "(PID=[0-9]+|PGID=[0-9]+|Process terminated)" /tmp/${module}_verify.txt; then
                echo "✅ $module.py controls real processes"
            else
                echo "❌ $module.py missing process operations"
            fi
            ;;
        *)
            if grep -qE "(✅|completed|passed|SUCCESS)" /tmp/${module}_verify.txt; then
                echo "✅ $module.py completed successfully"
            else
                echo "❌ $module.py missing success indicators"
            fi
            ;;
    esac
done

echo -e "\n$MARKER: Verification complete"

# Final transcript check
sleep 1
if rg "$MARKER" ~/.claude/projects/-home-graham-workspace-experiments-cc-executor/*.jsonl >/dev/null; then
    echo "✅ All verifications recorded in transcript"
else
    echo "❌ Verifications not found in transcript - possible hallucination"
fi
```

## Test This Prompt

```bash
# Extract and test
sed -n '/^```bash$/,/^```$/p' anti_hallucination_verification.md | sed '1d;$d' > /tmp/verify_test.sh
chmod +x /tmp/verify_test.sh
/tmp/verify_test.sh
```