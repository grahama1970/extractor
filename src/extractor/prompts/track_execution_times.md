# Track Execution Times — Self-Improving Prompt

## 📊 TASK METRICS & HISTORY
- **Success/Failure Ratio**: 0:0 (Requires 10:1 to graduate)
- **Last Updated**: 2025-06-25
- **Evolution History**:
  | Version | Change & Reason                                     | Result |
  | :------ | :---------------------------------------------------- | :----- |
  | v1      | Initial Redis-based execution time tracking         | TBD    |

---
## 🏛️ ARCHITECT'S BRIEFING (Immutable)

### 1. Purpose
Track stress test execution times in Redis to predict appropriate timeouts for MCP long-running tasks. Learn from actual execution times to avoid premature timeouts.

### 2. Core Principles & Constraints
- MCP tasks can take 5-10 minutes or more - timeouts must be generous
- Use Redis to persist execution history across runs
- Calculate percentiles, not just averages, for timeout predictions
- Always err on the side of longer timeouts for MCP

### 3. API Contract & Dependencies
- **Input Parameters:**
  - `task_id`: (string) Unique task identifier
  - `category`: (string) Task category (simple, complex, etc.)
  - `action`: (string) "record" or "predict"
  - `expected_time`: (float) Expected execution time (for record)
  - `actual_time`: (float) Actual execution time (for record)
  - `success`: (bool) Whether task succeeded (for record)
  - `base_timeout`: (float) Default timeout (for predict)
- **Output:**
  - For record: Confirmation of stored data
  - For predict: Recommended timeout and statistics
- **Dependencies:**
  - Redis running on localhost:6379
  - redis-cli command available

---
## 🤖 IMPLEMENTER'S WORKSPACE

### **Implementation Code Block**
```bash
#!/bin/bash
# Track execution times using Redis

# Parameters
ACTION="${ACTION:-predict}"  # "record" or "predict"
TASK_ID="${TASK_ID:-unknown}"
CATEGORY="${CATEGORY:-unknown}"
EXPECTED_TIME="${EXPECTED_TIME:-300}"
ACTUAL_TIME="${ACTUAL_TIME:-0}"
SUCCESS="${SUCCESS:-true}"
BASE_TIMEOUT="${BASE_TIMEOUT:-300}"

# Redis key pattern
KEY_PREFIX="cc_executor:times"
TASK_KEY="${KEY_PREFIX}:${CATEGORY}:${TASK_ID}"

if [ "$ACTION" = "record" ]; then
    echo "📝 Recording execution time for $CATEGORY:$TASK_ID"
    
    # Create timestamp
    TIMESTAMP=$(date +%s)
    
    # Create JSON record
    RECORD=$(cat <<EOF
{
  "timestamp": $TIMESTAMP,
  "expected": $EXPECTED_TIME,
  "actual": $ACTUAL_TIME,
  "success": $SUCCESS,
  "ratio": $(echo "scale=2; $ACTUAL_TIME / $EXPECTED_TIME" | bc)
}
EOF
)
    
    # Store in Redis sorted set (score = timestamp)
    redis-cli ZADD "${TASK_KEY}:history" $TIMESTAMP "$RECORD" > /dev/null
    
    # Keep only last 100 entries
    redis-cli ZREMRANGEBYRANK "${TASK_KEY}:history" 0 -101 > /dev/null
    
    # Update summary statistics
    if [ "$SUCCESS" = "true" ]; then
        redis-cli HINCRBY "${TASK_KEY}:stats" successes 1 > /dev/null
        redis-cli HINCRBYFLOAT "${TASK_KEY}:stats" total_success_time $ACTUAL_TIME > /dev/null
    else
        redis-cli HINCRBY "${TASK_KEY}:stats" failures 1 > /dev/null
    fi
    redis-cli HINCRBY "${TASK_KEY}:stats" total_runs 1 > /dev/null
    
    # Set expiry to 30 days
    redis-cli EXPIRE "${TASK_KEY}:history" 2592000 > /dev/null
    redis-cli EXPIRE "${TASK_KEY}:stats" 2592000 > /dev/null
    
    echo "✅ Recorded: ${ACTUAL_TIME}s (expected ${EXPECTED_TIME}s)"
    
elif [ "$ACTION" = "predict" ]; then
    echo "🔮 Predicting timeout for $CATEGORY:$TASK_ID"
    
    # Get recent history
    HISTORY=$(redis-cli ZREVRANGE "${TASK_KEY}:history" 0 19)
    
    if [ -z "$HISTORY" ]; then
        echo "📊 No history found, using base timeout: ${BASE_TIMEOUT}s"
        echo "RECOMMENDED_TIMEOUT=${BASE_TIMEOUT}"
        exit 0
    fi
    
    # Extract successful execution times
    SUCCESS_TIMES=$(echo "$HISTORY" | while read -r record; do
        if echo "$record" | grep -q '"success": true'; then
            echo "$record" | grep -o '"actual": [0-9.]*' | cut -d' ' -f2
        fi
    done)
    
    if [ -z "$SUCCESS_TIMES" ]; then
        # No successes, use max observed time * 2
        MAX_TIME=$(echo "$HISTORY" | grep -o '"actual": [0-9.]*' | cut -d' ' -f2 | sort -n | tail -1)
        RECOMMENDED=$(echo "scale=0; $MAX_TIME * 2" | bc)
        echo "⚠️ No successful runs, using 2x max observed: ${RECOMMENDED}s"
    else
        # Calculate 90th percentile of successful runs
        COUNT=$(echo "$SUCCESS_TIMES" | wc -l)
        P90_INDEX=$(echo "scale=0; $COUNT * 0.9" | bc | cut -d'.' -f1)
        P90_INDEX=$((P90_INDEX > 0 ? P90_INDEX : 1))
        
        P90_TIME=$(echo "$SUCCESS_TIMES" | sort -n | tail -n +$P90_INDEX | head -1)
        
        # For MCP, add generous 50% buffer to P90
        RECOMMENDED=$(echo "scale=0; $P90_TIME * 1.5" | bc)
        
        # Get statistics
        STATS=$(redis-cli HGETALL "${TASK_KEY}:stats")
        TOTAL_RUNS=$(echo "$STATS" | grep -A1 "total_runs" | tail -1)
        SUCCESSES=$(echo "$STATS" | grep -A1 "successes" | tail -1)
        SUCCESS_RATE=$(echo "scale=1; $SUCCESSES * 100 / $TOTAL_RUNS" | bc)
        
        echo "📊 History: $COUNT recent runs, ${SUCCESS_RATE}% success rate"
        echo "⏱️ P90 time: ${P90_TIME}s"
        echo "🎯 Recommended timeout: ${RECOMMENDED}s (P90 + 50% buffer)"
    fi
    
    # Never go below base timeout
    if [ "$RECOMMENDED" -lt "$BASE_TIMEOUT" ]; then
        RECOMMENDED=$BASE_TIMEOUT
    fi
    
    # For MCP, ensure minimum 5 minutes
    if [ "$RECOMMENDED" -lt "300" ]; then
        RECOMMENDED=300
    fi
    
    echo "RECOMMENDED_TIMEOUT=${RECOMMENDED}"
    
else
    echo "❌ Unknown action: $ACTION (use 'record' or 'predict')"
    exit 1
fi
```

