# Task List: Collaborative Calibration via Conversation

**Goal:** Human-agent collaborative preset calibration through natural conversation

**Architecture:** Claude Code conversation + tools + ArangoDB persistence

**NOT a web UI** - Agent and human collaborate in the same terminal, sharing screenshots and reasoning

---

## Questions/Blockers

None

## Design Principles

1. **Conversation IS the loop** - No managed state machine, just natural dialogue
2. **Agent shows reasoning** - "I think this is a table because..." -> human corrects
3. **Rich feedback captured** - Human explains WHY, not just yes/no
4. **State persists** - ArangoDB stores everything, survives compaction
5. **Flight check validates** - Run at end to ensure quality

## Design Decisions (Human-Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| pdf-screenshot access | Via skills-sync to `.claude/skills/` | Already configured |
| Element types | Header, Table, Figure (core 3) | Start simple, expand later |
| Pattern proposal trigger | After 5 same-type verdicts | Enough signal, not spammy |
| Verdict input | Natural language only | "correct", "that's a figure" |
| Convergence threshold | 90% accuracy overall | Across all types combined |
| Session resume | Auto-detect by PDF path | `/calibrate same.pdf` resumes |
| Flight check coverage | All 3 types required | Blocks if any type missing |

---

## Crucial Dependencies

| Dependency | Sanity Script | Status |
|------------|---------------|--------|
| pdf-screenshot skill | `.claude/skills/pdf-screenshot/sanity.sh` | Synced via skills-sync |
| Calibration modules | `src/extractor/pipeline/calibration/` | COMPLETE |
| ArangoDB | `tools/tasks_loop/sanity/arango_calibration_schema.py` | PASS |
| scillm (Stage 3) | `tools/tasks_loop/sanity/scillm_paved_path.py` | PASS |

---

## Phase 1: Skill Foundation

- [x] **Task 1**: Create `/calibrate` skill entry point
  - Location: `.claude/skills/calibrate/SKILL.md`
  - Entry command: `/calibrate <pdf_path> [--preset <id>] [--resume]`
  - Behavior:
    - Check ArangoDB for existing session -> offer resume
    - Load PDF, get page count
    - Initialize session in ArangoDB
    - Show first suggested page with detected elements
  - **Definition of Done:**
    - Test: Manual invocation with test PDF
    - Assertion: Session created in ArangoDB, first screenshot shown

- [x] **Task 2**: Create session resume logic
  - On `/calibrate --resume` or auto-detect existing session:
    - Load session state from ArangoDB
    - Show progress: "Resuming session: 45 elements reviewed, 87% accuracy"
    - Continue from where left off
  - **Definition of Done:**
    - Test: Start session, interrupt, resume with `--resume`
    - Assertion: State preserved, no duplicate reviews

- [x] **Task 3**: Create CLI wrappers for calibration modules
  - `src/extractor/cli/calibrate_cli.py`:
    - `calibrate detect <pdf> --page N` -> JSON with detected elements
    - `calibrate sample <session_id> --count N` -> suggested page numbers
    - `calibrate verdict <session_id> <element_id> <verdict> [--note "..."]`
    - `calibrate status <session_id>` -> accuracy, reviewed count, convergence
    - `calibrate finish <session_id>` -> trigger flight check
  - **Definition of Done:**
    - Test: `tests/cli/test_calibrate_cli.py`
    - Assertion: Each subcommand works standalone

---

## Phase 2: Conversational Workflow

- [x] **Task 4**: Define calibration conversation protocol in SKILL.md
  - Agent workflow:
    1. Show element with screenshot + reasoning
    2. Wait for human verdict (natural language)
    3. Parse verdict, record to ArangoDB
    4. Propose pattern if applicable
    5. Suggest next element or page
  - Human can say:
    - "correct" / "yes" / "looks good"
    - "wrong, that's a figure" / "no, it's emphasis not a header"
    - "adjust the bbox - it's cutting off the right side"
    - "skip" / "flag for later"
    - "show me page 12" / "next page" / "suggest pages"
    - "what patterns have you learned?"
    - "done" / "finish calibration"
  - **Definition of Done:**
    - Test: SKILL.md documents all interaction patterns
    - Assertion: Example dialogues cover common scenarios

- [x] **Task 5**: Implement element presentation format
  - Agent shows:
    ```
    Element 3/12 on Page 5 (Round 2)

    Type: Table (78% confidence)
    Bbox: [72, 200, 540, 400]
    Reasoning: Grid lines detected, cells with numeric content

    [screenshot with highlighted bbox]

    Is this correct? (or describe what's wrong)
    ```
  - Uses `pdf-screenshot --page 5 --highlight "72,200,540,400"`
  - **Definition of Done:**
    - Test: Element presentation includes all fields
    - Assertion: Screenshot shows with highlighted bbox

- [x] **Task 6**: Implement verdict parsing
  - Natural language -> `HumanVerdict` enum:
    - "correct", "yes", "good" -> `CORRECT`
    - "wrong type", "that's a X" -> `WRONG_TYPE` + correction
    - "not an element", "ignore", "false positive" -> `NOT_ELEMENT`
    - "split this", "two elements" -> `SPLIT`
    - "flag", "unsure", "ask expert" -> `FLAGGED`
  - Extract correction type from: "that's a figure" -> correct_type="Figure"
  - Extract notes from natural language
  - **Definition of Done:**
    - Test: `tests/calibration/test_verdict_parsing.py`
    - Assertion: Common phrasings correctly mapped

