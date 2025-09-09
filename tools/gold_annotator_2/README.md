# Gold Annotator 2 — Tasks Index

- Start here: `docs/tasks/001_Task_Build.md` (single unified checklist + progress meter).
- This repo iteration starts fresh; previous task files are consolidated into the one build checklist.

Progress meter

- Update the progress bar at the top of `001_Task_Build.md` by running:
  - `python scripts/update_checklist_progress.py tools/gold_annotator_2/docs/tasks/001_Task_Build.md`

Notes

- Screenshots follow the convention used in the checklist (under `tools/gold_annotator_2/docs/screenshots/...`).
- Automation/E2E scripts can read `- [ ]` items if you want to track progress programmatically.

Quick start (after Node/npm available)

- `cd tools/gold_annotator_2`
- `npm i`
- Copy the PDF.js worker: `cp node_modules/pdfjs-dist/build/pdf.worker.min.js public/pdf.worker.min.js`
- `npm run dev` and open `http://localhost:3002`
- Use the file picker to load a local PDF; navigate with Prev/Next and Zoom.
