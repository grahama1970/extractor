# Pipeline Invalidation Matrix (Stage 07 micro‑pipeline)

| Upstream change | Rerun required |
|-----------------|----------------|
| 07a canonical (anchors/ordering) | 07b, 07c, 07d, 07e, 07g, 07h, 07i, 07j, 07k, 07l, 07m, 07n |
| 07b polish | 07e, 07n |
| 07c titles | 07e, 07n |
| 07d captions | 07e, 07n |
| 07e reflow | 07g, 07h, 07i, 07j, 07k, 07l, 07m, 07n |
| 07g refs | 07l, 07n |
| 07h requirements | 07l, 07n |
| 07i entities | 07n |
| 07j equations | 07n |
| 07k table spans | — |
| 07l confidence | 07n |
| 07m deltas | — |

Implementation notes:
- 07n aggregates deterministic/hash metadata; rerun whenever any prior stage reruns.
- For partial re‑ingest of a document version, skip unchanged anchors by comparing `anchor_id` + `block_hash`.

