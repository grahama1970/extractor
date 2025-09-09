# Label Studio Quickstart (Extractor Project)

This guide walks you through using Label Studio to annotate PDFs for our extractor pipeline. No prior Label Studio experience required.

## 0) Prerequisites
- Docker + Docker Compose installed
- Python environment with `pymupdf` if you plan to run the converters locally: `pip install pymupdf`
- This repository checked out

## 1) Start Label Studio (Docker)
- Copy env and set a strong password:
  - `cp .env.labelstudio.example .env.labelstudio`
  - Edit `.env.labelstudio` → set `LABEL_STUDIO_PASSWORD`
- Launch:
  - `docker compose up -d`
- Open the UI:
  - http://localhost:8080
  - Login with `LABEL_STUDIO_USERNAME` / `LABEL_STUDIO_PASSWORD` from `.env.labelstudio`

## 2) Preload tasks from your marked PDFs (optional but recommended)
If your PDFs already contain Box + FreeText notes (our mini-schema), convert them into pre-annotated Label Studio tasks:

- Run converter (example):
  - `python -m src.extractor.tools.labelstudio.convert_pdf_annotations \
    --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
    --out data/labelstudio \
    --render-dpi 150`
- This creates:
  - Page images: `data/labelstudio/images/<doc_id>/page_001.png`…
  - Tasks JSON (array): `data/labelstudio/tasks/<doc_id>.tasks.json`
  - Per‑task JSON (for Local files storage): `data/labelstudio/tasks/<doc_id>_local/task_001.json`, `task_002.json`, …

## 3) Create a project and configure labeling UI
- In Label Studio: “Create Project” → name it (e.g., “PDF Annotations”)
- Use this labeling config:

```
<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="label" toName="image">
    <Label value="Table"/>
    <Label value="Requirements"/>
    <Label value="Figure"/>
  </RectangleLabels>
  <Choices name="type" toName="image" perRegion="true">
    <Choice value="table"/>
    <Choice value="requirements"/>
    <Choice value="figure"/>
  </Choices>
  <TextArea name="id" toName="image" perRegion="true"/>
  <TextArea name="expected_json" toName="image" perRegion="true"/>
  </View>
```

## 4) Point Label Studio to your local files
- Settings → Storage → Local Storage → Add source storage
  - Base path: `/label-studio/localdata` (maps to repo `./data`)
  - Include: `labelstudio/images/` (where the converter placed page images)

## 5) Import pre-annotated tasks (or just import images)
- Easiest (no tokens): Settings → Cloud Storage → Add Source Storage → Local files
  - Path: `/label-studio/localdata/labelstudio/tasks/<doc_id>_local`
  - File filter: `.*\.json$`
  - Keep “Treat every bucket object as a source file” OFF
  - Save → Sync Storage
- Or: Project → Import → select `data/labelstudio/tasks/<doc_id>.tasks.json` (client upload)
- Or: Import images only via Local Storage, then draw boxes and fill fields manually

## 6) Annotate
- For each region you care about (tables, requirements, figures):
  - Draw a rectangle
  - Set `type` (table | requirements | figure)
  - Set `id` (e.g., `bht_table_001`)
  - Set `expected_json` (relative path to the gold JSON file you want to create, e.g., `data/gold_standards/tables/bht_table_001.json`)
- Save/Submit the task

## 7) Export and round‑trip back to PDFs (optional)
- Project → Export → JSON (save to `data/labelstudio/exports/<name>.json`)
- Embed reviewed annotations back into PDFs so the pipeline (Stage 01) can consume them:
  - `python -m src.extractor.tools.labelstudio.ls_export_to_pdf \
    --export data/labelstudio/exports/<name>.json \
    --out-dir data/labelstudio/annotated_pdfs`
- Output: `data/labelstudio/annotated_pdfs/<doc>_ls_marked.pdf`

## 8) Generate gold JSON stubs directly from Label Studio export (optional)
- Create or update gold files referenced by `expected_json`:
  - `python -m src.extractor.tools.labelstudio.ls_export_to_gold \
    --export data/labelstudio/exports/<name>.json \
    --repo-root .`
- What it writes:
  - For `type=table`: `{ "type": "table", "id": "...", "columns": [], "rows": [] }`
  - For `type=requirements|section`: `{ "type": "section", "id": "...", "title": "INFERRED: <id>", "columns": [], "rows": [] }`
- Use `--force` to overwrite existing files (writes a `.orig.json` backup once)

## 9) Run the extractor pipeline as usual
- The pipeline still reads PDF annotations (Boxes + FreeText mini-schema) in Stage 01
- Your LS-reviewed PDFs or gold JSONs will be used by subsequent stages/evals

## Tips & Troubleshooting
- Credentials: managed in `.env.labelstudio`; don’t commit secrets
- File visibility: the repo `./data` is mounted at `/label-studio/localdata` in the container
- DPI: page render DPI doesn’t affect coordinates—converters use percentages internally
- Need help? Export JSON and share; we can inspect and assist
