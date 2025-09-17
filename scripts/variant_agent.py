#!/usr/bin/env python3
"""
Variant Agent (Deterministic v1)

Agent Contract (summary):
- Self-iterating, headless worker for a single approach.
- Loop: synthesize template if missing -> run benchmark -> write JSON summaries -> deterministic mutate -> repeat until plateau (epsilon/window) or max iters.
- Artifacts per iteration: iter_XX.json (raw) + iter_XX_summary.json (score, metrics, stderr/stdout digests, mutation info).
- No external LLM calls in this v1. (An LLM-enabled variant can replace the mutation step but must keep JSON contracts.)
"""
from __future__ import annotations

import argparse
import json
import time
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, List


def _post_json(url: str, payload: Dict[str, Any]) -> None:
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _function_exists(module_path: Path, func_name: str) -> bool:
    try:
        txt = module_path.read_text(encoding="utf-8")
    except Exception:
        return False
    needle = f"def {func_name}("
    return needle in txt


def _append_code(module_path: Path, code: str) -> None:
    module_path.parent.mkdir(parents=True, exist_ok=True)
    if not module_path.exists():
        module_path.write_text(code.strip() + "\n", encoding="utf-8")
        return
    with module_path.open("a", encoding="utf-8") as f:
        f.write("\n\n" + code.strip() + "\n")


def _template_for(approach: str) -> Optional[str]:
    if approach == "mul_shift_add":
        return (
            "def mul_shift_add(a: int, b: int) -> int:\n"
            "    \"\"\"Iterative shift-add (Russian peasant) with sign correction.\"\"\"\n"
            "    sign = -1 if (a < 0) ^ (b < 0) else 1\n"
            "    x, y = abs(a), abs(b)\n"
            "    res = 0\n"
            "    while y > 0:\n"
            "        if y & 1:\n"
            "            res += x\n"
            "        x <<= 1\n"
            "        y >>= 1\n"
            "    return res * sign\n"
        )
    if approach == "mul_karatsuba":
        return (
            "def mul_karatsuba(a: int, b: int) -> int:\n"
            "    \"\"\"Karatsuba multiplication with tunable bit cutoff.\n"
            "    CUTOFF_BITS = 64\n"
            "    \"\"\"\n"
            "    sign = -1 if (a < 0) ^ (b < 0) else 1\n"
            "    x, y = abs(a), abs(b)\n"
            "\n"
            "    def kar(u: int, v: int) -> int:\n"
            "        if u == 0 or v == 0:\n"
            "            return 0\n"
            "        if u.bit_length() <= CUTOFF_BITS and v.bit_length() <= CUTOFF_BITS:\n"
            "            return u * v\n"
            "        n = max(u.bit_length(), v.bit_length())\n"
            "        m = n // 2\n"
            "        uh, ul = u >> m, u & ((1 << m) - 1)\n"
            "        vh, vl = v >> m, v & ((1 << m) - 1)\n"
            "        z0 = kar(ul, vl)\n"
            "        z2 = kar(uh, vh)\n"
            "        z1 = kar(ul + uh, vl + vh) - z2 - z0\n"
            "        return (z2 << (2 * m)) + (z1 << m) + z0\n"
            "\n"
            "    return sign * kar(x, y)\n"
        )
    if approach == "mul_chunked":
        return (
            "def mul_chunked(a: int, b: int) -> int:\n"
            "    \"\"\"Chunked schoolbook multiplication with tunable base exponent.\n"
            "    BASE_EXP = 4  # base = 10**BASE_EXP\n"
            "    \"\"\"\n"
            "    sign = -1 if (a < 0) ^ (b < 0) else 1\n"
            "    x, y = abs(a), abs(b)\n"
            "    if x == 0 or y == 0:\n"
            "        return 0\n"
            "    base = 10 ** BASE_EXP\n"
            "    ax, ay = [], []\n"
            "    while x:\n"
            "        ax.append(x % base)\n"
            "        x //= base\n"
            "    while y:\n"
            "        ay.append(y % base)\n"
            "        y //= base\n"
            "    n, m = len(ax), len(ay)\n"
            "    out = [0] * (n + m)\n"
            "    for i in range(n):\n"
            "        carry = 0\n"
            "        for j in range(m):\n"
            "            s = out[i + j] + ax[i] * ay[j] + carry\n"
            "            out[i + j] = s % base\n"
            "            carry = s // base\n"
            "        k = i + m\n"
            "        while carry:\n"
            "            s = out[k] + carry\n"
            "            out[k] = s % base\n"
            "            carry = s // base\n"
            "            k += 1\n"
            "    res = 0\n"
            "    for d in reversed(out):\n"
            "        res = res * base + d\n"
            "    return res * sign\n"
        )
    return None


