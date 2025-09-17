Title: Selected box label chip highlights with tasteful ring

Summary
- When a box is selected, the small label chip displayed above the rectangle should also visually highlight (subtle ring/stroke consistent with ShadCN tokens) to mirror selection state.

Context
- Source request: src/extractor/pipeline/steps/015_id_change.md (Label Highlight section)
- Area: Classic layout, center canvas overlay; label chip is rendered above each annotation rectangle.

Acceptance
- Add a stable test id on the chip element for each box: `data-testid="box-chip"`.
- Behavior:
  - Selecting a box adds a visible but tasteful highlight to its chip (e.g., `ring-2 ring-primary ring-offset-1 ring-offset-background` or a subtle token-based border).
  - Non-selected boxes’ chips remain unhighlighted.
  - Works for all label types and regardless of zoom or night mode.

Verification (Smoke: scripts/smokes/issue_020.mjs)
- Loads /classic, selects a box, and asserts that the selected box’s `[data-testid=box-chip]` has a ring/border highlight while another unselected box’s chip does not.
- Artifacts saved under scripts/artifacts/ (log + screenshot). If selectors are missing, the smoke fails with reason `selector_missing`.

Notes
- Keep highlight subtle; prefer ShadCN ring tokens for theme compatibility.
- Ensure no layout shift or overlap with the annotation rectangle.

