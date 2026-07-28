# Task List: pdf_oxide becomes `/extract-pdf` Skill

**Created**: 2026-03-07
**Goal**: Transform pdf_oxide from a library into `/extract-pdf` — a self-contained skill with pipeline logic built into Rust. `/extractor` becomes a thin file-type dispatcher that delegates PDFs to `/extract-pdf`.

## Context

pdf_oxide already has 97.5% text extraction parity with PyMuPDF, plus block classification (12 types), section hierarchy, document profiling, engineering detection, and strategy recommendation — all in Rust. But the Python extractor pipeline (S00-S14) still wraps these in 10,000+ lines of Python with `import fitz` fallbacks and `from scillm.batch` imports.

The fix: move remaining deterministic pipeline logic INTO Rust (pdf_oxide), then create `/extract-pdf` as a skill with a thin Python orchestrator that calls pdf_oxide for all PDF parsing and composes with `/extract-tables`, `/lean4-prove`, and scillm for LLM calls. `/extractor` becomes a file-type router.

## Capability Overlap

- `/extract-tables` — already uses pdf_oxide internally; `/extract-pdf` composes with it
- `/scillm` — proxy at localhost:4001 handles LLM cascading; thin wrapper wraps it
- `/lean4-prove` — Docker skill for theorem proving; `/extract-pdf` calls it
- `/extractor` — becomes thin dispatcher, NOT rebuilt. Existing S07b-S14 stay in `/extractor`

## Crucial Dependencies (Sanity Scripts)

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| pdf_oxide | `extract_document()` (new) | `sanity/pdf_oxide_extract.py` | [ ] PENDING |
| pdf_oxide | `normalize_text()` (new) | `sanity/pdf_oxide_normalize.py` | [ ] PENDING |
| scillm proxy | `POST /v1/chat/completions` | `sanity/scillm_proxy.py` | [ ] PENDING |

> All sanity scripts must PASS before proceeding to implementation.

## Questions/Blockers

None — architecture confirmed by user.

## Tasks

### Phase R: Rust — Move Pipeline Logic into pdf_oxide

These tasks add new Rust modules to pdf_oxide that absorb deterministic logic currently scattered across Python pipeline steps S00, S02, S04, S06, S07.

---

- [ ] **Task R.1**: Add `src/extractors/text_normalizer.rs` — absorb S02/S07b text normalization into Rust
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - **Description**: Create a Rust text normalizer that handles what S02_pymupdf_extractor and S07b_text_cleaner do in Python:
    - Unicode control character removal (U+200B, U+FEFF, etc.)
    - Directional formatting strip (LTR/RTL marks)
    - Ligature normalization (fi, fl, ff, ffi, ffl → component chars)
    - Whitespace collapse (multiple spaces → single, trailing removal)
    - Hyphen normalization (soft hyphens, figure dashes → standard)
    - Symbol density calculation (ratio of math/special chars to alphanumeric)
    - Public API: `normalize_text(text: &str) -> String` + `symbol_density(text: &str) -> f32`
    - Wire into Python: `doc.normalize_text(text)` and `doc.symbol_density(text)`
  - **Files**: `src/extractors/text_normalizer.rs` (new), `src/python.rs`, `src/lib.rs`
  - **Definition of Done**:
    - Test: `cargo test text_normalizer` passes with 8+ test cases
    - Assertion: Normalizes "\u200BHello\u00ADWorld" to "HelloWorld"; symbol_density("x=y+z") > 0.3

---

- [ ] **Task R.2**: Add `src/extractors/block_merger.rs` — absorb S07 overlap suppression + paragraph formation
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - **Description**: Create a Rust block merger that handles what S07_duckdb_ingest does in Python:
    - Overlap suppression: when two ClassifiedBlocks overlap by >80% bbox IOU, keep the one with more text
    - Paragraph formation: merge consecutive Body blocks separated by <1.5x font_size vertically
    - Header/footer dedup: if same text appears as Header/Footer on 3+ pages, mark as running_header/running_footer
    - Block ordering: emit blocks in reading order (already handled by MuPDF-style builder, but validate)
    - Public API: `merge_blocks(blocks: Vec<ClassifiedBlock>, page_height: f32) -> Vec<MergedBlock>` where MergedBlock adds `is_running_header: bool`, `paragraph_id: usize`
    - Wire into Python: `doc.merge_blocks(page_idx)` returns list of merged block dicts
  - **Files**: `src/extractors/block_merger.rs` (new), `src/python.rs`, `src/lib.rs`
  - **Definition of Done**:
    - Test: `cargo test block_merger` passes with 5+ test cases
    - Assertion: Two overlapping blocks (90% IOU) merge to one; 3 consecutive body blocks within 1.5x font_size merge into one paragraph

