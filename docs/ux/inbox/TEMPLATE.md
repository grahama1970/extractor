# [Short, Descriptive Title]

Route: /main  
Viewport: 1440x900  
Owner (optional): @your-handle  
Date (optional): YYYY-MM-DD

## Problem
- What is confusing, broken, or missing? One or two bullets max.
- Add any short context needed to understand the screenshot(s).

## Fix Directive
- Explicit change(s) you want. Avoid ambiguity.
- Scope it narrowly (component/area + change).

## Acceptance
- One‑line, assertable rule (what we’ll verify in puppeteer/health gate).
- Example: “Toolbar does not occlude canvas; sticky inside center column.”

## Images
Paste images into this same folder and reference with relative paths. Prefer per‑route/labeled snapshots (see `npm run ux:snapshots`).

- Screenshot 1:
  ![label](./your_screenshot_1.png)
- Screenshot 2 (optional):
  ![label](./your_screenshot_2.png)

## Notes (optional)
- Extra details, edge cases, or follow‑ups.

---

How to use
- Duplicate this file (do not edit TEMPLATE.md directly):
  - Example: `docs/ux/inbox/001_toolbar_sticky.md`
- Paste PNGs directly into the new file’s folder (VS Code supports copy/paste).
- Keep image links relative (e.g., `./image.png`) so the agent can read them.
- Rebuild the index so it’s easy to find your note:
  - `npm run ux:ingest` → updates `docs/ux/index.md`

Tips
- Keep each note focused on a small slice (one component/area).
- Include Route + Viewport so we can reproduce quickly.
- If helpful, also attach fresh labeled route screenshots from:
  - `scripts/artifacts/classic_*.png`, `tabbed_*.png`, `dashboard_*.png` (via `npm run ux:snapshots`).
