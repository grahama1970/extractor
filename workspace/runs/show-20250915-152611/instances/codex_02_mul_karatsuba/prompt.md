# Gamified Instance Prompt — codex_02 / mul_karatsuba

## Original Prompt
```markdown
approaches: mul_shift_add, mul_karatsuba, mul_chunked
```

## Context
- Codebase: /home/graham/workspace/experiments/extractor
- Variant: mul_karatsuba
- Output Dir: /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-152611/instances/codex_02_mul_karatsuba
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
python scripts/variant_agent.py --approach mul_karatsuba --bench bench/multiply_benchmark.py --baseline src/core/multiply.py --variants /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-152611/instances/codex_02_mul_karatsuba/variants.py --out-dir /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-152611/instances/codex_02_mul_karatsuba --epsilon 0.15 --window 5 --max-iters 8 --run-id show-20250915-152611 --prompt-file /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-152611/instances/codex_02_mul_karatsuba/prompt.md --api-base http://127.0.0.1:55547 --S_digits 3 --S_trials 1 --M_digits 6 --M_trials 1 --L_digits 8 --L_trials 1 --L_timeout_ms 250
```

## Monitoring
- Web logs: http://localhost:5199
- API scoreboard: http://127.0.0.1:55547/scoreboard?run_id=show-20250915-152611
- API episodes (latest): http://127.0.0.1:55547/episodes?run_id=show-20250915-152611&variant=mul_karatsuba&limit=1
- API logs (tail): http://127.0.0.1:55547/logs?run_id=show-20250915-152611&variant=mul_karatsuba&limit=50
- Note: Codex harness may terminate long-lived parents; rely on web logs for progress.