---

- [ ] **Task R.3**: Enhance `src/extractors/section_hierarchy.rs` — absorb S04 TOC-guided promotion + filtering
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - **Description**: The current section_hierarchy.rs builds a tree from font-size-based headers only. S04_section_builder adds 1400 lines of Python for:
    - **TOC-guided promotion**: If document has TOC (outline), match TOC entries to detected headers by text similarity, promote header_level to match TOC level
    - **Section numbering parsing**: Detect "1.2.3" numbering patterns, infer hierarchy from numbering depth
    - **Glossary/appendix filtering**: Recognize "Glossary", "Appendix", "Index", "References" as terminal sections
    - **Header false-positive rejection**: From S02's 21 filters — reject blocks classified as Title if they match equation patterns, bibliography entries, author names, or are too long (>200 chars)
    - Add these as enhancement methods on `SectionTree`:
      - `promote_from_outline(outline: &[OutlineItem])` — match TOC to headers
      - `promote_from_numbering()` — detect "1.2.3" patterns
      - `filter_false_positives()` — reject equation/reference/author headers
    - Wire into Python: `doc.get_section_hierarchy(use_toc=True, filter_false_positives=True)`
  - **Files**: `src/extractors/section_hierarchy.rs`, `src/python.rs`
  - **Definition of Done**:
    - Test: `cargo test section_hierarchy` passes with 6+ test cases (3 existing + 3 new)
    - Assertion: Given TOC with "1. Introduction" at level 1, a header "1. Introduction" detected at level 3 gets promoted to level 1; "References" is marked as terminal section

---

- [ ] **Task R.4**: Add `src/extractors/figure_detector.rs` — absorb S06 spatial analysis
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - **Description**: Create a Rust figure detector that handles S06_figure_extractor's spatial analysis:
    - Image bbox extraction (already exists in extractors/images.rs)
    - Caption association: find closest Caption block above or below image bbox
    - Context text extraction: get Body blocks within 2x font_size above/below figure bbox
    - Section mapping: which section does this figure belong to (nearest preceding Title)
    - Figure numbering: parse "Figure N" from caption text
    - Public API: `detect_figures(page: usize) -> Vec<DetectedFigure>` where DetectedFigure has: bbox, caption, caption_number, context_above, context_below, section_title
    - Wire into Python: `doc.detect_figures(page_idx)` returns list of figure dicts
  - **Files**: `src/extractors/figure_detector.rs` (new), `src/python.rs`, `src/lib.rs`
  - **Definition of Done**:
    - Test: `cargo test figure_detector` passes with 4+ test cases
    - Assertion: Image with "Figure 3: Diagram" caption below gets caption_number=3 and correct bbox

---

- [ ] **Task R.5**: Add `extract_document()` unified orchestrator to `src/extractors/mod.rs`
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task R.1, R.2, R.3, R.4
  - **Description**: Create a single `extract_document()` function that runs the full Rust extraction pipeline:
    1. `predict_extraction()` — profile, classify, detect engineering features
    2. For each page: `extract_spans()` → `classify_spans()` → `merge_blocks()`
    3. `build_section_hierarchy()` with TOC promotion + false positive filtering
    4. `detect_figures()` for all pages
    5. `normalize_text()` on all block text
    6. Return `DocumentExtraction` struct containing: profile, sections, pages (with blocks, figures), engineering, recommended_strategy
    - This is the Rust-side "do everything deterministic" call. LLM and table calls stay in Python.
    - Wire into Python: `doc.extract_document()` returns a single nested dict
  - **Files**: `src/extractors/mod.rs`, `src/python.rs`
  - **Definition of Done**:
    - Test: `cargo test extract_document` — integration test on a test PDF
    - Assertion: Returns non-empty profile, sections, and page blocks for a multi-page test PDF

