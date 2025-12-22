#!/usr/bin/env python3
"""
Gamified Orchestrator CLI (canonical location under prototypes/gamified)

This Typer app owns the orchestrator logic. The legacy entrypoint at
scripts/gamified.py imports and re-exports this app to maintain CLI/CI stability.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import socket
from pathlib import Path
import asyncio
from typing import Optional, List, Dict, Any

import typer

try:
    # Prefer robust asyncio-based runner for Codex exec (deprecated helper)
    from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec  # type: ignore
except Exception:  # pragma: no cover - optional import for environments without src on PYTHONPATH
    run_codex_exec = None  # type: ignore

app = typer.Typer(help="Run gamified evaluation in one command: codebase + prompt/rules + instances")


def _which(cmd: str) -> bool:
    return shutil.which(cmd) is not None



def _is_exe(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.access(path, os.X_OK)
    except Exception:
        return False


def _find_codex_bin() -> str:
    """Resolve codex binary path.
    - Prefer explicit CODEX_BINARY_PATH
    - Then PATH via shutil.which('codex')
    - Fallback to $CODEX_HOME/bin/codex if present
    - Otherwise return 'codex' and let caller handle availability check
    """
    explicit = os.environ.get("CODEX_BINARY_PATH")
    if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        return explicit
    p = shutil.which("codex")
    if p:
        return p
    home = os.environ.get("CODEX_HOME")
    if home:
        from pathlib import Path as _P
        cand = _P(home) / "bin" / "codex"
        if cand.exists():
            return cand.as_posix()
    # nvm fallback: ~/.nvm/versions/node/*/bin/codex (pick latest by name)
    try:
        nvm_root = Path(os.environ.get("NVM_DIR", Path.home() / ".nvm"))
        vroot = nvm_root / "versions" / "node"
        if vroot.exists():
            vers = sorted([p for p in vroot.iterdir() if p.is_dir()])
            for candidate in reversed(vers):  # newest-ish first
                cb = candidate / "bin" / "codex"
                if cb.exists() and os.access(cb, os.X_OK):
                    return cb.as_posix()
    except Exception:
        pass
    return "codex"

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _find_free_port(host: str = "127.0.0.1") -> int:
    s = socket.socket()
    try:
        s.bind((host, 0))
        return s.getsockname()[1]
    finally:
        try:
            s.close()
        except Exception:
            pass


def _parse_api_base(api_base: str) -> tuple[str, str, Optional[int]]:
    try:
        scheme = "http"
        rest = api_base
        if "://" in api_base:
            scheme, rest = api_base.split("://", 1)
        host_port = rest.split("/", 1)[0]
        if ":" in host_port:
            host, port_s = host_port.split(":", 1)
            return scheme, host, int(port_s)
        return scheme, host_port, None
    except Exception:
        return "http", "127.0.0.1", None


def _compose_api_base(scheme: str, host: str, port: int) -> str:
    return f"{scheme}://{host}:{port}"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _ensure_gamified_skeleton() -> None:
    """Best-effort: recreate prototypes/gamified skeleton if missing. No overwrite."""
    root = Path("prototypes/gamified").resolve()
    (root / "rules").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    # README
    _ensure_file(
        root / "README.md",
        "# Gamified Orchestrator (Prototype)\n\nThis directory contains prompt-first assets for the Codex-exec orchestrator.\nIf this folder was recreated automatically, minimal defaults were written.\n",
    )
    # Rules defaults
    _ensure_file(
        root / "rules/score_v1.json",
        json.dumps(
            {
                "scoring": {
                    "weights": {
                        "efficiency": 0.55,
                        "accuracy": 0.20,
                        "stability": 0.15,
                        "ux": 0.10,
                    }
                },
                "plateau": {"epsilon": 0.15, "window": 5},
            },
            indent=2,
        ),
    )
    # Prompt default
    prompt_path = root / "docs/prompt_multiplication_with_tasks.md"
    _ensure_file(
        prompt_path,
        """## Gamified Run Spec — Multiplication POC (with tasks)

## Codebase
repo_root: .

## Mode
mode: generate

## Baseline
path: src/core/multiply.py
create_if_missing: true
content: |
  def multiply(a: int, b: int) -> int:
      '''Baseline: delegate to Python's built-in integer multiplication.'''
      return a * b

## Approaches
# Invent three distinct multiplication strategies. Do not assume prior specifics.
# For each, provide a short name and a one-paragraph mechanics description (how it works in general terms).
# The agent will concretize and implement them.

## Runner
type: python_benchmark
entry: bench/multiply_benchmark.py
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
""",
    )


def _start_dashboard(api_base: str, port: int = 5199) -> Optional[subprocess.Popen]:
    """Start the React dashboard (vite dev) in the background. Returns the Popen or None."""
    dashboard_dir = Path("prototypes/gamified/dashboard").resolve()
    if not (dashboard_dir / "package.json").exists():
        typer.echo("[dashboard] package.json not found; skipping dashboard start")
        return None
    env = os.environ.copy()
    env["VITE_API_BASE"] = api_base
    # Hint port to vite via common env keys; vite can read PORT in vite.config
    env["PORT"] = str(port)
    env["VITE_PORT"] = str(port)
    # Ensure deps installed once (best-effort)
    try:
        subprocess.run(["npm", "install"], cwd=str(dashboard_dir), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(dashboard_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        typer.echo(f"[dashboard] Started on http://localhost:{port} (VITE_API_BASE={api_base})")
        return proc
    except Exception as e:
        typer.echo(f"[dashboard] failed to start: {e}")
        return None


def _stop_process(proc: Optional[subprocess.Popen]) -> None:
    if not proc:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
        if proc.poll() is None:
            proc.kill()
    except Exception:
        pass


def _slug(name: str) -> str:
    s = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in name.strip().lower())
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "v"


def _parse_approaches_from_prompt(prompt: str) -> List[Dict[str, str]]:
    import re
    text = prompt or ""
    # Try to isolate the Approaches section
    m = re.search(r"##\s*Approaches\s*(.*?)\n## ", text, flags=re.S|re.I)
    block = m.group(1) if m else text
    names: List[str] = []
    # 1) YAML code block parsing by regex: "- name: XYZ"
    for line in block.splitlines():
        mm = re.match(r"\s*-\s*name\s*:\s*([A-Za-z0-9_\-]+)", line)
        if mm:
            names.append(mm.group(1).strip())
    # 2) Fallback to bullets and inline lists
    if not names:
        lines_raw = text.splitlines()
        lines = [ln.rstrip() for ln in lines_raw]
        items: List[str] = []
        acc: List[str] = []
        capturing = False
        for ln in lines:
            low = ln.strip().lower()
            if low.startswith("approaches:") or low.startswith("approach:") or low.startswith("try ") or low == "try:" or low == "approaches" or low == "approach" or low.startswith("#") and "approaches" in low:
                capturing = True
                if ":" in ln and not ln.strip().startswith("#"):
                    tail = ln.split(":", 1)[1].strip()
                    if tail:
                        acc.append(tail)
                continue
            if capturing:
                if not ln:
                    break
                if ln.lstrip()[:1] in ("-", "*", "•"):
                    acc.append(ln.split(ln.lstrip()[:1], 1)[1].strip())
                elif ln[:2].isdigit() and ln[1:2] == ".":
                    acc.append(ln[2:].strip())
                else:
                    if ln.strip().startswith("#") or ln.strip().endswith(":"):
                        break
                    else:
                        continue
        if not acc:
            mm2 = re.search(r"(?:approaches|approach|try)\s*:?\s*(.+)", text, flags=re.IGNORECASE)
            if mm2:
                acc = [x.strip() for x in mm2.group(1).split(",") if x.strip()]
        for s in acc:
            parts = [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]
            for it in (parts if parts else [s]):
                if it.lower().startswith("name:"):
                    names.append(it.split(":", 1)[1].strip())
                else:
                    names.append(it)
    # Normalize and uniquify
    seen = set()
    out: List[Dict[str, str]] = []
    for it in names:
        if not it:
            continue
        nm = _slug(it)
        if nm in seen:
            idx = 2
            nn = f"{nm}-{idx}"
            while nn in seen:
                idx += 1
                nn = f"{nm}-{idx}"
            nm = nn
        seen.add(nm)
        out.append({"name": nm, "hint": it})
    return out


def _parse_codebase_from_prompt(prompt: str) -> Optional[Path]:
    import re
    for ln in (prompt or "").splitlines():
        if ":" in ln and ln.lower().strip().startswith(("codebase:", "path:", "dir:", "directory:", "repo_root:")):
            p = ln.split(":", 1)[1].strip()
            if p:
                pp = Path(p).expanduser()
                if pp.exists() and pp.is_dir():
                    return pp
    # fallback: look for an absolute path-like token
    m = re.search(r"(/[^\s]+)", prompt)
    if m:
        pp = Path(m.group(1)).expanduser()
        if pp.exists() and pp.is_dir():
            return pp
    return None


def _compile_prompt_to_rules(prompt: str, base_rules_path: Path) -> dict:
    """Deterministic prompt compiler: extracts approaches and merges universal rules.
    Keep it simple and offline; power users can still pass --rules explicitly.
    """
    base = _read_json(base_rules_path)
    if not base:
        base = {
            "scoring": {
                "weights": {"efficiency": 0.55, "accuracy": 0.20, "stability": 0.15, "ux": 0.10}
            },
            "plateau": {"epsilon": 0.15, "window": 5},
        }
    variants = _parse_approaches_from_prompt(prompt)
    rules: Dict[str, Any] = {
        "meta": {"name": "prompt-run"},
        "variants": variants,
        "scoring": {
            "weights": (base.get("weights") or base.get("scoring", {}).get("weights") or {"efficiency": 0.55, "accuracy": 0.20, "stability": 0.15, "ux": 0.10})
        },
        "plateau": base.get("plateau", {"epsilon": 0.15, "window": 5}),
    }
    return rules


def _ensure_file(path: Path, content: str, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return
    path.write_text(content, encoding="utf-8")


def _generate_multiplication_poc(codebase: Path, approaches: List[Dict[str, str]]) -> Dict[str, Any]:
    """Create baseline, variants, and benchmark if missing.
    Returns dict with paths and approach names.
    """
    root = codebase.resolve()
    baseline = root / "src/core/multiply.py"
    variants = root / "src/algos/multiply_variants.py"
    bench = root / "bench/multiply_benchmark.py"

    _ensure_file(
        baseline,
        """def multiply(a: int, b: int) -> int:\n    \"\"\"Baseline: delegate to Python's built-in integer multiplication.\"\"\"\n    return a * b\n""",
    )
    # Provide working defaults if not present (reuse repo's reference implementations)
    # Adjust for location under prototypes/gamified: repo root is two levels up
    repo_root = Path(__file__).resolve().parents[2]
    if not variants.exists():
        _ensure_file(variants, (repo_root / "src/algos/multiply_variants.py").read_text(encoding="utf-8"))
    if not bench.exists():
        _ensure_file(bench, (repo_root / "bench/multiply_benchmark.py").read_text(encoding="utf-8"))

    names = [v.get("name") for v in approaches if isinstance(v, dict) and v.get("name")]
    if not names:
        names = ["mul_shift_add", "mul_karatsuba", "mul_chunked"]

    return {
        "baseline": str(baseline),
        "variants": str(variants),
        "bench": str(bench),
        "approach_names": names,
    }


