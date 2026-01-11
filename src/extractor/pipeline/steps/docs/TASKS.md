# Wiggum Loop Amendments - Implementation Tasks

## Overview

This document outlines the implementation tasks to add deterministic verification
to the Ralph/Wiggum loop. The amendments ensure every file Claude creates is
standalone, verifiable, and the project has a deterministic end goal.

**Core Concept**: Give the Wiggum loop an iterative update where it can safely
run code against asserts and ensure compliance with an overall deterministic contract.

---

## Design Decisions

| Decision              | Choice                         | Rationale                                |
| --------------------- | ------------------------------ | ---------------------------------------- |
| Worktree setup        | Every cycle                    | Simple, slower, reliable                 |
| Feedback injection    | Prepended                      | Claude sees failure first                |
| Multiple failures     | All at once                    | Claude fixes multiple per loop           |
| Catastrophic failure  | Exit after 3 repeated failures | Prevent infinite loops                   |
| GOAL.md timing        | Every loop                     | Prevents drift and hallucination         |
| Existing exit signals | Log but don't act              | GOAL.md is sole authority                |
| Verification scope    | `--verify` flag                | Disabled by default, backward compatible |
| Human intervention    | Existing behavior              | No special handling needed               |
| Test fixtures         | Must be committed              | Claude must `git add` fixtures           |
| Context management    | Fresh each loop                | Files are memory, not conversation       |
| Changelog             | None                           | Git is the changelog                     |

---

## Phase 1: Contract Files & Templates

### Task 1.1: Create GOAL. md Template

**File**: `templates/GOAL.md`

**Purpose**: Template for the deterministic project contract.

**Requirements**:

- [ ] Description section (what the project accomplishes)
- [ ] Test Fixtures section (required fixture files, must be committed)
- [ ] Final Assertions section (one or more bash code blocks)
- [ ] Success Criteria section (what "done" means)

**Assert**:
Command: test -f templates/GOAL.md && grep -q "Final Assertion" templates/GOAL.md
Exit: 0

---

### Task 1.2: Create CLAUDE_CONTRACT.md

**File**: `templates/CLAUDE_CONTRACT.md`

**Purpose**: Mandatory rules injected into every Claude invocation when --verify is enabled.

**Requirements**:

- [ ] File creation rules:
  - Every file must be standalone executable
  - Every file must have shebang line
  - Every file must have docstring with Purpose and Assert
  - Every file must be under ~650 lines
  - Every file must exit 0 on success, non-zero on failure
- [ ] Docstring format examples for Python, Bash, TypeScript
- [ ] How to read and work toward GOAL.md
- [ ] Test fixtures must be committed (`git add`)
- [ ] Context rule:
  - Each loop starts fresh (no conversation history)
  - Files are your memory
  - Do not reference previous conversations
  - All decisions must be captured in code or docs/DECISIONS.md
- [ ] Clarification requirement:
  - If unclear about ANY requirement → STOP and ask human
  - If unclear about what an assert should verify → STOP and ask human
  - If unclear about what a script's purpose is → STOP and ask human
  - If unclear about what a GOAL.md item means → STOP and ask human
  - Do not guess, do not assume
  - No exceptions
- [ ] Failure admission requirement:
  - If same failure occurs 3 times → must output EXIT_FAILURE
  - Format:
    ```
    EXIT_FAILURE:  true
    REASON: <specific explanation of what cannot be done>
    SUGGESTION: <what human could do to unblock>
    ```
  - Do not continue attempting after 3 identical failures
- [ ] Keep concise (Claude reads this every loop)

**Assert**:
Command: test -f templates/CLAUDE_CONTRACT.md && grep -q "ASK" templates/CLAUDE_CONTRACT.md && grep -q "EXIT_FAILURE" templates/CLAUDE_CONTRACT. md && grep -q "fresh" templates/CLAUDE_CONTRACT.md
Exit: 0

---

### Task 1.3: Update PROMPT.md Template

**File**: `templates/PROMPT.md`

**Purpose**: Add reference to contract rules.

**Requirements**:

- [ ] Add note that CLAUDE_CONTRACT.md rules apply when --verify enabled
- [ ] Add reference to GOAL.md as success criteria
- [ ] Keep project-specific content separate from contract rules

