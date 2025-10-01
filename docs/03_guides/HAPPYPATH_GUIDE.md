# Happy Path Guide — Single CLI Surface

Purpose
- Provide one minimal CLI for all extractions (PDF fast/accurate and all structured formats) with predictable outputs and artifacts.
- Keep option surface small; defaults should work end-to-end without extra flags.

Principles
- One command: `python -m src.cli extract` for everything.
- Deterministic where possible: offline/fast-embedding defaults for accurate PDF runs from the CLI.
- Canonical shape: normalize to `UnifiedDocument` and Stage 10 for accurate and structured paths.

**Single Command Surface**
- `python -m src.cli extract <input> <out_dir> [--mode fast|accurate]`
- Works for:
  - PDF: choose `--mode fast` (PyMuPDF text-only) or `--mode accurate` (full pipeline with deterministic skips).
  - Structured formats: HTML, DOCX, PPTX, XLSX, EPUB, RST, XML, MD (no `--mode` needed).

**Quick Start**
- PDF (fast text-only):
  ```bash
  python -m src.cli extract \
    data/input/pipeline/BHT_CV32A65X_marked.pdf \
    data/results/fast_pdf \
    --mode fast
  ```
- PDF (accurate, normalized outputs):
  ```bash
  python -m src.cli extract \
    data/input/pipeline/BHT_CV32A65X_marked.pdf \
    data/results/pipeline \
    --mode accurate
  ```
  - Prove on demand (Lean4):
    ```bash
    python -m src.cli extract \
      data/input/pipeline/BHT_CV32A65X_marked.pdf \
      data/results/pipeline_prove \
      --mode accurate --prove
    ```
- Structured (HTML example):
  ```bash
  python -m src.cli extract \
    data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.html \
    data/results/structured_html
  ```

**Outputs**
- PDF fast:
  - `<out_dir>/<stem>_fast.json` (text-only; no normalized stages)
- PDF accurate:
  - `<out_dir>/07_reflow_section/json_output/07_reflowed.json`
  - `<out_dir>/10_arangodb_exporter/json_output/10_flattened_data.json`
  - Additional stage artifacts under `<out_dir>/<stage>/...`
- Structured formats:
  - `<out_dir>/<stem>/07_reflow_section/json_output/07_reflowed.json`
  - `<out_dir>/<stem>/10_arangodb_exporter/json_output/10_flattened_data.json`

**Verification**
- CLI smokes:
  - `uv run scripts/smokes/pipeline/smoke_cli_fast_pdf.py`
  - `uv run scripts/smokes/pipeline/smoke_cli_structured.py`
  - `uv run scripts/smokes/pipeline/smoke_cli_structured_all.py`
- Requirement extraction + proving (offline, deterministic Lean4):
  - Sentences with modal verbs → Lean4: `uv run scripts/smokes/pipeline/requirements/smoke_sentence_shall.py`
  - Bullet list inheritance → Lean4: `uv run scripts/smokes/pipeline/requirements/smoke_bullets_inherit.py`
  - Table constraints → Lean4: `uv run scripts/smokes/pipeline/requirements/smoke_table_constraints.py`
  - Formal artifact (prove and save .lean): `uv run scripts/smokes/pipeline/requirements/smoke_lean4_formal_artifact.py`
  - Merged table → Lean4 (deterministic): `uv run scripts/smokes/pipeline/requirements/smoke_table_merge_to_lean4.py`
- Stage checks (spotlight):
  - Stage 05 quality: `uv run scripts/smokes/pipeline/smoke_stage05_strategy_quality.py`
  - Meta parity across formats: `uv run scripts/smokes/pipeline/smoke_meta_parity_all_formats.py`

**Troubleshooting**
- Accurate mode requires optional deps (camelot, pandas, etc.). If it fails, ensure `pip install -e .[dev]` or install via `make setup`.
- For Arango-backed stages (10–12) in operator runs, set `ARANGO_*` env vars; CLI defaults skip DB/embeddings unless configured.
- Use `pipeline-run --json --mode fast|accurate` for operator-friendly envelopes; preferred surface for most users remains `python -m src.cli extract`.

**Agent Memory (Lessons)**
- Local memory: `memory/README.md`; shared workspace: `/home/graham/workspace/experiments/memory/README.md`.
- Use memory recall to speed pipeline/UX debugging and reuse prior fixes.
- Quick recall:
  ```bash
  make lessons-recall-last TAGS=cdp SCOPE=tabbed
  ```
- Direct query (BM25 + graph; JSON output):
  ```bash
  uv run scripts/lessons/recall_agent.py \
    --q "puppeteer connect hang" \
    --scope tabbed --depth 2 --k 5 --json
  ```
- Add a lesson after a fix:
  ```bash
  uv run scripts/lessons/add.py \
    --title "Fix: Vite overlay crash" \
    --problem "Dev overlay appears after annotation draw" \
    --playbook "Restart vite; clear .vite; check console" \
    --tags ui,overlay --scope tabbed
  ```

**Notes**
- Fast mode is for iteration only; it does not produce normalized outputs used by downstream consumers.
- Accurate mode invoked from this CLI uses deterministic toggles by default (offline-friendly) and is suitable for parity checks.

## Requirement Tuning (Stage 07½/08)

After Stage 07 (reflow), the pipeline automatically runs a deterministic Requirements Miner (Stage 07½) that writes:

- `<out_dir>/07_requirements_miner/json_output/07_requirements.json`

When you opt into proving (`--prove`), Stage 08 will also emit per‑requirement enrichment:

