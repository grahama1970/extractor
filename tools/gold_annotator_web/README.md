# Gold Annotator Web

A Next.js 14 app for rendering PDFs to images, drawing annotation boxes, extracting content, and exporting annotated PDFs.

Quick start

- Install JS deps: `npm i`
- Install Python deps (for backend scripts): e.g., `pip install pymupdf`
- Start dev server: `npm run dev` (default `http://localhost:3002`)

Checklists and screenshots

- Persistent task checklists live under `docs/tasks`. Start with `docs/tasks/README.md`.
- Save screenshots under `docs/screenshots/<flow>/NN_title.png`.

Puppeteer interactions

- JSON flows are in `tests/interactions`. Runner: `npm run interactions`.
- Filter runs: `npm run interactions -- --pattern render,boxes_and_hud`.
- Override base URL: `BASE_URL=http://localhost:3002 npm run interactions`.

Notes

- Some API routes call Python scripts (render, crop, extract, export). Ensure `python3` is available and required packages are installed.
- If selectors change, update `tests/interactions/*.json` or enhance the runner.