def _synthesize_if_missing(approach: str, variants_path: Path, prompt_file: Optional[Path], api_base: str, run_id: str) -> None:
    if _function_exists(variants_path, approach):
        return
    code = _template_for(approach)
    if code:
        _append_code(variants_path, code)
        _post_json(api_base.rstrip("/") + "/ingest/log", {"ts": time.time(), "run_id": run_id, "variant": approach, "episode_id": None, "stream": "app", "source": "variant_agent", "message": "synthesis: template added", "meta": {}})
    else:
        _post_json(api_base.rstrip("/") + "/ingest/log", {"ts": time.time(), "run_id": run_id, "variant": approach, "episode_id": None, "stream": "stderr", "source": "variant_agent", "message": "no template for approach; skipping", "meta": {}})


def _extract_function_block(text: str, func_name: str) -> tuple[int, int]:
    """Return (start_idx, end_idx) char indices of the function block or (-1, -1)."""
    needle = f"def {func_name}("
    i = text.find(needle)
    if i == -1:
        return -1, -1
    # Find start of line
    start = text.rfind("\n", 0, i)
    if start == -1:
        start = 0
    else:
        start += 1
    # Heuristic: function ends before next top-level def (column 0)
    j = i
    while True:
        j = text.find("\n", j + 1)
        if j == -1:
            return start, len(text)
        # Next line start
        k = j + 1
        # End if a new top-level def/class starts
        if text.startswith("def ", k) or text.startswith("class ", k):
            return start, j


def _replace_function(module_path: Path, func_name: str, new_code: str) -> None:
    try:
        src = module_path.read_text(encoding="utf-8")
    except Exception:
        src = ""
    s, e = _extract_function_block(src, func_name)
    if s == -1:
        _append_code(module_path, new_code)
        return
    updated = src[:s] + new_code.strip() + "\n" + src[e:]
    module_path.write_text(updated, encoding="utf-8")


