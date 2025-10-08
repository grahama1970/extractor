## Quick Start (Strict and Reliable)

These commands assume:
- Linux/macOS shell
- venv at `.venv/`
- `.env` contains CHUTES_API_BASE=/v1, CHUTES_API_KEY, and model slugs

### 0) Environment
```bash
source .venv/bin/activate && set -a && source .env && set +a
export PYTHONPATH=$(pwd)/src
```

### 1) Run PDF pipeline to Stage 06 (captions)
```bash
python -m extractor.pipeline.steps.01_annotation_processor run \
  data/pdfs/qb50_system_requirements_and_recommendations_marked.pdf \
  -o data/results/pipeline

python -m extractor.pipeline.steps.02_marker_extractor run \
  data/pdfs/qb50_system_requirements_and_recommendations_marked.pdf \
  -o data/results/pipeline --output-suffix with_requirements --no-spawn

python src/extractor/pipeline/steps/03_suspicious_headers.py run \
  data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks_with_requirements.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline -c 1 --dpi 150

python src/extractor/pipeline/steps/04_section_builder.py run \
  data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline

python src/extractor/pipeline/steps/05_table_extractor.py run \
  data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline

FIGURE_MAX_CONCURRENCY=1 \
python src/extractor/pipeline/steps/06_figure_extractor.py run \
  data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks_with_requirements.json \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline
```

### 2) Stage 07 Strict Reflow (MED VLM, selective vision)
```bash
export LITELLM_VLM_MODEL="$LITELLM_MED_VLM_MODEL"
export STAGE07_STRICT_JSON_SCHEMA=1   # prefer json_schema
export STAGE07_VISION_SELECTIVE=1
export STAGE07_TIMEOUT=200
export MAX_CONCURRENT_LLM_CALLS=1 LITELLM_MAX_PARALLEL=1
export LITELLM_NUM_RETRIES=2 LITELLM_RETRY_AFTER_MIN=0.5

python src/extractor/pipeline/steps/07_reflow_section.py run \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
  --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
  -o data/results/pipeline --timeout 200
```

### 3) Structured Providers (HTML/Markdown)
#### HTML (placeholders for tables/images)
```bash
python - <<'PY'
from extractor.core.providers.html import HTMLProvider
doc = HTMLProvider().extract_document('data/html/sample_bht.html')
print('Blocks:', len(doc.blocks), 'schema:', doc.metadata.format_metadata.get('schema_version'))
PY
```

#### Markdown (root heading + merges)
```bash
python - <<'PY'
from extractor.core.providers.markdown import MarkdownProvider
doc = MarkdownProvider().extract_document('data/md/sample.md')
print('Blocks:', len(doc.blocks), 'schema:', doc.metadata.format_metadata.get('schema_version'))
PY
```

### 4) Logs & Artifacts
- Stage 07 responses: `data/results/pipeline/07_reflow_section/logs/`
- Router retries/backoff: `data/results/pipeline/logs/litellm_call.log`

### 5) Common Issues
- 404/NotFound: model slug not provisioned; verify with `debug/chutes_list_models.py`
- 429: keep concurrency=1; ensure `Retry-After` honored; selective vision reduces payload
- Empty responses on Gemini: avoid setting `max_tokens` for strict calls; use json_schema where possible

