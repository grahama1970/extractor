MB: /main HUD — Visible Attach toggle + indicator

Assignees:
Labels: micro-brief, status:proposed

Context
- Route/Element: /main · HUD

Friction
- H/R keyboard toggles are undiscoverable; no visual state for attach mode.

Target Feel
- Add a small toggle chip in the HUD to switch Free/Attach with tooltip; show current mode (‘Attached’) visually.

Acceptance
- [ ] HUD shows a Free/Attach toggle with tooltip
- [ ] Toggle mirrors H key; state persists
- [ ] In Attach mode, a subtle ‘Attached’ indicator is visible

Verify (60–120s)
1) Click toggle → HUD follows selection; click again → returns to free
2) Press H → toggle updates; reload → mode persists
