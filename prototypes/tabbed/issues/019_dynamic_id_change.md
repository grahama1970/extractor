Title: Dynamic ID prefix updates when label type changes

Summary
- Changing a selected annotation’s label type must update its instance ID prefix accordingly and reflect immediately in the center-pane label chip.
- Example: switching type to Section updates `table-ro3` → `section-ro3` (preserve suffix), and the chip shows the new instance id.

Context
- Source request: src/extractor/pipeline/steps/015_id_change.md
- Area: Classic layout, Right Inspector (Label Type, Instance ID) and Center canvas chip above the box.

Acceptance
- Add stable test ids:
  - `data-testid="inspector-label-type"` on the Label Type select trigger.
  - `data-testid="inspector-instance-id"` on the Instance ID input.
  - `data-testid="box-chip"` on the small label chip rendered above each box.
- Behavior:
  - Given a selected box with instance id `table-ro3`, when the Label Type is changed to `Section` then:
    - The instance id input updates to `section-ro3` automatically.
    - The chip above the selected box updates to display `Section · section-ro3`.
  - Suffix logic: keep the suffix after the first `-` unchanged; only replace the prefix with the new type in lowercase.
  - Works when switching between any existing types (Section/Table/Figure and custom label types from the palette).

Verification (Smoke: scripts/smokes/issue_019.mjs)
- Loads /classic, selects a box, sets `instance-id` to `table-ro3`, changes type to `Section` via `inspector-label-type` and asserts:
  - `inspector-instance-id` value becomes `section-ro3`.
  - `[data-testid=box-chip]` for the selected box contains `Section · section-ro3`.
- Artifacts saved under scripts/artifacts/ (log + screenshot) and failure explains missing selectors/behavior.

Notes
- Ensure updates are debounced minimally (instant for this prototype is fine).
- Keep behavior reversible (changing back to Table restores `table-…` prefix while preserving suffix).

