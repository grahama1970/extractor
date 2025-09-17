MB: /main Drawing — New (crosshair) mode indicator + affordance

Assignees:
Labels: micro-brief, status:proposed

Context
- Loom: https://loom.com/i/e2e3c51c50ef43e2bb57f5da8c72b8bd
- The target (crosshair) icon appears to do nothing; there is no visible state indicating Draw mode is armed.

Friction
- Users click the target and expect immediate ability to draw, but receive no confirmation/feedback.

Target Feel
- Clicking New (or pressing N) visibly arms Draw mode: cursor changes to crosshair, HUD shows a subtle “Draw armed” chip, and an instructional hint appears once per session.
- After the first box is created, Draw mode auto‑disarms and the hint fades.
- ESC cancels Draw mode.

Acceptance
- [ ] New (N) toggles a visible “Draw armed” indicator in the HUD; cursor is crosshair over the canvas
- [ ] First successful draw auto‑disarms New; ESC cancels Draw mode
- [ ] A one‑time hint appears (“Drag on the page to create a box”) and never nags again in the same session

Verify (60–120s)
1) Click New → crosshair + HUD chip appear; drag to create → chip disappears
2) Press N → crosshair + chip show; press ESC → both disappear

Automated check
- scripts/ux_mb003.mjs: assert Draw chip visibility via data-testid and that draw occurs only when armed.