**Assert**:  
 Command: grep -q "GOAL.md" templates/PROMPT. md
Exit: 0

---

## Phase 2: Docstring Parser

### Task 2.1: Create Docstring Parser

**File**: `lib/docstring_parser.sh`

**Purpose**: Extract Assert blocks from source files.

**Requirements**:

- [ ] Detect language from file extension:
  - .py → Python (`""".. ."""`)
  - .sh, .bash → Bash (`# comments`)
  - .ts, .js → TypeScript/JavaScript (`/**... */`)
- [ ] Fallback: detect from shebang if no extension
- [ ] Extract `Purpose:  ` line
- [ ] Extract all `Assert:` blocks with:
  - `Command: ` (required)
  - `Exit:` (required)
  - `Output contains:` (optional)
  - `File exists:` (optional)
- [ ] Output format: one assertion per line
      `command|expected_exit|expected_output|expected_file`
- [ ] Return empty (exit 0) for files without Assert blocks
- [ ] Exit 1 only on parse errors

**Assert**:
Command: echo -e '#!/usr/bin/env python3\n"""Purpose: Test.\n\nAssert:\n Command: echo hi\n Exit: 0\n"""' > /tmp/test. py && bash lib/docstring_parser.sh /tmp/test.py && rm /tmp/test.py
Exit: 0
Output contains: "echo hi|0"

---

### Task 2.2: Create Parser Test Fixtures

**Files**:

- `tests/fixtures/valid_python.py`
- `tests/fixtures/valid_bash.sh`
- `tests/fixtures/valid_typescript.ts`
- `tests/fixtures/no_assertions.py`

**Purpose**: Sample files for testing parser.

**Requirements**:

- [ ] Each valid\_\* file has Purpose and Assert blocks
- [ ] Each valid\_\* file actually passes its own assertion
- [ ] no_assertions.py has no Assert block (tests that case)

**Assert**:
Command: python tests/fixtures/valid_python.py
Exit: 0

---

## Phase 3: Worktree Verification

### Task 3.1: Create Worktree Verification Script

**File**: `lib/worktree_verify.sh`

**Purpose**: Run assertions in isolated git worktree.

**Requirements**:

- [ ] Create temporary worktree from current HEAD
- [ ] Run setup (every cycle, simple and reliable):
  - If requirements. txt exists: `pip install -r requirements.txt`
  - If package.json exists: `npm install`
- [ ] Accept list of files to verify
- [ ] For each file:
  - Extract assertions using docstring_parser. sh
  - If no assertions found: FAIL with "Missing Assert block"
  - Run each assertion command with timeout (default 30s, configurable via RALPH_ASSERT_TIMEOUT)
  - Check exit code matches expected
  - Check output contains expected string (if specified)
  - Check file exists (if specified)
- [ ] Collect results (pass/fail per assertion)
- [ ] Cleanup worktree on exit (trap EXIT)
- [ ] Return 0 if all pass, 1 if any fail

**Assert**:
Command: bash lib/worktree_verify.sh tests/fixtures/valid_python.py 2>/dev/null
Exit: 0
Output contains: "PASS"

---

### Task 3.2: Create Failure Feedback Formatter

**File**: `lib/format_feedback.sh`

**Purpose**: Format assertion failures for Claude.

**Requirements**:

- [ ] Accept: file, command, expected_exit, actual_exit, stdout, stderr
- [ ] Output format:

  ```
  ## ASSERTION FAILED:  <file>

  Contract:
      Command: <command>
      Expected exit: <expected>

  Result:
      Exit: <actual>
      Stdout: <stdout>     ← only if non-empty
      Stderr: <stderr>     ← only if non-empty

  Fix this and ensure the assertion passes.
  ```

- [ ] Omit Stdout line if empty
- [ ] Omit Stderr line if empty
- [ ] Keep concise (token-efficient)

**Assert**:
Command: bash lib/format_feedback.sh "test. py" "python test.py" 0 1 "" "Error" | grep -q "ASSERTION FAILED"
Exit: 0

---

### Task 3.3: Create GOAL.md Verification Script

**File**: `lib/goal_verify.sh`

**Purpose**: Run GOAL.md final assertions.

