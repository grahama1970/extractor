# Gamified Instance Prompt — invent-three-distinct-multiplication-strategies-do-not-assume-prior-specifics

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
- Variant: invent-three-distinct-multiplication-strategies-do-not-assume-prior-specifics
- Output Dir: /home/graham/workspace/experiments/extractor/workspace/agent/gamified_invent-three-distinct-multiplication-strategies-do-not-assume-prior-specifics
## Gamified Rules (Summary)
- Plateau: epsilon=0.15, window=5
- Max iters: 5
- Scoring (internal per-iteration): correctness/speed/robustness/brevity -> 100 total

## Stop Condition
- Do not stop until plateau (per epsilon/window) or max iterations reached.

## Iteration Contract
- If the function for this approach is missing, implement it.
- Run the benchmark; capture stdout/stderr; compute metrics.
- Write a well-formatted JSON summary per iteration in the output dir: iter_XX_summary.json with score, metrics, stderr/stdout digests, and mutation info.
- Propose and apply a code change based on metrics; repeat until stop condition.

## Benchmark Parameters
- Scales/trials: S=6x5, M=200x5, L=2000x5; L timeout=2000ms

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