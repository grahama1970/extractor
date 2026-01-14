# Contract Loop Enhancement Tasks (Q1 2026)

This checklist scopes the next round of improvements for `tools/contract_loop`.
Each task is actionable, paired with required files, and has concrete
acceptance criteria so we can tighten the pipeline contracts without guesswork.
**Important:** these tasks require joint changes in both the contract loop
infrastructure *and* the pipeline step modules under
`src/extractor/pipeline/steps/*.py`. Build the framework and step outputs
in lockstep; neither layer can satisfy the contract alone.

## Current State vs. Target

**Current Reality:**

- **Self-Contained Engine**: `core.py` and `extractor.py` (adapter) fully drive the pipeline today using existing `src/extractor/pipeline/steps/` CLIs.
- **Artifacts**: Steps already produce deterministic outputs (e.g., `04_section_builder/json_output/04_sections.json`, `05_table_extractor/visual_output/`). The adapter enforces contracts on these _existing_ files.
- **Error Handling**: Currently, failures pause execution and print plain-text questions to the console. The operator must manually inspect `stage.log` files.
- **Lean4**: `s08_lean4_theorem_prover` is disabled/skipped by default pending upstream fixes. Visual requirements below explicitly exempt it until re-enabled.

**Target State (Q1 2026):**

- **Rich Debugging**: Automating log capture and hygiene (Task 2).
- **Visual Collaboration**: Replacing console questions with a TUI/HTML form (Task 4) that surfaces the images/thumbnails already being generated.
- **Portability**: Making it easy for other pipelines to adopt this loop (Task 3/5).

## Scope Summary

- Enforce strict upstream/downstream clearing and capture per-run provenance.
- Introduce a `--debug` collaboration mode with richer logs, walkthrough links,
  and override hooks while still keeping contracts strict.
- Upgrade clarifying-question handoffs to structured prompts/forms inspired by
  `pi-interview-tool` to reduce ambiguity when a step exhausts retries.
- Guarantee that **every** extracted object (sections, merged sections, tables,
  figures, contiguous text blocks, etc.) ships with a bounding box **and** a
  reviewable visual (PNG/JPEG) so agents/humans can validate results quickly.
- Improve documentation (Mermaid diagrams, adapter templates) so other projects
  can reuse the loop without spelunking code.

## Task Matrix

| #   | Task                                | Key Files                                                                        | Prereqs   | Done When                                                       |
| --- | ----------------------------------- | -------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------- |
| 1   | Manifest + provenance               | `tools/contract_loop/core.py`, `tools/contract_loop/verify_pipeline_contract.py` | None      | **[x]** Manifest logs toggles, inputs, per-step output hashes   |
| 2   | `--debug` discipline                | Same as above + docs                                                             | Task 1    | **[x]** Flag enforces rerun/clean, enriches manifest, captures logs + summary |
| 3   | Collaboration bundle                | `core.py`, adapter questions, new bundle helper                                  | Tasks 1-2 | **[x]** Bundle zip archives stdout/stderr, judge prompts, manifest refs + guardrails |
| 4   | Structured clarifications UI        | New `clarify/` helper (HTML or TUI), adapter question data                       | Task 2    | **[x]** CLI emits curses/Flask prompts, writes `clarifications/` JSON, manifest/bundles reference responses |
| 5   | Diagram + adapter template docs     | `tools/contract_loop/docs/*.md`, new Mermaid assets                              | Parallel  | Docs show flow + template, referenced from README               |
| 6   | Visual artifact guarantees (non-neg) | `src/extractor/pipeline/steps/*`, adapter fixtures, clarifying UI asset loader    | Tasks 1-4 | Every object emits bbox + image, surfaced in UI + contracts     |
| 7   | Task contract loop harness          | `tools/contract_loop/run_task_loop.py`, contracts, gates                          | Task 0c   | **[x]** Per-task codex exec loop + deterministic+LLM gate + JSON contracts |

## Visual Requirements Snapshot