### **Task Execution Plan & Log**

#### **Step 1: Test Recording**
*   **Goal:** Verify we can record execution times to Redis
*   **Action:** Record a sample execution
*   **Verification Command:** `redis-cli ZRANGE "cc_executor:times:simple:test:history" 0 -1`
*   **Expected Output:** JSON record with timestamp, times, and success status

**--- EXECUTION LOG (Step 1) ---**
```bash
ACTION=record TASK_ID=test CATEGORY=simple EXPECTED_TIME=30 ACTUAL_TIME=45 SUCCESS=true bash track_execution_times.sh
```

#### **Step 2: Test Prediction**
*   **Goal:** Verify timeout prediction from history
*   **Action:** Predict timeout based on recorded data
*   **Verification Command:** Check recommended timeout is appropriate
*   **Expected Output:** Recommended timeout based on P90 + buffer

**--- EXECUTION LOG (Step 2) ---**
```bash
ACTION=predict TASK_ID=test CATEGORY=simple BASE_TIMEOUT=30 bash track_execution_times.sh
```

---
## 🎓 GRADUATION & VERIFICATION

### 1. Component Integration Test
*   **Test Cases:**
    - Record multiple executions with varying times
    - Predict timeout with no history (should use base)
    - Predict timeout with failed runs (should use 2x max)
    - Predict timeout with successful runs (should use P90 + 50%)
    - Verify minimum 5-minute timeout for MCP

### 2. Self-Verification (`if __name__ == "__main__"`)
```bash
# Self-test
echo "=== Testing Execution Time Tracker ==="

# Clean test data
redis-cli DEL "cc_executor:times:test:selftest:history" > /dev/null
redis-cli DEL "cc_executor:times:test:selftest:stats" > /dev/null

# Record some executions
ACTION=record TASK_ID=selftest CATEGORY=test EXPECTED_TIME=60 ACTUAL_TIME=45 SUCCESS=true bash track_execution_times.sh
ACTION=record TASK_ID=selftest CATEGORY=test EXPECTED_TIME=60 ACTUAL_TIME=75 SUCCESS=true bash track_execution_times.sh
ACTION=record TASK_ID=selftest CATEGORY=test EXPECTED_TIME=60 ACTUAL_TIME=180 SUCCESS=false bash track_execution_times.sh
ACTION=record TASK_ID=selftest CATEGORY=test EXPECTED_TIME=60 ACTUAL_TIME=90 SUCCESS=true bash track_execution_times.sh

# Predict timeout
echo -e "\n=== Prediction Test ==="
ACTION=predict TASK_ID=selftest CATEGORY=test BASE_TIMEOUT=60 bash track_execution_times.sh

# Verify data in Redis
echo -e "\n=== Redis Verification ==="
echo "History entries:"
redis-cli ZCARD "cc_executor:times:test:selftest:history"
echo "Stats:"
redis-cli HGETALL "cc_executor:times:test:selftest:stats"

echo -e "\n✅ Self-test complete!"
```

## Notes:
- Designed for MCP long-running tasks (5-10+ minutes)
- Uses Redis sorted sets for efficient time-series data
- Calculates P90 instead of average for more reliable timeouts
- Always adds generous buffers for MCP tasks
- Minimum 5-minute timeout enforced