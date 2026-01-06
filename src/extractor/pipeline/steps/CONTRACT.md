Pipeline Steps Contract (Deterministic + Live)

Scope

- Documents minimal, testable invariants for the stages executed by `src/extractor/pipeline/run_pipeline.py`.
- Complements data/expected/pipeline/\* golden artifacts and pytest gates.

General Rules

- **Strict Coordinate System**: All spatial coordinates (bounding boxes, points) **MUST** use the Top-Left Origin system (PyMuPDF standard). Legacy formats (e.g., PDF Bottom-Left) **MUST** be normalized before leaving their respective stage.

- Steps are pure Python modules with a callable `run(...)`. No CLI frameworks (Typer/click/argparse) inside steps.
- Steps must not have import-time side effects. Loading `.env` happens in the driver or under `if __name__ == "__main__"` only.
- Each step writes to `data/results/<run>/<step>/{json_output,image_output,visual_output,logs}`.
- `stage.log` present per step when the driver provides a log sink.
- Each step exposes `sanity()` + `python -m <step> sanity` which emits a Sparta-style JSON summary via `run_step_sanity`.

Active Stages (run_pipeline.py order)

- 01_annotation_processor
- 02_marker_extractor
- 03_suspicious_headers
- 04_section_builder
- 04a_layout_audit
- 05_table_extractor
- 05b_table_describer (LLM; optional / skipped in summary-only)
- 05c_table_merger
- 06_figure_extractor
- 06b_figure_describer (LLM; optional / skipped in summary-only)
- 07_assemble_corpus (DuckDB ingest)
- 08_extract_requirements (LLM; optional / skipped in summary-only)
- 09_section_summarizer (LLM; optional / skipped in summary-only)
- 10_markdown_exporter (always)
- 14_report_generator (always, best‑effort)

Required Artifacts (deterministic base)

- 01_annotation_processor/json_output/01_annotations.json
  - Keys: { timestamp, source_pdf, clean_pdf_path, pages, annotations }
- 02_marker_extractor/json_output/02_marker_blocks.json
  - Keys: { timestamp, source_pdf, blocks, suspicious_block_count }
- 03_suspicious_headers/json_output/03_verified_blocks.json
  - Keys: { blocks } with `verdict` on suspicious headers
- 04_section_builder/json_output/04_sections.json
  - Keys: { sections } with section bbox and page indices
- 04a_layout_audit/json_output/04a_layout_audit.json
  - Keys: { ok, errors, checks } with `ok == true` and `errors == 0`
- 05_table_extractor/json_output/05_tables.json
  - Keys: { tables } with per-table bbox, page, metrics (pandas_metrics, camelot_metrics)
- 05c_table_merger/json_output/05c_tables.json
  - Keys: { tables } with merged/normalized tables (must fall back to 05 if 05b absent)
- 06_figure_extractor/json_output/06_figures.json
  - Keys: { figures } (page or page_idx, bbox, image_path). In deterministic mode, ai_description may be stubbed.
- 07_assemble_corpus
  - Output: pipeline.duckdb
  - Required tables: sections, blocks, tables, figures, merged_content
  - merged_content row count must be > 0
- 10_markdown_exporter/markdown_output/full_document.md
  - Non-empty; sections/ directory should exist (section markdown files)
- 14_report_generator/json_output/final_report.json
  - Required keys: { status, issues, checks } (from report generator)
- 14_report_generator/text_output/report.md
  - Non-empty

Optional / LLM-augmented Artifacts (full mode)

- 05b_table_describer/json_output/05b_tables.json
  - Keys: { tables } with llm_description/llm_title metadata
- 06b_figure_describer/json_output/06b_figures.json
  - Keys: { figures } with llm_description/llm_title metadata
- 08_extract_requirements
  - pipeline.duckdb table `requirements` exists (min row count configurable by verifier)
- 09_section_summarizer
  - `sections.llm_summary` populated for at least one section
- 08_lean4_theorem_prover
  - Verification is currently skipped (upstream certainly/lean4 updates in progress).

Verifier (fail-fast + retry)

- Use `scripts/verify_pipeline_contract.py` to run each step, verify artifacts, and retry per-step up to `--max-tries`.
- Deterministic mode skips LLM steps; full mode runs all steps:
  - `python scripts/verify_pipeline_contract.py --pdf <PDF> --mode deterministic`
  - `python scripts/verify_pipeline_contract.py --pdf <PDF> --mode full --min-requirements 1`
- Fixture-specific expectations are stored under `contracts/fixtures/` and can be enforced with:
  - `python scripts/verify_pipeline_contract.py --pdf <PDF> --fixture contracts/fixtures/<fixture>.json --mode deterministic`
- Optional LLM reasonableness judging (Codex exec) can be enabled with:
  - `python scripts/verify_pipeline_contract.py --pdf <PDF> --fixture contracts/fixtures/<fixture>.json --mode full --llm-judge`
- Lean4 verification can be skipped explicitly (default behavior until upstream fixes land):
  - `python scripts/verify_pipeline_contract.py --pdf <PDF> --mode full --skip-lean4`

Legacy / Out-of-Scope (for this contract)

- 09a PDF Annotator is not executed by `run_pipeline.py` and is excluded from this contract.

Golden Artifacts

- Expected files live under data/expected/pipeline/<slug>. Use the tools:
  - Bless: `uv run scripts/tools/expected_bless.py --pdf <PDF> --out <OUT> --expected-root data/expected/pipeline --steps 01,02,03,04,04a,05,05c,06,07,10,14`
  - Verify: `uv run scripts/tools/expected_verify.py --pdf <PDF> --out <OUT> --expected-root data/expected/pipeline --steps …`
  - Visuals: `uv run scripts/tools/expected_render.py …` + `expected_imgdiff.py` for pixel diffs.

