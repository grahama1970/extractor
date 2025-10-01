Lean4 → Graph Integration (Datalake‑Ready)

This guide shows a frictionless path from Lean4 batch output to an ArangoDB graph with multi‑hop queries, tuned for offline/CI and large corpora.

1) Produce Lean4 artifacts (offline‑friendly)

```
uv venv; source .venv/bin/activate && uv pip install -e .[dev]
python -m lean4_prover.cli_mini batch \
  --input-file in.json \
  --output-file out.json \
  --deterministic --no-llm \
  --emit-edge-hints edge_hints.json
```

Notes
- OUT.json contains proof_results with analysis.* (normalized_prop, polarity, shape, used_lemmas when available).
- edge_hints.json adds nodes (sections, lemmas) and edge candidates (depends_on, contradicts, refines).

Optional (dev‑rich): enable LSP lemma extraction

```
export LEAN4_ANALYSIS_MODE=lsp
export LEAN4_LSP_IMPL=lean_serve   # or lake_serve
export LEAN4_ANALYSIS_TIMEOUT_S=5
```

2) Bootstrap ArangoDB once

```
export ARANGODB_URL=http://localhost:8529
export ARANGODB_USERNAME=root
export ARANGODB_PASSWORD=…
uv run scripts/db/arangodb_bootstrap.py lean4_prod
```

Creates collections (sections, lemmas, theorems) and edge collections (depends_on, contradicts, refines, similar_knn), a named graph lean4_g, and an ArangoSearch view v_sections for BM25.

3) Upsert edges

Using edge hints directly:

```
uv run scripts/pipeline/stage11_build_edges.py edge_hints.json edges.json --arangodb lean4_prod
```

From Stage 10 flattened JSON (with lemma pass‑through):

```
uv run scripts/pipeline/stage10_pass_through_lemmas.py out.json flat10.json
uv run scripts/pipeline/stage11_build_edges.py flat10.json edges.json --arangodb lean4_prod \
  --fallback-lemma-candidates
```

The --fallback-lemma-candidates flag densifies graphs offline by using analysis.lemma_candidates when used_lemmas is empty.

4) Add KNN similarity edges (optional, scalable)

```
uv run scripts/pipeline/compute_embeddings_knn.py flat10.json knn_edges.json --arangodb lean4_prod --knn-k 5
```

Uses sentence‑transformers embeddings + FAISS to upsert similar_knn edges. For very large corpora, run this as a batch job.

5) Query recipes (impact diagnostics)

```
uv run scripts/queries/run_aql.py --db lean4_prod scripts/queries/q1_find_contradictions.aql
uv run scripts/queries/run_aql.py --db lean4_prod scripts/queries/q2_downstream_impact.aql \
  --params '{"start_id":"sections/S1","max_hops":3,"graph":"lean4_g"}'
uv run scripts/queries/run_aql.py --db lean4_prod scripts/queries/q3_bm25_topk_sections.aql \
  --params '{"q":"even numbers","k":5}'
```

Make targets (shortcuts)

```
make arango-bootstrap
# HINTS=edge_hints.json DB=lean4_prod make graph-edges-from-hints
# FLAT10=flat10.json DB=lean4_prod make graph-knn
```

Operational tips
- CI/offline: keep LEAN4_ANALYSIS_MODE=regex and --fallback-lemma-candidates on Stage 11 to densify graphs without LSP.
- Dev‑rich: flip to LSP/Pantograph for higher precision; increase LEAN4_ANALYSIS_TIMEOUT_S modestly (≤5s) to bound runtime.
- One‑time DB setup: run the bootstrap script per environment.

With these steps, scientists and engineers can run contradiction checks, multi‑hop dependency queries, and similarity exploration across a large corpus with a few commands.
