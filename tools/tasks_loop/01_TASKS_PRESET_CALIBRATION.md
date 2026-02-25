# Task List: Extraction Preset Calibration Skill

> **⚠️ SUPERSEDED**: This task file has been replaced by `02_TASKS_CALIBRATION_COLLAB.md` (v2).
> The conversation-based approach is complete with all 15 tasks implemented and tested.
> This file is retained for reference - advanced features (dirty twins, cross-format parity) may be revisited later.

> Generated: 2026-01-20
> Skill: `/extraction-preset`
> Quality Gate: Enabled via preflight.sh

## Context

Replace the blocking TUI loop in `tools/contract_loop/clarify/` with a conversational workflow that:
1. Uses **one-element-at-a-time feedback** with progress indicators (Antigravity-style)
2. **Auto-resumes unfinished sessions** for the same document
3. Implements the **3-stage pattern learning** (regex → Python → scillm LLM)
4. Creates **synthetic "dirty twin" fixtures** for automated testing
5. Supports **both accuracy AND improvement testing** for preset efficacy

Key design decisions (from collaboration):
- **Entry**: User invokes `/extraction-preset path/to/doc.pdf`, agent confirms, batch mode auto-creates session with log
- **Feedback**: One element at a time with `[3/12 tables]` progress indicator
- **Session**: ArangoDB persistence, auto-resume if doc_hash matches incomplete session
- **scillm**: ONLY use scillm paved path (no bespoke wrappers)
- **Efficacy**: Both (a) compare to ground truth AND (b) compare old vs new preset

---

## Crucial Dependencies (Sanity Scripts)

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| fitz (PyMuPDF) | `page.get_text("dict")` | `tools/tasks_loop/sanity/fitz_font_extraction.py` | [x] PASS |
| pymupdf4llm | `to_markdown()` | `tools/tasks_loop/sanity/pymupdf4llm_markdown.py` | [x] PASS |
| scillm | `parallel_acompletions_iter` | `tools/tasks_loop/sanity/scillm_paved_path.py` | [x] PASS |
| ArangoDB | calibration collections | `tools/tasks_loop/sanity/arango_calibration_schema.py` | [x] PASS |
| fixture gen | multi-format output | `tools/tasks_loop/sanity/fixture_generation.py` | [x] PASS |
| pdf-screenshot | `/pdf-screenshot` skill | pi-mono skill sanity.sh | [x] PASS |

> Run all: `for f in tools/tasks_loop/sanity/*.py; do python "$f"; done`

---

## Tasks

### Phase 1: Foundation (Session Management)

- [x] **Task 1**: Implement session auto-resume logic

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - Notes: When user invokes `/extraction-preset doc.pdf`, check ArangoDB for existing session with matching doc_hash. If incomplete session exists, offer to resume.
  - **Sanity**: `tools/tasks_loop/sanity/arango_calibration_schema.py` (must pass first)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_session_resume.py::test_resume_incomplete_session`
    - Assertion:
      ```python
      # 1. Create session with doc_hash="abc123", status="labeling", completed_elements=5
      # 2. Call get_or_create_session(doc_hash="abc123")
      # 3. Assert: returns SAME session._key (not new session)
      # 4. Assert: session.completed_elements == 5
      # 5. Assert: session.status == "labeling"
      ```

- [ ] **Task 2**: Create session state machine

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1
  - Notes: States: `new → sampling → labeling → learning → validating → complete`. Store state transitions in ArangoDB with timestamps.
  - **Sanity**: None (uses standard Python dataclasses + arango)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_session_resume.py::test_state_transitions`
    - Assertion:
      ```python
      # 1. Create session in "new" state
      # 2. Call session.transition_to("sampling") - should succeed
      # 3. Call session.transition_to("labeling") - should succeed
      # 4. Call session.transition_to("complete") - should RAISE StateTransitionError
      # 5. Assert: session.transitions list has timestamps for each transition
      # 6. Assert: len(session.transitions) == 2
      ```

### Phase 2: Page Sampling

