# 008 — UX × Pipeline Alignment (Happy Path)

Owner: Agents/Engineering  
Date: 2025‑09‑19

Goal
- Tighten the PDF annotation UX around Happy Path while keeping the single CLI surface intact. Add targeted smokes to isolate complexity and prevent regressions.

References
- docs/03_guides/HAPPYPATH_GUIDE.md
- USER_FLOW.md
- docs/STATE_OF_PROJECT.md (Auto‑Run Validation)

Acceptance (Definition of Done)
- [ ] Typecheck passes; UX health gate passes (no overlays, no console/page errors; toolbarClear=true; pointerDrawOk=true).
- [ ] New smokes pass locally and produce artifacts under `scripts/artifacts/`.
- [ ] No new backend surfaces required for MVP (prototype endpoints only); CLI remains `python -m src.cli extract`.

Milestones & Tasks (with Smokes)

1) Search UX — highlights + thumbnail markers (DONE)
- [x] In‑page hit highlights (normalized boxes) — `[data-testid="hit-box"]`
- [x] Thumbnail hit markers — `[data-testid="thumb-hit"]`
- [x] Smoke: `scripts/smokes/ui_search_highlight_thumb.mjs`

2) Keyboard‑only core (DONE)
- [x] `[` / `]` paging, `N` draw, `?` help, `Esc` cancel
- [x] Smoke: `scripts/smokes/ui_keyboard_core.mjs`

3) Zoom ergonomics (DONE)
- [x] Fit to width / Fit to page buttons; space‑bar pan
- [x] Smoke: `scripts/smokes/ui_zoom_fit_pan.mjs`

4) Selection handles & resize (MVP)
- [ ] 8 handles with adequate hit‑area; drag to resize; keyboard nudge (arrows)
- [ ] Smoke: `scripts/smokes/ui_selection_handles_resize.mjs`

5) Thumbnails virtualization (MVP)
- [ ] Virtualized rails remain stable; rail present and interactive in left/bottom modes
- [ ] Smoke: `scripts/smokes/ui_thumbnails_virtualized.mjs`

6) Comments/Threads (MVP; local only)
- [ ] Right‑pane minimal thread list bound to selection; `@mention` from recent reviewers; author/timestamp
- [ ] Smoke (skip‑tolerant until implemented): `scripts/smokes/ui_comments_threads_panel.mjs`

7) A11y & Escape behavior
- [ ] Visible focus on actionable elements (toolbar, handles, dialogs)
- [ ] `Esc` closes help/dialogs; tab order sane
- [ ] Smoke: `scripts/smokes/ui_a11y_focus_escape.mjs`

8) Pipeline glue & conflicts (DONE)
- [x] Load pipeline annos uses latest pointer or request trail
- [x] Conflicts load/resolve — fall back to artifact file when list endpoint absent
- [x] Smokes: `scripts/smokes/ui_load_pipeline_annos_from_latest.mjs`, `scripts/smokes/ui_conflicts_load_and_resolve.mjs`

How to run (subset)
```bash
BASE_URL=http://127.0.0.1:8080/main \
node scripts/ux_check_broken.mjs

BASE_URL=http://127.0.0.1:8080 \
node scripts/smokes/ui_keyboard_core.mjs && \
node scripts/smokes/ui_search_highlight_thumb.mjs && \
node scripts/smokes/ui_zoom_fit_pan.mjs && \
node scripts/smokes/ui_selection_handles_resize.mjs && \
node scripts/smokes/ui_thumbnails_virtualized.mjs && \
node scripts/smokes/ui_a11y_focus_escape.mjs && \
node scripts/smokes/ui_comments_threads_panel.mjs && \
node scripts/smokes/ui_conflicts_load_and_resolve.mjs
```

Notes
- New smokes are skip‑tolerant when a feature is not yet implemented (return OK with a `skip=` note). Enable hard‑enforcement by removing the skip path once each slice lands.

