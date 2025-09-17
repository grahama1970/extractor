from __future__ import annotations

from pathlib import Path
from typing import List, Optional

try:
    from pydantic import BaseModel, Field, model_validator
except Exception:  # pragma: no cover
    class BaseModel:  # type: ignore
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)
        def model_dump(self):
            return self.__dict__
    def Field(default=None, **_):
        return default
    def model_validator(*_, **__):
        def deco(f):
            return f
        return deco

import yaml  # type: ignore


class Codebase(BaseModel):
    repo_root: str = Field(default='.')


class Approach(BaseModel):
    name: str
    summary: Optional[str] = None
    verification: Optional[List[str]] = None


class Runner(BaseModel):
    type: str = Field(default='analysis_sim')
    notes: Optional[str] = None


class Scoring(BaseModel):
    weights: dict = Field(default_factory=lambda: {'correctness': 35, 'robustness': 25, 'speed': 25, 'brevity': 15})

    @model_validator(mode='after')
    def _normalize(self):  # type: ignore
        w = self.weights or {}
        s = float(sum(float(v) for v in w.values())) or 1.0
        if abs(s - 100.0) > 1e-6:
            factor = 100.0 / s
            self.weights = {k: float(round(v * factor, 6)) for k, v in w.items()}
        return self


class Optimizer(BaseModel):
    rules: str = Field(default='prototypes/gamified/rules/prompt_optimization.yaml')


class Execution(BaseModel):
    concurrency: int = 3
    codex_exec: bool = True
    autostart_backend: bool = True
    autostart_dashboard: bool = True


class Observability(BaseModel):
    backend: str = Field(default='arango')
    dashboard: bool = True


class Constraints(BaseModel):
    edge_density_threshold: float
    q_min: float
    beta_max: float
    heat_flux_peak_max: float


class SpecV1(BaseModel):
    version: int = 1
    codebase: Codebase
    approaches: List[Approach]
    runner: Runner = Field(default_factory=Runner)
    scoring: Scoring = Field(default_factory=Scoring)
    constraints: Constraints
    optimizer: Optimizer = Field(default_factory=Optimizer)
    execution: Execution = Field(default_factory=Execution)
    observability: Observability = Field(default_factory=Observability)

    @model_validator(mode='after')
    def _checks(self):  # type: ignore
        if not self.approaches or len(self.approaches) < 3:
            raise ValueError('spec.approaches: need at least 3 approaches')
        if len(self.approaches) > 5:
            raise ValueError('spec.approaches: at most 5 approaches')
        for a in self.approaches:
            nm = a.name.strip()
            if not nm or not (nm[0].isalpha()):
                raise ValueError(f'approach name invalid: {a.name}')
        return self


def load_spec(path: Path | str) -> SpecV1:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('spec: YAML must be a mapping at top-level')
    return SpecV1(**data)


def render_prompt(spec: SpecV1) -> str:
    lines: List[str] = []
    lines.append("## Codebase\n")
    lines.append(f"repo_root: {spec.codebase.repo_root}\n")

    lines.append("## Approaches\n")
    app_items = []
    for a in spec.approaches:
        app_items.append({
            'name': a.name,
            'summary': (a.summary or ''),
            'verification': (a.verification or []),
            'outputs': ['stability_margin', 'density_ok', 'heat_flux_peak', 'constraints_ok'],
        })
    lines.append("```yaml\n" + yaml.safe_dump(app_items, sort_keys=False) + "```\n")

    lines.append("## Runner\n")
    lines.append(f"type: {spec.runner.type}\n")
    if spec.runner.notes:
        lines.append(f"notes: {spec.runner.notes}\n")

    lines.append("\n## Scoring\n")
    lines.append("```yaml\n" + yaml.safe_dump({"weights": spec.scoring.weights}, sort_keys=False) + "```\n")

    lines.append("\n## Constraints\n")
    c_map = {
        'edge_density_threshold': spec.constraints.edge_density_threshold,
        'q_min': spec.constraints.q_min,
        'beta_max': spec.constraints.beta_max,
        'heat_flux_peak_max': spec.constraints.heat_flux_peak_max,
    }
    lines.append("```yaml\n" + yaml.safe_dump(c_map, sort_keys=False) + "```\n")

    lines.append("\n## Execution\n")
    exec_map = {
        'execution': {
            'concurrency': spec.execution.concurrency,
            'codex_exec': spec.execution.codex_exec,
            'autostart_backend': spec.execution.autostart_backend,
            'autostart_dashboard': spec.execution.autostart_dashboard,
        }
    }
    lines.append("```yaml\n" + yaml.safe_dump(exec_map, sort_keys=False) + "```\n")

    return '\n'.join(lines).strip() + '\n'
