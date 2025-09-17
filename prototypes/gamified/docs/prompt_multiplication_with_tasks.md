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
      '''Baseline: delegate to Python\'s built-in integer multiplication.'''
      return a * b

## Approaches
# Invent three distinct multiplication strategies. Do not assume prior specifics.
# For each, provide a short name and a one-paragraph mechanics description (how it works in general terms).
# The agent will concretize and implement them.

## Runner
type: python_benchmark
entry: prototypes/gamified/bench/multiply_benchmark.py
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
