# Gamified Instance Prompt — codex_03 / mul_chunked

## Original Prompt
```markdown
## Gamified Run Spec — Tokamak Stress Test

The three amended approaches to increase the efficiency of a tokamak reactor, now including their corresponding mathematical or algorithmic methods for testing and verification, are:

1. Increasing Plasma Density with Controlled Fueling — PDE-driven MPC with safety constraints and MIQP verification.
2. Magnetic and Wave Pattern Control to Suppress Edge Instabilities — Grad–Shafranov + MHD stability models with RL-based policy optimization.
3. Optimized Heat Management and Extraction — Integrated multi-physics heat transport + reduced-order models for coolant/plasma-facing components.

Notes: This prompt is intentionally long/complex to stress the orchestrator, Codex concurrency, and the Arango-backed web logger under heavier token/IO conditions.

## Approaches
- name: mul_shift_add
- name: mul_karatsuba
- name: mul_chunked

## Runner
# Keep the multiplication POC runner to exercise concurrency + scorecard.
# We are stress testing orchestration and web logging, not physics kernels.
```

## Context
- Codebase: /home/graham/workspace/experiments/extractor
- Variant: mul_chunked
- Output Dir: /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-154457/instances/codex_03_mul_chunked
## Gamified Rules (Summary)
- Plateau: epsilon=0.15, window=5
- Max iters: 8
- Scoring (internal per-iteration): correctness/speed/robustness/brevity -> 100 total

## Stop Condition
- Do not stop until plateau (per epsilon/window) or max iterations reached.

## Iteration Contract
- If the function for this approach is missing, implement it.
- Run the benchmark; capture stdout/stderr; compute metrics.
- Write a well-formatted JSON summary per iteration in the output dir: iter_XX_summary.json with score, metrics, stderr/stdout digests, and mutation info.
- Propose and apply a code change based on metrics; repeat until stop condition.

## Research MCPs (When Blocked)
- If blocked or an API/library detail is unknown, use research MCPs:
  - Perplexity Ask: craft a precise query; return concise, citation-backed notes.
  - Context7 Docs: fetch official docs for the relevant library/API and summarize key constraints.
- Keep research minimal and targeted to unblock; cite sources when applicable in logs.
- Do not stall the iteration loop waiting for exhaustive research; prefer incremental, testable changes.

## Benchmark Parameters
- Scales/trials: S=6x5, M=200x5, L=2000x5; L timeout=2000ms

## Execute Exactly (non-interactive)
Run this command now. When it exits, you are done:
```
python scripts/variant_agent.py --approach mul_chunked --bench bench/multiply_benchmark.py --baseline src/core/multiply.py --variants /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-154457/instances/codex_03_mul_chunked/variants.py --out-dir /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-154457/instances/codex_03_mul_chunked --epsilon 0.15 --window 5 --max-iters 8 --run-id show-20250915-154457 --prompt-file /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-154457/instances/codex_03_mul_chunked/prompt.md --api-base http://127.0.0.1:34597
```

## Monitoring
- Web logs: http://localhost:5199
- API scoreboard: http://127.0.0.1:34597/scoreboard?run_id=show-20250915-154457
- API episodes (latest): http://127.0.0.1:34597/episodes?run_id=show-20250915-154457&variant=mul_chunked&limit=1
- API logs (tail): http://127.0.0.1:34597/logs?run_id=show-20250915-154457&variant=mul_chunked&limit=50
- Note: Codex harness may terminate long-lived parents; rely on web logs for progress.