- [ ] **Task 3**: Implement smart page sampler

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 2
  - Notes: Extends existing `sampler.py`. Prioritize: first/last, tables, figures, random middle. Human/agent can add "difficult" pages (many tables, strange figures, formatting errors).
  - **Sanity**: `tools/tasks_loop/sanity/fitz_font_extraction.py` (must pass first)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_sampler.py::test_sample_diverse_pages` (EXISTS)
    - Assertion:
      ```python
      # EXISTING TEST - verifies:
      # 1. len(result.pages) >= 10 and <= 15
      # 2. 0 in page_nums (first page included)
      # 3. 99 in page_nums (last page included)
      # 4. all(isinstance(p, PageInfo) for p in result.pages)
      # 5. result.total_pages == 100
      ```

- [ ] **Task 4**: Add agent/human page selection endpoint

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 3
  - Notes: Allow adding specific pages to sample: `calibrator.add_page(page_num=42, reason="complex table layout")`. Store in session. Use `/pdf-screenshot doc.pdf --page 42` to show human the page for review.
  - **Sanity**: None (standard REST/function call)
  - **Visual Feedback**: `/pdf-screenshot --page N` (full page preview for human review)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_sampler.py::test_add_difficult_page` (NEW)
    - Assertion:
      ```python
      # 1. sampler.add_page(page_num=42, reason="complex table layout")
      # 2. Assert: 42 in sampler.selected_pages
      # 3. Assert: sampler.page_reasons[42] == "complex table layout"
      # 4. Assert: page persists in session after save/reload
      ```

### Phase 3: Element Detection & Labeling

- [ ] **Task 5**: Implement element detector with font metadata

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 3
  - Notes: Extends existing `detector.py`. Extract font name, size, bold/italic for each text span. Group into potential elements (headers, paragraphs, list items).
  - **Sanity**: `tools/tasks_loop/sanity/fitz_font_extraction.py` (must pass first)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_detector.py::test_extract_element_styles` (EXISTS)
    - Assertion:
      ```python
      # EXISTING TEST - verifies:
      # 1. len(elements) > 0
      # 2. all isinstance(elem, DetectedElement)
      # 3. elem.element_type in ["header", "table", "figure"]
      # 4. len(elem.bbox) == 4
      # 5. 0 <= elem.confidence <= 1
      # 6. elem.reasoning is not empty
      ```

- [ ] **Task 6**: Create one-at-a-time labeling workflow

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 5
  - Notes: Present elements sequentially with progress `[3/12 tables]`. Agent shows element preview using `/pdf-screenshot`, asks user to confirm/correct type. Store corrections in `calibration_examples`. **IMPORTANT**: Also show agent's reasoning and confidence to human (HITL best practice: consent and clarity mid-task).
  - **Sanity**: None (standard workflow)
  - **Visual Feedback**:
    - `/pdf-screenshot doc.pdf --page N --highlight "x0,y0,x1,y1"` (full page with element highlighted)
    - `/pdf-screenshot doc.pdf --page N --bbox "x0,y0,x1,y1"` (cropped to element for detail)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_labeling.py::test_one_at_a_time_flow` (NEW)
    - Assertion:
      ```python
      # 1. Create workflow with 12 elements
      # 2. Call workflow.label_element(elem_id, "header") 3 times
      # 3. Assert: workflow.progress == (3, 12)
      # 4. Assert: workflow.progress_display == "[3/12 elements]"
      # 5. Query calibration_examples: len(list(examples)) == 3
      # 6. Assert: each example has session_id, element_type, bbox
      # 7. Assert: workflow displays agent confidence and reasoning to human
      ```

- [ ] **Task 6a**: Add extraction preview to labeling - CRITICAL

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6
  - Notes: **Gap identified in assessment**: Human sees screenshot but not what agent EXTRACTED. For headers: show extracted text. For tables: show CSV preview. For figures: show OCR text. Without this, human may approve "correct" detection with garbage extraction.
  - **Sanity**: None (uses existing extractors)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_labeling.py::test_extraction_preview` (NEW)
    - Assertion:
      ```python
      # 1. workflow.present_element(table_element)
      # 2. Assert: workflow.current_preview has "screenshot_path"
      # 3. Assert: workflow.current_preview has "extracted_content"
      # 4. Assert: for table, extracted_content has "csv" or "rows"
      # 5. Assert: for header, extracted_content has "text"
      # 6. Human can compare screenshot vs extracted content
      ```

- [ ] **Task 6b**: Add bbox adjustment verdict - CRITICAL

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6
  - Notes: **Gap identified in assessment**: Human can say "wrong" but can't FIX partial errors. Add new verdict: `adjust_bbox` with corrected coordinates. Example: Agent detects table but bbox clips the last row - human adjusts bbox without rejecting whole detection.
  - **Sanity**: None (extends existing feedback_handler)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_labeling.py::test_adjust_bbox_verdict` (NEW)
    - Assertion:
      ```python
      # 1. handler.save_bbox_adjustment(
      #      ..., original_bbox=[72,200,540,380],
      #      corrected_bbox=[72,195,545,400],
      #      note="Table extended to include footer row"
      #    )
      # 2. Assert: example.human_verdict == "adjust_bbox"
      # 3. Assert: example.correction.corrected_bbox == [72,195,545,400]
      # 4. Assert: bbox adjustment persists and is used for pattern learning
      ```

