# Task List: Calibration UI Extension

> **⚠️ DEFERRED**: The conversation-based TUI approach (`02_TASKS_CALIBRATION_COLLAB.md`) is complete and sufficient.
> This web UI extension is deferred until there's a clear need for multi-user or remote calibration scenarios.
> All 15 core calibration tasks are implemented via the `/calibrate` skill.

**Goal:** Extend `prototypes/tabbed` with calibration workflow for human-in-the-loop preset tuning

**Architecture:** Web UI (React) + FastAPI backend + existing calibration modules

**NOT a conversation loop** - Human interacts directly with web UI, flight check runs on "Finish"

---

## Questions/Blockers

- None

---

## Crucial Dependencies

| Dependency | Sanity Script | Status |
|------------|---------------|--------|
| Existing tabbed UI | `prototypes/tabbed/STATUS.md` | WORKING |
| Calibration modules | `src/extractor/pipeline/calibration/` | COMPLETE |
| ArangoDB | `tools/tasks_loop/sanity/arango_calibration_schema.py` | PASS |
| PyMuPDF | `tools/tasks_loop/sanity/fitz_font_extraction.py` | PASS |

---

## Phase 1: API Endpoints (Backend)

- [ ] **Task 1**: Add calibration session endpoints to `api/server.py`
  - `POST /api/calibration/session` - Create/resume session
  - `GET /api/calibration/session/{id}` - Get session state
  - `POST /api/calibration/session/{id}/finish` - Mark session done
  - Wire to: `CalibrationSchema`, `CalibrationSession`, `FeedbackHandler`
  - **Definition of Done:**
    - Test: `tests/api/test_calibration_endpoints.py::test_session_crud`
    - Assertion: POST returns `{"ok": true, "session_id": "..."}`, GET returns session with status

- [ ] **Task 2**: Add element detection endpoint
  - `POST /api/calibration/detect` - Detect elements on page(s)
  - Input: `{pdf_path, pages: [1,2,3]}`
  - Output: `{elements: [{page, bbox, type, confidence, font_info}]}`
  - Wire to: `ElementDetector`, `detect_elements()`
  - **Definition of Done:**
    - Test: `tests/api/test_calibration_endpoints.py::test_detect_elements`
    - Assertion: Returns elements with bbox in 0-1 normalized coords

- [ ] **Task 3**: Add verdict submission endpoint
  - `POST /api/calibration/verdict` - Submit human verdict
  - Input: `{session_id, element_id, verdict, correction?}`
  - Wire to: `FeedbackHandler.record_verdict()`
  - Trigger pattern learning after N verdicts
  - **Definition of Done:**
    - Test: `tests/api/test_calibration_endpoints.py::test_submit_verdict`
    - Assertion: Verdict persisted to ArangoDB, accuracy updated

- [ ] **Task 4**: Add sampling endpoint
  - `GET /api/calibration/suggest-pages` - Get next pages to review
  - Input: `{session_id, count: 3}`
  - Output: `{pages: [5, 12, 23], reason: "diversity sampling"}`
  - Wire to: `PageSampler`, `sample_pages()`
  - **Definition of Done:**
    - Test: `tests/api/test_calibration_endpoints.py::test_suggest_pages`
    - Assertion: Returns page numbers sorted by priority

- [ ] **Task 5**: Add convergence check endpoint
  - `GET /api/calibration/convergence` - Get current accuracy + convergence status
  - Output: `{accuracy: 0.87, converged: false, rounds: 3, examples_reviewed: 45}`
  - **Definition of Done:**
    - Test: `tests/api/test_calibration_endpoints.py::test_convergence`
    - Assertion: Accuracy calculated from verdicts, converged=true when >=0.95

---

## Phase 2: UI Components (Frontend)

- [ ] **Task 6**: Add verdict buttons to Inspector panel
  - Location: `html/src/pages/ClassicLayout.tsx` Inspector section
  - Buttons: ✅ Correct | ❌ Wrong Type | 🚫 Not Element | ✂️ Split | 🔧 Adjust
  - "Wrong Type" shows dropdown for correct type
  - "Adjust" enables bbox resize mode
  - **Definition of Done:**
    - Test: `scripts/smokes/calibration_verdict_buttons.mjs`
    - Assertion: Click verdict → POST to `/api/calibration/verdict`, element marked reviewed