| Step Module                          | Current Visual Status (Jan 2026) | Action Needed |
| ------------------------------------ | -------------------------------- | ------------- |
| s01_annotation_processor             | Needs audit (bbox exists, images TBD) | Ensure annotation thumbnails written + referenced |
| s02_marker_extractor                 | Partial (`visual_output/` optional) | Standardize bbox/image export |
| s03_suspicious_headers               | No visuals today                 | Add candidate header crops |
| s04_section_builder                  | JSON only                        | Generate per-section stitched images |
| s04a_layout_audit                    | Emits screenshots via audit? verify | Confirm audit JSON references visuals |
| s05_table_extractor                  | Has table crops                  | Ensure metadata references paths |
| s05b_table_describer                 | Reuses S05 images                | Link to visuals in JSON before LLM |
| s05c_table_merger                    | No visuals yet                   | Create merged-table image (using bbox tuples) |
| s06_figure_extractor                 | Has figure images                | Confirm bbox normalization |
| s06b_figure_describer                | Uses S06 images                  | Reference visual path in judge samples |
| s07_duckdb_ingest                    | N/A (DB ingest)                  | Provide pointers to upstream visuals instead of new renders |
| s08_extract_requirements             | Needs bbox/page anchors           | Require page+bbox in outputs; snapshots optional |
| s08_lean4_theorem_prover             | Skipped currently                | Exempt until step re-enabled |
| s09_section_summarizer               | Needs section preview image      | Reuse s04 visuals + highlight summarized text |
| s10_arangodb_exporter                | Downstream consumer (no new renders) | Propagate upstream `visual_path` references without mutation |
| s10_markdown_exporter                | Downstream Markdown packaging    | Embed upstream visuals/links; document N/A for new captures |
| s14_report_generator                 | Final report assembly            | Reference upstream assets; confirm exemption in manifest |

Document updates should reflect the audit above as progress occurs.

## Task Details

### 0. Core Sanity Preconditions (Gate Before Task 1)

- **Goal:** Contract Loop work only proceeds if baseline sanity scripts pass so agents don’t try to enforce contracts on a broken pipeline. This gate is mandatory before any task execution or refactor.
- **Global minimum set (extend as the project evolves):**
  1. `uv run src/extractor/pipeline/sanity/camelot_sanity.py` — verifies s05 table extraction fundamentals.
  2. `uv run src/extractor/pipeline/sanity/s08_prove_simple_sanity.py` — exercises the `scillm.parallel_acompletions_iter` path to guarantee Chutes reachability.
  3. `source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a && python scripts/tools/scillm_quick_doctor.py` — confirms env + model wiring.
  4. `python tools/contract_loop/verify_pipeline_contract.py --mode deterministic` — adapter-level smoke outside of debug mode.
- **Per-step requirement:** Every pipeline module listed below must advertise at least one passing sanity command recorded in the **project** sanity matrix (e.g., `tools/contract_loop/adapters/<project>/docs/SANITY_MATRIX.md`). Agents may not touch the step (or run the loop) until its sanity entry exists and is green. Lean4 remains exempt until re-enabled, but its slot stays reserved.
  - `s01_annotation_processor.py`
  - `s02_marker_extractor.py`
  - `s03_suspicious_headers.py`
  - `s04_section_builder.py`
  - `s04a_layout_audit.py`
  - `s05_table_extractor.py`
  - `s05b_table_describer.py`
  - `s05c_table_merger.py`
  - `s06_figure_extractor.py`
  - `s06b_figure_describer.py`
  - `s07_duckdb_ingest.py`
  - `s08_extract_requirements.py`
  - `s08_lean4_theorem_prover.py` (documented as “skipped” until re-enabled)
  - `s09_section_summarizer.py`
  - `s10_arangodb_exporter.py`
  - `s10_markdown_exporter.py`
  - `s14_report_generator.py`
- **Enforcement:** `tools/contract_loop/core.py` must call a helper that runs the global scripts and then iterates the **project sanity matrix** entries before any step executes. If a sanity check fails or is missing, the loop exits with a hard error and instructs the agent to fix the prerequisite first.
- **Extensibility:** Each pipeline step may declare additional sanity requirements (e.g., via metadata in `src/extractor/pipeline/steps/<step>.py`). When a step adds such a dependency, update this section, the matrix, and the helper so the loop enforces it automatically.

### 0b. Contract Loop Self-Sanity Matrix (Module-Level)