---

- [ ] **Task R.6**: Expose `extract_document()` via Python bindings with JSON-serializable output
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task R.5
  - **Description**: Ensure `doc.extract_document()` in Python returns a dict that's directly JSON-serializable:
    ```python
    result = doc.extract_document()
    # result = {
    #   "profile": {"domain": "defense", "preset": "defense_document", ...},
    #   "engineering": {"is_engineering": true, "doc_subtype": "...", ...},
    #   "sections": [{"title": "...", "level": 1, "page": 0, "children": [...]}],
    #   "pages": [
    #     {"page": 0, "blocks": [...], "figures": [...]}
    #   ],
    #   "recommended_strategy": "structured_extraction"
    # }
    import json
    json.dumps(result)  # must work
    ```
    - Validate round-trip: Python dict → JSON string → Python dict matches
  - **Files**: `src/python.rs`
  - **Definition of Done**:
    - Test: `python -c "import pdf_oxide; d=pdf_oxide.PdfDocument('test.pdf'); import json; json.dumps(d.extract_document())"` exits 0
    - Assertion: All fields present, JSON-serializable, no PyO3 objects leaking

---

### Phase S: Skill — Create `/extract-pdf` Scaffold

These tasks create the `/extract-pdf` skill that wraps pdf_oxide and composes with other skills.

---

- [ ] **Task S.1**: Create `/extract-pdf` skill scaffold
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task R.6
  - **Description**: Create the skill directory structure:
    ```
    pi-mono/.pi/skills/extract-pdf/
      SKILL.md           # name, triggers, provides, composes
      run.sh             # uv run --project . main.py "$@"
      sanity.sh          # Check pdf_oxide importable, test PDF extractable
      pyproject.toml     # deps: pdf_oxide>=0.3.14, httpx, loguru
      main.py            # CLI entry: parse args, call pipeline.run()
      extract_pdf/
        __init__.py
        pipeline.py      # Orchestrator: pdf_oxide.extract_document() + LLM + tables
        llm_provider.py  # Thin wrapper: scillm proxy + direct OAuth
        config.py        # ExtractionConfig dataclass
    ```
    - **SKILL.md** provides: `[pdf-extraction, pdf-text, pdf-figures, pdf-sections]`
    - **composes**: `[extract-tables, lean4-prove, scillm, memory, task-monitor, extractor-quality-check]`
    - **triggers**: `[extract pdf, process pdf, pdf extraction]`
  - **Files**: All new files in skill directory
  - **Definition of Done**:
    - Test: `sanity.sh` exits 0
    - Assertion: `python -c "from extract_pdf.pipeline import run"` imports cleanly

---

- [ ] **Task S.2**: Implement `extract_pdf/llm_provider.py` — thin LLM wrapper
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: none (can run alongside R tasks)
  - **Description**: Thin async LLM wrapper that supports provider selection:
    - `proxy` mode (default): POST to `http://localhost:4001/v1/chat/completions` with `model=text` or `model=vlm`. Auth: `Bearer sk-dev-proxy-123`. Proxy handles cascading/retries.
    - `claude` mode: Anthropic API via `ANTHROPIC_API_KEY`
    - `codex` mode: OpenAI API via `OPENAI_API_KEY`
    - `gemini` mode: Google API via `GOOGLE_API_KEY`
    - `skip` mode: returns empty/stub responses
    - Selection via `EXTRACT_PDF_LLM_PROVIDER` env var (default: `proxy`)
    - Core interface:
      ```python
      async def complete(messages, model=None, temperature=0.3, max_tokens=4096) -> str
      async def batch_complete(prompts, concurrency=5) -> list[str]
      async def vlm_complete(messages, images, model=None) -> str
      ```
    - Direct modes: basic retry (3 attempts with backoff). Heavy cascading stays in proxy.
  - **Files**: `extract_pdf/llm_provider.py` (new)
  - **Definition of Done**:
    - Test: `pytest tests/test_llm_provider.py::test_skip_mode` returns stub
    - Assertion: `EXTRACT_PDF_LLM_PROVIDER=skip` returns empty string; `proxy` constructs httpx client to localhost:4001