- [ ] **Task 6c**: Add batch review mode

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6a, Task 6b
  - Notes: **HITL best practice**: Avoid fatigue by simplifying tasks. For documents with 50+ elements, one-at-a-time is tedious. Add optional batch mode: show grid of thumbnails, bulk approve obvious ones, focus review on ambiguous ones. Based on research: "Leverage automated pre-screening to reduce workload."
  - **Sanity**: None (workflow enhancement)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_labeling.py::test_batch_review_mode` (NEW)
    - Assertion:
      ```python
      # 1. workflow.enable_batch_mode()
      # 2. workflow.present_batch(element_type="table")  # Show all tables
      # 3. Assert: returns list of (element_id, thumbnail_path) tuples
      # 4. workflow.bulk_approve([1,2,4,7,8])  # Approve multiple
      # 5. Assert: 5 examples created with verdict="correct"
      # 6. remaining = workflow.get_pending()
      # 7. Assert: remaining excludes approved elements
      ```

- [ ] **Task 6d**: Add token-level bbox snapping

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6b
  - Notes: **Research insight (PAWLS)**: "Normalize the bounding box to be a fixed padded distance from the maximally large token boundary." When human adjusts bbox, snap to nearest word/line boundaries using PyMuPDF text extraction. Prevents partial word selections.
  - **Sanity**: `tools/tasks_loop/sanity/fitz_font_extraction.py` (uses same text extraction)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_labeling.py::test_bbox_snapping` (NEW)
    - Assertion:
      ```python
      # 1. rough_bbox = [72.3, 200.7, 539.2, 379.8]  # Human's rough selection
      # 2. snapped_bbox = workflow.snap_to_tokens(page, rough_bbox)
      # 3. Assert: snapped_bbox aligns with word boundaries
      # 4. Assert: all words partially in rough_bbox are fully in snapped_bbox
      # 5. Assert: no extra words included beyond padding
      ```

- [ ] **Task 6e**: Add relation annotation

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6
  - Notes: **Research insight (PAWLS)**: Supports "N-ary relations" between elements. Human should be able to annotate: "caption X belongs to figure Y", "header X starts section Y", "table X continues on next page as table Y". Saves to ArangoDB as edges between elements.
  - **Sanity**: `tools/tasks_loop/sanity/arango_calibration_schema.py` (needs edge collection)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_labeling.py::test_relation_annotation` (NEW)
    - Assertion:
      ```python
      # 1. handler.save_relation(
      #      from_element="page3_elem5",  # Caption
      #      to_element="page3_elem4",    # Figure
      #      relation_type="caption_of"
      #    )
      # 2. Assert: edge created in calibration_relations collection
      # 3. Assert: edge._from == "calibration_examples/page3_elem5"
      # 4. Assert: edge._to == "calibration_examples/page3_elem4"
      # 5. relations = handler.get_relations("page3_elem4")
      # 6. Assert: "caption_of" in [r.type for r in relations]
      ```

### Phase 4: 3-Stage Pattern Learning

- [ ] **Task 7**: Implement Stage 1 regex pattern extraction

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6
  - Notes: Analyze labeled examples, extract common patterns (e.g., "headers are font size 14+, bold"). Generate regex rules. Test against labeled data.
  - **Sanity**: None (standard Python regex)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_pattern_learner.py::test_learn_header_pattern` (EXISTS)
    - Assertion:
      ```python
      # EXISTING TEST - verifies:
      # 1. Create 4 header examples: "1.0 Introduction", "1.1 Background", etc.
      # 2. Call learner.learn_from_session(session_key, min_examples=3)
      # 3. Assert: isinstance(result, LearningResult)
      # 4. Assert: len(result.proposals) >= 1
      # 5. Assert: result.examples_used == 4
      # 6. Assert: pattern.stage1_regex contains r"\d+" (section numbers)
      # 7. Assert: pattern.confidence > 0.5
      ```