- **Goal:** The contract-loop module is shareable and must pass its own sanity checks independently of any specific project (like extractor). This includes the per-task Codex exec harness, JSON schema enforcement, bundle creation, and clarifying UI surfaces.
- **Deliverables:**
  - Add `tools/contract_loop/docs/SANITY_MATRIX_CONTRACT.md` to capture contract-loop-only checks (exec harness, contract validator, bundle guardrails, clarify UI server, TUI fallback).
  - Provide a `tools/contract_loop/sanity_config_contract.py` (or similar) listing the module-level commands, separate from project-specific matrices.
  - Update the sanity runner to execute both the contract-loop matrix and any project-provided matrix (e.g., via adapter config).
- **Acceptance Criteria:**
  - `tools/contract_loop` can run its own sanity suite without depending on extractor pipeline outputs.
  - Project-specific sanity matrices are injected through adapter configuration, not hardcoded into core.
  - Documentation clearly distinguishes **contract-loop-only** sanity vs **project** sanity.

### 0c. Project-Scoped Contract + Sanity Locations

- **Goal:** Each project using contract_loop must declare its own per-task contracts and sanity matrix in a dedicated location (e.g., `tools/contract_loop/adapters/<project>/docs/`).
- **Deliverables:**
  - Add an adapter-level config or manifest hook that points to a project’s contract docs + sanity matrix path.
  - Document this in `ADAPTER_TEMPLATE.md` so new pipelines can onboard without touching the shared module.
- **Acceptance Criteria:**
  - Contract loop runs with project-level matrices loaded dynamically.
  - The core module remains usable without any extractor-specific references.

### 1. Emit Strict Per-Run Manifest and Provenance

- **Goal:** Every contract-loop run produces `out/manifest.json` summarizing
  toggles, environment, input SHA256, fixture hash, and a table of
  `{step, attempt, output_paths, sha256}` for downstream audit.
- **Implementation Notes:**
  - Extend `run_contract_loop` to accumulate metadata each time a step finishes.
  - Hash output directories deterministically (e.g., hash sorted file contents)
    so we can prove no stale artifacts were reused.
  - Include CLI arguments, Git SHA (`git rev-parse HEAD`), and `PYTHONPATH`.
- **Acceptance Criteria:**
  - Manifest exists for deterministic and full runs.
  - Run fails if hashing fails (prevents silent truncation).
  - Mermaid-ready snippet embedded to show attempt graph.

### 2. Add `--debug` Mode with Enforced Discipline

- **Goal:** Provide a collaboration mode that **requires** rerunning upstream
  and cleaning downstream while adding verbose instrumentation.
- **Behavior:**
  - `--debug` is mutually exclusive with `--no-clean-downstream` and
    `--no-rerun-upstream`; CLI exits if both are provided.
  - Enables extended logging: capture stdout/stderr for each step attempt into
    `out/<step>/attempt_<n>/{stdout,stderr}.log`.
  - Manifest links to `tools/contract_loop/docs/DEBUG_PLAYBOOK.md` (create this
    doc outlining expectations and toggles).
- **Acceptance Criteria:**
  - Flag documented in README + adapter docs.
  - Tests demonstrate that disabling clean/rerun under `--debug` exits with a
    clear error.
  - `out/debug.md` summary lists where logs and bundles live.

### 3. Package Collaboration Bundle (Logs + Judge Prompts)

- **Goal:** After each failed attempt (debug mode first), emit a tar/zip bundle
  containing manifest, step logs, Codex judge prompts/responses, and any
  clarifying-question metadata so humans can open it in VS Code instantly.
- **Implementation Notes:**
  - Add `tools/contract_loop/utils.py` helper to compose bundles with relative
    paths.
  - Reference bundle path in CLI output and manifest.
- **Acceptance Criteria:**
  - Bundle creation is idempotent (re-running overwrites or version-stamps).
  - Size guardrail: warn once bundle exceeds 50 MB, fail the run if it would
    exceed 100 MB (require manual override).
  - Tests cover presence of required files.

### 4. Structured Clarifying Questions (HTML/TUI Form)

- **Goal:** Replace plain-text questions with a selectable checklist resembling
  `pi-interview-tool` so operators can answer “A/B/C” plus free text.
