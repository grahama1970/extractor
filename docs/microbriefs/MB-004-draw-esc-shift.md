MB: /main Drawing — ESC cancel + Shift constrain

Assignees:
Labels: micro-brief, status:proposed

Context
- Route/Element: /main · Annotation canvas

Friction
- Can’t cancel an in-progress draw; aspect ratio not constrainable.

Target Feel
- ESC cancels the current draw (no box created).
- Holding Shift while drawing constrains to 4:3 (or nearest common ratio) and snaps edges as usual.

Acceptance
- [ ] ESC during draw cancels with no box left behind
- [ ] Shift while drawing constrains box ratio (approx 4:3)
- [ ] Works after page switches and at different zoom levels

Verify (60–120s)
1) Start drawing, press ESC → nothing created
2) Start drawing with Shift held → resize keeps ~4:3

Automated check
- Extend scripts/ux_mb003.mjs or add scripts/ux_mb004.mjs to simulate pointer down/move with/without Shift; assert created box dimensions match ratio tolerance.
