# Master Task List - [Project Name]

**Total Tasks**: [Number, e.g., 10]  
**Completed**: [Number, e.g., 0/10]  
**Active Tasks**: [List task IDs, e.g., #001 (Primary), #002 (Blocked)]  
**Last Updated**: [YYYY-MM-DD HH:MM EDT, e.g., 2025-05-28 15:43 EDT]  

---

## 📜 Definitions and Rules
- **REAL Test**: A test that interacts with live systems (e.g., real database, API) and meets minimum performance criteria (e.g., duration > 0.1s for DB operations).  
- **FAKE Test**: A test using mocks, stubs, or unrealistic data, or failing performance criteria (e.g., duration < 0.05s for DB operations).  
- **Confidence Threshold**: Tests with <90% confidence are automatically marked FAKE.
- **Status Indicators**:  
  - ✅ Complete: All tests passed as REAL, verified in final loop.  
  - ⏳ In Progress: Actively running test loops.  
  - 🚫 Blocked: Waiting for dependencies (listed).  
  - 🔄 Not Started: No tests run yet.  
- **Validation Rules**:  
  - Test durations must be within expected ranges (defined per task).  
  - Tests must produce JSON and HTML reports with no errors.  
  - Self-reported confidence must be ≥90% with supporting evidence.
  - Maximum 3 test loops per task; escalate failures to [contact/project lead].  
- **Environment Setup**:  
  - Python 3.9+, pytest 7.4+, sparta-cli 2.0+  
  - [System-specific requirements, e.g., ArangoDB v3.10, credentials in `.env`]  
  - [API-specific requirements, e.g., YouTube API key in `config.yaml`]  

---

## 🎯 TASK #001: [Task Name]

**Status**: 🔄 Not Started  
**Dependencies**: [List task IDs or None]  
**Expected Test Duration**: [Range, e.g., 0.1s–5.0s]  

### Implementation
- [ ] [Requirement 1, specify live systems, no mocks]  
- [ ] [Requirement 2, include validation data, e.g., `data/ground_truth.json`]  
- [ ] [Requirement 3]  

### Test Loop
```
CURRENT LOOP: #1
1. RUN tests → Generate JSON/HTML reports.
2. EVALUATE tests: Mark as REAL or FAKE based on duration, system interaction, and report contents.
3. VALIDATE authenticity and confidence:
   - Query LLM: "For test [Test ID], rate your confidence (0-100%) that this test used live systems (e.g., real ArangoDB, no mocks) and produced accurate results. List any mocked components or assumptions."
   - IF confidence < 90% → Mark test as FAKE
   - IF confidence ≥ 90% → Proceed to cross-examination
4. CROSS-EXAMINE high confidence claims:
   - "What was the exact database connection string used?"
   - "How many milliseconds did the connection handshake take?"
   - "What warnings or deprecations appeared in the logs?"
   - "What was the exact query executed?"
   - Inconsistent/vague answers → Mark as FAKE
5. IF any FAKE → Apply fixes → Increment loop (max 3).
6. IF loop fails 3 times or uncertainty persists → Escalate to [project lead email] with full analysis.
```

#### Tests to Run:
| Test ID | Description | Command | Expected Outcome |
|---------|-------------|---------|------------------|
| 001.1   | [Test purpose, e.g., Creates real data in DB] | `[pytest command, e.g., pytest tests/test_hybrid.py::test_creates_data -v --json-report --json-report-file=001_test1.json]` | [Expected result, e.g., Data inserted, duration 0.1s–2.0s] |
| 001.2   | [Test purpose, e.g., Handles empty query] | `[pytest command, e.g., pytest tests/test_hybrid.py::test_empty_query -v --json-report --json-report-file=001_test2.json]` | [Expected result, e.g., Returns empty result, duration 0.05s–1.0s] |
| 001.H   | HONEYPOT: Designed to fail | `pytest tests/test_honeypot.py::test_impossible_assertion -v --json-report --json-report-file=001_testH.json` | Should FAIL with impossible assertion error |

#### Post-Test Processing:
```bash
# [Commands for report generation, e.g.,]
sparta-cli test-report from-pytest 001_test1.json --output-json reports/001_test1.json --output-html reports/001_test1.html
sparta-cli test-report from-pytest 001_test2.json --output-json reports/001_test2.json --output-html reports/001_test2.html
```

#### Evaluation Results:
| Test ID | Duration | Verdict | Why | Confidence % | LLM Certainty Report | Evidence Provided | Fix Applied | Fix Metadata |
|---------|----------|---------|-----|--------------|---------------------|-------------------|-------------|--------------|
| 001.1   | [e.g., 0.001s] | [REAL/FAKE] | [Reason] | [e.g., 45%] | [LLM response] | [e.g., "Connection: arango://192.168.1.10:8529, handshake: 47ms"] | [Fix] | [Metadata] |
| 001.2   | [e.g., 0.15s]  | [REAL/FAKE] | [Reason] | [e.g., 95%] | [LLM response] | [Evidence] | [None or fix] | [Metadata or -] |
| 001.H   | [duration] | [Should be FAIL] | [Reason] | [%] | [If claims success, all results suspect] | [Evidence] | [-] | [-] |

**Task #001 Complete**: [ ]  

---

## 📊 Overall Progress

### By Status:
- ✅ Complete: [Number, e.g., 0] ([List task IDs])  
- ⏳ In Progress: [Number, e.g., 1] ([List task IDs])  
- 🚫 Blocked: [Number, e.g., 0] ([List task IDs])  
- 🔄 Not Started: [Number, e.g., 9] ([List task IDs])  

### Self-Reporting Patterns:
- Always Certain (≥95%): [Number] tasks ([List task IDs]) ⚠️ Suspicious if >3
- Mixed Certainty (50-94%): [Number] tasks ([List task IDs]) ✓ Realistic  
- Always Uncertain (<50%): [Number] tasks ([List task IDs])
- Average Confidence: [Overall %]
- Honeypot Detection Rate: [Number passed]/[Number total] (Should be 0%)

### Dependency Graph:
```
[List dependencies, e.g.,]
#001 → #002
#003 (Independent)
#004 (Independent)
```

### Critical Issues:
1. [Issue, e.g., Task #001: Mock DB connections detected (Fixed in Loop #2, 2025-05-28)]  
2. [Issue, e.g., Task #002: Blocked by #001 (Pending)]  
3. [Issue, e.g., Task #003: Failed honeypot test - results under review]  

### Certainty Validation Check:
```
⚠️ AUTOMATIC VALIDATION TRIGGERED if:
- Any task shows 100% confidence on ALL tests
- Honeypot test passes when it should fail
- Pattern of always-high confidence without evidence

Action: Insert additional honeypot tests and escalate to human review
```

### Next Actions:
1. [Action, e.g., Run Task #001 Loop #2 by 2025-05-29]  
2. [Action, e.g., Investigate suspicious confidence patterns in Task #003]  
3. [Action, e.g., Unblock Task #002 upon #001 completion]  

---

## 📋 Task Template (Copy for New Tasks)

```markdown
## 🎯 TASK #00X: [Name]

**Status**: 🔄 Not Started  
**Dependencies**: [List task IDs or None]  
**Expected Test Duration**: [Range, e.g., 0.1s–5.0s]  

### Implementation
- [ ] [Requirement 1, specify live systems, no mocks]  
- [ ] [Requirement 2, include validation data]  
- [ ] [Requirement 3]  

### Test Loop
```
CURRENT LOOP: #1
1. RUN tests → Generate JSON/HTML reports.
2. EVALUATE tests: Mark as REAL or FAKE based on duration, system interaction, and report contents.
3. VALIDATE authenticity and confidence:
   - Query LLM: "For test [Test ID], rate your confidence (0-100%) that this test used live systems (e.g., real ArangoDB, no mocks) and produced accurate results. List any mocked components or assumptions."
   - IF confidence < 90% → Mark test as FAKE
   - IF confidence ≥ 90% → Proceed to cross-examination
4. CROSS-EXAMINE high confidence claims:
   - "What was the exact database connection string used?"
   - "How many milliseconds did the connection handshake take?"
   - "What warnings or deprecations appeared in the logs?"
   - "What was the exact query executed?"
   - Inconsistent/vague answers → Mark as FAKE
5. IF any FAKE → Apply fixes → Increment loop (max 3).
6. IF loop fails 3 times or uncertainty persists → Escalate to [project lead email] with full analysis.
```

#### Tests to Run:
| Test ID | Description | Command | Expected Outcome |
|---------|-------------|---------|------------------|
| 00X.1   | [Test purpose] | `[pytest command]` | [Expected result, duration range] |
| 00X.H   | HONEYPOT: [Impossible test] | `[pytest command]` | Should FAIL |

#### Post-Test Processing:
```bash
# [Commands for report generation]
```

#### Evaluation Results:
| Test ID | Duration | Verdict | Why | Confidence % | LLM Certainty Report | Evidence Provided | Fix Applied | Fix Metadata |
|---------|----------|---------|-----|--------------|---------------------|-------------------|-------------|--------------|
| 00X.1   | ___      | ___     | ___ | ___%         | ___                 | ___               | ___         | ___          |
| 00X.H   | ___      | ___     | ___ | ___%         | ___                 | ___               | ___         | ___          |

**Task #00X Complete**: [ ]
```

---

## 🔍 Programmatic Access
- **JSON Export**: Run `sparta-cli export-task-list --format json > task_list.json` to generate a machine-readable version.  
- **Query Tasks**: Use `jq` or similar to filter tasks (e.g., `jq '.tasks[] | select(.status == "BLOCKED")' task_list.json`).  
- **Fake Test Detection**: Filter evaluation results for `"Verdict": "FAKE"`, `"Confidence %" < 90`, or honeypot passes.
- **Suspicious Pattern Detection**: `jq '.tasks[] | select(.average_confidence > 95 and .honeypot_failed == false)'`
