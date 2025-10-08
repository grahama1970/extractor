#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List
import typer

app = typer.Typer(help="Detect numeric contradictions between constraints")


def detect_conflicts(items: List[Dict[str, Any]], pct_tol: float = 0.01, abs_tol: float = 1.0) -> List[Dict[str, Any]]:
    alerts = []
    # naive pairwise on same subject/unit
    by_key = {}
    for it in items:
        key = (it.get("subject"), it.get("unit"))
        by_key.setdefault(key, []).append(it)
    for key, group in by_key.items():
        vals = [(g.get("value"), g) for g in group if isinstance(g.get("value"), (int, float))]
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                v1, a = vals[i]; v2, b = vals[j]
                tol = max(abs(v1) * pct_tol, abs_tol)
                if abs(v1 - v2) <= tol:
                    alerts.append({
                        "type": "constraint_conflict",
                        "class": "near_conflict",
                        "severity": "low",
                        "subject": key[0],
                        "unit": key[1],
                        "old_value": v1,
                        "new_value": v2,
                        "tolerance": {"pct": pct_tol, "abs": abs_tol},
                    })
                else:
                    alerts.append({
                        "type": "constraint_conflict",
                        "class": "clear_conflict",
                        "severity": "medium",
                        "subject": key[0],
                        "unit": key[1],
                        "old_value": v1,
                        "new_value": v2,
                        "tolerance": {"pct": pct_tol, "abs": abs_tol},
                    })
    return alerts


@app.command()
def run(input_json: Path = typer.Option(..., "--input", exists=True), output_json: Path = typer.Option(Path("data/results/pipeline/alerts/alerts.json"), "--output")):
    items = json.loads(input_json.read_text())
    alerts = detect_conflicts(items)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps({"alerts": alerts}, indent=2))
    typer.echo(f"alerts: {len(alerts)} written to {output_json}")

if __name__ == "__main__":
    app()