def _mutate_based_on_metrics(approach: str, variants_path: Path, metrics: Dict[str, Any], prompt_file: Optional[Path], api_base: str, run_id: str) -> tuple[bool, Dict[str, Any]]:
    """Deterministic parameter tuning per approach (no external LLM)."""
    try:
        txt = variants_path.read_text(encoding="utf-8") if variants_path.exists() else ""
    except Exception:
        txt = ""
    changed = False
    info: Dict[str, Any] = {}
    if approach == "mul_karatsuba":
        import re
        grid: List[int] = [32, 48, 64, 80, 96, 128]
        m = re.search(r"CUTOFF_BITS\s*=\s*(\d+)", txt)
        cur = int(m.group(1)) if m else 64
        idx = grid.index(cur) if cur in grid else 2
        nxt = grid[idx + 1] if idx + 1 < len(grid) else None
        if nxt is not None:
            new_txt = re.sub(r"CUTOFF_BITS\s*=\s*\d+", f"CUTOFF_BITS = {nxt}", txt)
            variants_path.write_text(new_txt, encoding="utf-8")
            changed = True
            info = {"change_reason": f"CUTOFF_BITS {cur} -> {nxt}", "expected_impact": {"S": "same", "M": "faster", "L": "faster"}, "risks": ["too small cutoff reduces asymptotic benefit"]}
    elif approach == "mul_chunked":
        import re
        grid: List[int] = [3, 4, 5, 6]
        m = re.search(r"BASE_EXP\s*=\s*(\d+)", txt)
        cur = int(m.group(1)) if m else 4
        idx = grid.index(cur) if cur in grid else 1
        nxt = grid[idx + 1] if idx + 1 < len(grid) else None
        if nxt is not None:
            new_txt = re.sub(r"BASE_EXP\s*=\s*\d+", f"BASE_EXP = {nxt}", txt)
            variants_path.write_text(new_txt, encoding="utf-8")
            changed = True
            info = {"change_reason": f"BASE_EXP {cur} -> {nxt}", "expected_impact": {"S": "same", "M": "faster", "L": "faster"}, "risks": ["carry overhead with very large base"]}
    elif approach == "mul_shift_add":
        changed = False
        info = {"change_reason": "no tunables", "expected_impact": {"S": "same", "M": "same", "L": "same"}, "risks": []}
    return changed, info


