#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


def _import_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _count_loc_for_function(path: Path, func_name: str) -> int:
    try:
        src = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return 0
    start = None
    indent = None
    count = 0
    for i, ln in enumerate(src):
        if re.match(rf"\s*def\s+{re.escape(func_name)}\s*\(", ln):
            start = i
            indent = len(ln) - len(ln.lstrip())
            continue
        if start is not None:
            if re.match(r"\s*def\s+\w+\s*\(", ln) and (len(ln) - len(ln.lstrip())) <= (indent or 0):
                break
            s = ln.strip()
            if s and not s.startswith("#"):
                count += 1
    return count


def _rand_int_with_digits(d: int) -> int:
    if d <= 0:
        return 0
    first = random.randint(1, 9)
    rest = [random.randint(0, 9) for _ in range(max(0, d - 1))]
    n = int(str(first) + "".join(str(x) for x in rest))
    if random.random() < 0.5:
        n = -n
    return n


@dataclass
class ScaleCfg:
    digits: int
    trials: int
    timeout_ms: int | None = None


def run_one(
    approach: str, baseline_path: Path, variants_path: Path, scales: Dict[str, ScaleCfg], seed: int
) -> Dict:
    random.seed(seed)
    baseline_mod = _import_from(baseline_path, "baseline")
    variants_mod = _import_from(variants_path, "variants")
    base_fn = getattr(baseline_mod, "multiply")
    fn = getattr(variants_mod, approach)

    # Robustness battery
    robust_pairs = [
        (0, 0),
        (0, 5),
        (5, 0),
        (-7, 3),
        (7, -3),
        (-7, -3),
        (10**6, 10**6),
        (-(10**6), 10**6),
        (-(10**6), -(10**6)),
    ]
    robust_ok = True
    for a, b in robust_pairs:
        try:
            if fn(a, b) != base_fn(a, b):
                robust_ok = False
                break
        except Exception:
            robust_ok = False
            break

    timings: Dict[str, float] = {}
    correctness: Dict[str, bool] = {}

    for name, cfg in scales.items():
        ok = True
        total = 0.0
        for _ in range(cfg.trials):
            a = _rand_int_with_digits(cfg.digits)
            b = _rand_int_with_digits(cfg.digits)
            t0 = time.perf_counter()
            try:
                got = fn(a, b)
            except Exception:
                ok = False
                break
            t1 = time.perf_counter()
            # timeout check
            dt_ms = (t1 - t0) * 1000.0
            if cfg.timeout_ms is not None and dt_ms > cfg.timeout_ms:
                ok = False
                break
            ref = base_fn(a, b)
            if got != ref:
                ok = False
                break
            total += dt_ms
        correctness[name] = ok
        if ok:
            timings[name] = total / max(1, cfg.trials)
        else:
            timings[name] = float("inf")

    # LOC for brevity
    loc = _count_loc_for_function(variants_path, approach)

    return {
        "approach": approach,
        "correctness": correctness,
        "timings_ms": timings,
        "robust": robust_ok,
        "loc": loc,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--approach", required=True)
    ap.add_argument("--baseline", default="src/core/multiply.py")
    ap.add_argument("--variants", default="src/algos/multiply_variants.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1337)
    # Scales
    ap.add_argument("--S_digits", type=int, default=6)
    ap.add_argument("--S_trials", type=int, default=5)
    ap.add_argument("--M_digits", type=int, default=200)
    ap.add_argument("--M_trials", type=int, default=5)
    ap.add_argument("--L_digits", type=int, default=2000)
    ap.add_argument("--L_trials", type=int, default=5)
    ap.add_argument("--L_timeout_ms", type=int, default=2000)
    args = ap.parse_args()

    scales = {
        "S": ScaleCfg(args.S_digits, args.S_trials),
        "M": ScaleCfg(args.M_digits, args.M_trials),
        "L": ScaleCfg(args.L_digits, args.L_trials, args.L_timeout_ms),
    }

    baseline_path = Path(args.baseline)
    variants_path = Path(args.variants)
    res = run_one(args.approach, baseline_path, variants_path, scales, args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": args.out}))


if __name__ == "__main__":
    main()
