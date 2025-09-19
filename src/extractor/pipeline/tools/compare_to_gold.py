#!/usr/bin/env python3
"""Compare a stage output JSON against its gold standard expectations.

Usage:
  python -m extractor.pipeline.tools.compare_to_gold \
    --output data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json \
    --gold data/gold_standards/pipeline/002_marker_extractor_gs.json

Checks use the `expected_invariants` section of the gold JSON when present.
This script prints a human-readable summary and exits non-zero on hard failures.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import typer

app = typer.Typer(help="Compare a stage output JSON to its gold standard invariants")


@dataclass
class CompareResult:
    passed: bool
    details: Dict[str, Any]


def _load(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _has_keys(d: Dict[str, Any], keys: List[str]) -> Tuple[bool, List[str]]:
    missing = [k for k in keys if k not in d]
    return (len(missing) == 0, missing)


def compare(output: Dict[str, Any], gold: Dict[str, Any]) -> CompareResult:
    res: Dict[str, Any] = {"checks": []}
    ok = True

    invariants: Dict[str, Any] = gold.get("expected_invariants", {})
    top_level_keys = invariants.get("top_level_keys", [])
    if top_level_keys:
        has, missing = _has_keys(output, top_level_keys)
        res["checks"].append(
            {
                "name": "top_level_keys",
                "pass": has,
                "missing": missing,
            }
        )
        ok &= has

    # Heuristic item-level checks for blocks/sections/etc.
    if "blocks" in output and isinstance(output["blocks"], list):
        need = invariants.get("block_item_keys_min", [])
        if need:
            sample = output["blocks"][:5]
            missing_any = []
            for idx, item in enumerate(sample):
                if not isinstance(item, dict):
                    missing_any.append(f"item{idx}:not_dict")
                    continue
                _, miss = _has_keys(item, need)
                if miss:
                    missing_any.append({"idx": idx, "missing": miss})
            res["checks"].append(
                {
                    "name": "block_item_keys_min",
                    "pass": not missing_any,
                    "violations": missing_any,
                }
            )
            ok &= not missing_any

    if "sections" in output and isinstance(output["sections"], list):
        need = invariants.get("section_item_keys_min", [])
        if need:
            sample = output["sections"][:3]
            missing_any = []
            for idx, item in enumerate(sample):
                if not isinstance(item, dict):
                    missing_any.append(f"section{idx}:not_dict")
                    continue
                _, miss = _has_keys(item, need)
                if miss:
                    missing_any.append({"idx": idx, "missing": miss})
            res["checks"].append(
                {
                    "name": "section_item_keys_min",
                    "pass": not missing_any,
                    "violations": missing_any,
                }
            )
            ok &= not missing_any

    res["pass"] = ok
    return CompareResult(passed=ok, details=res)


@app.command()
def run(
    output: Path = typer.Option(
        ...,
        "--output",
        help="Path to stage output JSON",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    gold: Path = typer.Option(
        ...,
        "--gold",
        help="Path to gold standard JSON",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON report"),
) -> None:
    try:
        out_d = _load(output)
        gold_d = _load(gold)
    except Exception as e:
        typer.secho(f"Load error: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)

    result = compare(out_d, gold_d)
    if json_out:
        print(json.dumps(result.details, indent=2))
    else:
        print("=== Compare to Gold ===")
        print(f"Output: {output}")
        print(f"Gold:   {gold}")
        for c in result.details.get("checks", []):
            status = "PASS" if c.get("pass") else "FAIL"
            print(f"- {c.get('name')}: {status}")
            extra = {k: v for k, v in c.items() if k not in ("name", "pass")}
            if extra:
                print(f"  details: {extra}")
        print(f"Overall: {'PASS' if result.passed else 'FAIL'}")

    raise typer.Exit(0 if result.passed else 1)


if __name__ == "__main__":
    app()
