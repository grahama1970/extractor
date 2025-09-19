Remaining clarifications (small, unblockers)

  - Conflict artifact: confirm file path/name and shape. Proposal:
  scripts/artifacts/conflicts_<docId>.json with { docId, items:[{id,
  type:'duplicate'|'numeric_mismatch', groupId?, resolved:boolean,
  notes?}] }.
  > confirmed
  - JSON export v1: keep { page, boxes:[{ type, instance_id,
  group_id, bounding_box:[x,y,w,h] }]} as now? (Matches smokes and
  keeps room for schema growth.)
  - Progress microcopy: OK to use “Stage 0N: <name> … <percent>%”
  and show stage name only when percent unknown?
  > confirmed
  - docId: SHA‑256 full hex (64 chars) acceptable, or prefer short
  first-12 chars for UI display only (storage keeps full)?
  > first 12 characters is fine for now