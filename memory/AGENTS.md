# Graph Memory – Agent Quickstart

Use Graph Memory as your persistent Lessons Learned. It provides fast BM25 search, graph multihop recall, and FAISS clustering with agent-generated rationales.

## Install (local)

- cd /home/graham/workspace/experiments/memory
- uv pip install -e ".[faiss]"

## Environment

- ARANGO_URL=http://127.0.0.1:8529
- ARANGO_DB=lessons
- ARANGO_USER=root
- ARANGO_PASS=openSesame

## CLI (console scripts)

- Seed: `lessons-seed --count 50 --batch demoX --scope tabbed`
- Propose edges (FAISS): `lessons-propose --k 12 --sim-thresh 0.55 --min-top 3 [--scope tabbed]`
- Recall: `lessons-recall --q "cdp puppeteer" --scope tabbed --depth 2 --k 5`
- Recall diff: `lessons-recall-diff --q "cdp puppeteer" --scope tabbed`
- Related: `lessons-related --title "..." --scope tabbed`
- Multihop: `lessons-multihop --title "..." --scope tabbed --depth 2`
- Approve edge: `lessons-approve approve --edge-id lesson_edges/... --human-rationale "Approved"`
- Prune: `lessons-prune prune`

## Best Practices (Agent)

- When blocked: run recall on your error/log tokens (use recall-diff if needed), then expand via neighbors/multihop.
- Document solutions: add lessons and link solving edges; approve with rationale.
- Keep demo data separate with demo=true and demo_batch; clean regularly.
- Scope matters: cluster per-scope when appropriate; cross-scope only when concepts bridge.

