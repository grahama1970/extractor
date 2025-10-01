# 009 — Requirements Miner and Workbench (Stage 07½)

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done

Purpose
- Add a deterministic, offline‑friendly requirements identification step after Stage 07 (reflow), and provide a UX workbench to fix low‑quality requirements before formalization/proving (Stage 08). Keep the single CLI surface and Happy Path guarantees.

Scope (Happy Path‑aligned)
- One CLI: `python -m src.cli extract --mode accurate` always runs the miner after Stage 07.
- Proving stays opt‑in (`--prove`). No extra user flags for the miner.
- Artifacts: strict JSONs and clear summaries; smokes write artifacts under `scripts/artifacts/`.

Out of scope (for this issue)
- Full UI implementation — we only define selectors and server endpoints needed. A follow‑up UX task will wire the pane.
- ML models — miner is deterministic with optional LLM assist behind an env toggle.

Deliverables
- Stage: `src/extractor/pipeline/steps/07_requirements_miner.py`
- Runner integration: call miner between 07 and 08 in `src/extractor/pipeline/run_all.py`
- Artifacts:
  - `07_requirements.json` (see schema below)
  - `07_requirements_summary.json` (counts, modality/condition histograms)
  - `08_requirements_enriched.json` (Stage 08 adds status/diagnostics)
- Smokes: 5 pipeline, 1 UX stub (listed below)
- Docs: brief note in `docs/03_guides/HAPPYPATH_GUIDE.md` (miner runs automatically)

JSON schema (minimal, stable)
```
{
  "requirements": [
    {
      "id": "req_000123",
      "source": {"section_id": "section_0", "page_num": 2, "bbox": [x0,y0,x1,y1], "block_ids": ["/page/2/Text/3"]},
      "from": "paragraph|bullet|table_cell",
      "text_raw": "REQ-…: The controller shall …",
      "text_canonical": "The controller shall …",
      "modality": "shall|must|should|will|rule|constraint",
      "condition": "if/when/unless …" | null,
      "confidence": 0.0–1.0,
      "units": [{"var":"V","value":"3.3","unit":"V","normalized":"volt"}] | [],
      "tags": ["timing","safety"]
    }
  ]
}
```

Pipeline tasks
1) Miner step (deterministic core)
- [ ] Add `src/extractor/pipeline/steps/07_requirements_miner.py` with Typer CLI (`run`, `debug-bundle`).
- [ ] Inputs: `07_reflowed.json` (sections, para/bullets, tables).
- [ ] Heuristics: modality regex; sentence splitting; table‑cell constraint capture; requirement ID patterns (REQ‑*).
- [ ] Condition extractor: `\b(if|when|unless)\b … \b(shall|must|will|should)\b`.
- [ ] Canonicalization: de‑dup whitespace; split multi‑req paragraphs; normalize bullets/IDs.
- [ ] Confidence scoring: combine modality + position + ID presence (+ header level signal).
- [ ] Outputs: `07_requirements.json`, `07_requirements_summary.json`.
- [ ] Optional LLM assist (env‑gated; cached); never required for offline.

2) Wire into runner
- [ ] In `run_all.py`, call miner between Stage 07 and Stage 08 (respect `--offline`).
- [ ] Ensure `--prove` behavior unchanged. No new flags.
- [ ] Add manifest/resume marks for `07_requirements_miner`.

3) Stage 08 enrichment
- [ ] Accept `07_requirements.json` (batch API stays same). 
- [ ] Always write `08_requirements_enriched.json` with per‑item status:
  - new|edited|ready_for_formal|compile_error|unproved|proved
  - `compile_log`, `lean_code?`, `diagnostics[]`.
- [ ] Preserve `08_theorems.json` for proofs summary.

4) Stage 10/11/14 threading
- [ ] Stage 10: attach `rtm.lean4_status`, `compile_ok` to flattened objects; carry evidence.
- [ ] Stage 11: already writes `proves` edges; confirm requirement IDs are graph nodes/attrs when available.
- [ ] Stage 14: include counts in `run_summary.json` and a “Requirements” section in `final_report.md`.

Server/API tasks (prototype server)
- [ ] GET `/api/requirements/list?results_dir=…` → merge of 07/08 views.
- [ ] POST `/api/requirements/save` → persist `text_canonical` edits; mark `edited`/`ready_for_formal`.
- [ ] POST `/api/requirements/rerun` → re‑run Stage 08 for filtered items.

UX selectors (for follow‑up pane)
- [ ] `req-pane`, `req-item`, `req-status`, `req-edit`, `req-save`, `req-rerun-batch`, `req-log`, `req-jump`.

Smokes (to add)
Pipeline (offline by default)
- [ ] `scripts/smokes/pipeline/requirements/smoke_07_miner_sentences.py`
  - Assert ≥N sentence‑level requirements with modality + evidence; write `scripts/artifacts/req_miner_sentences.json`.
- [ ] `scripts/smokes/pipeline/requirements/smoke_07_miner_table_cells.py`
  - Assert table‑cell constraints captured with row/col context; artifact `req_miner_table.json`.
- [ ] `scripts/smokes/pipeline/requirements/smoke_08_compile_statuses.py`
  - Deterministic/no‑LLM run; ensures `compile_error` is recorded for malformed input; artifact `req_compile_status.json`.
- [ ] `scripts/smokes/pipeline/acceptance/smoke_requirements_summary.py`
  - After accurate run, assert `run_summary.json` contains requirements counts.
- [ ] `scripts/smokes/pipeline/acceptance/smoke_requirements_ids_stable.py`
  - Ensure requirement IDs are stable across resume; artifact `req_ids_stability.json`.

UX/CDP (stub now; wire later)
- [ ] `scripts/smokes/ui_requirements_pane_stub.mjs`
  - Loads a fixture via `/api/requirements/list`, asserts list render + selectors present; saves screenshot/logs under `scripts/artifacts/`.

Artifacts (expected)
- [ ] `…/07_requirements.json`, `…/07_requirements_summary.json`
- [ ] `…/08_requirements_enriched.json`
- [ ] `scripts/artifacts/req_miner_sentences.json`, `req_miner_table.json`, `req_compile_status.json`
- [ ] `scripts/artifacts/ui_requirements_pane_stub.png`, `ui_requirements_pane_stub.log`

Operational notes
- Offline runs produce full JSONs without LLM; proving remains opt‑in.
- Use `litellm_cache` when LLM assist/proving are enabled to avoid repeated costs.
- All changes keep compatibility with `docs/03_guides/HAPPYPATH_GUIDE.md`.

Rollback
- Runner gate: set `STAGE07_REQUIREMENTS_MINER=0` to skip while retaining code.

Owner & Timeline
- Owner: Pipeline/Backend
- ETA: Miner + runner wire (1–2 days), smokes (1 day), Stage 08 enrich (0.5 day), docs (0.5 day).