- **Approach:**
  - Introduce `tools/contract_loop/clarify/` module with two surfaces:
    1. **Single-question TUI** rendered inline in the agent chat when only one
       decision is needed (e.g., “Retry with relaxed min tables?”).
    2. **React/TypeScript form** (`tools/contract_loop/clarify-ui`, launched via
       the Flask host) for multi-question clarifications. Build with
       `tools/contract_loop/scripts/build_clarify_ui.sh`; DEV server available
       via `clarify_ui_dev.sh`.
  - Provide a **bash-first scaffolder** (`tools/contract_loop/scripts/new_form.sh`)
    modeled on the “What if you don’t need MCP?” workflow so agents can express
    question schemas (JSON/YAML) and preferred HTML widgets from a shell script.
    The helper should generate/extend the corresponding React Hook Form /
    TypeScript components under `clarify-ui/`, ensuring the agent can pick radio
    buttons, checkboxes, uploads, etc. without editing TS manually. Document the
    workflow alongside the bash helper.
  - Debug flow: CLI prints `Open http://127.0.0.1:<port>/clarify/<step>` and
    waits until `out/clarifications/<step>.json` is written.
  - Adapter question definitions become structured objects with `id`,
    `prompt`, `options`, `docs_link`, `artifact_paths`, and `visual_assets` so
    the Flask UI can display evidence (e.g., merged section images).
  - For data-heavy stages (e.g., `s04_section_builder`), the form should preload
    known expectations for the debug PDF (section hierarchy, expected names,
    merged section image thumbnails built via PIL) and ask targeted checks such
    as:
    - “Verify this is the section hierarchy.”
    - “Is this the complete section image for 3.1.1 <Section Name>?”
    - “Does the contract expect a different title than what code produced?”
  - Contract loop pauses until responses exist. **Timeout policy:** default wait
    is 15 minutes; if the human form doesn’t respond, the loop aborts the run
    (fail-fast) rather than auto-accepting. Provide a `--clarify-timeout`
    override for long investigations.
- **Acceptance Criteria:**
  - CLI clearly states where to open the form (URL or helper command).
  - Responses echoed in console and appended to manifest/bundle.
  - Flask UI displays step-specific visuals (section hierarchies, table/figure
    screenshots) and records operator acknowledgements.
  - Form supports “pivot” hooks (e.g., rerun with relaxed fixture) recorded for
    audit.

### 5. Documentation + Diagram Refresh

- **Goal:** Make the enhanced workflow legible for contributors and downstream
  teams.
- **Deliverables:**
  - Update `tools/contract_loop/docs/CONTRACT_LOOP.md` with two Mermaid
    diagrams (control-flow + data-flow).
  - Add `tools/contract_loop/docs/ADAPTER_TEMPLATE.md` describing how to build a
    new adapter (required overrides, fixtures, judge integration).
  - Cross-link from README and the new `DEBUG_PLAYBOOK.md`.
- **Acceptance Criteria:**
  - Docs reference manifest, debug mode, bundle, and clarifying UI.
  - README contains a “Quickstart for other pipelines” section pointing to the
    adapter template.

### 6. Visual Artifact Guarantees (Non-Negotiable)

- **Goal (Required):** Every extractor output—sections (including any merged
  across pages), tables, figures, contiguous text blocks, requirement snippets,
  etc.—must ship with accurate bounding boxes in canonical coordinates. For
  most steps, a reviewable visual (PNG/JPEG) is also required. Requirements
  are the exception: they must include page + bbox anchors, but images are
  optional. “Canonical” = PDF points with a top-left origin (PyMuPDF
  convention), per-page bounding boxes encoded as `[page_index, x0, y0, x1, y1]`.
  Multi-page spans must emit ordered lists of `(page, bbox)` tuples so visual
  stitchers can reconstruct merged regions. A consistent tuple set is sufficient
  to generate or stitch those visuals with PyMuPDF / PIL; the pipeline must
  expose these tuples even if rendering happens later. When serialized to JSON,
  treat each tuple as an array: `bbox` must be `[page_index, x0, y0, x1, y1]`,
  and multi-page spans must be `[[page_index, x0, y0, x1, y1], ...]` so
  downstream consumers (Flask UI, bundles, auditors) can parse the data without
  Python-specific tuple syntax.
