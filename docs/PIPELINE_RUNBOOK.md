# Pipeline Runbook (Offline-First, Then Online)

Goal: Methodically validate the PDF extraction pipeline end-to-end. First run "offline" (no LLM/DB calls) to confirm structure and artifacts. Then run "online" with real LLM calls (SciLLM via `CHUTES_*`) and ArangoDB export/graph.

## Prerequisites

- Python venv activated; project installed with extras.
- `.env` present and loaded. Required keys:
- `CHUTES_API_BASE`, `CHUTES_API_KEY`, and `CHUTES_TEXT_MODEL` (for online runs)
  - `ARANGO_HOST`, `ARANGO_PORT`, `ARANGO_USER`, `ARANGO_PASSWORD`
- Set `PYTHONPATH=src` when running Python modules directly.
- Canonical input PDF: `data/input/pipeline/BHT_CV32A65X_marked.pdf`

Quick environment load:

```
source .venv/bin/activate
set -a && source .env && set +a
export PYTHONPATH=$(pwd)/src
```

Sanity checks:

- LLM (online): `python scripts/tools/scillm_quick_doctor.py` (expects {"ok":true})
- Arango: quick ping in Python

```
python - << 'PY'
from arango import ArangoClient
client = ArangoClient(hosts='http://localhost:8529')
db = client.db('_system', username='root', password='openSesame')
print('Arango OK:', db.version())
PY
```

## Offline Pass (fast, structural)

Notes:
- Avoid LLM/VLM calls; skip DB writes. Confirms PDF parsing, stitching, flattening, reporting.
- Uses existing Stage 01 outputs if present.

Commands:

1) Stage 02
```
python src/extractor/pipeline/steps/02_marker_extractor.py run \
  data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.pdf \
  -o data/results/pipeline
```
2) Stage 03
```
python src/extractor/pipeline/steps/03_suspicious_headers.py run \
  data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline
```
3) Stage 04
```
python src/extractor/pipeline/steps/04_section_builder.py run \
  data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline
```
4) Stage 05
```
python src/extractor/pipeline/steps/05_table_extractor.py run \
  data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline
```
5) Stage 06 (skip descriptions)
```
python src/extractor/pipeline/steps/06_figure_extractor.py run \
  data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline \
  --skip-descriptions
```
6) Stage 07 (summary-only)
```
python src/extractor/pipeline/steps/07_reflow_section.py run \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
  --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
  -o data/results/pipeline --summary-only
```
7) Stage 08 (skip proving)
```
python src/extractor/pipeline/steps/08_lean4_theorem_prover.py run \
  data/results/pipeline/07_reflow_section/json_output/07_reflowed.json \
  -o data/results/pipeline --skip-proving
```
8) Stage 10 (flatten only)
```
python src/extractor/pipeline/steps/10_arangodb_exporter.py run \
  --reflowed  data/results/pipeline/07_reflow_section/json_output/07_reflowed.json \
  --summaries data/results/pipeline/09_section_summarizer/json_output/09_summaries.json \
  -o data/results/pipeline --skip-export
```
9) Stage 11 (no DB)
```
python src/extractor/pipeline/steps/11_arango_create_graph.py run \
  data/results/pipeline/10_arangodb_exporter/json_output/10_flattened_data.json \
  -o data/results/pipeline --skip-graph-creation
```
10) Stage 14 (report)
```
python src/extractor/pipeline/steps/14_report_generator.py run data/results/pipeline
```

## Online Pass (LLM + DB)

