# Gamified Instance Prompt — codex_02 / mul_karatsuba

## Original Prompt
```markdown
## Gamified Run Spec — Multiplication POC (with tasks)

## Codebase
repo_root: .

## Mode
mode: generate

## Baseline
path: src/core/multiply.py
create_if_missing: true
content: |
  def multiply(a: int, b: int) -> int:
      """Baseline: delegate to Python's built-in integer multiplication."""
      return a * b

## Approaches
# Invent three distinct multiplication strategies. Do not assume prior specifics.
# For each, provide a short name and a one-paragraph mechanics description (how it works in general terms).
# The agent will concretize and implement them.

## Runner
type: python_benchmark
entry: bench/multiply_benchmark.py
create_if_missing: true
params:
  scales:
    S: { digits: 6, trials: 5 }
    M: { digits: 200, trials: 5 }
    L: { digits: 2000, trials: 5, timeout_ms: 2000 }
  seed: 1337
  results_dir: bench/results

## Scoring
total: 100
weights: { correctness: 45, speed: 35, robustness: 10, brevity: 10 }
speed_split: { S: 11, M: 12, L: 12 }
plateau: { epsilon: 0.15, window: 5 }

## Execution
concurrency: auto
codex_exec: true
autostart_backend: true
autostart_dashboard: true
api_base: http://localhost:8000

## Tasks
```json tasks
[
  {
    "type": "run_shell",
    "name": "format_python",
    "scope": "pre",
    "cmd": "python -m black -q src bench || true"
  },
  {
    "type": "run_python",
    "name": "pre_bench_note",
    "scope": "pre",
    "code": "print('Pre-benchmark checks complete for', __file__)"
  },
  {
    "type": "run_shell",
    "name": "variant_hook",
    "scope": "per_variant",
    "cmd": "echo Running hooks for $VARIANT in $CODEBASE && sleep 0.1"
  },
  {
    "type": "run_shell",
    "name": "summarize_results",
    "scope": "post",
    "cmd": "ls -l bench/results && jq '.' bench/results/multiply_scorecard.json || true"
  }
]
```
```

## Context
- Codebase: /home/graham/workspace/experiments/extractor
- Variant: mul_karatsuba
- Output Dir: /home/graham/workspace/experiments/extractor/workspace/runs/20250912-142314/instances/codex_02_mul_karatsuba
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
Divide‑and‑conquer multiplication. Split operands into high/low halves, recursively compute z2, z0, and the cross term z1 = (x1+x0)(y1+y0)−z2−z0, and recombine. Uses builtin for small base cases (cutoff).

## Tasks (from original prompt)
```json tasks
[
  {
    "type": "run_shell",
    "name": "format_python",
    "scope": "pre",
    "cmd": "python -m black -q src bench || true"
  },
  {
    "type": "run_python",
    "name": "pre_bench_note",
    "scope": "pre",
    "code": "print('Pre-benchmark checks complete for', __file__)"
  },
  {
    "type": "run_shell",
    "name": "variant_hook",
    "scope": "per_variant",
    "cmd": "echo Running hooks for $VARIANT in $CODEBASE && sleep 0.1"
  },
  {
    "type": "run_shell",
    "name": "summarize_results",
    "scope": "post",
    "cmd": "ls -l bench/results && jq '.' bench/results/multiply_scorecard.json || true"
  }
]
```

## Execute Exactly (non-interactive)
Run this command now. When it exits, you are done:
```
python scripts/variant_agent.py --approach mul_karatsuba --bench bench/multiply_benchmark.py --baseline src/core/multiply.py --variants /home/graham/workspace/experiments/extractor/workspace/runs/20250912-142314/instances/codex_02_mul_karatsuba/variants.py --out-dir /home/graham/workspace/experiments/extractor/workspace/runs/20250912-142314/instances/codex_02_mul_karatsuba --epsilon 0.15 --window 5 --max-iters 8 --run-id 20250912-142314 --prompt-file /home/graham/workspace/experiments/extractor/workspace/runs/20250912-142314/instances/codex_02_mul_karatsuba/prompt.md
```