- [ ] **Task 8**: Implement Stage 2 Python validation

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 7
  - Notes: When regex fails, generate Python validation function. Uses font metrics, position heuristics. Store as code string in `learned_patterns`.
  - **Sanity**: None (standard Python AST)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_pattern_learner.py::test_learn_table_pattern` (EXISTS)
    - Assertion:
      ```python
      # EXISTING TEST - verifies:
      # 1. Create 4 table examples with extraction hints (camelot_flavor="lattice")
      # 2. Call learner.learn_from_session(session_key, min_examples=3)
      # 3. Assert: pattern.stage2_python is not None
      # 4. Assert: "lattice" in pattern.stage2_python
      # 5. Assert: "25" in pattern.stage2_python (line_scale param)
      ```

- [ ] **Task 9**: Implement Stage 3 scillm LLM judge for ambiguous cases

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 8
  - Notes: Stage 3 is a JUDGE for grey areas where regex/Python rules are uncertain. Uses `from scillm.batch import parallel_acompletions_iter` (programmatic, not skill). Decisions include: merge tables?, is this a header?, which figure does caption belong to?, footnote or paragraph? When human review is needed, use `/pdf-screenshot` to show the ambiguous region.
  - **Sanity**: `tools/tasks_loop/sanity/scillm_paved_path.py` (must pass first)
  - **Visual Feedback**: `/pdf-screenshot doc.pdf --page N --highlight "bbox"` (show ambiguous element for human override of LLM judge)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_pattern_learner.py::test_stage3_judge` (NEW)
    - Assertion:
      ```python
      # Stage 3 acts as JUDGE for ambiguous decisions:
      # 1. Create ambiguous cases: [
      #      {"question": "merge_tables", "context": "Table A ends, Table B starts 10px below"},
      #      {"question": "is_header", "context": "Bold 12pt text: 'Important Note'"},
      #    ]
      # 2. from scillm.batch import parallel_acompletions_iter
      # 3. async for result in parallel_acompletions_iter(prompts, ...):
      #      judgments.append(result)
      # 4. Assert: each result has "decision" in ["yes", "no", "uncertain"]
      # 5. Assert: each result has "reasoning" explaining the judgment
      # 6. Assert: each result has "confidence" between 0.0 and 1.0
      # 7. Assert: response_format={"type":"json_object"} enforces structure
      ```

### Phase 5: Fixture Generation & Testing

- [ ] **Task 10**: Create dirty twin fixture generator

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 9
  - Notes: Generate synthetic PDFs with known ground truth from learned patterns. Include edge cases: merged cells, rotated text, nested lists, footnotes.
  - **Sanity**: `tools/tasks_loop/sanity/fixture_generation.py` (must pass first)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_fixtures.py::test_dirty_twin_generation` (NEW)
    - Assertion:
      ```python
      # 1. generator = DirtyTwinGenerator(patterns)
      # 2. fixture = generator.create(tables=3, figures=2, edge_cases=["merged_cells", "footnotes"])
      # 3. Assert: len(fixture.tables) >= 3
      # 4. Assert: len(fixture.figures) >= 2
      # 5. Assert: fixture.ground_truth is not None
      # 6. Assert: "merged_cells" in fixture.edge_cases_included
      # 7. Assert: fixture.pdf_path.exists() and fixture.pdf_path.stat().st_size > 0
      ```

- [ ] **Task 11**: Implement cross-format parity test

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 10
  - Notes: Generate identical content in 11 formats. Run extraction on each. Compare results. Flag format-specific extraction failures.
  - **Sanity**: `tools/tasks_loop/sanity/fixture_generation.py` (must pass first)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_fixtures.py::test_cross_format_parity` (NEW)
    - Assertion:
      ```python
      # 1. content = StandardTestContent(tables=2, figures=1, headers=5)
      # 2. pdf_result = extract(generate_pdf(content))
      # 3. docx_result = extract(generate_docx(content))
      # 4. html_result = extract(generate_html(content))
      # 5. Assert: abs(pdf_result.table_count - docx_result.table_count) <= 1
      # 6. Assert: abs(pdf_result.table_count - html_result.table_count) <= 1
      # 7. Assert: pdf_result.header_count == docx_result.header_count == html_result.header_count
      ```