Notes:
- Provider: use the configured default model from `.env` (`DEFAULT_LITELLM_MODEL` or `LITELLM_DEFAULT_MODEL`).
- Concurrency: start with `--max-concurrent 8` for LLM-heavy steps.
- Timeouts: Stage 06/09 `--timeout 45`, Stage 07 `--timeout 240` (more complex prompt). You can also set `STAGE07_LLM_TIMEOUT` (seconds) to control Stage 07 strictly in CI.
 - Stage 07 knobs (when providers are finicky):
   - `STAGE07_MINIMAL_JSON=1` forces compact JSON mode
   - `STAGE07_TRIM_CHARS=1500` trims initial context
   - `STAGE07_MAX_TOKENS=2048` (non-Gemini) caps response size
   - `MAX_CONCURRENT_LLM_CALLS=3` bounds concurrency
   - `STAGE07_FIGURE_FALLBACK=1` allows a safety figure block if missing
- DB: use a non-system DB (e.g., `ARANGO_DATABASE=pdf_knowledge_base_test`).

Prepare DB (ensure it exists) by inserting annotations first:
```
export ARANGO_DATABASE=pdf_knowledge_base_test
python src/extractor/pipeline/steps/12_insert_annotations.py run \
  --annotations data/results/pipeline/01_annotation_processor/json_output/01_annotations.json \
  -o data/results/pipeline --mode insert
```

Run LLM steps:

6) Stage 06 (descriptions on)
```
python src/extractor/pipeline/steps/06_figure_extractor.py run \
  data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline
```
7) Stage 07 (full reflow)
```
python src/extractor/pipeline/steps/07_reflow_section.py run \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
  --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
  -o data/results/pipeline --timeout 240
```
9) Stage 09 (summaries)
```
python src/extractor/pipeline/steps/09_section_summarizer.py run \
  data/results/pipeline/07_reflow_section/json_output/07_reflowed.json \
  -o data/results/pipeline --max-concurrent 8 --window-size 2 --strict-json --timeout 45
```

DB stages (export + graph + annotations bridge):

10) Stage 10 (export to Arango)
```
python src/extractor/pipeline/steps/10_arangodb_exporter.py run \
  --reflowed  data/results/pipeline/07_reflow_section/json_output/07_reflowed.json \
  --summaries data/results/pipeline/09_section_summarizer/json_output/09_summaries.json \
  -o data/results/pipeline \
  --fast-embeddings   # CI-friendly deterministic vectors (optional)
```
11) Stage 11 (graph)
```
# Optional: disable rationales unless you set GRAPH_RATIONALE_MODEL to a supported provider
export GRAPH_ENABLE_RATIONALES=false
python src/extractor/pipeline/steps/11_arango_create_graph.py run \
  data/results/pipeline/10_arangodb_exporter/json_output/10_flattened_data.json \
  -o data/results/pipeline
```
12) Stage 12 (annotations bridge edges)
```
python src/extractor/pipeline/steps/12_insert_annotations.py run \
  --annotations data/results/pipeline/01_annotation_processor/json_output/01_annotations.json \
  -o data/results/pipeline --mode bridge
```

14) Stage 14 (report)
```
python src/extractor/pipeline/steps/14_report_generator.py run data/results/pipeline
```

## Per-Step Isolation (Inputs/Outputs)

Use this as a quick-reference while debugging. Mark when a step is verified.

- [ ] 01 Annotation Processor
  - In: `data/input/pipeline/BHT_CV32A65X_marked.pdf`
  - Out: `01_annotation_processor/json_output/01_annotations.json`, `*_clean.pdf`
- [ ] 02 Marker Extractor
  - In: Stage 01 clean PDF
  - Out: `02_marker_extractor/json_output/02_marker_blocks.json`
- [ ] 03 Suspicious Headers
  - In: Stage 02 blocks, `--pdf-dir` to Stage 01 dir
  - Out: `03_suspicious_headers/json_output/03_verified_blocks.json`
- [ ] 04 Section Builder
  - In: Stage 03 JSON, `--pdf-dir` Stage 01 dir
  - Out: `04_section_builder/json_output/04_sections.json`
- [ ] 05 Table Extractor
  - In: Stage 04 JSON, `--pdf-dir` Stage 01 dir
  - Out: `05_table_extractor/json_output/05_tables.json`