---

- [ ] **Task S.3**: Implement `extract_pdf/pipeline.py` — thin orchestrator
  - Agent: general-purpose
  - Parallel: 2
  - Dependencies: Task R.6, Task S.1, Task S.2
  - **Description**: The core pipeline orchestrator. Thin Python that calls Rust for deterministic work:
    ```python
    async def run(pdf_path: str, config: ExtractionConfig) -> dict:
        doc = PdfDocument(str(pdf_path))

        # 1. Rust does ALL deterministic extraction
        extraction = doc.extract_document()

        # 2. LLM calls for non-deterministic steps (parallel)
        llm = LLMProvider(config.llm_provider)
        suspicious_headers = await verify_suspicious_headers(extraction, llm)

        # 3. Delegate tables to /extract-tables skill
        tables = await extract_tables(pdf_path, extraction["pages"])

        # 4. Delegate figures to VLM for description
        figure_descriptions = await describe_figures(extraction, llm)

        # 5. Assemble JSON envelope
        return assemble_output(extraction, tables, figure_descriptions, suspicious_headers)
    ```
    - Steps that stay in Python: suspicious header VLM verification (S03), figure description (S06b), table description (S05b), section summarization (S09)
    - Steps absorbed by Rust: profiling (S00), text extraction (S02), section building (S04), figure detection (S06), block merging (S07)
    - Steps that stay in `/extractor`: S07b text cleaning (thin wrapper), S08-S14 (downstream processing)
  - **Files**: `extract_pdf/pipeline.py` (new)
  - **Definition of Done**:
    - Test: `python -m extract_pdf.pipeline test.pdf --provider skip` produces JSON output
    - Assertion: Output has non-empty `profile`, `blocks`, `sections` from Rust; `tables` array present (may be empty with skip mode)

---

- [ ] **Task S.4**: Define `/extract-pdf` output JSON contract
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task R.6
  - **Description**: Create `extract_pdf/schema.py` with the output JSON contract that `/extractor` will consume:
    ```json
    {
      "version": "1.0",
      "engine": "pdf_oxide",
      "engine_version": "0.3.14",
      "profile": { "domain": "...", "preset": "...", "is_scanned": false, ... },
      "engineering": { "is_engineering": false, ... },
      "sections": [{ "title": "...", "level": 1, "page": 0, "children": [...] }],
      "pages": [{
        "page": 0,
        "blocks": [{ "id": "p0_b0", "text": "...", "block_type": "body", "bbox": [...], "font_size": 11.0, "is_bold": false, "header_level": null, "paragraph_id": 0 }],
        "figures": [{ "figure_id": "p0_f0", "bbox": [...], "caption": "...", "caption_number": 1, "image_path": null, "context_above": "..." }]
      }],
      "tables": [{ "page": 0, "bbox": [...], "strategy": "lattice", "rows": [...] }],
      "diagnostics": { "recommended_strategy": "...", "cascade_decisions": [] }
    }
    ```
    - Include a `validate_output(data: dict) -> bool` function that checks required fields
  - **Files**: `extract_pdf/schema.py` (new)
  - **Definition of Done**:
    - Test: `pytest tests/test_schema.py::test_validate_output` passes
    - Assertion: Valid output passes validation; missing `profile` fails validation

---

### Phase E: Extractor — Simplify to File-Type Dispatcher

These tasks modify `/extractor` to delegate PDF work to `/extract-pdf`.

---

- [ ] **Task E.1**: Add PDF dispatch in `/extractor` pipeline runner
  - Agent: general-purpose
  - Parallel: 2
  - Dependencies: Task S.3
  - **Description**: Modify `extractor/pipeline/run_pipeline.py` to detect PDF files and dispatch to `/extract-pdf`:
    ```python
    if file_path.suffix.lower() == ".pdf":
        result = await extract_pdf_skill.run(file_path, config)
        # Map /extract-pdf JSON output to S02/S05/S06 format for downstream steps
        pipeline_state.blocks = result["pages"]
        pipeline_state.tables = result["tables"]
        pipeline_state.figures = result["pages"][n]["figures"]
        # Skip S00, S01, S02, S03, S04, S05, S06 — already done by /extract-pdf
        # Continue from S07b (text cleaning) onward
    ```
    - Keep the existing HTML pathway unchanged
    - Map `/extract-pdf` output schema to what S07b-S14 expect
  - **Files**: `src/extractor/pipeline/run_pipeline.py`
  - **Definition of Done**:
    - Test: Run extractor on a PDF — dispatches to /extract-pdf, continues from S07b
    - Assertion: `grep -c "import fitz" src/extractor/pipeline/run_pipeline.py` returns 0

