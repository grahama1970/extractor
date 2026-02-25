# Task List: Iterative Preset Calibration (`doc-preset` Skill)

## Context

The current preset detection (`s00_profile_detector.py`) is a one-shot automated guess. For real-world documents (1000+ pages), this doesn't work well. We need an **iterative calibration workflow** where:

1. Agent analyzes PDF and proposes detected elements
2. Human reviews 10-15 sampled pages and provides corrections
3. Agent learns patterns from corrections (ALWAYS explains reasoning, ALWAYS confirms with human)
4. Human validates on new pages
5. Repeat until converged (95%+ accuracy or human says "good enough")
6. Save learned patterns to preset (hybrid: refines existing preset)

This is **ongoing collaboration**, not a one-off detection. Presets are ALWAYS open to refinement.

## Architecture: Skill + Library

Because preset calibration is **highly collaborative** (iterative human-agent dialogue), it's implemented as a **skill** that syncs across all IDEs:

```
┌─────────────────────────────────────────────────────────────────────┐
│               agent-skills (Canonical Source of Truth)              │
│                ~/workspace/experiments/agent-skills/skills          │
│                                                                     │
│  doc-preset/                 ← SKILL (conversation, TUI)            │
│  ├── SKILL.md               # Triggers: /doc-preset, /calibrate     │
│  ├── run.sh                 # Entry point                           │
│  ├── calibrate.py           # TUI orchestration                     │
│  └── sanity.sh              # Skill health check                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                   skills-broadcast push
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ Claude Code │      │    Codex    │      │ Antigravity │
│   /doc-preset      │  /doc-preset │     │  /doc-preset │
└─────────────┘      └─────────────┘      └─────────────┘
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              │
                    All IDEs can invoke:
                    /doc-preset start boeing.pdf --preset boeing-specs
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                extractor/pipeline/calibration/                      │
│                                                                     │
│  ← LIBRARY (PDF analysis, pattern learning, ArangoDB)               │
│  ├── schema.py              # ArangoDB collections                  │
│  ├── models.py              # Pydantic data models                  │
│  ├── detector.py            # Element detection + font metadata     │
│  ├── sampler.py             # Smart page sampling                   │
│  ├── pattern_learner.py     # 3-stage learning                      │
│  └── feedback_handler.py    # Save corrections to ArangoDB          │
└─────────────────────────────────────────────────────────────────────┘
```

**Why this split:**
- **Skill** handles conversation (TUI, session mgmt, explaining reasoning, confirming patterns)
- **Library** handles domain logic (PDF analysis, pattern learning, camelot params, ArangoDB)
- **Skill syncs to all IDEs** via `skills-broadcast push`
- **Library lives in extractor** where it integrates with pipeline steps

## Resolved Design Decisions