- [ ] 06 Figure Extractor
  - In: Stage 02 + 04, `--pdf-dir` Stage 01 dir
  - Out: `06_figure_extractor/json_output/06_figures.json`, images
- [ ] 07 Reflow Section
  - In: Stage 04/05/06 (+ optional annotations)
  - Out: `07_reflow_section/json_output/07_reflowed.json`
- [ ] 08 Lean4
  - In: Stage 07 JSON
  - Out: `08_lean4_theorem_prover/json_output/08_theorems.json`
- [ ] 09 Section Summarizer
  - In: Stage 07 or 08 JSON
  - Out: `09_section_summarizer/json_output/09_summaries.json`
 - [ ] 09a PDF Annotator (post‑reflow)
  - In: Stage 01 clean PDF, Stage 04/05/06 JSONs, Stage 07 reflow JSON, Stage 02 blocks
  - Out: `09a_pdf_annotator/annotated.pdf`, `09a_pdf_annotator/json_output/annotations.json`
- [ ] 10 Arango Export
  - In: Stage 07 + 09 JSON
  - Out: `10_arangodb_exporter/json_output/10_flattened_data.json` + confirmation when exporting
- [ ] 11 Graph Create
  - In: Stage 10 flattened JSON
  - Out: `11_arango_create_graph/json_output/11_graph_edges.json` or confirmation when exporting
- [ ] 12 Insert Annotations
  - In: Stage 01 annotations JSON
  - Out: `12_insert_annotations/json_output/12_insert_confirmation.json`
- [ ] 14 Report Generator
  - In: results dir
  - Out: `final_report.json`, `final_report.md`

## Notes and Tips

- If litellm_call fails due to provider JSON enforcement, toggle `--strict-json/--no-strict-json` on Stage 09.
- For Stage 11 rationales, set `GRAPH_RATIONALE_MODEL` to your provider (e.g., Gemini) or set `GRAPH_ENABLE_RATIONALES=false`.
- Keep `LITELLM_ATTACH_SESSION=true` (default) for better cache namespacing.
### One Way To Call Chutes (Paved Path)

We use exactly one allowed shape for Chutes calls (no alternates, no discovery):

- Provider: `openai_like`
- Auth: `Authorization: Bearer $CHUTES_API_KEY` (never x-api-key)
- Single pinned model: `CHUTES_TEXT_MODEL` set to a vendor id that returns 200 on `/chat/completions`
- JSON mode only: `response_format={"type":"json_object"}`
- Router lifecycle: stages close routers automatically at the end

Environment (CI/prod)

```
export CHUTES_API_BASE=https://llm.chutes.ai/v1
export CHUTES_API_KEY=cpk_...
export CHUTES_TEXT_MODEL=moonshotai/Kimi-K2-Instruct-0905
unset SCILLM_AUTO_ROUTER CHUTES_TEXT_MODEL_ALT1 CHUTES_TEXT_MODEL_ALT2 CHUTES_AUTH_STYLE
```

Sanity probes (must succeed before long runs)

```
curl -sS -w '%{http_code}\n' -o /dev/null \
  -H "Authorization: Bearer $CHUTES_API_KEY" \
  "$CHUTES_API_BASE/models"   # expect 200

printf '%s' '{"model":"'"$CHUTES_TEXT_MODEL"'","messages":[{"role":"user","content":"Return only {\"ok\":true} as JSON."}],"response_format":{"type":"json_object"}}' >/tmp/payload.json
curl -sS -w '%{http_code}\n' -o /tmp/chat.json \
  -H "content-type: application/json" \
  -H "Authorization: Bearer $CHUTES_API_KEY" \
  -d @/tmp/payload.json \
  "$CHUTES_API_BASE/chat/completions"  # expect 200
```

If you see “Unmapped LLM provider”, your pinned model id is not routed to `/chat/completions` on this host. Set `CHUTES_TEXT_MODEL` to a routable id and re‑probe.
