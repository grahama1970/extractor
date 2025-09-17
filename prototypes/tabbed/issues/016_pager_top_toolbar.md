## Issue
Location: /classic (Viewer Top Toolbar)
Task: Promote page navigation controls to the top toolbar alongside zoom.

## Context
Bottom-centered chevrons are easy to miss. Co-locating pager with primary controls improves discoverability.

## Desired Behavior
- Top toolbar contains: first/prev, slider, page label, next/last (duplicates allowed initially).
- Controls operate the same as bottom controls.

## Acceptance
- [ ] `[data-testid="top-toolbar"]` contains pager controls (btn-first/prev/next/last) and a range input (`pager-slider-top`).
- [ ] Changing the top slider updates the page label.

## Routes
- /classic

## Smokes
- scripts/smokes/page_controls_top_toolbar.mjs

## Meta
- id: 016
Last_smoke_at: (pending)
Last_suite_at: (pending)
Status: Open