def _post_json(url: str, payload: Dict[str, Any]) -> None:
    try:
        import urllib.request
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _extract_tasks_json(prompt: str) -> List[Dict[str, Any]]:
    """Find a code-fenced block like ```json tasks ... ``` and parse it as a list of tasks.
    Each task: {"type": "run_shell|run_python|create_file", "name": str, "scope": "pre|per_variant|post", ...}
    """
    tasks: List[Dict[str, Any]] = []
    if not prompt:
        return tasks
    fence = "```"
    lines = prompt.splitlines()
    inside = False
    buf: List[str] = []
    for ln in lines:
        if not inside and ln.strip().lower().startswith("```json tasks"):
            inside = True
            buf = []
            continue
        if inside and ln.strip().startswith(fence):
            inside = False
            # parse
            try:
                obj = json.loads("\n".join(buf))
                if isinstance(obj, list):
                    tasks = obj
            except Exception:
                pass
            continue
        if inside:
            buf.append(ln)
    return tasks


def _run_task(task: Dict[str, Any], env: Dict[str, str], api_base: str) -> None:
    tname = str(task.get("name") or task.get("type") or "task")
    scope = str(task.get("scope") or "pre")
    _post_json(api_base.rstrip("/") + "/ingest/log", {
        "ts": time.time(), "run_id": "gamified", "variant": env.get("VARIANT"), "episode_id": None,
        "stream": "app", "source": "gamified_cli", "message": f"task start: {scope}:{tname}", "meta": {}
    })
    try:
        typ = str(task.get("type"))
        cwd = task.get("cwd")
        if typ == "create_file":
            p = Path(task["path"]).expanduser()
            _ensure_file(p, str(task.get("content", "")), overwrite=bool(task.get("overwrite", False)))
        elif typ == "run_shell":
            cmd = str(task["cmd"])
            subprocess.run(cmd, shell=True, cwd=cwd or None, check=False, env=env)
        elif typ == "run_python":
            code = str(task["code"]) if "code" in task else ""
            if not code and task.get("path"):
                code = Path(str(task["path"]))
                if Path(str(code)).exists():
                    code = Path(str(code)).read_text(encoding="utf-8")
            if code:
                # run a short-lived python process; propagate env
                code_patched = "__file__='-';\n" + code
                subprocess.run([sys.executable, "-c", code_patched], cwd=cwd or None, check=False, env=env)
        else:
            pass
    finally:
        _post_json(api_base.rstrip("/") + "/ingest/log", {
            "ts": time.time(), "run_id": "gamified", "variant": env.get("VARIANT"), "episode_id": None,
            "stream": "app", "source": "gamified_cli", "message": f"task end: {scope}:{tname}", "meta": {}
        })


def _scoreboard_from_results(raw: Dict[str, Dict[str, Any]], wmap: Dict[str, float], speed_split: Dict[str, float]) -> Dict[str, Any]:
    """Build Scorecard-like dict with ApproachScore shape expected by tests.

    raw[name] should contain: correctness (dict), timings_ms (dict), robust (bool), loc (int).
    We compute per-scale speed_points relative to the best observed timing.
    """
    board: Dict[str, Any] = {"approaches": {}}
    scales = ("S", "M", "L")
    best_speed: Dict[str, float] = {k: float("inf") for k in scales}
    for r in raw.values():
        sp = r.get("timings_ms", {}) or {}
        for k in scales:
            try:
                best_speed[k] = min(best_speed[k], float(sp.get(k, float("inf"))))
            except Exception:
                pass
    # derive best loc for brevity normalization
    best_loc = None
    for r in raw.values():
        try:
            locv = int(r.get("loc", 0) or 0)
            if locv > 0:
                best_loc = locv if best_loc is None else min(best_loc, locv)
        except Exception:
            pass
    for name, r in raw.items():
        corr_map = r.get("correctness", {}) or {}
        sp = r.get("timings_ms", {}) or {}
        robust = bool(r.get("robust", False))
        loc = int(r.get("loc", 0) or 0)
        # speed points per scale: better timing gets closer to 1.0
        speed_pts: Dict[str, float] = {}
        for k in scales:
            try:
                s = float(sp.get(k, float("inf")))
                b = float(best_speed.get(k, float("inf")))
                pct = 0.0
                if s > 0 and b > 0 and b < float("inf"):
                    pct = max(0.0, min(1.0, b / s))
            except Exception:
                pct = 0.0
            speed_pts[k] = pct
        # normalized subscores for total_points
        correctness_sub = sum(1.0 if bool(corr_map.get(k)) else 0.0 for k in scales) / len(scales)
        speed_sub = sum(speed_pts.values()) / len(scales)
        robustness_sub = 1.0 if robust else 0.0
        if best_loc and loc > 0:
            brevity_sub = max(0.0, min(1.0, float(best_loc) / float(loc)))
        else:
            brevity_sub = 0.5 if loc == 0 else 1.0
        total = (
            correctness_sub * wmap.get("correctness", 0.0)
            + speed_sub * wmap.get("speed", 0.0)
            + robustness_sub * wmap.get("robustness", 0.0)
            + brevity_sub * wmap.get("brevity", 0.0)
        )
        board["approaches"][name] = {
            "correctness": {k: bool(corr_map.get(k, False)) for k in scales},
            "timings_ms": {k: float(sp.get(k, float("inf"))) for k in scales},
            "robust": bool(robust),
            "loc": int(loc),
            "speed_points": speed_pts,
            "brevity_points": float(brevity_sub),
            "total_points": float(total),
        }
    # pick best
    winner = None
    best_total = -1.0
    for nm, data in board["approaches"].items():
        if float(data.get("total_points", -1.0)) > best_total:
            best_total = float(data["total_points"]) 
            winner = nm
    board["winner"] = winner
    return board


def _ideate_approaches(prompt: str) -> List[Dict[str, str]]:
    low = (prompt or "").lower()
    if "multiply" in low or "multiplication" in low:
        return [
            {
                "name": "mul_shift_add",
                "mechanics": "Binary shift‑and‑add: iterate bits of the multiplier; add shifted multiplicand when bit is set. Optimizable with early exits and fixed‑width operations.",
            },
            {
                "name": "mul_karatsuba",
                "mechanics": "Karatsuba divide‑and‑conquer: split integers into halves, compute three products recursively, and combine using Karatsuba identities. Handles small inputs with a base case (e.g., grade‑school multiply).",
            },
            {
                "name": "mul_chunked",
                "mechanics": "Chunked/base‑N multiplication: convert integers to base‑B (e.g., 10^k). Represent operands as arrays of base‑digits, accumulate products with carries, then rebuild the integer. Emphasizes clarity over asymptotic optimality.",
            },
        ]
    # Generic placeholders
    return [
        {"name": "variant_alpha", "mechanics": "Baseline iterative/refinement strategy; emphasizes simplicity and correctness first."},
        {"name": "variant_beta", "mechanics": "Divide‑and‑conquer style strategy; reduces problem size recursively and recombines."},
        {"name": "variant_gamma", "mechanics": "Block/tiling strategy; partitions inputs into chunks and aggregates partial results with normalization."},
    ]


