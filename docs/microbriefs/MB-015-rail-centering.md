MB: /main Thumbnails — Rail/filmstrip centering and alignment

Assignees:
Labels: micro-brief, status:proposed

Context
- Loom: https://loom.com/i/b52d06fbfae84065820ab4459605b415
- The rail/filmstrip appears off-centered; padding/margins look uneven.

Friction
- Visual imbalance; reduced perceived quality.

Target Feel
- Center filmstrip within its container with consistent gutters; vertical rail aligns with canvas edge and HUD margins.

Acceptance
- [ ] Horizontal filmstrip centered with even padding
- [ ] Vertical rail aligns flush with layout grid; consistent spacing from canvas

Verify (60–120s)
1) Switch Bottom → check filmstrip center and padding
2) Switch Left → check alignment with canvas and spacing

Automated check
- Optional visual diff or DOM geometry check for padding/center (data-testid wrappers).
