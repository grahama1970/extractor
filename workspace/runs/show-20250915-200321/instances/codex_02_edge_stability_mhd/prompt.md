# Gamified Instance Prompt — codex_02 / edge_stability_mhd

## Original Prompt
```markdown
## Codebase

repo_root: .

## Approaches

```yaml
- name: fueling_density_mpc
  summary: Increase core density using pellet injection and edge fueling with MPC
    to respect safety limits and sustain confinement.
  verification:
  - PDE
  - MPC
  - MIQP
  outputs:
  - stability_margin
  - density_ok
  - heat_flux_peak
  - constraints_ok
- name: edge_stability_mhd
  summary: Suppress edge instabilities (e.g., ELMs) via shaped magnetic fields and
    RF/wave control guided by MHD and Grad-Shafranov analysis.
  verification:
  - GradShafranov
  - MHD
  outputs:
  - stability_margin
  - density_ok
  - heat_flux_peak
  - constraints_ok
- name: heat_extraction_adaptive
  summary: Optimize boundary heat removal and coolant routing with adaptive controls
    to maximize extraction while protecting plasma-facing components.
  verification:
  - HeatTransport
  - ROM
  outputs:
  - stability_margin
  - density_ok
  - heat_flux_peak
  - constraints_ok
```

## Runner

type: analysis_sim
notes: Minimal analysis-mode run for orchestration/logging; no device control.

## Scoring

```yaml
weights:
  correctness: 35.0
  robustness: 25.0
  speed: 25.0
  brevity: 15.0
```

## Constraints

```yaml
edge_density_threshold: 1.0e19     # m^-3
q_min: 2.0                         # safety factor lower bound
beta_max: 0.04                     # plasma beta (fraction)
heat_flux_peak_max: 10.0           # MW/m^2
```

## Evidence

```yaml
- approach: fueling_density_mpc
  expected:
  - stability_margin: (number)
  - density_ok: (boolean)
  - heat_flux_peak: (number)
  - constraints_ok: (boolean)
- approach: edge_stability_mhd
  expected:
  - stability_margin: (number)
  - density_ok: (boolean)
  - heat_flux_peak: (number)
  - constraints_ok: (boolean)
- approach: heat_extraction_adaptive
  expected:
  - stability_margin: (number)
  - density_ok: (boolean)
  - heat_flux_peak: (number)
  - constraints_ok: (boolean)
```

## Execution

```yaml
execution:
  concurrency: 3
  codex_exec: true
  autostart_backend: true
  autostart_dashboard: true
```

## References

- https://arxiv.org/pdf/2306.00415.pdf
- https://www.osti.gov/servlets/purl/1430529
- https://www.nature.com/articles/s41586-021-04301-9
- https://www.sciencedirect.com/science/article/pii/S0920379617309031
- https://www.imsi.institute/activities/computational-challenges-and-optimization-in-kinetic-plasma-physics/
- https://cpb.iphy.ac.cn/article/2019/1969/cpb_28_1_015201.html
- https://www.sciencedirect.com/science/article/pii/S0920379623001990
- https://pubs.aip.org/aip/pop/article/30/9/092510/2911814/Flexible-integrated-modeling-of-tokamak-stability

## Tasks

```json
[
  {"type": "run_python", "name": "log_context", "scope": "pre", "code": "print('Tokamak approaches: fueling_density_mpc, edge_stability_mhd, heat_extraction_adaptive')"},
  {"type": "run_python", "name": "emit_references", "scope": "pre", "code": "print('Key refs listed in References section')"}
]
```
```

## Context
- Codebase: /home/graham/workspace/experiments/extractor
- Variant: edge_stability_mhd
- Output Dir: /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-200321/instances/codex_02_edge_stability_mhd
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
python scripts/variant_agent.py --approach edge_stability_mhd --bench bench/multiply_benchmark.py --baseline src/core/multiply.py --variants /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-200321/instances/codex_02_edge_stability_mhd/variants.py --out-dir /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-200321/instances/codex_02_edge_stability_mhd --epsilon 0.15 --window 5 --max-iters 8 --run-id show-20250915-200321 --prompt-file /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-200321/instances/codex_02_edge_stability_mhd/prompt.md --api-base http://127.0.0.1:41503
```

## Monitoring
- Web logs: http://localhost:5199
- API scoreboard: http://127.0.0.1:41503/scoreboard?run_id=show-20250915-200321
- API episodes (latest): http://127.0.0.1:41503/episodes?run_id=show-20250915-200321&variant=edge_stability_mhd&limit=1
- API logs (tail): http://127.0.0.1:41503/logs?run_id=show-20250915-200321&variant=edge_stability_mhd&limit=50
- Note: Codex harness may terminate long-lived parents; rely on web logs for progress.