---

- [ ] **Task E.2**: Remove fitz from ALL extractor pipeline steps
  - Agent: general-purpose
  - Parallel: 2
  - Dependencies: Task E.1
  - **Description**: With PDF dispatch to `/extract-pdf`, S00-S06 are no longer called for PDFs. But they may still be imported or referenced:
    - Delete all `import fitz` lines (S00:51, S01:24, S02:31, S02_marker:661/800/841/852, S03:44, S04:80, S04a:172, S05:27, S06:28, S09:440, S14:596)
    - Delete `_OxideDocProxy`/`_OxidePageProxy` shim classes in S05 (lines 115-166)
    - Replace any remaining rendering calls (S09, S14) with pdf_oxide: `PdfDocument(path).render_page(page, dpi=144)`
    - Remove `PyMuPDF` / `fitz` from `pyproject.toml` dependencies
  - **Files**: All files in `src/extractor/pipeline/steps/` that import fitz
  - **Definition of Done**:
    - Test: `grep -r "import fitz" src/extractor/ | wc -l` returns 0
    - Assertion: `fitz` not in pyproject.toml; `pip show PyMuPDF` returns "not found"

---

- [ ] **Task E.3**: Replace all `from scillm.batch` imports with `/extract-pdf` llm_provider
  - Agent: general-purpose
  - Parallel: 2
  - Dependencies: Task S.2
  - **Description**: For steps that stay in `/extractor` (S07b-S14), replace scillm imports:
    - `s09_section_summarizer.py:141,323` — replace with `llm_provider.batch_complete()`
    - `s08_extract_requirements.py:25` — replace with `llm_provider.batch_complete()`
    - `s08_lean4_theorem_prover.py:150` — remove dead `from scillm.extras.providers import certainly_prove_iter`
    - `scillm_preflight_validator.py:94,97` — remove commented scillm references
    - Steps that moved INTO `/extract-pdf` (S03, S05b, S06b, S01) no longer need migration here — they use the skill's own llm_provider
    - Import path: `from extract_pdf.llm_provider import LLMProvider`
  - **Files**: `s08_extract_requirements.py`, `s08_lean4_theorem_prover.py`, `s09_section_summarizer.py`, `scillm_preflight_validator.py`
  - **Definition of Done**:
    - Test: `grep -r "from scillm" src/extractor/ | wc -l` returns 0
    - Assertion: No scillm imports remain anywhere in extractor

---

### Phase V: Validation — Blind Testing + Integration

---

- [ ] **Task V.1**: Create sanity scripts for `/extract-pdf`
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task R.6
  - **Description**: Create sanity scripts in the skill directory:
    - `sanity/pdf_oxide_extract.py` — verify `doc.extract_document()` returns valid dict on test PDF
    - `sanity/pdf_oxide_normalize.py` — verify `doc.normalize_text()` handles Unicode edge cases
    - `sanity/scillm_proxy.py` — verify scillm proxy responds at localhost:4001
    - `sanity.sh` — run all sanity scripts, exit 0 only if all pass
  - **Files**: `sanity/` dir in skill
  - **Definition of Done**:
    - Test: `./sanity.sh` exits 0
    - Assertion: All 3 sanity scripts pass individually

---