def _backend_up(api_base: str) -> bool:
    import urllib.request, urllib.error
    try:
        with urllib.request.urlopen(api_base.rstrip("/") + "/scoreboard", timeout=2) as r:
            return 200 <= getattr(r, "status", 200) < 500
    except Exception:
        return False


def _start_backend(api_base: str, extra_env: Optional[Dict[str, str]] = None) -> Optional[subprocess.Popen]:
    # Only supports localhost targets today
    if not api_base.startswith("http://localhost:") and not api_base.startswith("http://127.0.0.1:"):
        return None
    port = int(api_base.rsplit(":", 1)[-1])
    env = os.environ.copy()
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items() if v is not None})
    # Try uvicorn via module
    cmd = ["uv", "run", "--script", "scripts/logger_uv.py", "--host", "127.0.0.1", "--port", str(port)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        return proc
    except FileNotFoundError:
        # Fallback: inline python runner
        code = (
            "import uvicorn, extractor.core.scripts.server as s; "
            f"uvicorn.run(s.app, host='127.0.0.1', port={port})"
        )
        try:
            proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            return proc
        except Exception:
            return None



async def _run_codex_exec_fallback(*, codex_bin: str, cwd: str, prompt_text: str, yolo: bool, on_out, on_err) -> type('R', (), {})():
    import asyncio
    args = [codex_bin, 'exec', '-']
    if yolo:
        args.append('--dangerously-bypass-approvals-and-sandbox')
    args.extend(['-C', cwd])
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Feed stdin
    if proc.stdin:
        try:
            proc.stdin.write(prompt_text.encode('utf-8'))
            await proc.stdin.drain()
        except Exception:
            pass
        try:
            proc.stdin.close()
        except Exception:
            pass
    async def pump(reader, cb):
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            try:
                cb(chunk)
            except Exception:
                pass
    await asyncio.gather(pump(proc.stdout, on_out), pump(proc.stderr, on_err))
    rc = await proc.wait()
    R = type('Exec', (), {})
    r = R()
    r.returncode = rc
    r.timed_out = False
    r.idle_timed_out = False
    r.was_killed = False
    return r
def _wait_for_backend(api_base: str, timeout_s: float = 25.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _backend_up(api_base):
            return True
        time.sleep(0.5)
    return False


@app.command()
def run(
    codebase: Optional[Path] = typer.Option(None, file_okay=False, dir_okay=True, help="Directory of the project to gamify (can be provided in --prompt)"),
    rules: Optional[Path] = typer.Option(Path("prototypes/gamified/rules/score_v1.json"), help="Rules JSON file (optional if --prompt provided)"),
    prompt: Optional[str] = typer.Option(None, help="Single prompt containing codebase path, approaches to try, and any hints."),
    prompt_file: Optional[Path] = typer.Option(None, help="Markdown prompt file with sections (Codebase, Approaches, etc.)."),
    instances: Optional[int] = typer.Option(None, help="Number of Codex CLI instances (concurrency). Default adapts to your CPU"),
    run_id: Optional[str] = typer.Option(None, help="Run identifier used to group artifacts (default: YYYYMMDD-HHMMSS)"),
    api_base: str = typer.Option("http://localhost:8000", help="Ingest API base"),
    start_dashboard: bool = typer.Option(True, help="Start the React dashboard (web logs)"),
    dashboard_port: int = typer.Option(5199, help="Dashboard port (vite dev)"),
    autostart_backend: bool = typer.Option(True, help="Start the FastAPI backend if not running"),
    yolo: bool = typer.Option(True, help="Pass --dangerously-bypass-approvals-and-sandbox to codex exec for non-interactive runs"),
    emit_only: bool = typer.Option(False, help="Emit per-instance prompts and exit (do not spawn codex)"),
    aggregate_only: bool = typer.Option(False, help="Aggregate a scorecard for --run-id from existing instance outputs and exit"),
    detach: bool = typer.Option(False, help="Spawn codex instances and return immediately without waiting (write PID files)"),
    sequential: bool = typer.Option(False, help="Force sequential execution (pool size = 1). Workaround for flaky harnesses."),
    instance_timeout_s: int = typer.Option(300, help="Per-instance hard timeout in seconds (default 300s)."),
    idle_timeout_s: int = typer.Option(300, help="Per-instance idle timeout in seconds (default 300s)."),
    max_wall_time_s: Optional[int] = typer.Option(None, help="Maximum wall time for the master wait loop in seconds (optional)."),
    codex_bin_opt: Optional[Path] = typer.Option(None, help="Explicit path to codex CLI (overrides autodetect and env)."),
    optimize_prompt: bool = typer.Option(True, help="Validate/optimize the prompt with prompt_optimization.yaml before running"),
    compile_prompt: bool = typer.Option(False, help="Compile a research file into a structured prompt via LLM before optimizing"),
    prompt_research_file: Optional[Path] = typer.Option(None, help="Research Markdown to compile into a prompt (used when --compile-prompt)"),
    rules_path: Optional[Path] = typer.Option(Path("prototypes/gamified/rules/prompt_optimization.yaml"), help="Path to prompt optimization rules YAML"),
    spec: Optional[Path] = typer.Option(None, help="Run from a spec YAML (Happy Path). Overrides other options except --run-id and --fast."),
    # ArangoDB connection (required for full web logger functionality)
    arango_host: str = typer.Option(os.environ.get("ARANGO_HOST", "127.0.0.1"), help="ArangoDB host"),
    arango_port: int = typer.Option(int(os.environ.get("ARANGO_PORT", 8529)), help="ArangoDB port"),
    arango_username: str = typer.Option(os.environ.get("ARANGO_USERNAME", "root"), help="ArangoDB username"),
    arango_password: str = typer.Option(os.environ.get("ARANGO_PASS", "openSesame"), help="ArangoDB password"),
    arango_db: str = typer.Option(os.environ.get("ARANGO_DB", "marker"), help="ArangoDB database name"),
):
    """Minimal, batteries-included gamified run."""
    # Ensure prototypes/gamified skeleton exists so docs/rules paths resolve
    _ensure_gamified_skeleton()
    # Defaults for plateau and iteration if not provided via prompt/rules
    default_epsilon = 0.15
    default_window = 5
    default_max_iters = 8
    # Ensure src/ is importable for in-repo modules when running under uv
    try:
        import sys as _sys
        from pathlib import Path as _P
        _src = _P('src').resolve()
        if str(_src) not in _sys.path:
            _sys.path.insert(0, str(_src))
        # Try to (re)import run_codex_exec if optional import failed at module import time
        if globals().get('run_codex_exec') is None:
            try:
                from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec as _rc  # type: ignore
                globals()['run_codex_exec'] = _rc
            except Exception:
                pass
    except Exception:
        pass
    # Preflight
    # Happy Path: if --spec provided, load spec and render prompt
    spec_snapshot_text = None
    if spec is not None:
        try:
            from prototypes.gamified.spec.v1 import load_spec, render_prompt  # type: ignore
            spec_obj = load_spec(spec)
            prompt = render_prompt(spec_obj)
            codebase = Path(spec_obj.codebase.repo_root).resolve()
            instances = int(spec_obj.execution.concurrency)
            autostart_backend = bool(spec_obj.execution.autostart_backend)
            start_dashboard = bool(spec_obj.execution.autostart_dashboard)
            optimize_prompt = True
            if rules_path is None:
                rules_path = Path(spec_obj.optimizer.rules)
            spec_snapshot_text = Path(spec).read_text(encoding='utf-8')
        except Exception as e:
            raise typer.BadParameter(f'Failed to load spec: {e}')
    if not _which("node"):
        typer.echo("warning: node is not available; some validators or tools may not run")
    use_codex = True
    codex_bin = codex_bin_opt.as_posix() if codex_bin_opt else _find_codex_bin()
    sandbox = None

    # Enforce codex CLI presence; we do not fall back silently in this mode
    if use_codex and not (_which(codex_bin) or _is_exe(codex_bin)):
        typer.echo("error: codex CLI not found on PATH; please install and retry.")
        raise typer.Exit(code=2)
    # Announce resolved codex path and persist for run introspection
    try:
        resolved = shutil.which(codex_bin) or (codex_bin if _is_exe(codex_bin) else None)
        if resolved:
            typer.echo(f"[codex] using {resolved}")
    except Exception:
        pass

    # Preflight codex: verify we can run a trivial command
    def _codex_preflight() -> bool:
        try:
            p = subprocess.run([codex_bin, "exec", "-C", str(Path.cwd().resolve()), "-"], input="echo codex_ok", capture_output=True, text=True, timeout=10)
            return p.returncode == 0 and ("codex_ok" in (p.stdout or "") or "codex_ok" in (p.stderr or ""))
        except Exception:
            return False

    # Soft preflight note: we intentionally avoid a strict I/O assertion here because
    # different Codex builds may handle trivial prompts differently. We still error if
    # codex is not present (above), per project requirements.

    # If requested, compile a research file into a prompt via LLM
    if compile_prompt and prompt_research_file is not None and prompt is None and prompt_file is None:
        try:
            from prototypes.gamified.tools.prompt_compile import _call_llm_compile  # type: ignore
            research_txt = prompt_research_file.read_text(encoding="utf-8")
            prompt = _call_llm_compile(research_txt)
            typer.echo(f"[prompt] compiled from research -> {prompt_research_file}")
        except Exception as e:
            raise typer.BadParameter(f"Failed to compile research file: {e}")

    # Read prompt file if provided
    if (prompt is None) and prompt_file is not None:
        try:
            prompt = prompt_file.read_text(encoding="utf-8")
            typer.echo(f"[prompt] loaded from {prompt_file}")
        except Exception as e:
            raise typer.BadParameter(f"Failed to read --prompt-file: {e}")

    # Optional: optimize prompt through rules
    if optimize_prompt and prompt:
        try:
            from prototypes.gamified.tools.prompt_opt import PromptOptimizer  # type: ignore
            import yaml  # type: ignore
            rules_obj = None
            if rules_path and rules_path.exists():
                try:
                    rules_obj = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
                except Exception:
                    rules_obj = None
            if rules_obj:
                opt = PromptOptimizer(rules_obj)
                optimized, rep = opt.validate_and_optimize(prompt)
                # If errors, abort with a short summary
                if rep.errors:
                    typer.echo("error: prompt optimization failed; please address the following:")
                    for e in rep.errors:
                        typer.echo(f" - [{e.code}] {e.message}")
                    raise typer.Exit(code=2)
                # Write optimized prompt for traceability and use it downstream
                run_root = Path("workspace/runs").resolve() / (run_id or time.strftime("%Y%m%d-%H%M%S"))
                (run_root / "manifests").mkdir(parents=True, exist_ok=True)
                outp = run_root / "manifests" / "prompt_optimized.md"
                outp.write_text(optimized, encoding="utf-8")
                prompt = optimized
                typer.echo(f"[prompt] optimized -> {outp}")
            else:
                typer.echo("warning: rules not found or unreadable; skipping prompt optimization")
        except Exception as e:
            typer.echo(f"warning: prompt optimizer unavailable or failed ({e}); proceeding with raw prompt")

    # Resolve codebase from CLI or prompt
    if codebase is None and prompt:
        codebase = _parse_codebase_from_prompt(prompt)
    if codebase is None:
        raise typer.BadParameter("Provide --codebase or include a 'codebase:' line in --prompt")

    # Default instances if not provided: small, adaptive value
    if instances is None:
        cpu = os.cpu_count() or 2
        instances = max(1, min(3, cpu))

    # Resolve run id and workspace roots
    if not run_id:
        run_id = time.strftime("%Y%m%d-%H%M%S")
    run_root = Path("workspace/runs").resolve() / run_id
    # Persist spec snapshot if provided
    if 'spec_snapshot_text' in locals() and spec_snapshot_text:
        (run_root / 'manifests').mkdir(parents=True, exist_ok=True)
        (run_root / 'manifests' / 'spec.yaml').write_text(spec_snapshot_text, encoding='utf-8')
    inst_root = run_root / "instances"
    inst_root.mkdir(parents=True, exist_ok=True)
    try:
        (run_root / "codex_bin.txt").write_text((shutil.which(codex_bin) or codex_bin), encoding="utf-8")
    except Exception:
        pass

    # Guard incompatible modes
    if emit_only and aggregate_only:
        raise typer.BadParameter("--emit-only and --aggregate-only cannot be used together")
    if aggregate_only and detach:
        raise typer.BadParameter("--aggregate-only and --detach cannot be used together")

    # 1) Ensure backend is up (optional auto-start)
    backend_proc: Optional[subprocess.Popen] = None
    if not _backend_up(api_base):
        if autostart_backend:
            # Select a free local port if the provided api_base is missing a port or appears busy
            scheme, host, port = _parse_api_base(api_base)
            if host in ("localhost", "127.0.0.1"):
                # If no port or the current port seems occupied, pick a free one
                chosen = port
                if port is None:
                    chosen = _find_free_port(host="127.0.0.1")
                else:
                    try:
                        with socket.socket() as s:
                            s.bind(("127.0.0.1", port))
                            # bind succeeded ⇒ port was free; release and reuse
                            chosen = port
                    except Exception:
                        chosen = _find_free_port(host="127.0.0.1")
                api_base = _compose_api_base(scheme, "127.0.0.1", int(chosen))
            typer.echo(f"[backend] not reachable; starting uvicorn server on {api_base} …")
            backend_env = {
                "ARANGO_HOST": arango_host,
                "ARANGO_PORT": str(arango_port),
                "ARANGO_USERNAME": arango_username,
                "ARANGO_PASS": arango_password,
                "ARANGO_DB": arango_db,
            }
            backend_proc = _start_backend(api_base, extra_env=backend_env)
            if not backend_proc or not _wait_for_backend(api_base):
                _stop_process(backend_proc)
                typer.echo("error: failed to start backend; check your environment")
                raise typer.Exit(code=2)
            typer.echo(f"[backend] up (Arango at {arango_host}:{arango_port}, db={arango_db})")
        else:
            typer.echo("warning: backend not reachable and autostart disabled")

    # Build/infer rules from prompt or file
    rules_obj: Dict[str, Any] = {}
    if prompt:
        try:
            rules_compiled = _compile_prompt_to_rules(prompt, Path("prototypes/gamified/rules/score_v1.json").resolve())
            # If no approaches found, fall back to 3 generic names
            if not rules_compiled.get("variants"):
                ideas = _ideate_approaches(prompt)
                rules_compiled["variants"] = ideas
            else:
                # If variants look instructional/invalid for multiplication, replace with ideated set
                try:
                    names = [str(v.get("name")) for v in (rules_compiled.get("variants") or []) if isinstance(v, dict) and v.get("name")]
                except Exception:
                    names = []
                low = (prompt or "").lower()
                if ("multiply" in low or "multiplication" in low) and (len(names) < 3 or not all(n.startswith("mul_") for n in names)):
                    rules_compiled["variants"] = _ideate_approaches(prompt)
            # Write to temp rules path next to manifest
            tmp_rules = Path("workspace/manifests").resolve() / f"rules_prompt_{int(time.time())}.json"
            _write_json(tmp_rules, rules_compiled)
            rules = tmp_rules
            rules_obj = rules_compiled
            typer.echo(f"[rules] compiled from prompt -> {tmp_rules}")
        except Exception as e:
            typer.echo(f"warning: failed to compile rules from prompt: {e}; using default rules file")
            if rules is None:
                rules = Path("prototypes/gamified/rules/score_v1.json").resolve()
            rules_obj = _read_json(rules.resolve())
    else:
        if rules is None:
            rules = Path("prototypes/gamified/rules/score_v1.json").resolve()
        rules_obj = _read_json(rules.resolve())
    desired_variants: Optional[int] = None
    try:
        if isinstance(rules_obj.get("variants"), list):
            desired_variants = len(rules_obj["variants"])  # explicit variants list
        elif isinstance(rules_obj.get("variants_count"), int):
            desired_variants = int(rules_obj["variants_count"])
        elif isinstance(rules_obj.get("execution", {}).get("instances"), int):
            desired_variants = int(rules_obj["execution"]["instances"])  # fallback
    except Exception:
        desired_variants = None

    # 2) Manifest not required for the POC runner; direct agent orchestration follows

    # Persist the resolved API base for smokes / tooling
    try:
        (run_root / "api_base.txt").write_text(api_base, encoding="utf-8")
    except Exception:
        pass

    # 4) Start dashboard (optional)
    dash_proc: Optional[subprocess.Popen] = None
    if start_dashboard:
        dash_proc = _start_dashboard(api_base=api_base, port=dashboard_port)
    # Proactive guidance: some harnesses kill long-lived parents; direct humans to web logs
    dash_url = f"http://localhost:{dashboard_port}" if start_dashboard else api_base.rstrip("/") + "/proto/dashboard"
    typer.echo(f"[monitor] Web logs available at {dash_url} (scoreboard: {api_base.rstrip('/')}/scoreboard)")

    # Extract optional instructions tasks from prompt and run pre tasks
    tasks_list: List[Dict[str, Any]] = _extract_tasks_json(prompt or "") if prompt else []
    pre_tasks = [t for t in tasks_list if str(t.get("scope") or "pre") == "pre"]
    base_env = os.environ.copy()
    base_env["CODEBASE"] = str(codebase.resolve())
    for t in pre_tasks:
        _run_task(t, base_env, api_base)

    # 5) Generate POC artifacts (baseline/variants/bench) and run N headless benchmark instances
    gen = _generate_multiplication_poc(codebase, rules_obj.get("variants") or [])
    try:
        vnames = gen.get("approach_names") or [f"v{i+1}" for i in range(desired_variants or instances)]
        results_dir = Path("bench/results").resolve()
        results_dir.mkdir(parents=True, exist_ok=True)
        out_paths: Dict[str, Path] = {}
        procs: List[subprocess.Popen] = []
        per_variant_tasks = [t for t in tasks_list if str(t.get("scope") or "pre") == "per_variant"]
        inst_dirs: Dict[str, Path] = {}
        launch_lines: List[str] = []

        def _mk_legacy_symlink(name: str, target: Path) -> None:
            try:
                legacy_parent = Path("workspace/agent").resolve()
                legacy_parent.mkdir(parents=True, exist_ok=True)
                link = legacy_parent / f"gamified_{name}"
                if link.exists() or link.is_symlink():
                    try:
                        link.unlink()
                    except Exception:
                        pass
                # Create symlink pointing to the new instance directory
                link.symlink_to(target)
            except Exception:
                # best-effort: ignore symlink issues on platforms without support
                pass

        def _spawn_one(idx: int, name: str) -> subprocess.Popen:
            # Build per-instance prompt
            inst_dir = (inst_root / f"codex_{idx:02d}_{name}").resolve()
            inst_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = inst_dir / "prompt.md"
            # Back-compat symlink for existing tools that expect workspace/agent/gamified_<name>
            _mk_legacy_symlink(name, inst_dir)
            # Compose a minimal, self-contained instance prompt
            p_lines = []
            p_lines.append(f"# Gamified Instance Prompt — codex_{idx:02d} / {name}")
            p_lines.append("")
            if prompt:
                p_lines.append("## Original Prompt")
                p_lines.append("""
```markdown
""".strip())
                p_lines.append(prompt.strip())
                p_lines.append("```")
                p_lines.append("")
            p_lines.append("## Context")
            p_lines.append(f"- Codebase: {codebase.resolve()}")
            p_lines.append(f"- Variant: {name}")
            p_lines.append(f"- Output Dir: {inst_dir}")
            # Rules summary
            plat = rules_obj.get("plateau", {}) or {}
            exec_cfg = rules_obj.get("execution", {}) or {}
            exec_max_iters = int(exec_cfg.get("max_iters", default_max_iters))
            p_lines.append("## Gamified Rules (Summary)")
            p_lines.append(f"- Plateau: epsilon={plat.get('epsilon', default_epsilon)}, window={plat.get('window', default_window)}")
            p_lines.append(f"- Max iters: {exec_max_iters}")
            p_lines.append("- Scoring (internal per-iteration): correctness/speed/robustness/brevity -> 100 total")
            p_lines.append("")
            p_lines.append("## Stop Condition")
            p_lines.append("- Do not stop until plateau (per epsilon/window) or max iterations reached.")
            p_lines.append("")
            p_lines.append("## Iteration Contract")
            p_lines.append("- If the function for this approach is missing, implement it.")
            p_lines.append("- Run the benchmark; capture stdout/stderr; compute metrics.")
            p_lines.append("- Write a well-formatted JSON summary per iteration in the output dir: iter_XX_summary.json with score, metrics, stderr/stdout digests, and mutation info.")
            p_lines.append("- Propose and apply a code change based on metrics; repeat until stop condition.")
            p_lines.append("")
            p_lines.append("## Research MCPs (When Blocked)")
            p_lines.append("- If blocked or an API/library detail is unknown, use research MCPs:")
            p_lines.append("  - Perplexity Ask: craft a precise query; return concise, citation-backed notes.")
            p_lines.append("  - Context7 Docs: fetch official docs for the relevant library/API and summarize key constraints.")
            p_lines.append("- Keep research minimal and targeted to unblock; cite sources when applicable in logs.")
            p_lines.append("- Do not stall the iteration loop waiting for exhaustive research; prefer incremental, testable changes.")
            p_lines.append("")
            p_lines.append("## Benchmark Parameters")
            p_lines.append("- Scales/trials: S=6x5, M=200x5, L=2000x5; L timeout=2000ms")
            # Include mechanics if provided via rules variants
            mech = None
            try:
                for v in (rules_obj.get("variants") or []):
                    if isinstance(v, dict) and v.get("name") == name and v.get("mechanics"):
                        mech = v.get("mechanics")
                        break
            except Exception:
                mech = None
            if mech:
                p_lines.append("")
                p_lines.append("## Mechanics")
                p_lines.append(mech)

            # Embed Tasks block (if present in the original prompt)
            if tasks_list:
                p_lines.append("")
                p_lines.append("## Tasks (from original prompt)")
                try:
                    import json as _json
                    p_lines.append("```json tasks")
                    p_lines.append(_json.dumps(tasks_list, indent=2))
                    p_lines.append("```")
                except Exception:
                    pass
            # Add explicit, non-interactive execution step for Codex
            exec_cfg = rules_obj.get("execution", {}) or {}
            exec_max_iters = int(exec_cfg.get("max_iters", default_max_iters))
            pe = (rules_obj.get("plateau", {}) or {}).get("epsilon", default_epsilon)
            pw = (rules_obj.get("plateau", {}) or {}).get("window", default_window)
            # Optional fast bench args for Codex path (to keep smokes quick)
            fast_args = ""
            if os.environ.get("GAMIFIED_FAST_BENCH"):
                fast_args = " " + " ".join([
                    "--S_digits", "3", "--S_trials", "1",
                    "--M_digits", "6", "--M_trials", "1",
                    "--L_digits", "8", "--L_trials", "1", "--L_timeout_ms", "250",
                ])
            cmd_line = (
                f"python scripts/variant_agent.py --approach {name} "
                f"--bench bench/multiply_benchmark.py --baseline src/core/multiply.py "
                f"--variants {inst_dir.as_posix()}/variants.py --out-dir {inst_dir.as_posix()} "
                f"--epsilon {pe} --window {pw} --max-iters {exec_max_iters} "
                f"--run-id {run_id} --prompt-file {prompt_path.as_posix()} "
                f"--api-base {api_base}" + fast_args
            )
            p_lines.append("")
            p_lines.append("## Execute Exactly (non-interactive)")
            p_lines.append("Run this command now. When it exits, you are done:")
            p_lines.append("```")
            p_lines.append(cmd_line)
            p_lines.append("```")
            p_lines.append("")
            p_lines.append("## Monitoring")
            p_lines.append(f"- Web logs: {dash_url}")
            p_lines.append(f"- API scoreboard: {api_base.rstrip('/')}/scoreboard?run_id={run_id}")
            p_lines.append(f"- API episodes (latest): {api_base.rstrip('/')}/episodes?run_id={run_id}&variant={name}&limit=1")
            p_lines.append(f"- API logs (tail): {api_base.rstrip('/')}/logs?run_id={run_id}&variant={name}&limit=50")
            p_lines.append("- Note: Codex harness may terminate long-lived parents; rely on web logs for progress.")
            # Write prompt file for reference and launch Codex with stdin-fed prompt
            prompt_text = "\n".join(p_lines)
            prompt_path.write_text(prompt_text, encoding="utf-8")
            inst_dirs[name] = inst_dir

            # Record a launch command line for convenience (outside harness)
            launch_lines.append(
                f"codex exec -C {Path.cwd().resolve().as_posix()} --dangerously-bypass-approvals-and-sandbox - < {prompt_path.as_posix()}"
            )

            cmd = [codex_bin, "exec", "-C", str(Path.cwd().resolve())]
            if yolo:
                cmd.append("--dangerously-bypass-approvals-and-sandbox")
            if sandbox:
                cmd.extend(["--sandbox", sandbox])
            cmd.append("-")

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=bool(detach),
            )
            try:
                assert proc.stdin is not None
                proc.stdin.write(prompt_text)
                proc.stdin.flush()
                proc.stdin.close()
            except Exception:
                pass
            return proc

        # Pre-create instance prompts and metadata for asyncio runner
        prompt_meta: Dict[str, Dict[str, Any]] = {}
        for idx, name in enumerate(vnames, start=1):
            env = base_env.copy()
            env["VARIANT"] = name
            for t in per_variant_tasks:
                _run_task(t, env, api_base)
            inst_dir = (inst_root / f"codex_{idx:02d}_{name}").resolve()
            inst_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = inst_dir / "prompt.md"
            _mk_legacy_symlink(name, inst_dir)
            p_lines: List[str] = []
            p_lines.append(f"# Gamified Instance Prompt — codex_{idx:02d} / {name}")
            p_lines.append("")
            if prompt:
                p_lines.append("## Original Prompt")
                p_lines.append("""
```markdown
""".strip())
                p_lines.append(prompt.strip())
                p_lines.append("```")
                p_lines.append("")
            p_lines.append("## Context")
            p_lines.append(f"- Codebase: {codebase.resolve()}")
            p_lines.append(f"- Variant: {name}")
            p_lines.append(f"- Output Dir: {inst_dir}")
            plat = rules_obj.get("plateau", {}) or {}
            exec_cfg = rules_obj.get("execution", {}) or {}
            exec_max_iters = int(exec_cfg.get("max_iters", default_max_iters))
            p_lines.append("## Gamified Rules (Summary)")
            p_lines.append(f"- Plateau: epsilon={plat.get('epsilon', default_epsilon)}, window={plat.get('window', default_window)}")
            p_lines.append(f"- Max iters: {exec_max_iters}")
            p_lines.append("- Scoring (internal per-iteration): correctness/speed/robustness/brevity -> 100 total")
            p_lines.append("")
            p_lines.append("## Stop Condition")
            p_lines.append("- Do not stop until plateau (per epsilon/window) or max iterations reached.")
            p_lines.append("")
            p_lines.append("## Iteration Contract")
            p_lines.append("- If the function for this approach is missing, implement it.")
            p_lines.append("- Run the benchmark; capture stdout/stderr; compute metrics.")
            p_lines.append("- Write a well-formatted JSON summary per iteration in the output dir: iter_XX_summary.json with score, metrics, stderr/stdout digests, and mutation info.")
            p_lines.append("- Propose and apply a code change based on metrics; repeat until stop condition.")
            p_lines.append("")
            p_lines.append("## Research MCPs (When Blocked)")
            p_lines.append("- If blocked or an API/library detail is unknown, use research MCPs:")
            p_lines.append("  - Perplexity Ask: craft a precise query; return concise, citation-backed notes.")
            p_lines.append("  - Context7 Docs: fetch official docs for the relevant library/API and summarize key constraints.")
            p_lines.append("- Keep research minimal and targeted to unblock; cite sources when applicable in logs.")
            p_lines.append("- Do not stall the iteration loop waiting for exhaustive research; prefer incremental, testable changes.")
            p_lines.append("")
            p_lines.append("## Benchmark Parameters")
            p_lines.append("- Scales/trials: S=6x5, M=200x5, L=2000x5; L timeout=2000ms")
            mech = None
            for v in (rules_obj.get("variants") or []):
                if isinstance(v, dict) and v.get("name") == name and v.get("mechanics"):
                    mech = v.get("mechanics")
                    break
            if mech:
                p_lines.append("## Mechanics")
                p_lines.append(mech)
                p_lines.append("")
            if tasks_list:
                p_lines.append("")
                p_lines.append("## Tasks (from original prompt)")
                try:
                    import json as _json
                    p_lines.append("```json tasks")
                    p_lines.append(_json.dumps(tasks_list, indent=2))
                    p_lines.append("```")
                except Exception:
                    pass
            plat = rules_obj.get("plateau", {}) or {}
            exec_cfg = rules_obj.get("execution", {}) or {}
            exec_max_iters = int(exec_cfg.get("max_iters", default_max_iters))
            pe = plat.get("epsilon", default_epsilon)
            pw = plat.get("window", default_window)
            fast_args = ""
            if os.environ.get("GAMIFIED_FAST_BENCH"):
                fast_args = " " + " ".join([
                    "--S_digits", "3", "--S_trials", "1",
                    "--M_digits", "6", "--M_trials", "1",
                    "--L_digits", "8", "--L_trials", "1", "--L_timeout_ms", "250",
                ])
            cmd_line = (
                f"python scripts/variant_agent.py --approach {name} "
                f"--bench bench/multiply_benchmark.py --baseline src/core/multiply.py "
                f"--variants {inst_dir.as_posix()}/variants.py --out-dir {inst_dir.as_posix()} "
                f"--epsilon {pe} --window {pw} --max-iters {exec_max_iters} "
                f"--run-id {run_id} --prompt-file {prompt_path.as_posix()} "
                f"--api-base {api_base}" + fast_args
            )
            p_lines.append("")
            p_lines.append("## Execute Exactly (non-interactive)")
            p_lines.append("Run this command now. When it exits, you are done:")
            p_lines.append("```")
            p_lines.append(cmd_line)
            p_lines.append("```")
            p_lines.append("")
            p_lines.append("## Monitoring")
            p_lines.append(f"- Web logs: {dash_url}")
            p_lines.append(f"- API scoreboard: {api_base.rstrip('/')}/scoreboard?run_id={run_id}")
            p_lines.append(f"- API episodes (latest): {api_base.rstrip('/')}/episodes?run_id={run_id}&variant={name}&limit=1")
            p_lines.append(f"- API logs (tail): {api_base.rstrip('/')}/logs?run_id={run_id}&variant={name}&limit=50")
            p_lines.append("- Note: Codex harness may terminate long-lived parents; rely on web logs for progress.")
            prompt_text = "\n".join(p_lines)
            prompt_path.write_text(prompt_text, encoding="utf-8")
            inst_dirs[name] = inst_dir
            prompt_meta[name] = {"idx": idx, "inst_dir": inst_dir, "prompt_path": prompt_path, "prompt_text": prompt_text}

        # If emit-only, write a launch script and exit early
        if emit_only:
            try:
                # Build prompts and launch lines without spawning
                launch_lines.clear()
                for idx, name in enumerate(vnames, start=1):
                    inst_dir = (inst_root / f"codex_{idx:02d}_{name}").resolve()
                    inst_dir.mkdir(parents=True, exist_ok=True)
                    prompt_path = inst_dir / "prompt.md"
                    _mk_legacy_symlink(name, inst_dir)
                    p_lines: List[str] = []
                    p_lines.append(f"# Gamified Instance Prompt — codex_{idx:02d} / {name}")
                    p_lines.append("")
                    if prompt:
                        p_lines.append("## Original Prompt")
                        p_lines.append("""
```markdown
""".strip())
                        p_lines.append(prompt.strip())
                        p_lines.append("```")
                        p_lines.append("")
                    p_lines.append("## Context")
                    p_lines.append(f"- Codebase: {codebase.resolve()}")
                    p_lines.append(f"- Variant: {name}")
                    p_lines.append(f"- Output Dir: {inst_dir}")
                    plat = rules_obj.get("plateau", {}) or {}
                    exec_cfg = rules_obj.get("execution", {}) or {}
                    exec_max_iters = int(exec_cfg.get("max_iters", default_max_iters))
                    p_lines.append("## Gamified Rules (Summary)")
                    p_lines.append(f"- Plateau: epsilon={plat.get('epsilon', default_epsilon)}, window={plat.get('window', default_window)}")
                    p_lines.append(f"- Max iters: {exec_max_iters}")
                    p_lines.append("- Scoring (internal per-iteration): correctness/speed/robustness/brevity -> 100 total")
                    p_lines.append("")
                    p_lines.append("## Stop Condition")
                    p_lines.append("- Do not stop until plateau (per epsilon/window) or max iterations reached.")
                    p_lines.append("")
                    p_lines.append("## Iteration Contract")
                    p_lines.append("- If the function for this approach is missing, implement it.")
                    p_lines.append("- Run the benchmark; capture stdout/stderr; compute metrics.")
                    p_lines.append("- Write a well-formatted JSON summary per iteration in the output dir: iter_XX_summary.json with score, metrics, stderr/stdout digests, and mutation info.")
                    p_lines.append("- Propose and apply a code change based on metrics; repeat until stop condition.")
                    p_lines.append("")
                    p_lines.append("## Research MCPs (When Blocked)")
                    p_lines.append("- If blocked or an API/library detail is unknown, use research MCPs:")
                    p_lines.append("  - Perplexity Ask: craft a precise query; return concise, citation-backed notes.")
                    p_lines.append("  - Context7 Docs: fetch official docs for the relevant library/API and summarize key constraints.")
                    p_lines.append("- Keep research minimal and targeted to unblock; cite sources when applicable in logs.")
                    p_lines.append("- Do not stall the iteration loop waiting for exhaustive research; prefer incremental, testable changes.")
                    p_lines.append("")
                    p_lines.append("## Benchmark Parameters")
                    p_lines.append("- Scales/trials: S=6x5, M=200x5, L=2000x5; L timeout=2000ms")
                    p_lines.append("")
                    mech = None
                    for v in (rules_obj.get("variants") or []):
                        if isinstance(v, dict) and v.get("name") == name and v.get("mechanics"):
                            mech = v.get("mechanics")
                            break
                    if mech:
                        p_lines.append("## Mechanics")
                        p_lines.append(mech)
                        p_lines.append("")
                    if tasks_list:
                        p_lines.append("")
                        p_lines.append("## Tasks (from original prompt)")
                        try:
                            import json as _json
                            p_lines.append("```json tasks")
                            p_lines.append(_json.dumps(tasks_list, indent=2))
                            p_lines.append("```")
                        except Exception:
                            pass
                    plat = rules_obj.get("plateau", {}) or {}
                    exec_cfg = rules_obj.get("execution", {}) or {}
                    exec_max_iters = int(exec_cfg.get("max_iters", default_max_iters))
                    pe = plat.get("epsilon", default_epsilon)
                    pw = plat.get("window", default_window)
                    fast_args = ""
                    if os.environ.get("GAMIFIED_FAST_BENCH"):
                        fast_args = " " + " ".join([
                            "--S_digits", "3", "--S_trials", "1",
                            "--M_digits", "6", "--M_trials", "1",
                            "--L_digits", "8", "--L_trials", "1", "--L_timeout_ms", "250",
                        ])
                    cmd_line = (
                        f"python scripts/variant_agent.py --approach {name} "
                        f"--bench bench/multiply_benchmark.py --baseline src/core/multiply.py "
                        f"--variants {inst_dir.as_posix()}/variants.py --out-dir {inst_dir.as_posix()} "
                        f"--epsilon {pe} --window {pw} --max-iters {exec_max_iters} "
                        f"--run-id {run_id} --prompt-file {prompt_path.as_posix()} "
                        f"--api-base {api_base}" + fast_args
                    )
                    p_lines.append("")
                    p_lines.append("## Execute Exactly (non-interactive)")
                    p_lines.append("Run this command now. When it exits, you are done:")
                    p_lines.append("```")
                    p_lines.append(cmd_line)
                    p_lines.append("```")
                    p_lines.append("")
                    p_lines.append("## Monitoring")
                    p_lines.append(f"- Web logs: {dash_url}")
                    p_lines.append(f"- API scoreboard: {api_base.rstrip('/')}/scoreboard?run_id={run_id}")
                    p_lines.append(f"- API episodes (latest): {api_base.rstrip('/')}/episodes?run_id={run_id}&variant={name}&limit=1")
                    p_lines.append(f"- API logs (tail): {api_base.rstrip('/')}/logs?run_id={run_id}&variant={name}&limit=50")
                    p_lines.append("- Note: Codex harness may terminate long-lived parents; rely on web logs for progress.")
                    prompt_text = "\n".join(p_lines)
                    prompt_path.write_text(prompt_text, encoding="utf-8")
                    inst_dirs[name] = inst_dir
                    launch_lines.append(
                        f"codex exec -C {Path.cwd().resolve().as_posix()} --dangerously-bypass-approvals-and-sandbox - < {prompt_path.as_posix()}"
                    )

                sh_path = run_root / "launch_all.sh"
                sh_lines = ["#!/usr/bin/env bash", "set -euo pipefail"] + [ln for ln in launch_lines]
                sh_path.write_text("\n".join(sh_lines) + "\n", encoding="utf-8")
                os.chmod(sh_path, 0o755)
                typer.echo(f"[emit-only] prompts ready in {inst_root}; launch via {sh_path}")
            finally:
                _stop_process(dash_proc)
                _stop_process(backend_proc)
            return

        # If aggregate-only, compute scoreboard from existing outputs and exit
        if aggregate_only:
            # Discover instance variant names from directories
            discovered: List[str] = []
            if inst_root.exists():
                for p in sorted(inst_root.glob("codex_*_*")):
                    try:
                        discovered.append(str(p.name.split("_", 2)[-1]))
                    except Exception:
                        pass
            if not discovered:
                typer.echo("warning: no instance outputs found to aggregate")
            else:
                vnames = discovered
            # Build mapping of latest iter_*.json per variant
            raw: Dict[str, Dict[str, Any]] = {}
            for name in vnames:
                apath = inst_root / f"codex_*_{name}"
                latest = None
                candidates = sorted(inst_root.glob(f"codex_*_{name}/iter_*.json"))
                if candidates:
                    latest = candidates[-1]
                if latest:
                    try:
                        raw[name] = json.loads(latest.read_text())
                    except Exception:
                        raw[name] = {"approach": name, "correctness": {"S": False, "M": False, "L": False}, "timings_ms": {"S": float("inf"), "M": float("inf"), "L": float("inf")}, "robust": False, "loc": 0}
                else:
                    raw[name] = {"approach": name, "correctness": {"S": False, "M": False, "L": False}, "timings_ms": {"S": float("inf"), "M": float("inf"), "L": float("inf")}, "robust": False, "loc": 0}

            speed_split = {"S": 11.0, "M": 12.0, "L": 12.0}
            wmap = {"correctness": 45.0, "speed": 35.0, "robustness": 10.0, "brevity": 10.0}
            board = _scoreboard_from_results(raw, wmap, speed_split)
            scorecard = {"scales": ["S", "M", "L"], "approaches": board["approaches"], "winner": board["winner"]}
            out_json_legacy = Path("bench/results/multiply_scorecard.json").resolve()
            out_json_legacy.parent.mkdir(parents=True, exist_ok=True)
            out_json_legacy.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
            run_scorecard = (run_root / "scorecard.json")
            run_scorecard.parent.mkdir(parents=True, exist_ok=True)
            run_scorecard.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
            typer.echo(f"[aggregate-only] winner={board['winner']} scorecard={run_scorecard}")
            _stop_process(dash_proc)
            _stop_process(backend_proc)
            return

        # Bounded concurrency or detached launch
        pool_size = 1 if sequential else min(len(vnames), instances)
        if detach:
            for name in vnames:
                meta = prompt_meta[name]
                idx = meta["idx"]
                proc = _spawn_one(idx, name)
                try:
                    pid_path = (inst_dirs.get(name) or Path(f"workspace/agent/gamified_{name}")) / "codex_pid.txt"
                    pid_path.write_text(str(proc.pid), encoding="utf-8")
                except Exception:
                    pass
                _post_json(api_base.rstrip("/") + "/ingest/log", {
                    "ts": time.time(), "run_id": "gamified", "variant": name, "episode_id": None,
                    "stream": "app", "source": "gamified_cli", "message": f"spawned(detached) {name} pid={proc.pid}", "meta": {}
                })
            typer.echo(f"[detach] spawned {len(vnames)} instances; monitor {inst_root} and web logs at {dash_url}; then run again with --aggregate-only to collate results")
            return

        async def _run_all_async():
            sem = asyncio.Semaphore(pool_size)
            cwd = str(Path.cwd().resolve())

            async def _one(name: str):
                async with sem:
                    meta = prompt_meta[name]
                    inst_dir: Path = meta["inst_dir"]
                    prompt_text: str = meta["prompt_text"]
                    out_path = inst_dir / "codex_stdout.log"
                    err_path = inst_dir / "codex_stderr.log"
                    out_f = open(out_path, "ab", buffering=0)
                    err_f = open(err_path, "ab", buffering=0)
                    def on_out(b: bytes):
                        try:
                            out_f.write(b)
                        except Exception:
                            pass
                    def on_err(b: bytes):
                        try:
                            err_f.write(b)
                        except Exception:
                            pass
                    _post_json(api_base.rstrip("/") + "/ingest/log", {
                        "ts": time.time(), "run_id": "gamified", "variant": name, "episode_id": None,
                        "stream": "app", "source": "gamified_cli", "message": f"started {name}", "meta": {}
                    })
                    try:
                        if run_codex_exec is None:
                            try:
                                from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec as _rc  # type: ignore
                                globals()['run_codex_exec'] = _rc
                            except Exception:
                                pass
                        res = await (run_codex_exec(
                            script_or_path="-",
                            codex_bin=codex_bin,
                            extra_args=["-C", cwd],
                            cwd=cwd,
                            forward_stdin=True,
                            stdin_bytes=prompt_text.encode("utf-8"),
                            bypass_approvals_and_sandbox=bool(yolo),
                            overall_timeout_s=float(instance_timeout_s) if instance_timeout_s else None,
                            idle_timeout_s=float(idle_timeout_s) if idle_timeout_s else None,
                            stdout_capture_limit=0,
                            stderr_capture_limit=0,
                            on_stdout_chunk=on_out,
                            on_stderr_chunk=on_err,
                        ) if globals().get('run_codex_exec') is not None else _run_codex_exec_fallback(codex_bin=codex_bin, cwd=cwd, prompt_text=prompt_text, yolo=bool(yolo), on_out=on_out, on_err=on_err))
                        if res.timed_out or res.idle_timed_out:
                            (inst_dir / "timed_out.txt").write_text(
                                "overall" if res.timed_out else "idle", encoding="utf-8"
                            )
                    finally:
                        try:
                            out_f.close(); err_f.close()
                        except Exception:
                            pass
                    _post_json(api_base.rstrip("/") + "/ingest/log", {
                        "ts": time.time(), "run_id": "gamified", "variant": name, "episode_id": None,
                        "stream": "app", "source": "gamified_cli", "message": f"finished {name}", "meta": {}
                    })

            await asyncio.gather(*[_one(n) for n in vnames])

        if max_wall_time_s:
            try:
                asyncio.run(asyncio.wait_for(_run_all_async(), timeout=float(max_wall_time_s)))
            except asyncio.TimeoutError:
                _post_json(api_base.rstrip("/") + "/ingest/log", {
                    "ts": time.time(), "run_id": "gamified", "variant": None, "episode_id": None,
                    "stream": "app", "source": "gamified_cli", "message": f"master wall time exceeded {max_wall_time_s}s; stopping waits", "meta": {}
                })
        else:
            asyncio.run(_run_all_async())

        # Collect and compute scoreboard from latest agent outputs
        raw: Dict[str, Dict[str, Any]] = {}
        for name in vnames:
            # Look for the latest iter_*.json under the new instance dir
            apath = inst_dirs.get(name) or Path(f"workspace/agent/gamified_{name}")
            latest = None
            if apath.exists():
                candidates = sorted([p for p in apath.glob("iter_*.json") if not p.name.endswith("_summary.json")])
                if candidates:
                    latest = candidates[-1]
            if latest:
                try:
                    raw[name] = json.loads(latest.read_text())
                except Exception:
                    raw[name] = {"approach": name, "correctness": {"S": False, "M": False, "L": False}, "timings_ms": {"S": float("inf"), "M": float("inf"), "L": float("inf")}, "robust": False, "loc": 0}
            else:
                raw[name] = {"approach": name, "correctness": {"S": False, "M": False, "L": False}, "timings_ms": {"S": float("inf"), "M": float("inf"), "L": float("inf")}, "robust": False, "loc": 0}

        speed_split = {"S": 11.0, "M": 12.0, "L": 12.0}
        wmap = {"correctness": 45.0, "speed": 35.0, "robustness": 10.0, "brevity": 10.0}
        board = _scoreboard_from_results(raw, wmap, speed_split)
        # Write combined scorecard
        scorecard = {
            "scales": ["S", "M", "L"],
            "approaches": board["approaches"],
            "winner": board["winner"],
        }
        # Write scorecard to both legacy path and run-scoped path
        out_json_legacy = Path("bench/results/multiply_scorecard.json").resolve()
        out_json_legacy.parent.mkdir(parents=True, exist_ok=True)
        out_json_legacy.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
        run_scorecard = (run_root / "scorecard.json")
        run_scorecard.parent.mkdir(parents=True, exist_ok=True)
        run_scorecard.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
        typer.echo(f"[scorecard] {out_json_legacy}")
        typer.echo(f"[run scorecard] {run_scorecard}")
        # Emit per-variant episodes (updates status) and winner marker
        now_ts = time.time()
        for vname, vdata in (board.get("approaches") or {}).items():
            try:
                _post_json(api_base.rstrip("/") + "/ingest/episode", {
                    "ts": now_ts, "run_id": "gamified", "episode_id": f"{vname}-{int(now_ts)}", "variant": vname,
                    "pass": True, "score": float(vdata.get("total_points", 0.0)), "metrics": {}, "error_count": 0, "screenshots": []
                })
            except Exception:
                pass
        if board.get("winner"):
            try:
                _post_json(api_base.rstrip("/") + "/ingest/episode", {
                    "ts": now_ts, "run_id": "gamified", "episode_id": f"win-{int(now_ts)}", "variant": board["winner"],
                    "pass": True, "score": board["approaches"][board["winner"]]["total_points"], "metrics": {}, "error_count": 0, "screenshots": []
                })
            except Exception:
                pass
        # Post-run tasks
        post_tasks = [t for t in tasks_list if str(t.get("scope") or "pre") == "post"]
        for t in post_tasks:
            _run_task(t, base_env, api_base)
    finally:
        _stop_process(dash_proc)
        _stop_process(backend_proc)

    typer.echo("Done. Dashboard streaming logs; scorecard ready.")


@app.command()
def status(
    run_id: Optional[str] = typer.Option(None, help="Run identifier (default: latest under workspace/runs)"),
    idle_threshold_s: int = typer.Option(300, help="Age threshold in seconds to consider stalled (default 300s)"),
):
    """Print per-variant status for a run (CLI-only, defaults for easy debugging)."""
    runs_root = Path("workspace/runs").resolve()
    if run_id is None:
        cand = sorted(runs_root.glob("*/instances"))
        if not cand:
            typer.echo("no runs found under workspace/runs")
            raise typer.Exit(code=1)
        inst_root = cand[-1]
        run_id = inst_root.parent.name
    inst_root = (runs_root / run_id / "instances").resolve()
    if not inst_root.exists():
        typer.echo(f"instances not found for run_id={run_id}")
        raise typer.Exit(code=1)

    def _alive(pid_file: Path) -> bool:
        try:
            pid = int(pid_file.read_text().strip())
        except Exception:
            return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    rows = []
    now = time.time()
    for d in sorted(inst_root.glob("codex_*_*")):
        name = d.name.split("_", 2)[-1]
        pidf = d / "codex_pid.txt"
        donef = d / "done.json"
        iters = sorted([p for p in d.glob("iter_*.json") if not p.name.endswith("_summary.json")])
        last_iter = iters[-1].name if iters else "-"
        last_age = (now - iters[-1].stat().st_mtime) if iters else None
        if donef.exists():
            status = "completed"
        elif pidf.exists() and _alive(pidf):
            status = "running"
        elif last_age is not None and last_age > idle_threshold_s:
            status = "stalled"
        else:
            status = "pending"
        age_str = f"{int(last_age)}s" if last_age is not None else "-"
        rows.append((name, status, last_iter, age_str))

    typer.echo(f"Run {run_id} — instance status (variant | status | last_iter | age)")
    for name, status, last_iter, age in rows:
        typer.echo(f"- {name:16} | {status:9} | {last_iter:12} | {age}")


@app.command()
def init(out: Path = typer.Option(Path("gamified.yaml"), help="Path to write the run spec")):
    """Interactive wizard to create a minimal spec (Happy Path)."""
    try:
        repo_root = typer.prompt("Codebase repo_root", default=".")
        a_csv = typer.prompt("Approach names (comma-separated, 3+)", default="fueling_density_mpc, edge_stability_mhd, heat_extraction_adaptive")
        approaches = [x.strip() for x in a_csv.split(',') if x.strip()]
        if len(approaches) < 3:
            typer.secho("Need at least 3 approaches", fg=typer.colors.RED)
            raise typer.Exit(code=2)
        typer.echo("Constraints (press Enter for defaults)")
        def _ask(prompt_text, default):
            try:
                return float(typer.prompt(prompt_text, default=str(default)))
            except Exception:
                return default
        edt = _ask("edge_density_threshold [m^-3]", 1.0e19)
        qmin = _ask("q_min", 2.0)
        beta = _ask("beta_max", 0.04)
        hfp = _ask("heat_flux_peak_max [MW/m^2]", 10.0)
        spec = {
            'version': 1,
            'codebase': {'repo_root': repo_root},
            'approaches': [{'name': n} for n in approaches],
            'runner': {'type': 'analysis_sim'},
            'scoring': {'weights': {'correctness': 35, 'robustness': 25, 'speed': 25, 'brevity': 15}},
            'constraints': {
                'edge_density_threshold': edt,
                'q_min': qmin,
                'beta_max': beta,
                'heat_flux_peak_max': hfp,
            },
            'optimizer': {'rules': 'prototypes/gamified/rules/prompt_optimization.yaml'},
            'execution': {'concurrency': 3, 'codex_exec': True, 'autostart_backend': True, 'autostart_dashboard': True},
            'observability': {'backend': 'arango', 'dashboard': True},
        }
        import yaml  # type: ignore
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml.safe_dump(spec, sort_keys=False), encoding='utf-8')
        typer.secho(f"Wrote spec → {out}", fg=typer.colors.GREEN)
    except KeyboardInterrupt:
        raise typer.Exit(code=130)