**Requirements**:

- [ ] Parse GOAL.md for all ```bash code blocks under "Final Assertion"
- [ ] Each code block is a separate assertion
- [ ] Run each in worktree with timeout
- [ ] ALL must pass for GOAL.md to pass
- [ ] Return 0 if all pass, 1 if any fail
- [ ] Output which specific assertion failed (if any)

**Assert**:
Command: echo -e "# Test\n## Final Assertion\n\`\`\`bash\necho ok\n\`\`\`" > /tmp/test_goal.md && bash lib/goal_verify.sh /tmp/test_goal.md && rm /tmp/test_goal. md
Exit: 0

---

## Phase 4: Loop Integration

### Task 4.1: Create File Discovery Function

**File**: `lib/file_discovery.sh`

**Purpose**: Find files needing verification.

**Requirements**:

- [ ] Accept baseline commit as argument (or read from . ralph_baseline)
- [ ] Use `git diff --name-only <baseline> HEAD` to find changed files
- [ ] Filter to supported extensions: .py, .sh, .bash, .ts, .js
- [ ] Exclude patterns: tests/fixtures/_, templates/_, node_modules/\*
- [ ] Output list of files (one per line)
- [ ] If no baseline provided, use all tracked files matching extensions
- [ ] If not a git repo, find all matching files in current directory

**Assert**:
Command: bash lib/file_discovery.sh HEAD~1 2>/dev/null || echo "ok"
Exit: 0

---

### Task 4.2: Create Verification Orchestrator

**File**: `lib/verify_all.sh`

**Purpose**: Orchestrate full verification.

**Requirements**:

- [ ] Read baseline from .ralph_baseline (if exists)
- [ ] Discover files using file_discovery.sh
- [ ] For each file:
  - Check file size (fail if > 650 lines)
  - Check shebang exists (fail if missing for files with Assert blocks)
  - Run worktree_verify.sh
- [ ] Collect ALL failures (send all at once to Claude)
- [ ] If any per-file checks fail:
  - Format all failures using format_feedback.sh
  - Write to . ralph_verification_feedback
  - Return 1
- [ ] If all per-file pass and GOAL.md exists:
  - Run goal_verify.sh
  - If fails: write feedback, return 1
  - If passes: return 0
- [ ] If all per-file pass and no GOAL. md:
  - Return 0 (backward compatible)

**Assert**:
Command: bash lib/verify_all.sh --help 2>&1 | grep -q -i "usage\|verify"
Exit: 0

---

### Task 4.3: Create Failure Tracking

**File**: `lib/failure_tracker.sh`

**Purpose**: Track repeated failures for catastrophic exit detection.

**Requirements**:

- [ ] Store failure signatures in . ralph_failure_history
- [ ] Failure signature = hash of (file + assertion + error message)
- [ ] Count occurrences of each signature
- [ ] If same signature appears 3 times:
  - Set CATASTROPHIC_FAILURE flag in .ralph_catastrophic
  - Include in feedback: "This failure has occurred 3 times. You must output EXIT_FAILURE with REASON and SUGGESTION."
- [ ] Reset history on successful verification
- [ ] Reset history on loop exit

**Assert**:
Command: bash lib/failure_tracker.sh --help 2>&1 | grep -q -i "usage\|track"
Exit: 0

---

### Task 4.4: Integrate Verification into ralph_loop.sh

**File**: `ralph_loop.sh`

**Purpose**: Add --verify flag and verification after Claude execution.

**Requirements**:

- [ ] Add --verify flag (disabled by default)
- [ ] When --verify enabled and loop starts:
  - Record HEAD as baseline: `git rev-parse HEAD > .ralph_baseline`
- [ ] When --verify enabled, before each Claude invocation:
  - Start with fresh context (no conversation history)
  - Context consists of (in order):
    1. Verification feedback (if . ralph_verification_feedback exists)
    2. CLAUDE_CONTRACT. md
    3. PROMPT.md
    4. GOAL.md
    5. Changed files since baseline (from git diff)
  - Delete .ralph_verification_feedback after reading
- [ ] When --verify enabled, after each Claude execution:
  - Call verify_all.sh
  - Run GOAL.md every loop (prevents drift/hallucination)
  - Track failure using failure_tracker.sh
  - If verify_all.sh returns 0 and GOAL.md passed:
    - Log success
    - Cleanup (. ralph_baseline, .ralph_failure_history, .ralph_catastrophic)
    - Exit loop with success
  - If . ralph_catastrophic exists (3 repeated failures):
    - Check if Claude output contains "EXIT_FAILURE: true"
    - If yes: log REASON and SUGGESTION, cleanup, exit loop with failure
    - If no: force exit anyway, log "Claude failed to acknowledge catastrophic failure", show last failure to human, cleanup, exit loop with failure
  - Else: continue loop
- [ ] When --verify enabled, handle existing exit signals:
  - Log EXIT_SIGNAL but do not act on it
  - GOAL.md is sole exit authority
- [ ] When --verify disabled:
  - Existing behavior unchanged (backward compatible)

**Assert**:
Command: grep -q "\-\-verify" ralph_loop.sh && grep -q "verify_all.sh" ralph_loop.sh && grep -q "CATASTROPHIC" ralph_loop.sh && grep -q "fresh context" ralph_loop.sh
Exit: 0

---

### Task 4.5: Cleanup on Exit

**File**: `ralph_loop.sh`

**Purpose**: Clean up verification artifacts on loop exit.

**Requirements**:

- [ ] On any exit (success, failure, interrupt):
  - Remove .ralph_baseline
  - Remove .ralph_verification_feedback
  - Remove .ralph_failure_history
  - Remove .ralph_catastrophic
- [ ] Use trap EXIT for reliable cleanup

**Assert**:  
 Command: grep -q "trap" ralph_loop.sh && grep -q ". ralph_baseline" ralph_loop. sh
Exit: 0

---

## Phase 5: Setup & Installation

### Task 5.1: Update ralph-setup

**File**: `setup.sh`

**Purpose**: Include new files in project setup.

**Requirements**:

- [ ] Copy templates/GOAL.md (with placeholder prompting user)
- [ ] Copy templates/CLAUDE_CONTRACT.md
- [ ] Update setup instructions mentioning --verify flag

**Assert**:
Command: grep -q "GOAL.md" setup.sh
Exit: 0

---

### Task 5.2: Update Installation

**File**: `install.sh`

**Purpose**: Install new lib/ files.

**Requirements**:

- [ ] Copy lib/docstring_parser.sh
- [ ] Copy lib/worktree_verify.sh
- [ ] Copy lib/format_feedback.sh
- [ ] Copy lib/goal_verify.sh
- [ ] Copy lib/file_discovery.sh
- [ ] Copy lib/verify_all.sh
- [ ] Copy lib/failure_tracker.sh
- [ ] Copy templates/CLAUDE_CONTRACT.md
- [ ] Copy templates/GOAL.md

**Assert**:  
 Command: grep -q "docstring_parser" install.sh
Exit: 0

---

## Phase 6: Testing

### Task 6.1: Create Parser Tests

**File**: `tests/test_docstring_parser.bats`

**Purpose**: Test docstring extraction.

**Requirements**:

- [ ] Test Python docstring parsing
- [ ] Test Bash comment parsing
- [ ] Test TypeScript JSDoc parsing
- [ ] Test file without assertions (should return empty, exit 0)
- [ ] Test malformed file (should not crash)

**Assert**:
Command: command -v bats && bats tests/test_docstring_parser.bats
Exit: 0

---

### Task 6.2: Create Verification Tests

**File**: `tests/test_verification.bats`

**Purpose**: Test worktree verification.

**Requirements**:

- [ ] Test passing assertion
- [ ] Test failing assertion (wrong exit code)
- [ ] Test failing assertion (wrong output)
- [ ] Test timeout handling
- [ ] Test missing Assert block detection
- [ ] Test file size limit enforcement
- [ ] Test shebang requirement

**Assert**:  
 Command: command -v bats && bats tests/test_verification.bats
Exit: 0

---

### Task 6.3: Create Failure Tracking Tests

**File**: `tests/test_failure_tracker.bats`

**Purpose**: Test catastrophic failure detection.

**Requirements**:

- [ ] Test single failure (no catastrophic flag)
- [ ] Test two repeated failures (no catastrophic flag)
- [ ] Test three repeated failures (catastrophic flag set)
- [ ] Test different failures don't trigger catastrophic
- [ ] Test reset on success

**Assert**:  
 Command: command -v bats && bats tests/test_failure_tracker.bats
Exit: 0

---

### Task 6.4: Create Integration Test

**File**: `tests/test_full_loop.bats`

**Purpose**: Test complete verification flow.

**Requirements**:

- [ ] Create test project with GOAL.md
- [ ] Create passing scripts
- [ ] Run verify_all.sh, confirm success
- [ ] Create failing script
- [ ] Run verify_all.sh, confirm failure and feedback file
- [ ] Test GOAL.md runs every loop
- [ ] Test catastrophic failure triggers exit
- [ ] Test fresh context (no conversation history carried forward)

**Assert**:
Command: command -v bats && bats tests/test_full_loop.bats
Exit: 0

---

## Phase 7: Documentation

### Task 7.1: Update README. md

**File**: `README.md`

**Purpose**: Document verification features.

**Requirements**:

- [ ] Add section on --verify flag
- [ ] Add section on GOAL.md
- [ ] Add section on docstring assertions
- [ ] Add section on fresh context per loop (files are memory)
- [ ] Add section on clarification requirement (Claude must ask, not guess)
- [ ] Add section on catastrophic failure handling
- [ ] Add examples for Python, Bash, TypeScript

**Assert**:
Command: grep -q "GOAL.md" README.md && grep -q "\-\-verify" README.md
Exit: 0

---

### Task 7.2: Create VERIFICATION. md

**File**: `docs/VERIFICATION.md`

**Purpose**: Detailed verification guide.

**Requirements**:

- [ ] Explain two-level verification (per-file + GOAL.md)
- [ ] Explain worktree isolation
- [ ] Explain failure feedback loop
- [ ] Explain fresh context strategy (why conversation history is not kept)
- [ ] Explain catastrophic failure exit (3 repeated failures)
- [ ] Explain clarification requirement (Claude must ask)
- [ ] Troubleshooting section
- [ ] Examples of good GOAL.md files
- [ ] Examples of good docstring assertions
- [ ] Why git is the changelog (no CHANGELOG.md needed)

**Assert**:
Command: test -f docs/VERIFICATION.md && grep -q "fresh context" docs/VERIFICATION.md
Exit: 0

---

## Implementation Order

```
Phase 1: Contract Files (Day 1)
    1. 1 GOAL.md template
    1.2 CLAUDE_CONTRACT.md
    1.3 Update PROMPT.md