- **Implementation Notes:**
  - Audit each step under `src/extractor/pipeline/steps/` to ensure it emits
    `visual_output/` assets (sibling to `json_output/`) or references upstream
    visuals explicitly. Where images don’t exist (e.g., merged section spans),
    generate them via PyMuPDF/PIL by stitching page regions. “Merged sections”
    refers to a single logical section from `s04_section_builder` whose content
    crosses page boundaries; do **not** conflate this with `s05c_table_merger`,
    which only merges tables.
  - Standardize metadata: add `visual_path` and `bbox` fields to JSON output so
    clarifying UIs can load assets automatically.
  - Update fixtures/contracts to assert presence of these visuals (e.g.,
    `keys` must include `visual_path`).
  - Ensure the Flask clarifying form can load and display these assets for any
    step (sections, tables, figures, text blocks, LLM descriptions). Centralize
    serving via `out/visuals/<step>/` symlinks so the web UI can read assets
    without sniffing every directory; the adapter should create/refresh these
    symlinks after each step finishes, so individual step modules only need to
    write `visual_output/` alongside their JSON results.
  - Explicitly validate the following modules meet the bbox+visual requirement:
    - `s01_annotation_processor.py`
    - `s02_marker_extractor.py`
    - `s03_suspicious_headers.py`
    - `s04_section_builder.py`
    - `s04a_layout_audit.py`
    - `s05_table_extractor.py`
    - `s05b_table_describer.py`
    - `s05c_table_merger.py`
    - `s06_figure_extractor.py`
    - `s06b_figure_describer.py`
    - `s07_duckdb_ingest.py` (reference upstream visuals; no new renders)
    - `s08_extract_requirements.py` (page + bbox anchors required; images optional)
    - `s08_lean4_theorem_prover.py` (exempt until step re-enabled)
    - `s09_section_summarizer.py`
    - `s10_arangodb_exporter.py` (propagate metadata, no additional renders)
    - `s10_markdown_exporter.py` (embed upstream assets only)
    - `s14_report_generator.py` (final report references; document exemption)
- **Acceptance Criteria:**
  - For the canonical debug PDF, `s04_section_builder`, `s05_table_extractor`,
    `s05c_table_merger`, `s06_figure_extractor`, `s09_section_summarizer`, etc.,
    all produce visuals and bbox metadata.
  - Adapter verification fails fast if visuals/bboxes are missing.
  - Clarifying UI shows those visuals automatically when a step fails.
  - A new audit helper (`tools/contract_loop/scripts/audit_visuals.py`) checks
    every JSON entry for `bbox` + `visual_path` and is wired into CI.

### 7. Task Contract Loop Harness (Per-Task Codex Exec)

- **Goal:** Each contract-loop task runs in its own Codex exec session with JSON
  output and a deterministic+LLM gate that must pass before moving on.
- **Implementation Notes:**
  - Per-task contracts live in the project (`contracts/contract_loop/`) and are
    referenced from `contracts/contract_loop/CONTRACT.md` (see examples in
    `tools/contract_loop/docs/examples/`).
  - Implement `tools/contract_loop/run_task_loop.py` to:
    - Run `codex exec --json` for each task (one session per task).
    - Tee JSONL output + final JSON response to logs under `logs/contract_loop/`.
    - Run deterministic checks + LLM audit; LLM uses strict JSON schema and is
      mandatory (even if deterministic checks pass).
    - Emit `failure_report.json` per iteration and resume the task until the
      contract passes or max iterations are hit.
- **Acceptance Criteria:**
  - Contracts are stored outside `tools/contract_loop/` (project-owned).
  - Every run produces a stable JSON log + failure report in `logs/contract_loop/`.
  - Deterministic results are fed to the LLM gate for each iteration.
  - Loop stops only when deterministic + LLM gates both pass.

## Verification Checklist

1. Unit tests for manifest hashing, debug flag guardrails, bundle writer.
2. Scenario test running `verify_pipeline_contract.py --debug --mode deterministic`
   that asserts manifest + bundle files exist.
3. Manual run capturing screenshots of the clarifying form (store under
   `scripts/artifacts/contract_loop_clarify.png`).
4. Documentation lint (e.g., `mdformat` or `markdownlint`) passes.
5. `tools/contract_loop/scripts/audit_visuals.py` confirms every section/table/
   figure JSON entry references an on-disk image and canonical bbox.

## Open Questions (Resolved)

- **Clarifying form runtime:** Use a minimal Flask app (debug-friendly, easy to
  extend). Document the endpoint layout in the upcoming `DEBUG_PLAYBOOK.md`.
- **Bundle contents:** Include relevant slices of the source PDF; no IP concerns
  at this stage (also noted in `docs/TODO.md`).
- **Sensitive human responses:** No secure storage requirement yet; track this
  assumption in `docs/TODO.md` so we can revisit when requirements change.

Record future answers in this section to keep the team aligned.
