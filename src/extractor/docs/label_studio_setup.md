# Label Studio (Docker) — Setup and Usage

This project can annotate PDFs/images at scale using Label Studio. We include a simple Docker setup to run it locally and serve files directly from the repository.

## Quick start

- Prerequisites:
  - Docker + Docker Compose
- Configure credentials (recommended):
  - `cp .env.labelstudio.example .env.labelstudio`
  - Edit `.env.labelstudio` and set a secure password and desired username.
- Start the service:
  - `docker compose up -d`
- Access:
  - http://localhost:8080
  - Login using the credentials from `.env.labelstudio` (defaults shown in `.env.labelstudio.example`).

## File mapping

- We mount `./data` from the repository into the container at `/label-studio/localdata`.
- Label Studio is configured to serve local files from `/label-studio/localdata`, so PDFs and page renders placed in `./data` are visible in the UI.

## Recommended annotation pattern

- Use a rectangle (Box) to mark each target region (table, requirements, etc.).
- Add attributes on the Box (or a nearby text field) with mini‑schema:
  - `id`: e.g., `qb50_table_007`, `bht_req_001`
  - `type`: `table` or `requirements`
  - `expected_json`: relative path to gold file (e.g., `data/gold_standards/tables/007_table.json`)

This matches the machine_note structure Stage 01 already extracts from native PDF annotations, so evals remain consistent.

## Import/export

- In Label Studio, export annotations as JSON.
- A small converter can map Label Studio JSON → `machine_note` entries (id/type/expected_json) for evals or for embedding back into PDFs. If you want, we can add this converter.

## Round‑trip converters

- PDF → Label Studio (pre-annotated tasks):
  - `python -m src.extractor.tools.labelstudio.convert_pdf_annotations --pdf <marked.pdf> --out data/labelstudio --render-dpi 150`
  - Produces page images + tasks JSON with predictions so LS opens with rectangles + fields pre-filled.

- Label Studio → PDF (embed reviewed annotations back into PDF):
  - `python -m src.extractor.tools.labelstudio.ls_export_to_pdf --export <ls_export.json> --out-dir data/labelstudio/annotated_pdfs`
  - Writes copies of source PDFs annotated with rectangles + FreeText JSON (machine_note). The pipeline can read these as usual.

## Notes

- Credentials are now managed via `.env.labelstudio`; avoid committing secrets.
- If you prefer not to build from a Dockerfile, you can switch the compose service to use `image: heartexlabs/label-studio:latest` directly.
- For multi‑user setups or SSO, see Label Studio docs.
