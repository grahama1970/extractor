# codex_exec.py
"""
Async wrapper for running `codex exec ...` with robust timeout, streaming, and termination.

Key features:
- Overall and idle timeouts (wall and silence).
- Graceful shutdown (SIGTERM) → hard kill (SIGKILL) with process-group awareness.
- Stream readers that cannot deadlock; cancellation-safe finalization.
- Rolling capture limits to avoid unbounded memory growth.
- Optional binary or decoded text outputs.
- Pluggable stdout/stderr chunk callbacks for live streaming.
- Safe logging (optional redaction) and controlled environment inheritance.

Requires: Python 3.10+, loguru
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import signal
from dataclasses import dataclass
import json
from enum import Enum, auto
from typing import Callable, Iterable, Mapping, Optional, Sequence, List, Any, Dict

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback if loguru missing
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    logger = _logging.getLogger("codex_call")
try:
    from tqdm.asyncio import tqdm as _tqdm_async  # type: ignore
except Exception:  # pragma: no cover - fallback if tqdm not installed
    import asyncio as _asyncio
    class _tqdm_async:  # type: ignore
        @staticmethod
        def as_completed(tasks, total=None, desc=None):  # minimal shim
            return _asyncio.as_completed(tasks)
try:
    import typer
    _HAS_TYPER = True
except Exception:
    _HAS_TYPER = False
    # Minimal shim so function signatures and decorators do not fail
    class _TyperShim:
        def __init__(self,*a,**k):
            pass
        def command(self,*a,**k):
            return lambda f: f
        def echo(self,msg,**kw):
            print(msg)
    def _arg_default(default=None,*a,**k):
        return default
    typer = _TyperShim()  # type: ignore
    typer.Typer = _TyperShim  # type: ignore
    typer.Argument = _arg_default  # type: ignore
    typer.Option = _arg_default  # type: ignore


# --------------------------
# Data structures
# --------------------------

@dataclass(frozen=True)
class ExecResult:
    args: list[str]
    returncode: Optional[int]
    duration_s: float
    timed_out: bool
    idle_timed_out: bool
    was_killed: bool

    # Raw bytes (authoritative)
    stdout_bytes: bytes
    stderr_bytes: bytes

    # Decoded (convenience; may be empty if encoding=None)
    stdout: str
    stderr: str


# --------------------------
# Helpers
# --------------------------

def _chunked(seq: List[Any], n: int) -> List[List[Any]]:
    """Return a list of slices of size n (last may be smaller)."""
    if n <= 0:
        return [list(seq)]
    return [seq[i : i + n] for i in range(0, len(seq), n)]


class _DeadlineResult(Enum):
    OK = auto()
    OVERALL_TIMEOUT = auto()
    IDLE_TIMEOUT = auto()


# --------------------------
# Utilities
# --------------------------

def _redact(seq: Sequence[str], redaction_markers: Sequence[str] | None) -> list[str]:
    """
    Redact sensitive flags in logs. Any arg containing a marker substring
    is replaced with '<redacted>' after '=' or entirely if no '='.
    Example markers: ["--token", "API_KEY", "Authorization"]
    """
    if not redaction_markers:
        return list(seq)
    redacted: list[str] = []
    for s in seq:
        lowered = s.lower()
        if any(m.lower() in lowered for m in redaction_markers):
            if "=" in s:
                k, _ = s.split("=", 1)
                redacted.append(f"{k}=<redacted>")
            else:
                redacted.append("<redacted>")
        else:
            redacted.append(s)
    return redacted


def _build_env(
    inherit_env: bool,
    base_env: Mapping[str, str] | None,
    allowlist: Iterable[str] | None,
    denylist: Iterable[str] | None,
) -> dict[str, str]:
    env = os.environ.copy() if inherit_env else {}
    if base_env:
        env.update(base_env)
    if allowlist:
        env = {k: v for k, v in env.items() if k in set(allowlist)}
        if base_env:
            for k, v in base_env.items():
                if k in allowlist:
                    env[k] = v
    if denylist:
        for k in denylist:
            env.pop(k, None)
    return env


def _check_deadlines(
    now: float,
    t0: float,
    last_activity: float,
    overall_timeout_s: Optional[float],
    idle_timeout_s: Optional[float],
) -> _DeadlineResult:
    if overall_timeout_s is not None and (now - t0) > overall_timeout_s:
        return _DeadlineResult.OVERALL_TIMEOUT
    if idle_timeout_s is not None and (now - last_activity) > idle_timeout_s:
        return _DeadlineResult.IDLE_TIMEOUT
    return _DeadlineResult.OK


async def _read_stream(
    stream: asyncio.StreamReader,
    sink: bytearray | None,
    on_chunk: Optional[Callable[[bytes], None]],
    last_activity_ref: list[float],
) -> None:
    """
    Read from `stream` until EOF. Extends `sink` if provided (bytearray).
    Calls on_chunk(bytes) for live streaming.
    Updates last_activity_ref[0] on every read.
    """
    try:
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                break
            last_activity_ref[0] = time.monotonic()

            if on_chunk:
                try:
                    on_chunk(chunk)
                except Exception:
                    logger.exception("on_chunk callback raised")

            if sink is not None:
                sink.extend(chunk)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Error while reading process stream")


async def _write_stdin_bytes(proc: asyncio.subprocess.Process, data: bytes) -> None:
    """
    Write stdin in safe chunks respecting backpressure; close when done.
    """
    try:
        if not proc.stdin:
            return
        view = memoryview(data)
        CHUNK = 65536
        offset = 0
        while offset < len(view):
            end = min(offset + CHUNK, len(view))
            proc.stdin.write(view[offset:end])
            await proc.stdin.drain()
            offset = end
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Failed writing to stdin")
    finally:
        try:
            if proc.stdin and not proc.stdin.is_closing():
                proc.stdin.close()
        except Exception:
            pass


def _apply_capture_limit(buf: bytearray, limit: Optional[int]) -> None:
    """
    Enforce rolling capture limit (tail). If limit is 0 -> no capture.
    If None -> unlimited. If >0, keep only last `limit` bytes.
    """
    if limit is None:
        return
    if limit <= 0:
        buf.clear()
        return
    if len(buf) > limit:
        del buf[0 : len(buf) - limit]


# --------------------------
# Main runner
# --------------------------

async def run_codex_exec(
    script_or_path: str,
    codex_bin: str = "codex",
    extra_args: Optional[Sequence[str]] = None,
    *,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    inherit_env: bool = True,
    env_allowlist: Iterable[str] | None = None,
    env_denylist: Iterable[str] | None = None,
    overall_timeout_s: Optional[float] = 600.0,
    idle_timeout_s: Optional[float] = None,
    kill_grace_s: float = 10.0,
    forward_stdin: bool = False,
    stdin_bytes: Optional[bytes] = None,
    on_stdout_chunk: Optional[Callable[[bytes], None]] = None,
    on_stderr_chunk: Optional[Callable[[bytes], None]] = None,
    stdout_capture_limit: Optional[int] = None,
    stderr_capture_limit: Optional[int] = None,
    # Decoding
    encoding: Optional[str] = "utf-8",
    errors: str = "replace",
    # Logging
    redact_in_logs: Sequence[str] | None = ("--token", "authorization", "api_key"),
    # Codex CLI execution policy
    bypass_approvals_and_sandbox: bool = False,
    yolo: bool | None = None,
    ask_for_approval: Optional[str] = None,
    sandbox_mode: Optional[str] = None,
) -> ExecResult:
    """
    Run `codex exec <script_or_path> [extra_args...]` with robust supervision.
    """
    args = [codex_bin, "exec", script_or_path]

    # Approvals / sandbox policy
    if yolo is None:
        yolo = bypass_approvals_and_sandbox
    if yolo:
        args.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        if ask_for_approval:
            args.extend(["--ask-for-approval", ask_for_approval])
        if sandbox_mode:
            args.extend(["--sandbox", sandbox_mode])

    if extra_args:
        args.extend(extra_args)

    merged_env = _build_env(inherit_env, env, env_allowlist, env_denylist)

    redacted_args = _redact(args, redact_in_logs)
    logger.info(f"Starting: {' '.join(redacted_args)} (cwd={cwd or os.getcwd()})")

    t0 = time.monotonic()
    start_new_session = not sys.platform.startswith("win")

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=merged_env,
        stdin=asyncio.subprocess.PIPE if forward_stdin else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=start_new_session,
    )

    stdout_buf = bytearray()
    stderr_buf = bytearray()

    last_activity_ref = [time.monotonic()]

    reader_stdout = asyncio.create_task(
        _read_stream(proc.stdout, stdout_buf if stdout_capture_limit != 0 else None, on_stdout_chunk, last_activity_ref)
    )
    reader_stderr = asyncio.create_task(
        _read_stream(proc.stderr, stderr_buf if stderr_capture_limit != 0 else None, on_stderr_chunk, last_activity_ref)
    )

    stdin_task = None
    if forward_stdin and stdin_bytes is not None:
        stdin_task = asyncio.create_task(_write_stdin_bytes(proc, stdin_bytes))

    timed_out = False
    idle_timed_out = False
    was_killed = False

    async def _poll_wait(interval: float) -> bool:
        try:
            await asyncio.wait_for(proc.wait(), timeout=interval)
            return True
        except asyncio.TimeoutError:
            return False

    try:
        while True:
            if proc.returncode is not None:
                break

            now = time.monotonic()
            outcome = _check_deadlines(now, t0, last_activity_ref[0], overall_timeout_s, idle_timeout_s)
            if outcome is _DeadlineResult.OVERALL_TIMEOUT:
                timed_out = True
                logger.warning(f"Overall timeout ({overall_timeout_s}s) hit; terminating...")
                break
            if outcome is _DeadlineResult.IDLE_TIMEOUT:
                idle_timed_out = True
                logger.warning(f"Idle timeout ({idle_timeout_s}s) hit; terminating...")
                break

            finished = await _poll_wait(0.25)
            if finished:
                break
    except asyncio.CancelledError:
        logger.warning("run_codex_exec cancelled; terminating child process")
        timed_out = True
    except Exception:
        logger.exception("Supervisor loop error; terminating child process")
        timed_out = True
    finally:
        _apply_capture_limit(stdout_buf, stdout_capture_limit)
        _apply_capture_limit(stderr_buf, stderr_capture_limit)

        if timed_out or idle_timed_out:
            try:
                if sys.platform.startswith("win"):
                    proc.terminate()
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)  # type: ignore[arg-type]
                    except PermissionError:
                        proc.send_signal(signal.SIGTERM)
                logger.info("Sent graceful termination signal")
            except ProcessLookupError:
                pass
            except Exception:
                logger.exception("Error sending graceful termination")

            try:
                await asyncio.wait_for(proc.wait(), timeout=kill_grace_s)
            except asyncio.TimeoutError:
                logger.error("Grace period elapsed; sending hard kill")
                was_killed = True
                try:
                    if sys.platform.startswith("win"):
                        proc.kill()
                    else:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)  # type: ignore[arg-type]
                        except PermissionError:
                            proc.send_signal(signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except Exception:
                    logger.exception("Error during hard kill")
                finally:
                    try:
                        await proc.wait()
                    except Exception:
                        pass

        if proc.stdin and not proc.stdin.is_closing():
            try:
                proc.stdin.close()
            except Exception:
                pass

        tasks = [reader_stdout, reader_stderr]
        if stdin_task:
            tasks.append(stdin_task)
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            logger.exception("Error awaiting stream tasks")

    duration = time.monotonic() - t0

    _apply_capture_limit(stdout_buf, stdout_capture_limit)
    _apply_capture_limit(stderr_buf, stderr_capture_limit)

    stdout_bytes = bytes(stdout_buf)
    stderr_bytes = bytes(stderr_buf)

    if encoding is None:
        stdout_text = ""
        stderr_text = ""
    else:
        stdout_text = stdout_bytes.decode(encoding, errors=errors)
        stderr_text = stderr_bytes.decode(encoding, errors=errors)

    logger.info(
        "Finished codex exec: rc={} in {:.2f}s | timed_out={} idle_timed_out={} killed={}",
        proc.returncode,
        duration,
        timed_out,
        idle_timed_out,
        was_killed,
    )

    return ExecResult(
        args=list(args),
        returncode=proc.returncode,
        duration_s=duration,
        timed_out=timed_out,
        idle_timed_out=idle_timed_out,
        was_killed=was_killed,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        stdout=stdout_text,
        stderr=stderr_text,
    )


# --------------------------
# Example (manual test)
# --------------------------
app = typer.Typer(name="codex_call", help="Run batch prompts through Codex exec (mirrors litellm_call UX).") if _HAS_TYPER else None



def _demo_payloads(model: Optional[str]) -> List[Dict[str, Any]]:
    """Load demo payloads from a static JSONL file for clarity.
    Reads from CODEX_DEMO_JSONL or defaults to data/demos/codex_call_demo_simple.jsonl.
    """
    path = os.environ.get("CODEX_DEMO_JSONL", "data/demos/codex_call_demo_simple.jsonl")
    payloads: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, str):
                obj = {"text": obj}
            if model and isinstance(obj, dict) and "model" not in obj:
                obj["model"] = model
            payloads.append(obj)
    if not payloads:
        raise ValueError(f"Demo JSONL at {path} contains no items")
    return payloads



@app.command() if _HAS_TYPER else (lambda f: f)
def run(
    prompts: List[str] = typer.Argument(None, help="Prompts to run (like litellm_call)."),
    demo: bool = typer.Option(False, "--demo", help="Run a built-in 5-item batch."),
    model: Optional[str] = typer.Option(None, "--model", help="Model name to include in JSONL dicts (e.g., 'ollama/gemma3:12b')."),
    reasoning_effort: Optional[str] = typer.Option(
        None,
        "--reasoning-effort",
        "--reasoning",
        help="Reasoning effort hint (e.g., low/minimal, medium, high). Alias: --reasoning",
    ),
    # Codex exec configuration
    codex_bin: str = typer.Option("codex", "--codex-bin", help="Path to Codex CLI."),
    script: str = typer.Option("python", "--script", help="Command run under Codex (default: python)."),
    target: str = typer.Option("", "--target", help="Optional worker script that accepts JSONL (e.g., litellm_call.py). If empty, use direct Codex mode."),
    concurrency: int = typer.Option(3, "--concurrency", min=1, help="Max parallel calls (like litellm_call)."),
    # Approvals / sandbox
    yolo: bool = typer.Option(False, "--yolo", help="--dangerously-bypass-approvals-and-sandbox"),
    ask_for_approval: Optional[str] = typer.Option(None, "--ask-for-approval", help="Approval mode (e.g., on-request)"),
    sandbox: Optional[str] = typer.Option(None, "--sandbox", help="Sandbox mode (e.g., workspace-write)"),
    # Input sources
    stdin: bool = typer.Option(False, "--stdin", help="Read prompts from stdin"),
    jsonl: bool = typer.Option(False, "--jsonl", help="When reading stdin, parse JSON Lines"),
    # Timeouts
    overall_timeout_sec: int = typer.Option(900, "--overall-timeout-sec", min=0, help="Overall wall timeout per exec (seconds). 0 disables."),
    idle_timeout_sec: Optional[int] = typer.Option(None, "--idle-timeout-sec", help="Idle timeout per exec (seconds). Unset disables; triggers if no output for N seconds."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print JSONL payload and exit (no Codex exec)"),
    emit_json: bool = typer.Option(False, "--emit-json", help="Emit a JSON array of {index,request,answer,rc,duration_s}"),
):
    """
    Runs a batch of prompts via Codex by invoking the LiteLLM helper as the child process.

    Examples:
    - python codex_call.py --demo
    - python codex_call.py "What is 2+2?" "Describe this image: data/images/table.png"
    - echo '"What is 2+2?"' | python codex_call.py --stdin --jsonl
    """
    # Resolve payloads as list of dicts (to match litellm_call JSONL usage)
    payloads: List[Dict[str, Any]] = []
    if demo:
        payloads = _demo_payloads(model)
    elif stdin:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            if jsonl:
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        if model and "model" not in obj:
                            obj = {**obj, "model": model}
                        payloads.append(obj)
                    elif isinstance(obj, str):
                        d: Dict[str, Any] = {"text": obj}
                        if model:
                            d["model"] = model
                        payloads.append(d)
                    else:
                        d = {"text": str(obj)}
                        if model:
                            d["model"] = model
                        payloads.append(d)
                except Exception:
                    # Fallback to raw line -> wrap as {text, model?}
                    d = {"text": line}
                    if model:
                        d["model"] = model
                    payloads.append(d)
            else:
                d = {"text": line}
                if model:
                    d["model"] = model
                payloads.append(d)
    else:
        # Positional prompts -> wrap as dicts
        for p in prompts:
            d = {"text": p}
            if model:
                d["model"] = model
            payloads.append(d)

    if not payloads:
        typer.echo("No prompts provided. Use --demo, pass prompts, or --stdin.", err=True)
        raise typer.Exit(1)
    # Inject flat model_reasoning_effort only (no nested keys) if requested
    if reasoning_effort:
        for i, obj in enumerate(payloads):
            if not isinstance(obj, dict):
                continue
            if "model_reasoning_effort" in obj:
                continue
            updated = dict(obj)
            updated["model_reasoning_effort"] = reasoning_effort
            payloads[i] = updated

    if dry_run:
        for obj in payloads:
            print(__import__("json").dumps(obj))
        return
    # Decide mode: direct Codex vs worker script
    if not target:
        # Direct Codex mode: build prompt strings and call `codex exec` directly
        async def _run_direct():
            # Process in small sequential groups to avoid whole-batch timeouts.
            # Each group still obeys the same concurrency limit.
            meta_all: List[Dict[str, Any]] = []
            outs_all: List[str] = []
            # Heuristic: 2x concurrency per group, minimum 2, maximum 6
            group_size = max(2, min(6, concurrency * 2))
            for group in _chunked(payloads, group_size):
                sem = asyncio.Semaphore(concurrency)
                results = [None] * len(group)
                meta = [None] * len(group)
                async def _one(i, item):
                    async with sem:
                        # Build prompt text from item
                        if isinstance(item, dict):
                            text = str(item.get("text", ""))
                            img = item.get("image")
                            if img and img not in text:
                                # Embed image path/URL explicitly for Codex
                                text = (text + " " + str(img)).strip()
                            model_eff = item.get("model", model)
                        else:
                            text = str(item)
                            model_eff = model

                        if not text:
                            results[i] = "[rc=?] Empty prompt"
                            meta[i] = {"index": i + 1, "request": item if isinstance(item, dict) else {"text": str(item)}, "answer": "", "rc": None, "duration_s": 0.0}
                            return

                        flags = []
                        if model_eff:
                            flags += ["--model", str(model_eff)]
                        if reasoning_effort:
                            flags += ["-c", f"model_reasoning_effort={reasoning_effort}"]

                        res = await run_codex_exec(
                            script_or_path=text,
                            codex_bin=codex_bin,
                            extra_args=flags,
                            overall_timeout_s=(overall_timeout_sec or None),
                            idle_timeout_s=idle_timeout_sec,
                            bypass_approvals_and_sandbox=yolo,
                            ask_for_approval=ask_for_approval,
                            sandbox_mode=sandbox,
                            stdout_capture_limit=256 * 1024,
                            stderr_capture_limit=256 * 1024,
                        )
                        # Heuristic parse: last non-empty line not starting with '[' or 'tokens used:'
                        lines = [ln for ln in (res.stdout or "").splitlines() if ln.strip()]
                        answer = ""
                        for ln in reversed(lines):
                            low = ln.lower().strip()
                            if low.startswith("tokens used:") or low.startswith("["):
                                continue
                            answer = ln.strip()
                            break
                        if res.returncode not in (0, None):
                            err_tail = (res.stderr or "").strip().splitlines()[-1:]  # last stderr line
                            tag = f"[rc={res.returncode}]"
                            if answer:
                                answer = f"{tag} {answer}"
                            else:
                                answer = tag
                            if err_tail:
                                answer = f"{answer} | {err_tail[0]}"
                        results[i] = answer
                        meta[i] = {
                            "index": i + 1,
                            "request": item if isinstance(item, dict) else {"text": str(item), **({"model": model} if model else {})},
                            "answer": answer,
                            "rc": res.returncode,
                            "duration_s": res.duration_s,
                        }

                tasks = [asyncio.create_task(_one(i, it)) for i, it in enumerate(group)]
                for t in _tqdm_async.as_completed(tasks, total=len(tasks), desc="Codex Direct Batch"):
                    await t
                # extend preserving order
                outs_all.extend([r or "" for r in results])
                meta_all.extend([m for m in meta])
            return outs_all, meta_all
        outs, meta = asyncio.run(_run_direct())
    else:
        # Worker script mode (e.g., litellm_call.py) via JSONL over stdin
        async def _run_worker():
            sem = asyncio.Semaphore(concurrency)
            results = [None] * len(payloads)
            meta = [None] * len(payloads)
            async def _one(i, item):
                async with sem:
                    res = await run_codex_exec_jsonl(
                        script_or_path=script,
                        payload=item,
                        codex_bin=codex_bin,
                        extra_args=[target, "--stdin", "--jsonl"],
                        bypass_approvals_and_sandbox=yolo,
                        ask_for_approval=ask_for_approval,
                        sandbox_mode=sandbox,
                        overall_timeout_s=(overall_timeout_sec or None),
                        idle_timeout_s=idle_timeout_sec,
                        stdout_capture_limit=256 * 1024,
                        stderr_capture_limit=256 * 1024,
                    )
                    out_lines = (res.stdout or "").strip().splitlines()
                    last = out_lines[-1] if out_lines else ""
                    if res.returncode not in (0, None):
                        err_tail = (res.stderr or "").strip().splitlines()[-1:]
                        tag = f"[rc={res.returncode}]"
                        last = f"{tag} {last}" if last else tag
                        if err_tail:
                            last = f"{last} | {err_tail[0]}"
                    results[i] = last
                    meta[i] = {
                        "index": i + 1,
                        "request": item,
                        "answer": last,
                        "rc": res.returncode,
                        "duration_s": res.duration_s,
                    }
            tasks = [asyncio.create_task(_one(i, it)) for i, it in enumerate(payloads)]
            for t in _tqdm_async.as_completed(tasks, total=len(tasks), desc="Codex JSONL Batch"):
                await t
            return [r or "" for r in results], [m for m in meta]
        outs, meta = asyncio.run(_run_worker())

    if emit_json:
        import json as _json
        # Emit compact JSON array mapping input to answer
        output = _json.dumps(meta, ensure_ascii=False)
        if _HAS_TYPER:
            typer.echo(output)
        else:
            print(output)
    else:
        for i, (p, o) in enumerate(zip(payloads, outs), start=1):
            preview = p.get("text") if isinstance(p, dict) else str(p)
            print(f"[{i}] {preview} -> {o}") if not _HAS_TYPER else typer.echo(f"[{i}] {preview} -> {o}")



# --------------------------
# JSONL helpers (fixed)
# --------------------------

async def run_codex_exec_jsonl(script_or_path: str, payload, **kwargs) -> ExecResult:
    """
    One-shot JSONL round-trip: serializes payload (dict or list of dicts) to JSON Lines,
    sends via stdin, closes it, and returns ExecResult.
    """
    lines: list[str] = []
    if isinstance(payload, dict):
        lines.append(json.dumps(payload))
    else:
        for obj in payload:
            lines.append(json.dumps(obj))
    stdin_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    return await run_codex_exec(
        script_or_path,
        forward_stdin=True,
        stdin_bytes=stdin_bytes,
        **kwargs,
    )


async def run_codex_batch_jsonl(
    script_or_path: str,
    payloads,
    *,
    concurrency: int = 4,
    desc: str = "Codex Batch",
    **kwargs
) -> list[str]:
    """
    Run a batch of JSONL payloads with limited concurrency and progress display.
    Returns a list of strings (last stdout line per task).
    """
    sem = asyncio.Semaphore(concurrency)
    results: list[Optional[str]] = [None] * len(payloads)

    async def _one(i, p):
        async with sem:
            res = await run_codex_exec_jsonl(script_or_path, p, **kwargs)
            out_lines = (res.stdout or "").strip().splitlines()
            results[i] = out_lines[-1] if out_lines else ""
            return results[i]

    tasks = [asyncio.create_task(_one(i, p)) for i, p in enumerate(payloads)]
    for t in _tqdm_async.as_completed(tasks, total=len(tasks), desc=desc):
        await t
    return [r or "" for r in results]
if __name__ == "__main__":
    # Typer-only entrypoint for consistency across the pipeline
    if app is not None:
        app()
    else:
        print("Typer is required to run codex_call CLI.", file=sys.stderr)
        sys.exit(2)