- [ ] **Task 7**: Add "Calibration Mode" toggle
  - Header toggle: Normal Annotation ↔ Calibration Mode
  - In calibration mode:
    - Auto-detect elements on page load
    - Show confidence scores on boxes
    - Enable verdict buttons
  - **Definition of Done:**
    - Test: `scripts/smokes/calibration_mode_toggle.mjs`
    - Assertion: Toggle persists to localStorage, mode changes UI behavior

- [ ] **Task 8**: Add convergence progress bar
  - Location: Header or Inspector top
  - Shows: `Accuracy: 87% | Reviewed: 45/120 | Round 3`
  - Color: red (<70%), yellow (70-90%), green (>90%)
  - **Definition of Done:**
    - Test: `scripts/smokes/calibration_convergence_ui.mjs`
    - Assertion: Progress bar updates after each verdict

- [ ] **Task 9**: Add "Suggest Pages" button
  - Location: Pager area
  - Click → calls `/api/calibration/suggest-pages`
  - Highlights suggested pages in thumbnail rail
  - **Definition of Done:**
    - Test: `scripts/smokes/calibration_suggest_pages.mjs`
    - Assertion: Suggested pages highlighted, click jumps to page

- [ ] **Task 10**: Add "Finish Calibration" button
  - Location: Header (visible in calibration mode)
  - Disabled until converged OR user confirms early finish
  - Click → runs flight check → shows results modal
  - **Definition of Done:**
    - Test: `scripts/smokes/calibration_finish.mjs`
    - Assertion: Button triggers flight check, modal shows pass/fail

---

## Phase 3: Flight Check Gate

- [ ] **Task 11**: Create flight check gate script
  - Location: `tools/tasks_loop/gates/gate_calibration.py`
  - Input: `--session-id <id>` or `--preset-id <id>`
  - Checks:
    1. Minimum examples reviewed (≥20)
    2. Accuracy threshold (≥90%)
    3. All element types covered
    4. Patterns generated for each type
  - Output: JSON report with pass/fail + metrics
  - Exit: 0 = PASS, 1 = FAIL
  - **Definition of Done:**
    - Test: `tests/gates/test_gate_calibration.py`
    - Assertion: Gate passes with good session, fails with insufficient data

- [ ] **Task 12**: Add held-out validation to flight check
  - Reserve 20% of pages as held-out
  - Run learned patterns on held-out pages
  - Compare to human verdicts
  - Report precision/recall per element type
  - **Definition of Done:**
    - Test: `tests/gates/test_gate_calibration.py::test_held_out_validation`
    - Assertion: Precision/recall reported, matches expected for test fixtures

- [ ] **Task 13**: Wire flight check to UI "Finish" button
  - POST `/api/calibration/session/{id}/finish`
  - Backend runs `gate_calibration.py`
  - Returns results to UI
  - UI shows modal with pass/fail + download preset config
  - **Definition of Done:**
    - Test: `scripts/smokes/calibration_flight_check_e2e.mjs`
    - Assertion: Full flow from verdict → finish → gate → results modal

---

## Phase 4: Integration

- [ ] **Task 14**: Create test fixtures for calibration flow
  - PDF with known elements (headers, tables, figures)
  - Pre-recorded verdicts JSON
  - Expected patterns output
  - **Definition of Done:**
    - Test: `tests/fixtures/calibration/README.md` exists
    - Assertion: Fixture PDF + verdicts + expected output checked in

- [ ] **Task 15**: End-to-end smoke test
  - Start UI server
  - Open PDF
  - Toggle calibration mode
  - Auto-detect elements
  - Submit 10 verdicts
  - Check convergence updates
  - Click Finish (or force)
  - Verify gate output
  - **Definition of Done:**
    - Test: `scripts/smokes/calibration_e2e.mjs`
    - Assertion: Full flow completes without error

---

## Summary

| Phase | Tasks | Purpose |
|-------|-------|---------|
| 1. API | 1-5 | Backend endpoints wiring calibration modules |
| 2. UI | 6-10 | Frontend verdict buttons + convergence + finish |
| 3. Gate | 11-13 | Flight check for quality assurance |
| 4. Integration | 14-15 | Fixtures + E2E smoke test |

**Total: 15 tasks** (down from 19 in conversation-based approach)

**Key difference:** Human uses web UI directly, no nested conversation loop.