Phase 2: Docstring Parser (Day 2)
    2.1 Parser implementation
    2.2 Test fixtures

Phase 3: Worktree Verification (Days 3-4)
    3.1 Worktree verification script
    3.2 Failure feedback formatter
    3.3 GOAL.md verification

Phase 4: Loop Integration (Days 5-6)
    4.1 File discovery
    4.2 Verification orchestrator
    4.3 Failure tracking
    4.4 ralph_loop.sh integration
    4.5 Cleanup on exit

Phase 5: Setup & Installation (Day 7)
    5.1 Update setup
    5.2 Update install

Phase 6: Testing (Day 8)
    6.1 Parser tests
    6.2 Verification tests
    6.3 Failure tracking tests
    6.4 Integration test

Phase 7: Documentation (Day 9)
    7.1 README
    7.2 Verification guide
```

---

## Success Criteria

The amendments are complete when:

1. `--verify` flag exists and is disabled by default
2. Every file Claude creates has a docstring with Assert block
3. Every file runs standalone with shebang
4. Every file is under 650 lines
5. Every file is verified in isolated worktree
6. GOAL.md defines deterministic project success
7. GOAL.md runs every loop (prevents drift)
8. Loop exits ONLY when all assertions + GOAL.md pass
9. All failures sent to Claude at once (prepended to prompt)
10. Fresh context each loop (files are memory, not conversation)
11. Catastrophic failure (3 repeated identical failures) triggers forced exit
12. Claude must ask human when confused (no guessing, no exceptions)
13. Existing behavior unchanged when --verify disabled
14. All tests pass
15. Git is the changelog (no CHANGELOG. md)
