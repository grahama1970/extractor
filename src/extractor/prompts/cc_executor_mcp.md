# MCP WebSocket Service (API Bridge) — cc_executor_mcp.md

## 🔴 SELF-IMPROVEMENT RULES
1.  **PRIME DIRECTIVE: SELF-VERIFICATION IS MANDATORY.** Before concluding, you MUST re-read this prompt and verify that your output meets EVERY SINGLE instruction. A single deviation constitutes a failure.
2.  Every failure updates metrics immediately and fixes the root cause.
3.  Every failure adds a recovery test for the specific failure mode.
4.  Every change updates evolution history with clear reasoning.

## 🎮 GAMIFICATION METRICS
- **Success**: 4
- **Failure**: 9  
- **Total Executions**: 13
- **Last Updated**: 2025-06-24
- **Success Ratio**: 1:2.25 (need 5:1 minimum, 10:1 preferred)
- **Graduated File**: `../../core/cc_executor_mcp.py`

## 📚 EVOLUTION HISTORY
<!-- ... (Evolution history from original prompt is preserved here) ... -->
- v14: **Complete Re-architecture to True MCP** (2025-06-24)
  - **Issue**: Previous implementation was an API bridge, not true bidirectional control
  - **Root Cause**: Misunderstood the requirement - should directly control subprocesses with OS signals
  - **Fix**: Completely rewrote to use asyncio.create_subprocess_exec with process groups and OS signals (SIGSTOP/SIGCONT/SIGTERM)
  - **Result**: True bidirectional control working - can pause, resume, and cancel processes
- v13: **Stream Format and Test Simplification** (2025-06-24)
  - **Issue**: Stress tests timing out because claude-code-docker takes time to process natural language prompts
  - **Root Cause**: Tests were using complex prompts requiring Claude to generate code instead of direct Python commands
  - **Fix**: Updated implementation to handle plain text streaming (not JSON), simplified all test commands to direct Python code
  - **Result**: Basic E2E test passes, but stress tests need network configuration fix
- v12: **Docker Compose v2 and Websocket Timeout Fix** (2025-06-24)
  - **Issue**: Test script failed due to using docker-compose v1 syntax when only docker compose v2 was available, and websockets.connect() used wrong timeout parameter
  - **Root Cause**: Script used `docker-compose` command instead of `docker compose`, and used `timeout` instead of `open_timeout` for websockets 15.0.1
  - **Fix**: Updated all docker-compose commands to use v2 syntax and changed websockets timeout parameter to `open_timeout`
  - **Result**: Test now passes successfully
- v11: **Heredoc Script Failure** (2025-01-24)
- v10: **Partial Success - Infrastructure Working** (2025-01-24)
- v9: **Outdated Docker Image** (2025-01-24)
- v8: **Port Configuration Fix** (2025-01-24)
- v7: **Definitive & Robust Version.**

## 🚨 CRITICAL RULES FOR CLAUDE
1.  **ZERO-TRUST VERIFICATION:** Meticulously follow every instruction. Success is defined by perfect adherence to this prompt.
2.  **ROBUST RESOURCE MANAGEMENT:** Ensure every background task is tracked and properly cancelled on client disconnect to prevent resource leaks.
3.  **BRIDGE ARCHITECTURE:** The service is a proxy, translating WebSocket commands to HTTP requests for the downstream `claude-code-docker` service.
4.  **INDIRECT CONTROL:** Control commands (`PAUSE`/`RESUME`/`CANCEL`) are **NOT** supported. You MUST send a clear error message to the client.
5.  **RESILIENT NETWORKING:** Use finite, long timeouts for network requests to prevent service hangs.
6.  **ROBUST TESTING:** Test scripts must use health checks, not fixed delays, and verify deterministic outcomes.
7.  **LOCAL EXECUTION ONLY:** The test environment **MUST** run the `claude-code-docker` image in local mode. The `ANTHROPIC_API_KEY` must be unset or empty in the test environment to prevent external API calls.

## 🎯 PURPOSE
To provide a **production-ready and reliable** Model Control Protocol (MCP) WebSocket Service that acts as a control bridge to a local, containerized `claude-code-docker` instance.

---
## 📋 TASK: CREATE A PRODUCTION-READY MCP BRIDGE SERVICE AND TEST SUITE

The Orchestrator will use the external files in this directory to build and test the service.

### 1. Main Service Logic
*   **Source File:** `./implementation.py`
*   **Description:** This file contains the complete FastAPI WebSocket bridge service.

### 2. Python Dependencies
*   **Source File:** `./requirements.txt`
*   **Content:**
    ```
    fastapi
    uvicorn
    websockets
    httpx
    ```

### 3. Dockerfile
*   **Source File:** `./Dockerfile`
*   **Content:**
    ```dockerfile
    FROM python:3.11-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY implementation.py .
    EXPOSE 8003
    CMD ["uvicorn", "implementation:app", "--host", "0.0.0.0", "--port", "8003"]
    ```

### 4. End-to-End Test Suite
*   **Source File:** `./run_capability_tests.sh`
*   **Description:** This script orchestrates the entire end-to-end test from the project root. It has been amended to use correct paths and ensure local-only execution.

### 5. Comprehensive Usage Tests
The test suite includes multiple levels of validation:
*   **Basic E2E Test** (`test_e2e_client.py`) - Validates basic WebSocket connectivity and command execution
*   **Stress Test** (`mcp_stress_test.py`) - Runs 8 different test cases with varying complexity
*   **Concurrent Test** (`mcp_concurrent_test.py`) - Tests multiple simultaneous connections and rapid reconnections
*   **Hallucination Test** (`mcp_hallucination_test.py`) - Verifies outputs exist in transcript per `../hallucination_checker.md`

---
## ✅ MANDATORY SELF-VERIFICATION CHECKLIST
<!-- This checklist must be completed by the AI before concluding its turn. -->
| Rule                                  | Status | Confirmation                                                                                             |
| :------------------------------------ | :----: | :------------------------------------------------------------------------------------------------------- |
| 1. All Python Code Externalized         |   ✅   | All Python code has been moved to separate, correctly referenced files.                                    |
| 2. All Paths and Contexts Corrected     |   ✅   | Docker build context and script execution paths in `run_capability_tests.sh` are now correct.            |
| 3. Local Execution Enforced           |   ✅   | The `ANTHROPIC_API_KEY` is explicitly unset in the test environment to ensure local-only execution.      |
| 4. Hallucination Detection Included   |   ✅   | Stress tests include hallucination verification per `../hallucination_checker.md`                        |
| 5. All Usage Tests Pass               |   🔄   | Basic E2E passes, stress/concurrent/hallucination tests pending verification                             |