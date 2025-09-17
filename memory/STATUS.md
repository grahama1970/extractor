# Graph Memory – STATUS

This package (graph-memory) globalizes the Lessons Learned system as a reusable library with BM25 + graph recall and FAISS proposer.

## Current State (0.1.0)

- Core modules
  - graph_memory.arango_client: env-based Arango connect
  - graph_memory.setup_schema: ensure collections + view + indexes
  - graph_memory.lessons.seed: seed demo lessons (demo, demo_batch)
  - graph_memory.lessons.proposer: FAISS KNN + rationale gate + symmetric edges + rejected_pairs
  - graph_memory.lessons.recall: BM25 + graph multihop fusion; BM25 vs Fused diff
  - graph_memory.lessons.related: 1-hop neighbors
  - graph_memory.lessons.multihop: BFS paths (ANY)
  - graph_memory.lessons.edges: approve (human rationale), prune pending edges
- CLI entry points (console_scripts)
  - lessons-seed, lessons-propose, lessons-recall, lessons-recall-diff
  - lessons-related, lessons-multihop, lessons-approve, lessons-prune
- Tests
  - memory/tests/test_e2e.py (baseline E2E + optional FAISS)

## Next Steps (High Priority)

1) Complete tests inside package
   - Add smoke tests for related + multihop CLIs (assert shape and minimal fields)
   - Add recall diff test (BM25-only vs fused) with stable sample data
   - Document RUN_FAISS_TESTS=1 gate; ensure tests pass without internet by skipping or using small local model cache

2) Documentation / Examples
   - Expand README with env setup, quick start, common commands
   - Add a minimal cookbook (seed → propose → recall → approve → prune)

3) Packaging & Distribution
   - Add license + classifiers in pyproject
   - Publish to internal package index (or path dependency initially)
   - Versioning policy (semver) and changelog stub

4) Integration with Extractor
   - Switch extractor Make targets to use CLIs (done with fallback)
   - Optionally add extractor pyproject dependency on graph-memory (path or index)

5) Service (Optional, next phase)
   - Extract a small FastAPI lessons-service for HTTP consumers
   - Mirror package APIs: /lessons/add/search, /edge/related/approve/reject, /related, /multihop, /propose/faiss, /prune
   - Add httpx tests in service repo; keep package tests here

6) MCP (Optional, later)
   - Thin MCP wrapper calling the service endpoints (search/add/related/multihop/approve/reject)

## Backlog / Enhancements

- Add synonyms adapter hooks per-project; configurable boosts
- Add directional "solving" edges and UI/CLI for contribution weights
- Add expires_at field and scheduled prune job helpers
- Add Slack bot example for recall on pasted logs

## CI Recommendations

- PR: run memory/tests/test_e2e.py (skip FAISS by default)
- Nightly: RUN_FAISS_TESTS=1 pytest; generate Markdown report from pytest JSON
- Artifacts: scripts/artifacts/lessons_status_report.md (generated in parent project; add similar task here if desired)
