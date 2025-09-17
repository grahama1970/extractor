## Codebase

repo_root: .

## Approaches

```yaml
- name: fueling_density_mpc
  summary: TBD
  verification: []
  outputs:
  - stability_margin
  - density_ok
  - heat_flux_peak
  - constraints_ok
- name: edge_stability_mhd
  summary: TBD
  verification: []
  outputs:
  - stability_margin
  - density_ok
  - heat_flux_peak
  - constraints_ok
- name: heat_extraction_adaptive
  summary: TBD
  verification: []
  outputs:
  - stability_margin
  - density_ok
  - heat_flux_peak
  - constraints_ok
```

## Runner

type: analysis_sim

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
edge_density_threshold: 1.0e+19
q_min: 2.0
beta_max: 0.04
heat_flux_peak_max: 10.0
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