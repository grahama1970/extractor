# Tabbed PDF Annotation Prototype (React + Tailwind + ShadCN)

Interactive UI prototype for PDF viewing and annotation with three layouts (Classic, Tabbed, Dashboard). Built with Vite, React, Tailwind, and ShadCN; renders PDFs via pdfjs-dist. Includes keyboard-first workflows, subtle selection/hover treatments, and thumbnail rails/filmstrips.

- Routes
  - `/` index (links to demos)
  - `/classic` or `/main` three‑panel annotator (left file list, center canvas, right inspector)
  - `/tabbed` tabbed sidebar prototype with floating tools
  - `/dashboard` cards demo

- Quick Start
  - Install deps: `npm ci`
  - Dev server: `npm run dev` (Vite on 8080, proxies `/api` and `/ws` to the backend in dev)
  - Build: `npm run build`
  - Preview: `npm run preview` or `npm run preview:8080`
  - Type check: `npx tsc --noEmit`
  - Lint: `npm run lint`

- Backend integration (dev)
  - Vite dev proxies `/api` and `/ws` to an auto‑detected backend (`127.0.0.1:{8000|8001}`) via `vite.config.ts`. Override with `VITE_API_PROXY=http://127.0.0.1:8000 npm run dev`.
  - Expected endpoints (FastAPI server examples):
    - `GET /api/list` → list of PDFs `{ name, rel, size? }`
    - `GET /api/pdf?rel=...` → PDF bytes (pdfjs-dist loads this)
    - `POST /api/ux/generate { prompt, image }` → JSON model output (table extractor prototype)
    - `POST /api/export/pdf|zip` → annotated PDF or combined ZIP

## Classic Layout (key features)

- Three panes: left explorer + thumbnail rail, center PDF canvas with annotation overlay, right inspector
- Thumbnails: left rail or bottom filmstrip or off (persisted; localStorage `anno_thumb_mode`)
- Selection + editing:
  - Click boxes to select; drag to move; eight handles to resize (snap guides)
  - Duplicate (D/Ctrl+D), Delete (Del), arrow‑key nudge (Shift = larger steps)
  - Draw mode (N) creates a new box via drag; Shift constrains to ~4:3; Esc cancels
- Suggestions (Tables):
  - Fetch suggestions via Camelot; suggested boxes appear with dashed outlines and inline Accept/Reject.
  - “Accept all” applies all current page suggestions in one click.
- Inspector (right):
  - Label Type (select) — changing type updates instance ID prefix automatically (e.g., `table-ro3` → `section-ro3`, suffix preserved)
  - Instance ID (free edit)
  - Generate JSON (non‑blocking chip shows progress)
- Label chip above selected box gains a tasteful highlight ring; non‑selected chips remain neutral
- Top toolbar: pager (First/Prev/Next/Last), zoom slider, Night page toggle; compact, non‑occluding center canvas

### Keyboard Shortcuts

- `N` arm draw mode; drag to create
- `[` / `]` previous/next page
- `+` / `-` zoom in/out; `Ctrl/Cmd+0` reset
- `D` or `Ctrl+D` duplicate selected box; `Delete` remove
- Arrow keys nudge selection (Shift = larger)
- `H` toggle HUD attach/free; `R` reset HUD position
- `Esc` cancel draw

### Subtle Hover + Hit Areas

- File list rows (left rail) and Open PDF dialog items use a full‑row 48px hit area with subtle hover (`hover:bg-muted`) and clear `aria-selected`/focus ring states.
- Selected rows show an accent ring/stripe for discoverability.

### Data Test IDs (for smokes)

- Page label: `[data-testid="page-label"]`
- Canvas overlay: `[data-testid="overlay"]`; annotation: `[data-testid="box"]`
- Label chip: `[data-testid="box-chip"]`
- Open PDF button: `[data-testid="btn-open-pdf"]`; open dialog: `[data-testid="open-dialog"]`; items: `[data-testid="open-item"]`
- Inspector: label type trigger `[data-testid="inspector-label-type"]`; instance id `[data-testid="inspector-instance-id"]`

### Thumbnail Modes

- Left rail: vertical Virtuoso list with page numbers, active indicator
- Bottom filmstrip: horizontal Virtuoso, compact single‑row for small docs
- Off: hides thumbnails (use pager or shortcuts to navigate)

### Exports (left rail)

- Export JSON, Export Annotated PDF, Export Both (ZIP)
- Export menu reveals on row hover/focus; disabled until file is active
- COCO Export: from HUD or left rail; “Open artifacts” link + “Copy path” in toast
- Per‑page and selection JSON export available from HUD

## Dev and Testing

- From repo root, run UX gates and smokes (saves artifacts to `scripts/artifacts/`):
  - Health gate (attach to Browserless/Chrome CDP): `npm run ux:check:cdp`
  - Non‑CDP health (launches a local Chrome): `npm run ux:check`
  - Full smokes: `node scripts/smokes/all.mjs` (requires live servers + CDP)
  - One‑command local CI (servers + gates + suite): `make ci`
- Start servers via VS Code Tasks:
  - `Prototype: Preview (0.0.0.0:8080)` or `Prototype: Dev (vite on 8080)`
  - `Backend: FastAPI (8000)` or the compound `Run: Backend + Preview`
- Chrome CDP (if not using Browserless): `google-chrome --remote-debugging-port=9222`

## Happy Path (MVP)

- Open a PDF from the left rail (or the Open dialog)
- Draw/select/label boxes on the current page (keyboard shortcuts above)
- Optional: Suggest Tables → Accept/Reject
- Generate JSON (non‑blocking); Export COCO/JSON/Annotated PDF
- Autosave persists per‑PDF annotations locally; re‑open is instant

## Tech Stack

- React 18, TypeScript, Vite, Tailwind, ShadCN
- pdfjs-dist for rendering PDFs
- react-virtuoso for virtualized lists (thumbnails, annotation list)

## Troubleshooting

- Blank page or errors:
  - Ensure the dev/preview server is running on 8080
  - For API calls, run the FastAPI backend on 8000/8001 or set `VITE_API_PROXY`
  - Run `npm run dev:force` to bust Vite cache if CSS/TS changes aren’t picked up
- Health gate failures (overlay/console errors): fix client errors, ensure routes mount, confirm required selectors (e.g., `[data-testid="page-label"]`)
- Thumbnails missing: confirm `/api/pdf?rel=...` returns valid bytes; fallback `public/bht.pdf` is used when backend is down

## Project Scripts

- `dev` start Vite dev server (proxies `/api`, `/ws`)
- `dev:force` dev with `--force` to refresh caches
- `build` production build
- `build:dev` development mode build
- `preview`/`preview:8080` serve built assets
- `lint` ESLint

## Notes

- The prototype intentionally prefers non‑blocking UI patterns and subtle visual states for better scanability.
- Smokes and UX checks live at the repo root (`scripts/`); see the root README’s “CI Quick Start” for end‑to‑end steps.