def _score_single_variant(metrics: Dict[str, Any]) -> float:
    # Per-variant internal score (no cross-variant ranking).
    # - Correctness: 45 points total (15 per S/M/L) if all trials correct on a scale
    # - Speed: 35 points split S=11, M=12, L=12 using inverse scaling against simple targets
    # - Robustness: 10 points if robust
    # - Brevity: 10 points scaled for lower LOC (1..200)
    corr = metrics.get("correctness", {})
    times = metrics.get("timings_ms", {})
    robust = bool(metrics.get("robust"))
    loc = int(metrics.get("loc", 200))

    total = 0.0
    # Correctness
    for s in ("S", "M", "L"):
        if corr.get(s):
            total += 15.0
    # Speed vs fixed targets (rough)
    targets = {"S": 0.1, "M": 5.0, "L": 200.0}
    splits = {"S": 11.0, "M": 12.0, "L": 12.0}
    for s in ("S", "M", "L"):
        t = float(times.get(s, float("inf")))
        if not corr.get(s) or t == float("inf"):
            continue
        pts = max(0.0, min(1.0, targets[s] / max(targets[s], t))) * splits[s]
        total += pts
    # Robustness
    total += 10.0 if robust else 0.0
    # Brevity (1..200 -> 10..0)
    loc = max(1, min(loc, 200))
    total += (200 - loc) / 199.0 * 10.0
    return round(total, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--approach", required=True)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--variants", required=True)
    ap.add_argument("--api-base", default="http://localhost:8000")
    ap.add_argument("--run-id", default="gamified")
    ap.add_argument("--epsilon", type=float, default=0.1)
    ap.add_argument("--window", type=int, default=5)
    ap.add_argument("--max-iters", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--prompt-file", help="Path to per-instance prompt markdown", default=None)
    ap.add_argument("--out-dir", help="Directory for this instance's outputs", default=None)
    # Accept and forward any additional benchmark-specific args instead of failing.
    # This lets callers tune S/M/L scales, trials, timeouts, etc., without changing the agent.
    args, bench_extra = ap.parse_known_args()

    approach = args.approach
    api_base = args.api_base.rstrip("/")

    log_url = api_base + "/ingest/log"
    epi_url = api_base + "/ingest/episode"

    def log(stream: str, msg: str, meta: Optional[Dict[str, Any]] = None):
        _post_json(
            log_url,
            {
                "ts": time.time(),
                "run_id": args.run_id,
                "variant": approach,
                "episode_id": None,
                "stream": stream,
                "source": "variant_agent",
                "message": msg,
                "meta": meta or {},
            },
        )

    scores: list[float] = []
    best: Dict[str, Any] = {}

    # Resolve out directory
    out_dir = Path(args.out_dir) if args.out_dir else Path(f"workspace/agent/{args.run_id}_{approach}")
    out_dir.mkdir(parents=True, exist_ok=True)
    # Log prompt file path if provided
    if args.prompt_file:
        try:
            p = Path(args.prompt_file)
            meta = {"prompt_file": str(p.resolve()), "prompt_bytes": p.stat().st_size}
        except Exception:
            meta = {"prompt_file": args.prompt_file}
        log("app", "instance prompt attached", meta)
    log("app", f"variant agent start: {approach}")
    # Synthesize code for this approach if missing
    _synthesize_if_missing(approach, Path(args.variants), Path(args.prompt_file) if args.prompt_file else None, api_base, args.run_id)

    for it in range(1, args.max_iters + 1):
        # Run benchmark
        out_file = out_dir / f"iter_{it:02d}.json"
        cmd = [
            "python",
            args.bench,
            "--approach",
            approach,
            "--baseline",
            args.baseline,
            "--variants",
            args.variants,
            "--out",
            str(out_file),
            "--seed",
            str(args.seed + it),
        ]
        # Forward any extra args intended for the benchmark
        if bench_extra:
            cmd.extend(bench_extra)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stderr:
            for ln in proc.stderr.splitlines():
                log("stderr", ln)
        metrics: Dict[str, Any] = {}
        try:
            metrics = json.loads(out_file.read_text())
        except Exception as e:
            log("stderr", f"metrics parse failed: {e}")
            break

        score = _score_single_variant(metrics)
        scores.append(score)

        # Write iteration summary JSON (for parent + instance)
        summary = {
            "iter": it,
            "score": score,
            "metrics": metrics,
            "stderr_sample": (proc.stderr or "").splitlines()[-10:] if proc.stderr else [],
            "stdout_sample": (proc.stdout or "").splitlines()[-10:] if proc.stdout else [],
            "stderr_lines": len((proc.stderr or "").splitlines()) if proc.stderr else 0,
            "stdout_lines": len((proc.stdout or "").splitlines()) if proc.stdout else 0,
        }
        (out_dir / f"iter_{it:02d}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        # Post episode update
        _post_json(
            epi_url,
            {
                "ts": time.time(),
                "run_id": args.run_id,
                "episode_id": f"{approach}-iter-{it}",
                "variant": approach,
                "pass": True,
                "score": score,
                "metrics": metrics,
                "error_count": 0 if all(metrics.get("correctness", {}).values()) else 1,
                "screenshots": [],
            },
        )

        # Track best
        if not best or score > best.get("score", -1):
            best = {"score": score, "iter": it, "metrics": metrics}

        # Plateau detection
        w = args.window
        if len(scores) >= w:
            recent = scores[-w:]
            diffs = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
            slope = sum(diffs) / max(1, len(diffs))
            log("app", f"iter {it} score={score:.2f} slope={slope:.3f}")
            if abs(slope) < args.epsilon:
                log("app", f"plateau detected at iter {it}; stopping")
                break

        # Mutation step: propose code change based on metrics
        changed, info = _mutate_based_on_metrics(approach, Path(args.variants), metrics, Path(args.prompt_file) if args.prompt_file else None, api_base, args.run_id)
        # Update summary with mutation info
        try:
            summary_path = out_dir / f"iter_{it:02d}_summary.json"
            data = json.loads(summary_path.read_text())
            data["mutation"] = {"applied": bool(changed), **({k: v for k, v in (info or {}).items() if v is not None})}
            summary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass
        if not changed:
            log("app", "no mutation applied; continuing to next iteration")

    # Finish
    log("app", f"variant agent complete: {approach}; best={best.get('score')}")
    # Write done sentinel with brief summary
    try:
        (out_dir / "done.json").write_text(
            json.dumps({
                "ok": True,
                "variant": approach,
                "best_score": best.get("score"),
                "best_iter": best.get("iter"),
            }, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