- [x] **Task 7**: Implement bbox adjustment flow
  - When human says "adjust bbox" or "too small/big":
    - Agent: "Describe the adjustment needed, or provide new coords [x0,y0,x1,y1]"
    - Human: "extend right by 50px" or "include the caption below"
    - Agent calculates new bbox, shows updated screenshot for confirmation
  - Alternative: Human provides exact coords
  - **Definition of Done:**
    - Test: Adjustment flow with relative and absolute adjustments
    - Assertion: New bbox recorded, screenshot confirms

---

## Phase 3: Pattern Learning Integration

- [x] **Task 8**: Integrate pattern proposal into conversation
  - After N verdicts on same type, agent proposes pattern:
    ```
    I've noticed a pattern for Headers in this document:
    - Font: Arial Bold, 14pt
    - Color: Blue (#0066CC)
    - Always starts with number (e.g., "3.2.1")

    Should I use this pattern? (yes/no/refine)
    ```
  - Human can refine: "Yes, but only if followed by body text"
  - **Definition of Done:**
    - Test: Pattern proposed after 5+ header verdicts
    - Assertion: Pattern includes human refinements

- [x] **Task 9**: Implement "what have you learned?" query
  - Human asks: "what patterns have you learned?" or "show patterns"
  - Agent summarizes:
    ```
    Learned patterns for boeing-spec:

    1. Headers (12 examples, 92% accuracy)
       - Arial Bold 14pt, Blue, starts with "X.Y.Z"

    2. Tables (8 examples, 87% accuracy)
       - Grid lines present, or "Table X" caption above

    3. Figures (5 examples, 100% accuracy)
       - "Figure X.Y" caption below
    ```
  - **Definition of Done:**
    - Test: Query returns formatted pattern summary
    - Assertion: Accuracy calculated from verdicts

- [x] **Task 10**: Implement Stage 3 LLM judge for edge cases
  - When confidence is low or patterns conflict:
    - Agent uses scillm to get second opinion
    - Shows both its reasoning and LLM judge reasoning
    - Human makes final call
  - Wire to: `PatternLearner.stage3_llm_judge()`
  - **Definition of Done:**
    - Test: Low-confidence element triggers LLM judge
    - Assertion: Both reasonings shown, human verdict recorded

---

## Phase 4: Flight Check

- [x] **Task 11**: Create flight check gate
  - Location: `tools/tasks_loop/gates/gate_calibration.py`
  - Input: `--session-id <id>`
  - Checks:
    1. Minimum examples (>=20)
    2. Accuracy threshold (>=90%)
    3. All element types have >=3 examples
    4. At least one pattern per type
    5. Held-out validation (20% reserved pages)
  - Output: JSON report + exit 0/1
  - **Definition of Done:**
    - Test: `tests/gates/test_gate_calibration.py`
    - Assertion: Pass/fail based on thresholds

- [x] **Task 12**: Implement "done" / "finish" command
  - Human says: "done", "finish calibration", "I'm done"
  - Agent:
    1. Runs flight check
    2. Shows results:
       ```
       Calibration Complete!

       Results:
       - Elements reviewed: 67
       - Accuracy: 94%
       - Patterns learned: 4

       Flight Check: PASS

       Preset saved to: presets/boeing-spec.yaml
       ```
    3. If FAIL, shows what's missing and offers to continue
  - **Definition of Done:**
    - Test: Full flow from start to finish
    - Assertion: Preset file generated on pass

- [x] **Task 13**: Generate preset configuration file
  - On successful flight check, generate:
    ```yaml
    # presets/boeing-spec.yaml
    preset_id: boeing-spec
    created: 2026-01-20
    calibrated_from: session_abc123

    patterns:
      headers:
        stage1_regex: "^\\d+\\.\\d+(\\.\\d+)?\\s+"
        stage2_python: |
          def match(elem):
            return elem.font_size >= 14 and elem.font_bold
        confidence_threshold: 0.85

      tables:
        detection: grid_lines OR caption_above
        merge_threshold: 0.9

      figures:
        caption_pattern: "Figure\\s+\\d+\\.\\d+"
        caption_position: below
    ```
  - **Definition of Done:**
    - Test: Preset YAML generated and valid
    - Assertion: Can be loaded by pipeline

---

## Phase 5: Testing and Integration

- [x] **Task 14**: Create test fixtures
  - `tests/fixtures/calibration/`:
    - `test_doc.pdf` - 10-page doc with known elements
    - `expected_elements.json` - ground truth
    - `sample_session.json` - pre-recorded session for testing
  - **Definition of Done:**
    - Test: Fixtures exist and are documented
    - Assertion: `README.md` describes fixture contents

- [x] **Task 15**: End-to-end integration test
  - Simulated conversation flow:
    1. Start calibration on test PDF
    2. Review 20 elements with scripted verdicts
    3. Verify patterns learned
    4. Run finish, verify flight check passes
    5. Verify preset file generated
  - **Definition of Done:**
    - Test: `tests/integration/test_calibration_e2e.py`
    - Assertion: Full flow completes programmatically

---

## Example Conversation Flow

```
Human: /calibrate pdfs/boeing-spec.pdf

Agent: Starting calibration session for boeing-spec.pdf (47 pages)
       No existing session found. Creating new session: boeing-spec_2026-01-20

       Sampling pages for diversity... Selected pages: 5, 12, 23, 31, 45

       Let's start with Page 5.

       Element 1/8 on Page 5
       Type: Header (85% confidence)
       Reasoning: Large font (16pt), bold, starts with "3.2"

       [screenshot with highlighted bbox]

       Is this correct?