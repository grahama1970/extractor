# Pipeline Happy Path Checklist (Draft)

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## 0) Happy Path Spec + CLI

- [ ] Create `pipeline.yaml` spec (PDF list, options, Arango config)
- [ ] Implement CLI verbs (mirroring docs/03_guides/HAPPYPATH_GUIDE.md):
  - [ ] `python -m prototypes.extract.cli init`
  - [ ] `python -m prototypes.extract.cli run --spec pipeline.yaml`
  - [ ] `python -m prototypes.extract.cli open [--run-id]`
  - [ ] `python -m prototypes.extract.cli replay <run_id>`
- [ ] Persist spec snapshots under `workspace/runs/<run_id>/`
- [ ] Log backend/dashboard URLs per run for `open`
- [ ] Optional run notes saved alongside artifacts

## 1) Stage 05 – Camelot Strategy Search

- [ ] Implement per-table strategy candidates (`line_scale` variations, `process_background`) 
- [ ] Integrate vision transcription (Gemini) for similarities (use `SequenceMatcher`/`rapidfuzz`) 
- [ ] Cache best-performing strategy for subsequent tables; fallback if quality drops
- [ ] Record `pandas_df_raw`, sanitized `pandas_df`, and `fragmentation_score` (already started)
- [ ] Log chosen strategy + quality metrics per table

## 2) Stage 06 / Stage 07 – Strict Prompts & Logging

- [ ] Stage 06 (figure extraction) enforce strict JSON schema; fail early on invalid responses
- [ ] Stage 07 prompt includes prompt version; capture sanitized table block in artifacts
- [ ] Log `table_cells_sanitized` with original/sanitized values (done)
- [ ] Add run artifact bundling Stage 07 context, raw response, parsed JSON, contract verdict

## 3) Batch Workflow (Annotate → Extract → QA)

- [ ] Extend spec to accept multiple PDFs
- [ ] Batch run loop with per-PDF run IDs and snapshots
- [ ] Write sanitized outputs (tables, sections) to ArangoDB (Stage 10) and verify embeddings
- [ ] Stage 11 FAISS index ready for question answering
- [ ] Add QA smoke: run simple question against sanitized data and check answer provenance

## 4) Observability & Smokes

- [ ] Update `smoke_stage05_table_image_compare.py` to fail if sanitized mismatch occurs (currently warns)
- [ ] Add smoke for batch spec (multi-PDF) run with fixtures
- [ ] Add smoke for `pipeline.yaml` CLI (init/run/open/replay) using fixtures
- [ ] Document artifacts location: logs per stage, sanitized diffs

## 5) Documentation & Contribution Guardrails

- [ ] Update docs: `docs/runbook.md`, `docs/observability.md`, `docs/prompts.md`, `docs/rules.md`
- [ ] `CONTRIBUTING_AGENT.md` outlining allowed edits (prompts/rules/adapter/tests)
- [ ] CI guard rails: protected paths, cost ceilings, artifact retention

## 6) Optional / Later

- [ ] Integrate optional Stage 08–12 (Lean, Graph, Annotations) with Arango flows 
- [ ] Nightly drift tests on goldens once strict prompt path is green
- [ ] Additional dashboards or QA UI hooks once MVP stable

---

*Notes*: Checklist complements existing `001_smokes.md` and `002_smokes_amended.md`. Mark items as `[x]` once merged. EOF
