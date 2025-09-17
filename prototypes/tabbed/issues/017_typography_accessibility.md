## Issue
Location: /classic (global)
Task: Typographic scale + focus/contrast AA pass.

## Context
Hierarchy and focus visibility need a consistent system:
- Titles (text-lg/semibold)
- Group labels (text-sm/medium)
- Help text (text-xs text-muted-foreground)
- Body (text-sm)
Ensure focus rings are consistent and WCAG AA contrast holds across light/dark.

## Desired Behavior
- All actionable controls have `focus-visible:ring-2 ring-offset-2` and maintain AA contrast.
- Labels use standardized sizes; help text is consistently muted.
- Chips/tags and toolbar elements meet AA when over tinted backgrounds.

## Acceptance
- [ ] Random sampling of buttons/inputs/switches shows consistent focus ring classes.
- [ ] Labels/help text sizes match the scale above.
- [ ] Contrast spot checks (3 samples across panes) pass AA (manual audit acceptable for now).

## Routes
- /classic

## Meta
- id: 017
Last_smoke_at: (pending)
Last_suite_at: (pending)
Status: Open

