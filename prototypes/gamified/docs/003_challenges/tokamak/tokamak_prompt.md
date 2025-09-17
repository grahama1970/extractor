## Gamified Run Spec — Tokamak Efficiency (3 Approaches)

## Codebase
repo_root: .

## Context
This challenge evaluates three strategies to increase tokamak efficiency. Each approach includes a concise plan and a mathematical/algorithmic verification method. The orchestrator will run three concurrent instances (one per approach), stream logs to the Arango‑backed web logger, and compute a winner.

## Approaches
- name: tokamak_fueling_density_mpc
  summary: Increase plasma core density with controlled fueling (pellet injection or edge fueling modulation) while maintaining confinement and avoiding disruptions.
  verification:
    - model: Coupled nonlinear drift‑diffusion PDEs for particle/heat transport
    - control: Model Predictive Control under safety constraints (e.g., edge density threshold)
    - solver: Mixed‑Integer Quadratic Programming (MIQP) to validate real‑time control strategies
    - outputs: density/temperature profiles, confinement metrics, disruption risk flags

- name: tokamak_edge_stability_mhd
  summary: Apply magnetic/wave patterns near the plasma edge to suppress ELMs, stabilizing the boundary for longer stable operation phases.
  verification:
    - model: Free‑boundary Grad–Shafranov equilibrium + MHD stability (q, β constraints)
    - coupling: Circuit models for coils + polynomial‑parametrized profiles
    - control: Reinforcement Learning policies optimized in simulation for stability margin gains
    - outputs: stability margins, ELM suppression indicators, constraint satisfaction

- name: tokamak_heat_extraction_adaptive
  summary: Optimize heat removal with adaptive coolant strategies and boundary control to maximize energy extraction while preventing material damage.
  verification:
    - model: Integrated multi‑physics (heat transport, turbulence, boundary layer dynamics)
    - surrogate: Reduced‑order neural networks or parameterized transport solvers
    - evaluation: Simulated heat flux loads, plasma edge stability impact, material safety limits
    - outputs: heat extraction efficiency, peak heat flux, stability/erosion metrics

## Runner
type: analysis_sim
notes:
  - This is a research and verification task; the live code execution in this repo uses a simple benchmark harness by default.
  - For live demos, the orchestrator will still spin three concurrent Codex instances and stream logs/episodes to the web logger.
  - If a domain‑specific tokamak_benchmark.py is provided later, the approach names above map 1:1 to variant implementations.

## Scoring
total: 100
weights: { correctness: 35, speed: 25, robustness: 25, brevity: 15 }
correctness:
  - degree‑of‑goal‑satisfaction: density targets, ELM suppression, flux management
  - constraints: safety (edge thresholds), stability (q, β), material limits
robustness:
  - sensitivity checks: parameter variations across profiles/edges
  - failure modes: disruption/ELM spikes, runaway heat flux
speed:
  - simulation/verification throughput for comparable scenarios
brevity:
  - implementation clarity and code size for the approach scaffolds

## References
- [1] arXiv:2306.00415 — MPC for plasma fueling/density control
- [2] OSTI 1430529 — Integrated multiphysics for heat management
- [3] Nature s41586‑021‑04301‑9 — ELM suppression via magnetic/wave strategies
- [4] S0920379617309031
- [5] IMSI: challenges in kinetic plasma physics
- [6] Chinese Phys. B 28(1):015201 (2019)
- [7] S0920379623001990
- [8] Physics of Plasmas 30(9):092510 (2023)

## Tasks
```json tasks
[
  {
    "type": "run_python",
    "name": "log_context",
    "scope": "pre",
    "code": "print('Tokamak approaches loaded: fueling_mpc, edge_stability_mhd, heat_extraction_adaptive')"
  },
  {
    "type": "run_python",
    "name": "emit_references",
    "scope": "pre",
    "code": "print('Key refs: [1],[2],[3],[8] — see prompt References block')"
  }
]
```

## Execution
concurrency: 3
codex_exec: true
autostart_backend: true
autostart_dashboard: true
notes:
  - Web logger streams to ArangoDB; use dashboard tabs (Status/Episodes/Logs).
  - Cmd/Ctrl+K for actions and ‘Copy Share URL’.