- `<out_dir>/08_lean4_theorem_prover/json_output/08_requirements_enriched.json`

The Classic UI exposes a minimal right‑pane workbench to fix and retry requirements without leaving `/main`:

- Refresh list: `/api/requirements/list?results_dir=…`
- Edit canonical text: POST `/api/requirements/save`
- Re‑run formalization: POST `/api/requirements/rerun`
- Jump to PDF evidence: `req-jump` (scrolls to `page_num`)

CI/Smokes (selected):
- Miner (sentences): `uv run scripts/smokes/pipeline/requirements/smoke_07_miner_sentences.py`
- Enriched statuses: `uv run scripts/smokes/pipeline/requirements/smoke_08_compile_statuses.py`

**Appendix — Useful Commands**
- PDF accurate (explicit run_all):
  ```bash
  python -m extractor.pipeline.run_all run \
    --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
    --results data/results/pipeline \
    --offline --skip-llm03 --skip-descriptions06 \
    --summary-only07 --skip-proving08 \
    --skip-export10 --fast-embeddings10 --skip-graph11
  ```
- Meta parity across all providers:
  ```bash
  uv run scripts/smokes/pipeline/smoke_meta_parity_all_formats.py
  ```
- Graph & Exporter Smokes (offline)
  - JSON‑LD export: `uv run scripts/smokes/pipeline/smoke_jsonld_export.py`
  - ReqIF export: `uv run scripts/smokes/pipeline/smoke_reqif_export.py`
  - Graph schema/health: `uv run scripts/smokes/pipeline/smoke_stage11_schema_invariants.py`
  - Proves‑only (no embeddings): `uv run scripts/smokes/pipeline/smoke_stage11_proves_only_offline.py`
  - Units conflicts: `uv run scripts/smokes/pipeline/smoke_stage11_units_conflicts.py`
  - Supersedes/Duplicates: `uv run scripts/smokes/pipeline/smoke_stage11_supersedes_min.py` / `..._duplicates_min.py`

Proving remains opt‑in (`--prove`); in offline contexts the CLI wires the live Lean4 batch CLI with `--deterministic --no-llm` for reproducible, zero‑network behavior. A formal artifact smoke confirms compiled Lean code is produced.

## Lean4 Graph — One‑Click Build (Optional, Offline‑Friendly)

Use this when you want contradictions + dependency hops + KNN neighborhoods in ArangoDB from Lean4 outputs.

Prereqs (once):
```bash
export ARANGODB_URL=http://localhost:8529
export ARANGODB_USERNAME=root
export ARANGODB_PASSWORD=…
```

Produce Lean4 artifacts (from the Lean4 repo) and copy the sidecar locally:
```bash
python -m lean4_prover.cli_mini batch \
  --input-file in.json \
  --output-file out.json \
  --deterministic --no-llm \
  --emit-edge-hints edge_hints.json
```

One‑click graph build in this repo (Extractor):
```bash
# Using edge_hints.json
make graph-oneclick DB=lean4_prod HINTS=edge_hints.json

# Or using flattened Stage 10 JSON (with lemma pass-through)
uv run scripts/pipeline/stage10_pass_through_lemmas.py out.json flat10.json
make graph-oneclick DB=lean4_prod FLAT10=flat10.json
```

What it does:
- Bootstraps DB (collections + lean4_g graph + ArangoSearch view for BM25).
- Upserts nodes/edges (with offline densification flag for lemma candidates when needed).
- Computes KNN edges from embeddings (if FLAT10 provided).
- Runs AQL recipes and writes aql_out/*.json.

Graph metrics:
```bash
make graph-metrics DB=lean4_prod
```

Dev‑rich (optional): improve lemma precision locally
```bash
export LEAN4_ANALYSIS_MODE=lsp
export LEAN4_LSP_IMPL=lake_serve
export LEAN4_ANALYSIS_TIMEOUT_S=5
# Re‑run Lean4 batch; Stage 11 will prefer used_lemmas over candidates automatically
```

Audit/Bulk import (DB-native edges JSON):
```bash
# Emit Arango-ready edge docs with _from/_to (no upsert)
make graph-emit-db-edges HINTS=edge_hints.json OUT=db_edges.json
# or
make graph-emit-db-edges FLAT10=flat10.json OUT=db_edges.json
```

CI/offline notes:
- Keep deterministic/no‑LLM for batch runs.
- Use `--fallback-lemma-candidates` (enabled by one‑click with FLAT10) to densify graphs without LSP.
- LSP/Pantograph jobs are opt‑in; do not enable in CI unless needed.
### Pre‑Feature Gate (UI)

- `cd prototypes/tabbed/html && npm run typecheck`
- `BASE_URL=http://127.0.0.1:8080/main npm run ux:check`
- DOM checks (as needed):
  - `node scripts/smokes/ui_inspector_pane_present.mjs`
  - `node scripts/smokes/ui_requirements_pane_dom.mjs`
- Artifacts: attach `scripts/artifacts/ux_check_*.{log,png}` to issues/PRs.

### Pre‑Feature Gate (Backend/CLI)

- Single CLI surface: `PYTHONPATH=src python -m src.cli extract <input> <out_dir> --mode fast|accurate`
- Pipeline smokes:
  - `python scripts/smokes/pipeline/smoke_stage10_flatten.py`
  - `python scripts/smokes/pipeline/smoke_stage11_graph.py`
  - `python scripts/smokes/pipeline/smoke_stage14_report.py`
  - `python scripts/smokes/pipeline/acceptance/smoke_requirements_summary.py`