| Question | Decision |
|----------|----------|
| Interaction model | Mixed: form for simple, dialogue for complex. Agent decides. |
| Agent reasoning | ALWAYS explain. ALWAYS confirm learned patterns with human. |
| Document styles | Separate presets (boeing-specs, boeing-memos) or use `client` field |
| Cross-client learning | Isolated. No sharing between clients. |
| Navigation | Free navigation for both human and agent. Screenshots allowed. |
| Session persistence | Multiple sessions. Always editable. |
| Contributors | Single owner (for now). |
| Ground truth storage | **ArangoDB** (queryable, integrates with pipeline) |
| Mistake correction | Append corrective entry (don't delete). Both usable as training data. |
| Validation | Iterative human review (no holdout split). |
| False positives | "Reject" action with reason (creates negative training example) |
| Merged elements | Text-based split description, optional image confirmation |
| Disabled element types | Configurable per preset (e.g., `figures: disabled`) |
| Confidence display | Verbal + numeric (e.g., "High (92%)") |
| Uncertainty handling | Both agent and human can flag for domain expert review |
| Preset relationship | Hybrid: start from preset, calibration refines, saves back |
| New document flow | Try preset first. Calibrate only if confidence low. |
| Success threshold | 95% default, human-adjustable |
| Preset locking | Never locked. Always refinable. |

## Core Workflow

```
┌──────────────────────────────────────────────────────────────────┐
│  ROUND 1: Agent Initial Scan                                     │
│  ─────────────────────────────────────────────────────────────── │
│  Agent: "I scanned 247 pages. Here's what I found on 12 sample   │
│          pages. Please review this annotated PDF."               │
│                                                                  │
│  Human: "Page 5 table is correct. Page 12 - you missed a table.  │
│          Page 15 header is actually a caption. Here's the        │
│          expected CSV for the table on page 5."                  │
├──────────────────────────────────────────────────────────────────┤
│  ROUND 2: Agent Learns & Re-proposes                             │
│  ─────────────────────────────────────────────────────────────── │
│  Agent: "Learned 3 patterns from your feedback:                  │
│          - Headers have blue font (#003366)                      │
│          - Borderless tables need stream mode                    │
│          - Captions start with 'Figure' or 'Table'               │
│          Accuracy improved 72% → 88%. Review these 5 new pages?" │
│                                                                  │
│  Human: "Page 67 table still wrong. Try line_scale=15."          │
├──────────────────────────────────────────────────────────────────┤
│  ROUND N: Converged                                              │
│  ─────────────────────────────────────────────────────────────── │
│  Agent: "Accuracy at 96% on sampled pages. Ready to finalize?"   │
│  Human: "Yes, save this preset."                                 │
│  Agent: "Saved boeing_spec preset with 7 learned patterns."      │
└──────────────────────────────────────────────────────────────────┘
```

## Crucial Dependencies (Sanity Scripts)

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| pymupdf4llm | `to_markdown(page_chunks=True)` | `S1_pymupdf_open.py` | [x] EXISTS |
| PyMuPDF | `page.get_text("dict")` for font info | `S1_pymupdf_open.py` | [x] EXISTS |
| PyMuPDF | `page.add_rect_annot()` | None needed | N/A (well-known) |
| camelot | `read_pdf()` | `camelot_table_extraction.py` | [x] EXISTS |
| rich | TUI formatting | None needed | N/A (well-known) |
| textual | Interactive TUI | None needed | N/A (well-known) |
| rapidfuzz | Fuzzy matching | None needed | N/A (well-known) |
| python-arango | ArangoDB client | `S_arango_calibration.py` | [x] PASS |

## ArangoDB Schema

```
calibration_sessions (collection)
├── _key: "boeing-specs_2026-01-19"
├── preset_id: "boeing-specs"
├── client: "boeing"
├── pdf_path: "data/input/BHT_CV32A65X.pdf"
├── page_count: 247
├── status: "in_progress" | "converged" | "archived"
├── accuracy_history: [0.72, 0.88, 0.95]
├── created_at: timestamp
├── updated_at: timestamp
└── owner: "graham"

calibration_examples (collection)
├── _key: "boeing-specs_2026-01-19_p5_elem_3"
├── session_key: "boeing-specs_2026-01-19"
├── preset_id: "boeing-specs"
├── round: 2
├── page: 5
├── element_idx: 3
├── element_type: "table"
├── bbox: [72, 200, 540, 400]
├── agent_detection: {type: "table", confidence: 0.78, reasoning: "..."}
├── human_verdict: "correct" | "wrong_type" | "not_element" | "split" | "flagged"
├── correction: {correct_type: "figure", note: "This is a diagram"}
├── expected_output: {csv: "...", format: "inline"}
├── extraction_hint: {camelot_flavor: "lattice", line_scale: 25}
├── created_at: timestamp
└── created_by: "human" | "agent"

learned_patterns (collection)
├── _key: "boeing-specs_header_blue_font"
├── preset_id: "boeing-specs"
├── element_type: "header"
├── pattern_name: "blue_font_header"
├── stage1_regex: "^\\d+\\.\\d+\\s+[A-Z]"
├── stage2_python: "def validate(text, font): return font.color == '#003366'"
├── stage3_prompt: "Is '{text}' a section header?"
├── confidence: 0.92
├── learned_from: ["p3_elem_1", "p7_elem_0", "p12_elem_2"]
├── confirmed_by_human: true
├── created_at: timestamp
└── active: true

# Edge: example CONFIRMS pattern
calibration_confirms (edge collection)
├── _from: "calibration_examples/boeing-specs_2026-01-19_p5_elem_3"
├── _to: "learned_patterns/boeing-specs_header_blue_font"
└── relationship: "confirms" | "contradicts"
```

## Tasks

### Part A: Library Tasks (extractor/pipeline/calibration/)

- [ ] **Task 1**: Create ArangoDB sanity script and schema

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - Notes: Create sanity script for python-arango. Define collections: calibration_sessions, calibration_examples, learned_patterns, calibration_confirms (edge).
  - **Sanity**: `tools/tasks_loop/sanity/S_arango_calibration.py` (must create)
  - **Definition of Done**:
    - File: `tools/tasks_loop/sanity/S_arango_calibration.py` exists and passes
    - File: `src/extractor/pipeline/calibration/schema.py` defines ArangoDB collections
    - Test: `tests/pipeline/calibration/test_arango_schema.py::test_create_collections`
    - Assertion: Collections can be created and basic CRUD works

- [ ] **Task 2**: Create calibration session data model

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1
  - Notes: Define CalibrationSession, CalibrationExample, LearnedPattern models. Pydantic for validation, ArangoDB for persistence.
  - **Sanity**: None (uses pydantic - well-known)
  - **Definition of Done**:
    - File: `src/extractor/pipeline/calibration/models.py` exists
    - Test: `tests/pipeline/calibration/test_calibration_models.py::test_session_roundtrip`
    - Assertion: Models serialize to ArangoDB documents and back correctly

- [ ] **Task 3**: Implement smart page sampling

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 2
  - Notes: Given a PDF, select 10-15 representative pages: first/last, pages with tables, pages with figures, random middle pages. Use pymupdf4llm analysis. Allow human/agent to jump freely.
  - **Sanity**: None (uses pymupdf4llm - covered by S1)
  - **Definition of Done**:
    - File: `src/extractor/pipeline/calibration/sampler.py` exists
    - Test: `tests/pipeline/calibration/test_sampler.py::test_sample_diverse_pages`
    - Assertion: Sampler returns 10-15 pages including first, last, and pages with detected elements

- [ ] **Task 4**: Implement element detection with font/style metadata

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 2
  - Notes: Extract headers, tables, figures with bbox AND style info (font color, size, weight). Use `page.get_text("dict")` for rich metadata. Support `element_types` config to disable types.
  - **Sanity**: None (uses PyMuPDF - well-known)
  - **Definition of Done**:
    - File: `src/extractor/pipeline/calibration/detector.py` exists
    - Test: `tests/pipeline/calibration/test_detector.py::test_extract_element_styles`
    - Assertion: Detector returns elements with bbox, type, font metadata, AND respects disabled types

### Part B: Skill Tasks (agent-skills/skills/doc-preset/)

- [ ] **Task 5**: Create doc-preset skill structure and SKILL.md

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 3, Task 4
  - Notes: Create skill in agent-skills repo. SKILL.md with triggers (/doc-preset, /calibrate, "calibrate preset"). run.sh entry point. Follows extractor skill pattern.
  - **Sanity**: `sanity.sh` in skill directory
  - **Definition of Done**:
    - File: `agent-skills/skills/doc-preset/SKILL.md` exists with triggers
    - File: `agent-skills/skills/doc-preset/run.sh` exists
    - Test: `skills-broadcast push` syncs to all IDEs
    - Assertion: `/doc-preset --help` works in Claude Code

- [ ] **Task 6**: Build Rich TUI for calibration review

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 5
  - Notes: Interactive TUI using `rich` and optionally `textual`. Show detected elements with agent reasoning. Support actions: [y]es, [n]o, [x] not element, [2] split, [s]kip, [f]lag. Agent explains reasoning. Human can navigate freely.
  - **Sanity**: None (uses rich/textual - well-known)
  - **Definition of Done**:
    - File: `agent-skills/skills/doc-preset/tui.py` exists
    - Test: Manual TUI interaction test
    - Assertion: TUI displays elements with confidence, accepts feedback, shows agent reasoning

- [ ] **Task 7**: Implement human feedback handler

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 2, Task 6
  - Notes: Process TUI feedback into ArangoDB records. Support: correct, wrong_type, not_element (with reason), split (with boundary), flagged_for_review. Append-only corrections for mistakes.
  - **Sanity**: None
  - **Definition of Done**:
    - File: `src/extractor/pipeline/calibration/feedback_handler.py` exists
    - Test: `tests/pipeline/calibration/test_feedback_handler.py::test_save_correction`
    - Assertion: Feedback saves to ArangoDB, corrections append without delete

- [ ] **Task 8**: Implement 3-stage pattern learner

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 4, Task 7
  - Notes: From human corrections, learn generalizable patterns. Stage 1: wide regex. Stage 2: Python + rapidfuzz. Stage 3: headless agent call (Claude Opus 4.5 or user-specified). ALWAYS explain reasoning. ALWAYS confirm with human.
  - **Sanity**: None (pure Python + rapidfuzz)
  - **Definition of Done**:
    - File: `src/extractor/pipeline/calibration/pattern_learner.py` exists
    - Test: `tests/pipeline/calibration/test_pattern_learner.py::test_learn_header_pattern`
    - Assertion: Given 3+ examples, learner outputs 3-stage pattern with explanation

- [ ] **Task 9**: Wire skill to library (run.sh orchestration)

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 5, Task 6, Task 7, Task 8
  - Notes: run.sh in skill calls extractor's calibration modules. Support subcommands: start, continue, finalize, review. Multi-session support.
  - **Sanity**: None
  - **Definition of Done**:
    - File: `agent-skills/skills/doc-preset/run.sh` orchestrates full flow
    - Test: `/doc-preset start test.pdf --preset test` launches TUI
    - Assertion: Skill calls extractor library, saves to ArangoDB

### Part C: Pipeline Integration Tasks (extractor)

- [ ] **Task 10**: Integrate with s00_profile_detector

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 9
  - Notes: When document comes in: try preset first, if confidence < threshold, flag for calibration. Use learned patterns from ArangoDB when available.
  - **Sanity**: None
  - **Definition of Done**:
    - Test: `tests/pipeline/test_profile_detector_calibrated.py::test_uses_calibrated_patterns`
    - Assertion: s00 uses learned patterns, flags low-confidence docs

- [ ] **Task 11**: Integrate with s05_table_extractor

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 9
  - Notes: When calibrated camelot params exist (per-pattern or per-page), use them. Support line_scale, flavor (lattice/stream), edge_tol.
  - **Sanity**: None
  - **Definition of Done**:
    - Test: `tests/pipeline/test_table_extractor_calibrated.py::test_uses_calibrated_params`
    - Assertion: s05 uses learned camelot params from calibration

## Completion Criteria

- **Skill deployed**: `/doc-preset` works in Claude Code, Codex, Antigravity via `skills-broadcast`
- **TUI works**: Rich TUI allows human to review elements, provide feedback, navigate freely
- **Collaboration**: Agent ALWAYS explains reasoning, ALWAYS confirms learned patterns with human
- **Persistence**: Feedback persists to ArangoDB (append-only corrections)
- **3-stage learning**: regex → Python/rapidfuzz → LLM fallback (user-configurable model)
- **Pipeline integration**: s00 uses learned patterns, s05 uses calibrated camelot params
- **Low-confidence flagging**: Documents that don't match preset flagged for human review
- **Multi-session**: Human can pause and resume calibration across days
- **End-to-end**: human skims 10-15 pages, agent extracts 1000+ pages at 95%+ accuracy
- **Always refinable**: Presets never locked, always open for refinement

## Example Session

```bash
# Human has a new 500-page Boeing spec - invoke via skill
# Works in Claude Code, Codex, or Antigravity

# Option 1: Slash command
/doc-preset start boeing_new.pdf --preset boeing-specs

# Option 2: Natural language trigger
"calibrate preset for boeing_new.pdf"

# Option 3: Direct script
~/workspace/experiments/agent-skills/skills/doc-preset/run.sh start boeing_new.pdf --preset boeing-specs

┌─────────────────────────────────────────────────────────────────┐
│  CALIBRATION SESSION: boeing-specs              Starting...     │
├─────────────────────────────────────────────────────────────────┤
│  Analyzing 500 pages with pymupdf4llm...                        │
│  ████████████████████████████████████████ 100%                  │
│                                                                 │
│  Detected: 45 tables, 230 headers, 0 figures                    │
│  Selected 12 pages for review: [1, 3, 8, 15, 45, 89, ...]       │
│                                                                 │
│  Press [Enter] to begin review, [q] to quit                     │
└─────────────────────────────────────────────────────────────────┘

# Human presses Enter, enters TUI review mode

┌─────────────────────────────────────────────────────────────────┐
│  CALIBRATION: boeing-specs                       Round 1 | 1/12 │
├─────────────────────────────────────────────────────────────────┤
│  Page 3 of 500                                                  │
│  ───────────────────────────────────────────────────────────────│
│                                                                 │
│  [1] HEADER  "3.1 Functional Requirements"        High (92%)    │
│      Reasoning: Font Arial 12pt Bold, color #003366,            │
│                 starts with decimal number, follows TOC pattern │
│      ┌─ [y] correct  [n] wrong type  [x] not element  [s] skip  │
│                                                                 │
│  [2] TABLE   6 rows × 4 columns                   Medium (78%)  │
│      Reasoning: Detected grid structure, has borders,           │
│                 column headers in first row                     │
│      Preview:                                                   │
│      ┌────────────────────────────────────────┐                 │
│      │ Parameter │ Value │ Unit │ Notes      │                 │
│      │ Voltage   │ 3.3   │ V    │ Nominal    │                 │
│      └────────────────────────────────────────┘                 │
│      ┌─ [y] correct  [n] wrong  [e] expected CSV  [h] hint      │
│                                                                 │
│  [a]dd missed element  [?] help  [n]ext page  [p]rev  [q]uit    │
├─────────────────────────────────────────────────────────────────┤
│  Progress: █░░░░░░░░░░░ 1/12 pages | Accuracy: --% (need data)  │
└─────────────────────────────────────────────────────────────────┘

# Human provides feedback via keypresses
# After reviewing 12 pages, agent shows learned patterns:

┌─────────────────────────────────────────────────────────────────┐
│  PATTERN LEARNING                                Round 1 Done   │
├─────────────────────────────────────────────────────────────────┤
│  From your 12 pages of feedback, I learned these patterns:      │
│                                                                 │
│  [1] HEADERS (confidence: 0.95)                                 │
│      Stage 1 regex: ^\d+(\.\d+)*\s+[A-Z]                        │
│      Stage 2 rule: font.color == '#003366' AND font.size >= 11  │
│      Learned from: pages 3, 8, 15, 45 (4 examples)              │
│      ┌─ [y] accept  [n] reject  [e] edit                        │
│                                                                 │
│  [2] BORDERED TABLES (confidence: 0.88)                         │
│      Camelot: flavor=lattice, line_scale=25                     │
│      Learned from: pages 3, 15, 89 (3 examples)                 │
│      ┌─ [y] accept  [n] reject  [e] edit                        │
│                                                                 │
│  [f]inalize  [c]ontinue to round 2  [q]uit and save progress    │
└─────────────────────────────────────────────────────────────────┘

# Human confirms patterns, continues to round 2 with new pages
# After 2-3 rounds, accuracy reaches 95%+

┌─────────────────────────────────────────────────────────────────┐
│  CALIBRATION COMPLETE                            Ready to Save  │
├─────────────────────────────────────────────────────────────────┤
│  Accuracy: 96% (46/48 elements correct)                         │
│  Rounds: 3                                                      │
│  Pages reviewed: 24                                             │
│  Patterns learned: 5                                            │
│                                                                 │
│  This preset will now be used for future boeing-specs documents │
│  You can always refine it later with: calibrate continue        │
│                                                                 │
│  [f]inalize and save  [c]ontinue refining  [q]uit               │
└─────────────────────────────────────────────────────────────────┘

$ python -m extractor.calibrate finalize --session boeing-specs_2026-01-19

Agent: Saved to ArangoDB: 5 patterns, 48 examples
Agent: Updated preset: boeing-specs (hybrid refinement)
Agent: Future documents will use these calibrated patterns
```

## Preset Lifecycle

Clients (Boeing, arXiv authors, etc.) follow their document style 95% of the time. The calibration workflow respects this:

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: Initial Calibration (Intensive)                       │
│  ───────────────────────────────────────────────────────────────│
│  • First document of this type                                  │
│  • 3-5 rounds of agent-human dialogue                           │
│  • Learn the client's consistent style patterns                 │
│  • Result: Solid preset covering 95% of cases                   │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 2: Steady State (Low Touch)                              │
│  ───────────────────────────────────────────────────────────────│
│  • Preset works well for most documents                         │
│  • Agent runs with confidence, human rarely involved            │
│  • Occasional spot-checks on random samples                     │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 3: Edge Case Flagging (As Needed)                        │
│  ───────────────────────────────────────────────────────────────│
│  • Agent detects document that doesn't match well               │
│  • Confidence score drops below threshold                       │
│  • Agent flags for human review: "This doc looks different"     │
│  • Human decides: tweak preset OR create new preset             │
└─────────────────────────────────────────────────────────────────┘
```

### Confidence-Based Flagging

When processing a new document, agent should:

```python
def should_flag_for_review(doc_profile: dict, preset: dict) -> bool:
    """Flag documents that don't match the preset well."""
    match_score = compute_preset_match(doc_profile, preset)

    if match_score < 0.7:
        return True  # "This doc looks different from usual"

    # Check for anomalies
    if doc_profile["table_count"] > preset["typical_tables"] * 2:
        return True  # "Unusually many tables"

    return False
```

This means:
- **High confidence docs** → Run pipeline automatically
- **Low confidence docs** → Pause and ask human: "This looks different. Review?"

## Design Decisions (Resolved)

### 1. Review Medium: Rich TUI

**Decision**: Use a rich textual TUI (Terminal UI) instead of annotated PDF.

```
┌─────────────────────────────────────────────────────────────────┐
│  CALIBRATION SESSION: boeing_spec                    Round 1/3  │
├─────────────────────────────────────────────────────────────────┤
│  Page 5 of 247                                      [←] [→]     │
│  ───────────────────────────────────────────────────────────────│
│                                                                 │
│  DETECTED ELEMENTS:                                             │
│                                                                 │
│  [1] HEADER  "3.1 Functional Requirements"                      │
│      Font: Arial 12pt Bold, Color: #003366                      │
│      ┌─ Is this correct? [y/n/s(kip)]                           │
│                                                                 │
│  [2] TABLE   6 rows × 4 columns                                 │
│      ┌────────────────────────────────────────┐                 │
│      │ Parameter │ Value │ Unit │ Notes      │                 │
│      │───────────│───────│──────│────────────│                 │
│      │ Voltage   │ 3.3   │ V    │ Nominal    │                 │
│      │ Current   │ 100   │ mA   │ Max        │                 │
│      └────────────────────────────────────────┘                 │
│      ┌─ Is this correct? [y/n/e(xpected csv)/h(int)]            │
│                                                                 │
│  [3] FIGURE  "Figure 2: System Block Diagram"                   │
│      ┌─ Is this correct? [y/n/s(kip)]                           │
│                                                                 │
│  MISSED ELEMENTS? [a]dd new element                             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Progress: ████████░░░░░░░░ 5/12 pages reviewed                 │
│  Accuracy: 78% (14/18 correct)                                  │
│  [q]uit  [f]inalize  [n]ext page  [p]rev page  [?]help          │
└─────────────────────────────────────────────────────────────────┘
```

**Libraries**: `rich` for formatting, `textual` for interactivity (optional).

### 2. Feedback Granularity: Page-Level

**Decision**: Human provides page-level corrections, not precise bbox.

- Human says: "Element 2 on page 5 is wrong" or "Page 5 is missing a table"
- Agent handles the bbox detection/refinement
- Faster for human, more scalable

### 3. Pattern Format: Multi-Stage Pipeline

**Decision**: Three-stage pattern matching:

```
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: Wide Net Regex (Fast)                                 │
│  ───────────────────────────────────────────────────────────────│
│  • Captures candidates broadly                                  │
│  • Example: r"^\d+\.\d+\s+[A-Z]" for section headers            │
│  • High recall, lower precision                                 │
├─────────────────────────────────────────────────────────────────┤
│  STAGE 2: Python + RapidFuzz (Medium)                           │
│  ───────────────────────────────────────────────────────────────│
│  • Fuzzy matching for variations                                │
│  • Font/style validation                                        │
│  • Example: rapidfuzz.fuzz.ratio(text, "Requirements") > 85     │
│  • Filters false positives from Stage 1                         │
├─────────────────────────────────────────────────────────────────┤
│  STAGE 3: Headless Agent Call (Slow, Expensive)                 │
│  ───────────────────────────────────────────────────────────────│
│  • Only for ambiguous cases Stage 2 can't resolve               │
│  • Uses Claude Code Opus 4.5 (or user-specified model)          │
│  • Example: "Is this text a section header or a caption?"       │
│  • Highest accuracy, use sparingly                              │
└─────────────────────────────────────────────────────────────────┘
```

**Pattern Definition Format**:

```yaml
# calibration_rules.yml
patterns:
  headers:
    - name: "section_header_decimal"
      stage1_regex: "^\\d+(\\.\\d+)*\\s+[A-Z]"
      stage2_python: |
        def validate(text, font_info):
            if font_info.get("size", 0) < 10:
                return False
            if font_info.get("color") != "#003366":
                return False
            return True
      stage3_prompt: "Is '{text}' a section header or something else?"
      confidence_threshold: 0.8  # Skip stage 3 if stage 2 confidence > 0.8

  tables:
    - name: "bordered_table"
      stage1_regex: null  # Tables detected by structure, not regex
      stage2_python: |
        def validate(table_data, page_context):
            if table_data.get("has_borders"):
                return {"flavor": "lattice", "line_scale": 25}
            return None
      camelot_params:
        flavor: lattice
        line_scale: 25

    - name: "borderless_table"
      stage2_python: |
        def validate(table_data, page_context):
            if not table_data.get("has_borders") and table_data.get("row_count", 0) > 2:
                return {"flavor": "stream", "edge_tol": 50}
            return None
      camelot_params:
        flavor: stream
        edge_tol: 50
```

## Questions/Blockers

None

All design questions were resolved in the collaborative design phase above.
