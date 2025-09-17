MB: /main HUD — Free/Attached explainer + attach indicator

Assignees:
Labels: micro-brief, status:proposed

Context
- Loom: https://loom.com/i/e2e3c51c50ef43e2bb57f5da8c72b8bd
- The Free/Attached toggle is unclear; users don’t know what it does.

Friction
- No discoverable explanation; in Attached mode, it’s not obvious that the HUD follows the selected box.

Target Feel
- Toggle shows a tooltip: “Free: drag HUD anywhere. Attached: HUD follows the selected box and avoids edges.”
- In Attached mode, show a faint leader line from the HUD to the selected box (or a subtle ‘Attached’ badge).

Acceptance
- [ ] Toggle has a tooltip; label reads Free/Attached accordingly
- [ ] In Attached mode a subtle affordance (leader line or badge) appears; toggling back removes it
- [ ] State persists; H mirrors the toggle

Verify (60–120s)
1) Hover toggle → tooltip explains behavior
2) Switch to Attached → affordance visible; switch back → affordance gone; reload → state persists

Automated check
- scripts/ux_suite.mjs: assert toggle presence; optional: check a data-state attribute for Attached mode.
