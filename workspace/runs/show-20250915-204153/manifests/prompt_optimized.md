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