- [ ] **Task 12**: Implement preset efficacy comparison (GROBID-style metrics)

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 11
  - Notes: (a) Compare extraction output to ground truth = accuracy score. (b) Compare old preset vs new preset = improvement delta. Report both. **Research insight (GROBID)**: Include precision/recall per element type, confusion matrix, and visual diff table for human review.
  - **Sanity**: None (pure comparison logic)
  - **Visual Output**: Side-by-side comparison table showing ground truth vs extraction per element
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_efficacy.py::test_preset_comparison` (NEW)
    - Assertion:
      ```python
      # 1. doc = load_document_with_ground_truth("fixtures/annotated_sample.pdf")
      # 2. old_result = extract(doc, preset="v1")
      # 3. new_result = extract(doc, preset="v2")
      # 4. report = compare_efficacy(old_result, new_result, doc.ground_truth)
      # 5. Assert: "accuracy_percent" in report and 0 <= report["accuracy_percent"] <= 100
      # 6. Assert: "improvement_delta" in report (can be negative for regression)
      # 7. Assert: "by_element_type" in report with keys: headers, tables, figures
      # 8. Assert: sum(report["by_element_type"].values()) / 3 ≈ report["accuracy_percent"]
      ```

### Phase 6: Integration

- [ ] **Task 13**: Create `/extraction-preset` skill entry point

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 12
  - Notes: Wire up full workflow: session management → sampling → labeling → learning → validation → export preset YAML.
  - **Sanity**: None (integration task)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_integration.py::test_full_workflow` (NEW)
    - Assertion:
      ```python
      # 1. result = await calibrator.run("fixtures/sample_requirements.pdf", interactive=False)
      # 2. Assert: result.preset_path.exists()
      # 3. preset = yaml.safe_load(result.preset_path.read_text())
      # 4. Assert: preset["document_type"] is not None
      # 5. Assert: "extraction_rules" in preset
      # 6. Assert: len(preset["extraction_rules"]) >= 1
      # 7. Verify preset works: pipeline_result = run_pipeline(doc, preset=preset)
      # 8. Assert: pipeline_result.exit_code == 0
      ```

- [ ] **Task 14**: Add batch mode for automated calibration

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 13
  - Notes: `--batch` flag auto-creates session, uses agent decisions (no human prompts), logs all decisions to file for review.
  - **Sanity**: None (CLI flag)
  - **Definition of Done**:
    - Test: `tests/pipeline/calibration/test_integration.py::test_batch_mode` (NEW)
    - Assertion:
      ```python
      # 1. result = await calibrator.run("fixtures/sample.pdf", batch_mode=True)
      # 2. Assert: result.completed == True
      # 3. Assert: result.prompt_count == 0 (no human prompts)
      # 4. Assert: result.decision_log_path.exists()
      # 5. decisions = json.loads(result.decision_log_path.read_text())
      # 6. Assert: len(decisions) > 0
      # 7. Assert: all(d.get("auto_decision") == True for d in decisions)
      # 8. Assert: result.preset_path.exists()
      ```

---

## Completion Criteria

1. All sanity scripts pass (dependencies verified)
2. All 14 tasks complete with tests passing
3. `/extraction-preset sample.pdf` produces working preset YAML
4. Preset efficacy shows both accuracy % and improvement delta
5. Session auto-resume works for interrupted calibrations
6. Cross-format parity test validates extraction equivalence

---

## Questions/Blockers

None

## Design Decisions (Resolved)

The following were resolved through human-agent collaboration:

| Question | Decision |
|----------|----------|
| Entry point | User confirms, batch mode auto-creates session with log |
| Feedback style | One element at a time with `[3/12]` progress indicator |
| Session resume | Auto-resume via doc_hash matching in ArangoDB |
| LLM integration | scillm paved path ONLY (batch_acompletions_iter) |
| Efficacy testing | Both accuracy vs ground truth AND improvement vs old preset |
| Fixture sources | Both synthetic twins AND real document samples |
| Sanity storage | File-based + ArangoDB for global recall via memory skill |

**scillm Reference**: The scillm skill is at `/home/graham/workspace/experiments/pi-mono/.pi/skills/scillm`
- Use `from scillm.batch import parallel_acompletions_iter` for batch LLM calls
- Refer to SCILLM_PAVED_PATH_CONTRACT.md for API usage