@app.command()
def open(run_id: str = typer.Option(None, help="Run ID to open (default: latest)", rich_help_panel="Happy Path")):
    """Prints dashboard URLs for a run (and attempts to open in browser)."""
    runs_dir = Path('workspace/runs')
    if not run_id:
        # pick the most recent run directory
        try:
            run_id = sorted([p.name for p in runs_dir.iterdir() if p.is_dir()])[-1]
        except Exception:
            typer.secho('No runs found', fg=typer.colors.RED)
            raise typer.Exit(code=2)
    run_root = runs_dir / run_id
    api_txt = run_root / 'api_base.txt'
    if not api_txt.exists():
        typer.secho('api_base.txt not found for this run', fg=typer.colors.RED)
        raise typer.Exit(code=2)
    api_base = api_txt.read_text().strip()
    proto = f"{api_base.rstrip('/')}/proto/dashboard"
    score = f"{api_base.rstrip('/')}/scoreboard?run_id={run_id}"
    vite = 'http://localhost:5199'
    typer.echo(f"Run: {run_id}\n- API scoreboard: {score}\n- Backend proto: {proto}\n- Dashboard (Vite): {vite}")
    try:
        typer.launch(proto)
    except Exception:
        pass

@app.command()
def replay(run_id: str = typer.Argument(..., help='Run ID to replay')):
    """Re-run using the stored spec snapshot if available; otherwise abort."""
    run_root = Path('workspace/runs') / run_id
    spec_path = run_root / 'manifests' / 'spec.yaml'
    if not spec_path.exists():
        typer.secho('No spec.yaml snapshot found for this run', fg=typer.colors.RED)
        raise typer.Exit(code=2)
    # Delegate to this module's run command with --spec
    import subprocess, sys
    cmd = [sys.executable, '-m', 'prototypes.gamified.cli', 'run', '--spec', str(spec_path)]
    typer.secho(f"[replay] running: {' '.join(cmd)}", fg=typer.colors.BLUE)
    raise typer.Exit(code=subprocess.run(cmd).returncode)

if __name__ == '__main__':
    app()
