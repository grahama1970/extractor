Pipeline Steps Contract (Deterministic + Live)

Scope

- Documents minimal, testable invariants for core steps and the 09a PDF Annotator.
- Complements data/expected/pipeline/\* golden artifacts and pytest gates.

General Rules

- **Strict Coordinate System**: All spatial coordinates (bounding boxes, points) **MUST** use the Top-Left Origin system (PyMuPDF standard). Legacy formats (e.g., PDF Bottom-Left) **MUST** be normalized before leaving their respective stage.

- Steps are pure Python modules with a callable `run(...)`. No CLI frameworks (Typer/click/argparse) inside steps.
- Steps must not have import-time side effects. Loading `.env` happens in the driver or under `if __name__ == "__main__"` only.
- Each step writes to `data/results/<run>/<step>/{json_output,image_output,visual_output,logs}`.
- `stage.log` present per step when the driver provides a log sink.
- Each step exposes `sanity()` + `python -m <step> sanity` which emits a Sparta-style JSON summary via `run_step_sanity`.

Required Artifacts (deterministic mode)

- 01_annotation_processor/json_output/01_annotations.json
  - Keys: { timestamp, source_pdf, clean_pdf_path, pages, annotations }
- 02_marker_extractor/json_output/02_marker_blocks.json
  - Keys: { timestamp, source_pdf, blocks, suspicious_block_count }
- 03_suspicious_headers/json_output/03_verified_blocks.json
  - Keys: { blocks } with `verdict` on suspicious headers
- 04_section_builder/json_output/04_sections.json
  - Keys: { sections } with section bbox and page indices
- 05_table_extractor/json_output/05_tables.json
  - Keys: { tables } with per-table bbox, page, metrics (pandas_metrics, camelot_metrics)
  - Optional metadata (live):
    - header_inferred: [string,...] (do not mutate Camelot DF; metadata-only)
    - header_provenance: "llm_assist" | "spatial"
    - demoted_text_blocks: [{ page_idx:int, bbox:[...], text:str, reason:str }] for table candidates rejected (prose-like or LLM-confirmed not table)
- 06_figure_extractor/json_output/06_figures.json
  - Keys: { figures } (page or page_idx, bbox, image_path). In deterministic mode, ai_description may be stubbed.
- 07_reflow_section/json_output/07_reflowed.json (summary-only allowed for deterministic CI)
  - Keys: { reflowed_sections|sections } minimal presence
- 09_section_summarizer/json_output/09_summaries.json
  - Keys: { summaries }

09a PDF Annotator Contract
Inputs

- sections_json (04), tables_json (05), figures_json (06), optional reflowed_json (07), blocks02_json (02)

Outputs

- annotated.pdf
- json_output/annotations.json
  - Keys:
    - summary.total_overlays: int
    - summary.by*kind: dict[str,int] (section, table, figure, header_candidate, table_rejected, reflow*\* …)
    - summary.pages_touched: [int]
    - overlays: [ { overlay_id:int, page:int, bbox:[x0,y0,x1,y1], kind:str, … } ]
- json_output/legend.json (color legend)
- logs/timings.jsonl (+ timings_summary.json) best-effort

Invariants (deterministic CI)

- bbox containment: every overlay bbox lies within its page rect.
- coverage parity (tolerant):
  - by_kind.section ∈ [1, len(sections)] when sections exist
  - by_kind.table ∈ [1, len(tables)] when tables exist
  - by_kind.figure ∈ [0, len(figures)] when figures exist
- total_overlays = sum(by_kind.values).
- pages_touched is non-empty and numbers are 1-based page indices.
- table_rejected count may be 0 (offline demoters can be absent depending on input).

Invariants (live CI additions)

- 07_reflowed.json has ≥ 1 reflowed section.
- timings_summary.json exists and total_ms > 0.
- Optional: stage latency caps and p95 acceptance can be enforced by policy.
- 07 table blocks include header_norm and logical_table_id (used for merged overlays in 09a when available).
- 09a may include table_rejected overlays sourced from 05.demoted_text_blocks.

Golden Artifacts

- Expected files live under data/expected/pipeline/<slug>. Use the tools:
  - Bless: `uv run scripts/tools/expected_bless.py --pdf <PDF> --out <OUT> --expected-root data/expected/pipeline --steps 01,02,04,05,06,07,09`
  - Verify: `uv run scripts/tools/expected_verify.py --pdf <PDF> --out <OUT> --expected-root data/expected/pipeline --steps …`
  - Visuals: `uv run scripts/tools/expected_render.py …` + `expected_imgdiff.py` for pixel diffs.

CI Mapping

- Deterministic CI (offline):
  - Pytest: tests/test_pipeline_annotator_offline.py validates 01→06(+06b)→09a and 09a contract above.
  - No network or SciLLM calls.
- Live CI (self-hosted):
  - make ci-live → runs LLM-inclusive pipeline + scripts/ci/verify_live_pipeline.py checks.
  - Requires CHUTES\_\* env and a resolvable scillm dependency on the runner.

Notes

- If any upstream object lacks bbox/page, 09a may skip that overlay; CI tolerance allows ≤ expected counts while we improve resilience/logging.
- Prefer adding WARN lines in 09a when an overlay is skipped for missing/invalid bbox/page to aid debugging and improve future parity.
- Stage 14 report generator is optional; the primary human-facing journal is `walkthrough.md` produced alongside 09a.

Reference Fixture: BHT_CV32A65X_with_requirements_noannots.pdf

Fixture path(s)

- Absolute: /home/graham/workspace/experiments/extractor/data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf
- Repo‑relative: data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf

Deterministic expectations (no LLM)

- Stage 05 (raw fragments): exactly 9 tables in 05_tables.json.
- Stage 06 (figures): exactly 1 figure in 06_figures.json.
- Stage 09a (annotator):
  - bboxes contained within page bounds
  - total_overlays = sum(by_kind)
  - by_kind.section ∈ [1, len(sections04)]
  - by_kind.table ∈ [1, len(tables05)]
  - by_kind.figure ∈ [0, len(figures06)]

Live expectations (LLM-enabled)

- Stage 07 reflowed_json:
  - Sections: exactly 3 reflowed sections
  - Tables (merged): exactly 5 logical tables total, with ≥ 1 merged across pages {0,1} and 4 unmerged (single-page) tables
- Stage 07r requirements: ≥ 12 total, with ≥ 2 conditional requirements
- Stage 06 figures: exactly 1 figure, and 09a by_kind.figure ≥ 1
- 09a: merged_table_groups ≥ 1 (when logical_table_id propagation is present); table_rejected ≥ 0 (tolerant).

Verification mapping

- 05_tables.json → counts raw tables (pre-merge)
  - Also the presence of demoted_text_blocks for rejected candidates (live).
- 07_reflowed.json → counts merged logical tables and sections
- 07_requirements.json → counts total and conditional requirements
- 06_figures.json and 09a annotations.json → figure presence (source + overlay)

Provider/Extractor Principles

- Camelot is the source of truth for table extraction; Pandas is used for metrics only.
- Header normalization/splitting is metadata-only (header_inferred/provenance); Camelot DataFrames are not rewritten.
- Low-confidence or empty Camelot results may be LLM-confirmed (live) before acceptance; rejected candidates are recorded under demoted_text_blocks and visualized by 09a as table_rejected overlays.
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
  - The UI reloads the results (e.g., `09a` output) for final verification.
