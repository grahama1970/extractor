# Gamified Instance Prompt — codex_03 / mul_chunked

## Original Prompt
```markdown
## Gamified Run Spec — Quick
## Codebase
repo_root: .
## Approaches
- name: mul_shift_add
## Runner
type: python_benchmark
entry: prototypes/gamified/bench/multiply_benchmark.py
create_if_missing: true
## Scoring
plateau: { epsilon: 0.15, window: 3 }
## Execution
max_iters: 1
api_base: http://localhost:8000
```

## Context
- Codebase: /home/graham/workspace/experiments/extractor
- Variant: mul_chunked
- Output Dir: /home/graham/workspace/experiments/extractor/workspace/runs/20250914-135749/instances/codex_03_mul_chunked
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
## Mechanics
Chunked/base‑N multiplication: convert integers to base‑B (e.g., 10^k). Represent operands as arrays of base‑digits, accumulate products with carries, then rebuild the integer. Emphasizes clarity over asymptotic optimality.


## Execute Exactly (non-interactive)
Run this command now. When it exits, you are done:
```
python scripts/variant_agent.py --approach mul_chunked --bench bench/multiply_benchmark.py --baseline src/core/multiply.py --variants /home/graham/workspace/experiments/extractor/workspace/runs/20250914-135749/instances/codex_03_mul_chunked/variants.py --out-dir /home/graham/workspace/experiments/extractor/workspace/runs/20250914-135749/instances/codex_03_mul_chunked --epsilon 0.15 --window 5 --max-iters 8 --run-id 20250914-135749 --prompt-file /home/graham/workspace/experiments/extractor/workspace/runs/20250914-135749/instances/codex_03_mul_chunked/prompt.md --S_digits 3 --S_trials 1 --M_digits 6 --M_trials 1 --L_digits 8 --L_trials 1 --L_timeout_ms 250
```

## Monitoring
- Web logs: http://localhost:8000/proto/dashboard
- API scoreboard: http://localhost:8000/scoreboard?run_id=20250914-135749
- API episodes (latest): http://localhost:8000/episodes?run_id=20250914-135749&variant=mul_chunked&limit=1
- API logs (tail): http://localhost:8000/logs?run_id=20250914-135749&variant=mul_chunked&limit=50
- Note: Codex harness may terminate long-lived parents; rely on web logs for progress.