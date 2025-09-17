MB: /main HUD — Inactive button audit (wire actions + tooltips)

Assignees:
Labels: micro-brief, status:proposed

Context
- Loom: https://loom.com/i/451149b6af4147e28289698446631da3
- A HUD button appears to have no effect (exact control unspecified in Loom).

Friction
- Buttons without visible effect erode trust; each should perform an action and show feedback.

Target Feel
- Every HUD button has a clear tooltip and a visible effect (e.g., selection change, dialog open, toast). Disabled state when action is not available.

Acceptance
- [ ] All HUD buttons have tooltips and perform visible actions; disabled when unavailable
- [ ] Clicking the identified inactive button performs its intended action (specify: <fill during implementation>)

Verify (60–120s)
1) Hover each HUD button → tooltip text appears
2) Click each → visible effect (selection change, dialog open, etc.)

Automated check
- Extend scripts/ux_suite.mjs to click each HUD button (by data-testid) and assert expected UI changes (or at least no console errors).
