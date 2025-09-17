MB: /main Labels — Replace Sec/Tbl chips with single Label control (palette)

Assignees:
Labels: micro-brief, status:proposed

Context
- Loom: https://loom.com/i/d7d94ff4caa54e5c92fd46ad3336a579
- Two separate chips (Sec, Tbl) clutter the HUD and diverge from the palette.

Friction
- Multiple label entry points are redundant and confusing.

Target Feel
- A single “Label” control (the + palette or a Label dropdown) is the source of truth; remove Sec/Tbl chips. Keyboard shortcuts still switch default type (e.g., L + 1..9).

Acceptance
- [ ] Sec/Tbl chips removed from HUD
- [ ] Single Label control opens the palette with all options
- [ ] Keyboard shortcuts (e.g., Alt+1..9) set default new‑box label; HUD shows current default

Verify (60–120s)
1) Click Label control → all labels visible; choose one → selected box/default updates
2) Press shortcut → HUD shows new default label

Automated check
- scripts/ux_mb003.mjs: assert Sec/Tbl chips are absent; palette contains labels from registry only.
