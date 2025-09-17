# url:

## Issue
Location: /classic (Classic Three-Panel Layout)
Task: Remove the pane labels (Explorer, Annotation, Inspector) and reclaim ~70px whitespace so the center pane has more annotation space.

## Context
Current layout renders three H2 pane labels above the panels:
- Explorer (left)
- Annotation (center)
- Inspector (right)

These headings and their margins consume valuable vertical space; they are no longer needed.

## Desired Behavior
- No "Explorer", "Annotation", or "Inspector" pane labels are visible.
- The center canvas sits closer to the top container (gap noticeably reduced, target < 24px).

## Acceptance
- [ ] No H2 (or visible element) with innerText matching Explorer|Annotation|Inspector.
- [ ] The vertical gap from the center content container to the canvas top is < 24px.

## Routes
- /classic

## Selectors (if known)
- Canvas: `document.querySelector('canvas')`
- Center overlay container: `document.querySelector('[data-testid="overlay"]')`

## Smokes to add
- scripts/smokes/issue_013.mjs

## Artifacts
- scripts/artifacts/issue_013_*.{log,png}

## Meta
- id: 013
- created_at: (auto)

Last_smoke_at: (pending)
Last_suite_at: (pending)
Status: Open
