# Interaction Runner

JSON-driven Puppeteer flows for exercising key UI interactions and taking screenshots.

Run locally

- Install dev dep: `npm i -D puppeteer`
- Start the app: `npm run dev` (expects `http://localhost:3002` by default)
- Run interactions:
  - All: `npm run interactions`
  - Filter by names: `npm run interactions -- --pattern render,boxes`
  - Override base URL: `BASE_URL=http://localhost:3002 npm run interactions`

Files

- `render.json`, `doc_select.json`, `pagination.json`
- `boxes_and_hud.json`, `save_boxes.json`
- `crop_extract.json`, `save_gold.json`, `suggest.json`
- `keyboard.json`, `export_annotated.json`

Screenshots are written under `tools/gold_annotator_web/docs/screenshots/...`.

