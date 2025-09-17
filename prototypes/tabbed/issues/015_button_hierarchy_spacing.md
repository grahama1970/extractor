## Issue
Location: /classic (Explorer + Inspector)
Task: Apply clear button hierarchy and consistent spacing rhythm.

## Context
- Primary actions should lead visually: Open PDF, Generate JSON, Export All.
- Secondary/tertiary actions should be outline/ghost.
- Adopt an 8px spacing grid for consistent rhythm.

## Desired Behavior
- Open PDF, Generate JSON, Export All use primary styling (brand color).
- Per-file export buttons use outline styling.
- Core stacks use gap-2/3/4/6 and space-y-3 consistently.

## Acceptance
- [ ] `btn-open-pdf` has a non-transparent background color (primary).
- [ ] `btn-generate-inspector` has primary styling.
- [ ] `btn-export-all` has primary styling.
- [ ] Left/Right panel group spacing uses `space-y-3`.

## Routes
- /classic

## Selectors
- `[data-testid="btn-open-pdf"]`
- `[data-testid="btn-generate-inspector"]`
- `[data-testid="btn-export-all"]`

## Smokes
- scripts/smokes/toolbar_hierarchy.mjs

## Meta
- id: 015
Last_smoke_at: (pending)
Last_suite_at: (pending)
Status: Open

