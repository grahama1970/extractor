# Lessons Learned – Functionality Status

This document tracks implemented capabilities for the Lessons Learned system, their verification status, and how to run them. It’s designed to help catch regressions and quickly validate end‑to‑end behavior.

## Summary

- Data model: `lessons` (docs), `lesson_edges` (graph edges), `rejected_pairs` (FAISS rejection cache), `incidents` (optional log), and ArangoSearch view `lessons_search`.
- Core flows: seed → BM25 search → FAISS KNN proposals (agent‑generated rationales) → graph recall (BM25 + multihop fusion) → approve/prune admin.
- Tests: E2E pytest covers setup, seed+BM25, link+approve; FAISS test opt‑in via `RUN_FAISS_TESTS=1`.

## Quick Use

- Seed demo lessons: `make lessons-seed-demo COUNT=50 BATCH=demoX`
- Cluster (FAISS): `make lessons-propose`
- Recall (fused): `uv run scripts/lessons/recall_agent.py --q "cdp puppeteer" --scope tabbed --depth 2 --k 5 --json`
- List edges: `uv run scripts/lessons/list_edges.py --status pending --limit 10`
- Approve edge: `uv run scripts/lessons/approve_edge.py --edge-id lesson_edges/… --human-rationale "Looks good"`
- Prune edges: `make lessons-prune`
- Delete demo lessons: `make lessons-delete-demo BATCH=demoX`

## Functionality Status

Legend: ✅ Verified • 🟡 Pending • 🧪 Present (opt‑in)

| Area | Feature | Status | How Verified | Notes |
|---|---|---|---|---|
| Schema | Ensure collections/view (`lessons`, `incidents`, `lesson_edges`, `rejected_pairs`, `lessons_search`) | ✅ Verified | scripts/lessons/setup.py | Adds best‑effort indexes on `_from`, `_to`, `pair_id`, `type/approved/status` |
| Seeding | Seed demo lessons with `demo`, `demo_batch` | ✅ Verified | scripts/lessons/seed_demo.py | Titles prefixed with `DEMO[batch] …`; used for clustering/regression data |
| Cleanup | Delete demo lessons by batch / all | ✅ Verified | scripts/lessons/delete_demo.py | Safe removal; keeps real data intact |
| Search | BM25 via `lessons_search` | ✅ Verified | scripts/lessons/recall_agent.py and direct AQL | View indexes `title/problem/playbook/tags/keywords/scope` |
| KNN | FAISS proposer (symmetric edges, rationale gate, rejection cache) | ✅ Verified | scripts/lessons/propose_faiss.py | K=12, sim≥0.55, min_top=3; agent sets `weight`; stores `raw_sim`, `pair_id` |
| Rejections | Cache rejected pairs | ✅ Verified | rejected_pairs filled during proposals | Prevents re‑suggestion of bad pairs |
| Graph | Related neighbors (1‑hop) | ✅ Verified | scripts/lessons/related.py | Returns neighbor + edge metadata sorted by weight |
| Graph | Multi‑hop traversal (ANY/OUTBOUND) | ✅ Verified | scripts/lessons/multihop.py | Raw paths; agent computes time‑decayed path score |
| Recall | BM25 + graph fusion | ✅ Verified | scripts/lessons/recall_agent.py | final = 0.6·BM25_norm + 0.4·graph_norm; depth 1–4 |
| Admin | List edges (filters: title/scope/approved/status) | ✅ Verified | scripts/lessons/list_edges.py | `--json` for machine output |
| Admin | Approve edge (human rationale) | ✅ Verified | scripts/lessons/approve_edge.py | Sets `approved=true`, `status=active`, appends `rationales[]` |
| Admin | Prune edges (stale/weak/pending/unused) | ✅ Verified | scripts/lessons/prune_pending.py (Make: `lessons-prune`) | Removes dead pending edges |
| HTTP | /api/lessons/edge/related (upsert symmetric), /edge/approve, /edge/reject | 🟡 Pending | Appended to prototypes/tabbed/api/server.py; run dev to test | Use curl/httpx smokes when server is up |
| HTTP | /api/lessons/related (neighbors), /api/lessons/multihop (paths) | 🟡 Pending | Appended; ready to verify | Mirrors CLI outputs |
| Tests | E2E: setup, seed+BM25, link+approve | ✅ Verified | tests/lessons/test_lessons_e2e.py | Skips if Arango not available |
| Tests | FAISS proposer scope test | 🧪 Present (opt‑in) | RUN_FAISS_TESTS=1 pytest … | Heavy; recommended for nightly CI |

## Test Coverage

- Baseline E2E (fast, PR‑safe)
  - Ensures schema/view, seeds 8 lessons, checks BM25 returns at least one item.
  - Creates two lessons, links them, verifies edge exists, approves it and validates `approved/status` fields.
- FAISS E2E (opt‑in, nightly)
  - Seeds 20 pipeline lessons, runs proposer (scope=pipeline), asserts related edges exist.

Run:
- `pytest -q tests/lessons/test_lessons_e2e.py`
- With FAISS: `RUN_FAISS_TESTS=1 pytest -q tests/lessons/test_lessons_e2e.py`

## CI Recommendations

- PR gate (fast):
  - Run baseline E2E tests against a live ArangoDB (docker: `arangodb/arangodb`, map 8529).
  - Ensure `ARANGO_URL/DB/USER/PASS` envs set in CI job.
- Nightly (comprehensive):
  - Enable `RUN_FAISS_TESTS=1` to validate proposer+clustering.
  - Optionally seed a known batch (`demo_ci`) and compare edge counts.
- Optional HTTP smokes (when dev server is run in CI):
  - POST `/api/lessons/edge/related` → GET `/api/lessons/related` → assert edge presence.
  - POST `/api/lessons/edge/reject` → verify `rejected_pairs` contains entry.
  - POST `/api/lessons/edge/approve` → assert `approved=true`.

## Agent Usage Scenarios

- When blocked (triage):
  - Run recall on your error/log tokens: `make lessons-recall-last TAGS=cdp SCOPE=tabbed`.
  - Expand via neighbors: `uv run scripts/lessons/related.py --title "…" --scope tabbed`.
  - Explore paths: `uv run scripts/lessons/multihop.py --title "…" --scope tabbed --depth 2`.
- Before coding (reuse patterns):
  - BM25 recall on your problem statement; read top lessons’ playbooks.
  - If results feel thin, run FAISS proposer to densify related clusters.
- After solving (capture knowledge):
  - Add a lesson with `scripts/lessons/add.py`; link solving edges to influential prior lessons.
  - Approve edges and add human rationale if needed.
- Regression triage (CI):
  - Seed a demo batch, cluster with FAISS, run recall diffs to spot changes.
  - Prune stale pending edges.
- Data hygiene:
  - Use `demo=true` and `demo_batch` for test data. Clean with `make lessons-delete-demo BATCH=…`.

## Notes & Next Steps

- The “demo” + “demo_batch” flags are effective for seeding and cleanup while keeping real data safe.
- You can add an `expires_at` field later for time‑based pruning; current prune job removes stale weak pending edges.
- Consider adding a “recall diff” CLI to print side‑by‑side BM25‑only vs fused rankings for a given query, to spot regressions in fusion logic.
- If HTTP endpoints become a primary integration point, add `httpx` tests under `tests/lessons/` to exercise them when the backend is running.
