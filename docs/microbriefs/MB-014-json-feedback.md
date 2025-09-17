MB: /main Inspector — Feedback when JSON is added/updated

Assignees:
Labels: micro-brief, status:proposed

Context
- Looms: https://loom.com/i/973787d881774fa3bf1d286735c7ac9c, https://loom.com/i/6ba372116c4744518fd03f818c91878a
- When adding/updating JSON, there’s no confirmation or state indication.

Friction
- Users cannot tell if an action succeeded.

Target Feel
- Show a toast “JSON updated” on save, highlight the JSON area briefly, and disable Save until changes exist. Provide a small ‘dirty’ marker when inspector JSON differs from last save.

Acceptance
- [ ] Save triggers a toast; Save disabled until form changes
- [ ] JSON area briefly highlights; dirty marker appears when unsaved changes exist

Verify (60–120s)
1) Edit JSON → Save becomes enabled; click Save → toast + highlight; Save disables
2) Edit again → dirty marker appears

Automated check
- scripts/ux_suite.mjs: detect Save button disabled/enabled transitions and a toast via data-testid.
