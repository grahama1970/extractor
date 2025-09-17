# url:

## Issue
Location: Top center toolbar
Task: Add Label (tag) action missing from toolbar next to annotation actions

## Desired Behavior
- A compact tag icon button exists in the top controls row with a tooltip
- The legacy header button is removed

## Acceptance
- [ ] Button exists: [data-testid="btn-add-annotation-top"]
- [ ] Tooltip or title visible on hover
- [ ] No header button [data-testid="btn-add-annotation"] present

## Smokes to add
- scripts/smokes/add_annotation_top_menu.mjs

## Artifacts
- scripts/artifacts/add_top_menu_*.{log,png}

## Meta
- id: 012
- Status: Fixed