CI Mapping

- Deterministic CI (offline):
  - Preferred: `python scripts/verify_pipeline_contract.py --pdf <PDF> --mode deterministic`
  - No network or SciLLM calls.
- Live CI (self-hosted):
  - Run LLM-inclusive pipeline + `python scripts/verify_pipeline_contract.py --pdf <PDF> --mode full --min-requirements 1`.
  - Requires CHUTES\_\* env and a resolvable scillm dependency on the runner.

Notes

- Stage 14 report generator is best-effort; if it fails, downstream consumers should tolerate a stub report.
- Prefer logging WARN lines when blocks are skipped for missing/invalid bbox/page to aid debugging and improve future parity.

Reference Fixture: BHT_CV32A65X_with_requirements_noannots.pdf

Fixture path(s)

- Absolute: /home/graham/workspace/experiments/extractor/data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf
- Repo‑relative: data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf

Deterministic expectations (no LLM)

- Stage 05 (raw fragments): exactly 9 tables in 05_tables.json.
- Stage 06 (figures): exactly 1 figure in 06_figures.json.
- Stage 07 (DuckDB): merged_content row count > 0.
- Stage 10: full_document.md exists and is non-empty.

Live expectations (LLM-enabled)

- Stage 05c (merged tables): exactly 5 logical tables for the fixture (1 merged across pages, 4 single-page).
- Stage 08 requirements: ≥ 12 total, with ≥ 2 conditional requirements for the fixture.
- Stage 09 summaries: at least 1 section has llm_summary.

Verification mapping

- 05_tables.json → counts raw tables (pre-merge)
  - Also the presence of demoted_text_blocks for rejected candidates (live).
- pipeline.duckdb → merged_content count + requirements count
- 10_markdown_exporter/markdown_output/full_document.md → final Markdown output presence

Provider/Extractor Principles

- Camelot is the source of truth for table extraction; Pandas is used for metrics only.
- Header normalization/splitting is metadata-only (header_inferred/provenance); Camelot DataFrames are not rewritten.
- Low-confidence or empty Camelot results may be LLM-confirmed (live) before acceptance; rejected candidates are recorded under demoted_text_blocks.
- SciLLM updates: `pyproject.toml` pins `scillm @ file:///home/graham/workspace/experiments/litellm`. To pick up upstream scillm changes, pull that repo and reinstall editable (`uv pip install -e ../litellm`). PyPI installs won’t apply until the dependency is moved off the file:// pin.
  - Convenience: use `scripts/update_scillm.sh` (pulls ../litellm then reinstalls editable).
  - Known benign warning: SciLLM shutdown warning is suppressed locally (pending upstream fix in paved path). Keep suppression until upstream resolves.
  - Legacy `codex_call` helper is deprecated and removed from the pipeline; SciLLM paved-path is the supported route. Demos remain under `deprecated_codex_call.py` only for historical reference.

Cross-format parity (gold standard)

- All supported input formats should converge to the same flattened structure as the canonical PDF fixture with ≥95% match rate (block kind + normalized text) in deterministic mode.
- Canonical reference: `data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json` (53 blocks; 52 text, 1 table).
- Gold artifacts: `data/input/parity_hand/clean.{html,md,rst,docx}` with re-flattened JSON under `data/input/parity_hand/reflat*.json`.
- Parity smokes:
  - `make smoke-parity-gold`: runs canonical + clean parity (HTML, MD, RST, DOCX, EPUB); reports pptx/xlsx counts.
  - `make smoke-parity-xml`: runs XML parity smoke (verifies extraction and reports counts).
  - `make smoke-parity-all`: runs all of the above.
- Passing threshold ≥0.95 currently holds for html/md/rst/docx/epub. XML is verified via smoke test (extraction success).
- CLI expectations: invocations documented in `docs/03_guides/HAPPYPATH_GUIDE.md` must yield comparable outputs across file types; section builder (04) and downstream steps must accept provider outputs uniformly.
- DOCX parity: simple mode is default (one paragraph/table per block). Set `DOCX_SIMPLE_MODE=0` to use the rich docx2python path.
- XLSX/PPTX policy: structure-first; parity not enforced. `smoke_parity_report.py` reports their counts; XLSX_SIMPLE_MODE=1 emits one table per sheet.

Interactive Workflow (Human-in-the-Loop)

- Goal: Enable human review and correction of annotations for large-scale document sets (e.g., aerospace datalakes).
- State Management:
  - Each PDF has a persistent "status" (e.g., `new`, `annotated`, `reviewed`, `done`) tracked in ArangoDB (or a local state file for offline mode).
  - User annotations are saved to a **JSON Sidecar File**: `.{pdf_filename}.annotations.json` located alongside the source PDF.
- Stage 01 (Annotation Processor) Contract Update:
  - **Input**: Must check for the existence of `.{pdf_filename}.annotations.json`.
  - **Behavior**:
    - If sidecar exists, load annotations from it.
    - Merge sidecar annotations with any embedded PDF annotations (sidecar takes precedence for conflicts).
    - Treat sidecar "boxes" as high-confidence human hints.
- UI/Pipeline Bridge:
  - The UI (Tabbed Prototype) writes the sidecar file.
  - The UI triggers the pipeline (via API).
- The Pipeline reads the sidecar, processes the document, and generates standard artifacts.
- The UI reloads the results (e.g., report/markdown output) for final verification.
