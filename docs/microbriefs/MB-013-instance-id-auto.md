MB: /main Inspector — Auto-generate Instance ID per label

Assignees:
Labels: micro-brief, status:proposed

Context
- Loom: https://loom.com/i/3d2e6e7c9f894c778f8b7247cd8df02c
- Instance ID does not auto-update when label type changes; users want label-aware IDs.

Friction
- Manual typing is slow and inconsistent.

Target Feel
- When label type changes, suggest an ID using the label prefix (e.g., figure-001) and a page-scoped counter with zero padding. Users can override.

Acceptance
- [ ] Changing label type suggests a new ID (non-destructive unless empty or accepted)
- [ ] Counter is per page and per label type
- [ ] IDs persist with the box and update only when user accepts or field is empty

Verify (60–120s)
1) Change label from Section → Figure → suggested ID changes to figure-001 (if field empty), otherwise stays until user accepts
2) Create second Figure → suggests figure-002 on same page

Automated check
- scripts/ux_suite.mjs: change types and assert suggested IDs via data-testid.