- [ ] **Task V.2**: End-to-end validation on 20 representative PDFs
  - Agent: general-purpose
  - Parallel: 3
  - Dependencies: Task E.1, Task E.2, Task E.3
  - **Description**: Run the full `/extractor` pipeline (with PDF dispatch to `/extract-pdf`) on 20 PDFs from the 12TB corpus: 4 defense, 4 academic, 3 engineering, 3 NIST, 2 IETF, 2 NASA, 2 scanned. Compare output against PyMuPDF baseline:
    - Mean text similarity >= 90% (we achieved 97.5% in isolation)
    - All tables extracted (compare count vs PyMuPDF)
    - All figures detected (compare count)
    - Sections present in output
  - **Definition of Done**:
    - Test: Pipeline run on 20 PDFs completes without crashes
    - Assertion: Mean similarity >= 90%; 0 page count mismatches; 0 crashes

---

- [ ] **Task V.3**: Verify zero fitz/scillm imports across entire extractor + skill
  - Agent: general-purpose
  - Parallel: 3
  - Dependencies: Task E.2, Task E.3
  - **Description**: Final sweep:
    - `grep -r "import fitz" src/extractor/` → 0 results
    - `grep -r "from scillm" src/extractor/` → 0 results
    - `fitz` not in any `pyproject.toml` or `requirements.txt`
    - Run full test suite: `pytest tests/ -v`
    - Run `skills-ci scan` on `/extract-pdf`
  - **Definition of Done**:
    - Test: `grep -rcE "import fitz|from scillm" src/extractor/ | grep -v ":0$" | wc -l` returns 0
    - Assertion: Zero imports remain; test suite passes; skills-ci clean

---

## Blind Evaluation

After Phase R and Phase S complete, `/test-lab` generates hidden adversarial tests. The coding agent sees only pass/fail output — never the test source.

**Blind test domains:**
- `rust-extraction`: verifies `extract_document()` returns correct block types, section hierarchy, figure detection for fixture PDFs
- `fitz-removal`: verifies no fitz imports, no PyMuPDF wheel, no fitz runtime calls across entire codebase
- `llm-provider`: verifies provider switching (proxy, skip, direct modes), error handling, timeout behavior
- `skill-contract`: verifies `/extract-pdf` output matches JSON schema contract for 10 fixture PDFs
- `dispatcher`: verifies `/extractor` correctly routes PDFs to `/extract-pdf` and non-PDFs to existing paths

**Trigger points:**
- After Phase R (Task R.6): `test-lab generate --domain rust-extraction src/extractors/`
- After Phase S (Task S.3): `test-lab generate --domain skill-contract extract_pdf/`
- After Phase E (Task E.2): `test-lab generate --domain fitz-removal src/extractor/`

Max retries per task: 5. Coding agent cannot view or modify blind tests.

## Completion Criteria

- [ ] All sanity scripts pass
- [ ] All tasks marked [x]
- [ ] All Definition of Done tests pass
- [ ] All `/test-lab` blind tests pass
- [ ] `doc.extract_document()` returns complete extraction in one Rust call
- [ ] `/extract-pdf` skill passes `skills-ci scan`
- [ ] `/extractor` dispatches PDFs to `/extract-pdf`, skips S00-S06
- [ ] Zero `import fitz` or `from scillm` in `src/extractor/`
- [ ] `EXTRACT_PDF_LLM_PROVIDER` env var selects between proxy/codex/gemini/claude/skip
- [ ] PyMuPDF removed from all dependency files

## Notes

- **Architecture**: pdf_oxide IS `/extract-pdf`. Pipeline logic lives in Rust. Python is thin orchestration for LLM calls + skill composition.
- **What Rust does**: Text extraction, block classification, block merging, section hierarchy (with TOC promotion), figure detection, text normalization, document profiling, engineering detection, strategy recommendation. All deterministic.
- **What Python does**: LLM calls (suspicious header verification, figure descriptions, table descriptions, section summaries), `/extract-tables` delegation, JSON assembly, file I/O.
- **What `/extractor` keeps**: S07b text cleaning, S08 requirements, S08 lean4, S09 summaries, S10-S14 exports/reports. All downstream of `/extract-pdf` output.
- **scillm proxy**: stays running at localhost:4001. Accessed via HTTP (not Python import). Handles cascading Chutes->Gemini->DeepSeek.
- **DPI mapping**: `fitz.Matrix(2, 2)` = 144 DPI in pdf_oxide
- **`page_count` is a METHOD**: `doc.page_count()` not `doc.page_count`
