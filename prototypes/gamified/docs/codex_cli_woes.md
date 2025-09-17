## ## From Github Copilot web

Below is a structured answer to every question you asked, plus concrete remediation steps, diagnostics to run, and a robust asyncio subprocess pattern (with strict + idle timeouts, signal handling, absolute binary resolution, and optional PTY fallback). Since I cannot see your live environment, I’ll show exactly how to discover each answer and adapt your launcher.

---

## 1. Codex Binary and PATH

### What you need to know
You must not rely on an interactive (login) shell to populate PATH. Non‑login shells (which most process supervisors and API servers use) skip `~/.zshrc`, `~/.bash_profile`, etc., so `codex` won’t resolve even if you can run it interactively.

### How to discover the absolute path
Run these in the SAME environment the agent uses (not your personal terminal if they differ):

```bash
command -v codex || which codex
echo "CODEX_HOME=$CODEX_HOME"
ls -l "$CODEX_HOME/bin/codex" 2>/dev/null || echo "No codex under CODEX_HOME/bin"
```

If `command -v` fails:
1. Check common global install locations:
   - `/usr/local/bin/codex`
   - `$HOME/.local/bin/codex`
   - `$HOME/.codex/bin/codex`
   - Node global: `npm root -g` then look at sibling `../bin/codex`
2. If installed via `npm i -g @openai/codex`, run:
   ```bash
   npm bin -g
   ls -l "$(npm bin -g)/codex"
   ```

### Recommend hardcoding once found
Store the absolute path (e.g. `/usr/local/bin/codex`) in your LiteLLM provider config (or a new env var `CODEX_BINARY_PATH`). Do not rely on PATH inside the spawned process—pass the full path in `create_subprocess_exec`.

### Fallback search function (Python)
```python
import os, shutil, pathlib

def resolve_codex_binary():
    # 1. Explicit env override
    for candidate in [
        os.getenv("CODEX_BINARY_PATH"),
        os.path.join(os.getenv("CODEX_HOME", ""), "bin", "codex") if os.getenv("CODEX_HOME") else None
    ]:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # 2. PATH search
    found = shutil.which("codex")
    if found:
        return found

    # 3. Common fallbacks
    guesses = [
        "/usr/local/bin/codex",
        str(pathlib.Path.home() / ".local/bin/codex"),
        str(pathlib.Path.home() / ".codex/bin/codex"),
    ]
    for g in guesses:
        if os.path.isfile(g) and os.access(g, os.X_OK):
            return g

    raise FileNotFoundError("Codex CLI binary not found. Set CODEX_BINARY_PATH or install @openai/codex globally.")
```

---

## 2. Environment Inheritance & PYTHONPATH

### Problem you saw
`RuntimeError: codex_call.run_codex_exec unavailable; set PYTHONPATH=./src` indicates the module import path (e.g. `extractor.pipeline.utils.codex_call`) wasn’t on `sys.path`.

### How to determine required PYTHONPATH
From repo root (where `src/` exists):
```bash
python - <<'EOF'
import sys, os
print("CWD:", os.getcwd())
print("sys.path:", sys.path)
try:
    import extractor.pipeline.utils.codex_call
    print("IMPORT_OK")
except Exception as e:
    print("IMPORT_FAIL:", e)
EOF
```

If it fails, you likely need to prepend the repo `src` directory:
```bash
export PYTHONPATH="$(pwd)/src"
```
If your agent shell cannot rely on exports, inject this into `env` when spawning subprocess (Codex usually doesn’t need it, but YOUR wrapper Python code might before spawning Codex).

### Capturing interactive env to replicate
If your interactive shell sets PATH/PYTHONPATH:
```bash
bash -l -c 'env -0' > /tmp/interactive-env.txt
```
Then parse the lines you actually need (PATH, PYTHONPATH, CODEX_HOME) and set them explicitly in the agent runtime.

---

## 3. Process / Sandbox Restrictions

Questions to confirm (you may have to run / ask ops):
- Are arbitrary binaries allowed outside repo tree? (e.g. security policies restricting `/usr/local/bin`)
- Is there a supervisor (Heroku dyno, container runtime) terminating processes after inactivity or a fixed wall-clock?
- Are you allowed to spawn process groups (`start_new_session=True`)? Some jailed environments disallow delivery of signals across groups.

### How to test quickly
```bash
python - <<'EOF'
import subprocess, time, os
p = subprocess.Popen(["sleep","5"])
print("PID", p.pid)
time.sleep(1)
p.terminate()
p.wait()
print("RC after terminate:", p.returncode)
EOF
```
If this hangs or returns permission errors, adjust strategy (no process group; use direct PID kill).

---

## 4. PTY vs Pipes

Some CLIs behave differently without a TTY. Start with pipes (simpler). If Codex appears to buffer until exit, try a PTY:

```python
import asyncio, pty, os

async def run_with_pty(cmd):
    master_fd, slave_fd = pty.openpty()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True
    )
    os.close(slave_fd)
    async def reader():
        loop = asyncio.get_event_loop()
        while True:
            try:
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                if not data:
                    break
                print("PTY:", data.decode(errors="replace"), end="")
            except OSError:
                break
    await asyncio.gather(reader(), proc.wait())
```
Only use PTY if you confirm buffering issues—PTY adds complexity (no clean separation of stdout/stderr).

---

## 5. Networking / Bind Constraints

If your earlier “backend autostart” (uvicorn) failed, possibilities:
- Port already bound / disallowed.
- Outbound network restricted (Codex may need remote model access unless pointed only at your internal LiteLLM proxy).
- Your image lacked build deps for optional packages (fastapi/uvicorn not essential if you only spawn Codex).

### Validate port & outbound
```bash
python - <<'EOF'
import socket
s=socket.socket()
try:
    s.bind(("127.0.0.1", 8000))
    print("Bind OK 8000")
except Exception as e:
    print("Bind FAIL 8000:", e)
EOF
```
If port busy, pick ephemeral or environment-provided (`$PORT`). For Codex runs that only invoke underlying HTTP model APIs, ensure outbound to those base URLs is permitted (no corporate firewall block).

---

## 6. Signals & Groups

Recommended pattern (if allowed):
- Spawn with `start_new_session=True` so you can kill an entire group (if Codex spawns children).
- On cancel: `os.killpg(proc.pid, signal.SIGTERM)` then escalate to SIGKILL after grace.

If `PermissionError` on group kill:
- Fall back to `proc.terminate()` and loop over `psutil.Process(proc.pid).children()` to kill individually.

Test group kill:
```bash
python - <<'EOF'
import subprocess, os, signal, time
p = subprocess.Popen(["sleep","30"], start_new_session=True)
time.sleep(1)
os.killpg(p.pid, signal.SIGTERM)
rc = p.wait(timeout=5)
print("Exit code:", rc)
EOF
```

---

## 7. Resource Limits (ulimits)

Run:
```bash
ulimit -a
```
Look for:
- `open files` (ulimit -n) — if very low (e.g. 256), multiple concurrent Codex runs could exhaust descriptors.
- `max user processes` (ulimit -u) — small numbers can block creating further subprocesses.

If limited, serialize runs or reduce internal concurrency (semaphore).

---

## 8. Approval / Sandbox Flags

You mentioned `--dangerously-bypass-approvals-and-sandbox` (or similar). For a server environment:
- Only use the bypass flag if you have strong external isolation (container, read-only FS where needed).
- If there is a safer read-only / restricted sandbox flag, prefer that for initial MVP and permit override in config.
- Document in logs if a run uses full-access so auditing is possible.

---

## 9. Practical Diagnostics Script (Run & Paste Back)

Run from repo root in the target environment:

```bash
echo "=== CODex Binary Resolution ==="
command -v codex || which codex || echo "codex not on PATH"
echo "CODEX_HOME=$CODEX_HOME"
[ -n "$CODEX_HOME" ] && ls -l "$CODEX_HOME/bin/codex"

echo "=== Codex Version ==="
codex --version || echo "codex version failed"

echo "=== Env Vars (PATH/PYTHONPATH/CODEX_HOME) ==="
env | egrep '^(PATH|PYTHONPATH|CODEX_HOME)='

echo "=== Python Import Test ==="
python - <<'EOF'
import sys, os
print("sys.path=", sys.path)
try:
    import extractor.pipeline.utils.codex_call as m
    print("IMPORT extractor.pipeline.utils.codex_call OK:", getattr(m, "__file__", None))
except Exception as e:
    print("IMPORT FAILED:", e)
EOF

echo "=== Simple Codex Exec Smoke ==="
codex exec -C "$(pwd)" - <<'EOF'
echo codex_ok
EOF
echo "Codex exec exit code: $?"

echo "=== Ulimits ==="
ulimit -a

echo "=== Group Kill Test ==="
python - <<'EOF'
import subprocess, os, signal, time
p = subprocess.Popen(["sleep","2"], start_new_session=True)
os.killpg(p.pid, signal.SIGTERM)
print("killed group; rc", p.wait())
EOF
```

Paste the full output (redact secrets) and we can tailor further.

---

## 10. Robust Asyncio Subprocess Pattern (with Strict + Idle Timeout)

```python
import asyncio, os, signal, time
from typing import AsyncGenerator, Optional

class CodexRunError(Exception): ...
class CodexTimeout(CodexRunError): ...
class CodexBinaryMissing(CodexRunError): ...

async def run_codex(
    prompt: str,
    codex_path: str,
    repo_root: str,
    extra_args: list[str] | None = None,
    wall_timeout: int = 600,          # hard wall-clock seconds
    idle_timeout: Optional[int] = 60, # cancel if no output for N seconds
    start_new_session: bool = True,
    env_overrides: dict | None = None,
    stream_callback=None,             # async or sync function(line:str, source:str)
) -> dict:
    """
    Returns:
        {
          "exit_code": int,
          "stdout_lines": [...],
          "stderr_lines": [...],
          "duration_s": float,
          "timed_out": bool,
          "idle_timed_out": bool
        }
    """
    if not (os.path.isfile(codex_path) and os.access(codex_path, os.X_OK)):
        raise CodexBinaryMissing(f"Codex binary not executable at {codex_path}")

    args = [codex_path, "exec", "-C", repo_root]
    if extra_args:
        args.extend(extra_args)
    # Final argument: feed prompt via stdin (dash means read from stdin)
    args.append("-")

    # Minimal deterministic env
    env = {k: v for k, v in os.environ.items() if k in ("PATH","HOME","LANG")}
    if env_overrides:
        env.update(env_overrides)

    creation_flags = {}
    if start_new_session:
        creation_flags["start_new_session"] = True

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        **creation_flags
    )

    stdout_lines, stderr_lines = [], []
    start_time = time.time()
    last_output_time = start_time
    timed_out = False
    idle_timed_out = False

    # Send prompt (ensure trailing newline)
    prompt_bytes = (prompt.rstrip("\n") + "\n").encode("utf-8")
    proc.stdin.write(prompt_bytes)
    await proc.stdin.drain()
    proc.stdin.close()

    async def read_stream(stream, dest_list, source):
        nonlocal last_output_time
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8","replace").rstrip("\n")
            dest_list.append(text)
            last_output_time = time.time()
            if stream_callback:
                maybe = stream_callback(text, source)
                if asyncio.iscoroutine(maybe):
                    await maybe

    stdout_task = asyncio.create_task(read_stream(proc.stdout, stdout_lines, "stdout"))
    stderr_task = asyncio.create_task(read_stream(proc.stderr, stderr_lines, "stderr"))

    try:
        while True:
            if proc.returncode is not None:
                break
            now = time.time()

            # Hard wall timeout
            if now - start_time > wall_timeout:
                timed_out = True
                break

            # Idle timeout
            if idle_timeout and (now - last_output_time > idle_timeout):
                idle_timed_out = True
                break

            await asyncio.sleep(0.2)
    finally:
        if timed_out or idle_timed_out:
            # Terminate process/group
            try:
                if start_new_session:
                    os.killpg(proc.pid, signal.SIGTERM)
                else:
                    proc.terminate()
            except ProcessLookupError:
                pass
            # Grace period
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                try:
                    if start_new_session:
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                except ProcessLookupError:
                    pass

    # Ensure readers finish
    await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
    rc = await proc.wait()

    duration = time.time() - start_time

    if timed_out:
        raise CodexTimeout(f"Codex run exceeded wall timeout {wall_timeout}s "
                           f"(pid={proc.pid}, partial stdout lines={len(stdout_lines)})")
    if idle_timed_out:
        raise CodexTimeout(f"Codex run idle for {idle_timeout}s (no output)")

    return {
        "exit_code": rc,
        "stdout_lines": stdout_lines,
        "stderr_lines": stderr_lines,
        "duration_s": duration,
        "timed_out": timed_out,
        "idle_timed_out": idle_timed_out
    }

# Example usage:
# result = await run_codex("echo codex_ok", "/usr/local/bin/codex", repo_root="/path/to/repo",
#                          extra_args=["--dangerously-bypass-approvals-and-sandbox"])
```

Key features:
- Absolute binary path (no PATH reliance).
- Minimal sanitized env plus overrides.
- Hard wall timeout & optional idle timeout.
- Graceful `SIGTERM` then `SIGKILL`.
- Optional streaming callback.
- Works in async context; safe line-by-line buffering.

---

## 11. Handling Your Observed Failures

| Failure | Likely Root Cause | Fix |
|---------|------------------|-----|
| `codex_call.run_codex_exec unavailable` | Missing PYTHONPATH/src not added | Export `PYTHONPATH=<repo_root>/src` before import or set in env for the agent |
| `codex CLI not found on PATH` | Non-login shell lacks PATH additions | Resolve absolute binary once; configure `CODEX_BINARY_PATH` |
| Child blocked / killed | Missing stdout consumption OR idle limit / supervisor kill | Ensure continuous read; implement idle + wall timeout; confirm no external watchdog |
| Backend autostart fails | Not needed; missing heavy deps or blocked port | Skip uvicorn for smoke tests; run Codex directly |
| Long-lived process killed | External platform timeout (PaaS) | Shorten run; run incremental tasks; or move to environment with longer allowance |

---

## 12. Approvals & Sandbox Flags

Only use the full bypass flag in a hardened container:
- Consider running with a safer flag first to validate streaming path.
- Provide config knob (e.g. `codex_default_args`) so production can force restricted mode.

---

## 13. Concurrency & Semaphore (If Integrating into LiteLLM)

Wrap `run_codex` calls with a global semaphore:

```python
CONCURRENCY = int(os.getenv("CODEX_MAX_CONCURRENCY", "3"))
codex_semaphore = asyncio.Semaphore(CONCURRENCY)

async def guarded_run(*a, **kw):
    async with codex_semaphore:
        return await run_codex(*a, **kw)
```

Return 429 / structured error if you prefer queue rejection.

---

## 14. Next Steps For You

1. Run the diagnostics block and capture output.
2. Locate & set `CODEX_BINARY_PATH`.
3. Decide on idle timeout (e.g. 60s?) vs no idle timeout (if agent may do long silent reasoning—rare).
4. Confirm whether process groups are allowed (run group kill test).
5. Apply the robust async runner; test a simple prompt “echo codex_ok”.
6. Gradually introduce real Codex tasks (refactor / generate code).
7. Only after stable: integrate into a LiteLLM provider abstraction.

---

## 15. What to Paste Back (so I can refine)

Please paste (sanitizing secrets):
- Output of diagnostics script.
- Absolute path chosen for Codex.
- Whether group termination succeeded.
- Any timeout or hang you observe with the async runner.
- If idle timeout fired prematurely.

---

## 16. Quick Checklist

| Item | Status (You fill) |
|------|-------------------|
| Absolute codex path resolved |  |
| PYTHONPATH set or not required |  |
| Group kill works |  |
| Wall timeout chosen |  |
| Idle timeout chosen / disabled |  |
| Concurrency limit decided |  |
| Sandbox flags approved by security |  |
| Underlying outbound network allowed |  |

---

If you provide the diagnostic outputs, I can tailor further (e.g., switching to PTY, altering env handling, or adding exponential backoff on startup). Let me know when you have that, or ask for a trimmed “Phase 1” subset if you want to move faster.

Want a condensed version for a future GitHub issue? Just ask and I’ll refactor this into an issue-ready draft.


## From Chatgpt 5 Web
Here’s a **practical unblocker**: direct answers (what to assume/do), a **copy-paste diagnostic script** to get the exact values on your box, and a **robust asyncio spawn template** that survives PATH/PYTHONPATH quirks, timeouts, signals, and optional PTY. Use this as your ground truth to finalize the provider + smokes.

---

# 1) What to do right now (answers & defaults you can ship)

## Codex binary & path

* **Do not rely on PATH**. Resolve an **absolute path** once and hardcode it in `litellm_config.yaml: codex_binary_path`.
* Accept these sources in order:

  1. `EXTRA_BODY.codex_binary_path` (smoke mode only)
  2. `CODEX_HOME/bin/codex` if `$CODEX_HOME` is set and executable
  3. `which codex` result captured **from the agent’s own env**, not interactive shell
* If none exist → fail fast with a clear error: “codex binary not found; set `codex_binary_path` or `CODEX_HOME`”.

## Environment inheritance

* **Do not assume** `PYTHONPATH=./src`. Set it explicitly for the subprocess:

  * `PYTHONPATH="<repo_root>/src:${PYTHONPATH:-}"`.
* If you need to import `extractor.pipeline.utils.codex_call`, require:

  * `PYTHONPATH` includes repo `src`
  * Minimal runtime deps installed (not the full dev stack)
* Ignore user dotfiles (`~/.zshrc`, asdf/direnv) entirely; replicate needed exports in the agent env:

  * `PATH="$CODEX_HOME/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"`
  * `PYTHONPATH` as above.

## Process / sandbox restrictions

* Treat the environment as **no long-lived servers** unless proven otherwise. For smokes, **avoid backend autostart**; drive CLI-only workflows and assert filesystem artifacts.
* Launch children without a TTY first (pipes). If the CLI misbehaves without a TTY, enable PTY mode (see code below).
* Use `start_new_session=True` (or `preexec_fn=os.setsid`) by default for group signals; add a config knob to disable if a supervisor forbids it.

## Networking/bind constraints

* Don’t bind UVicorn in smokes. If you must, prefer `127.0.0.1:8001`. Make host/port configurable via env; detect conflicts with `ss -ltn`.
* Assume **outbound** may be restricted; pass LiteLLM keys via allowlist env and let Codex fail clearly if egress is blocked.

## Signals & groups

* Default: send `SIGTERM` to the **process group**, wait `grace_seconds`, then `SIGKILL`.
* Add `use_process_group: true|false` to your runner config; set false if you observe “operation not permitted”.

## Resource limits

* Expect modest `ulimit -n` and `-u` in CI shells. Keep concurrency small in smokes (≤2). If you hit resource errors, document raising `nofile` to at least 1024 for local runs.

## Approval / sandbox flags

* Default to **read-only** sandbox. Only allow `--dangerously-bypass-approvals-and-sandbox` when an explicit `codex_allow_full_access: true` is set in config **and** the run is tagged as test/dev.

---

# 2) One-shot diagnostics (copy/paste)

Save as `scripts/smoke/codex_env_probe.sh` and run:

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "=== codex probe ==="
echo "[which codex]"; which codex || echo "which: not found"
echo
echo "[env vars of interest]"
env | egrep '(^PATH=|^PYTHONPATH=|^CODEX_HOME=|^OPENAI_API_KEY=|^LITELLM_)' || true
echo
if [ -n "${CODEX_HOME:-}" ]; then
  echo "[CODEX_HOME listing] $CODEX_HOME/bin"
  ls -l "$CODEX_HOME/bin" || true
fi
echo
echo "[codex --version]"
(set -x; ${CODEX_HOME:+$CODEX_HOME/bin/}codex --version) || echo "codex --version failed"
echo
echo "[python import check]"
python - <<'PY'
import sys, os
print("sys.executable:", sys.executable)
print("sys.version:", sys.version.split()[0])
sys.path.insert(0, os.path.abspath("src"))
try:
  import extractor.pipeline.utils.codex_call as m
  print("codex_call import: OK; module:", m.__name__)
except Exception as e:
  print("codex_call import: FAIL:", repr(e))
PY
echo
echo "[repo-root codex exec sanity]"
set -o pipefail
( set -x; ${CODEX_HOME:+$CODEX_HOME/bin/}codex exec -C "$(pwd)" - <<'EOF'
echo codex_ok
EOF
) && echo "exit=$?" || echo "exit=$?"
echo
echo "[ports]"
ss -ltn || true
echo "[ulimits]"
ulimit -a
echo "=== end ==="
```

If `which codex` and `$CODEX_HOME/bin/codex` both fail, the fix is: **set `litellm_params.codex_binary_path` to an absolute path** (e.g., `/usr/local/bin/codex`) or set `CODEX_HOME`.

---

# 3) Robust asyncio subprocess wrapper (drop-in template)

Use this for your provider runner (CLI-only smokes). It handles PATH/PYTHONPATH, PTY optional, timeouts, and group signals.

```python
# scripts/smoke/spawn_codex.py (or providers/codex_runner.py in your tree)
import asyncio, os, signal, sys, time, shlex
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional, Tuple

@dataclass
class RunCfg:
    cmd: list[str]                  # full argv, absolute binary preferred
    cwd: Path
    env: dict
    first_byte_s: int = 10
    idle_s: Optional[int] = 60
    hard_s: int = 600
    grace_s: int = 3
    use_process_group: bool = True
    use_pty: bool = False           # set True only if needed

async def _read_lines(stream: asyncio.StreamReader, q: asyncio.Queue, kind: str, cap: int = 8192):
    while True:
        line = await stream.readline()
        if not line:
            break
        s = line.decode("utf-8", "replace").rstrip("\n")
        if len(s) > cap:
            s = s[:cap] + " …[truncated]"
        await q.put((kind, s))

async def run_codex(cfg: RunCfg) -> AsyncIterator[Tuple[str, str]]:
    """
    Yields tuples: ("stdout"|"stderr", line)
    """
    preexec = os.setsid if (cfg.use_process_group and hasattr(os, "setsid")) else None

    # Build env defensively (no host leak)
    env = dict(os.environ)  # optionally start empty and merge allowlist
    env.update(cfg.env or {})
    # Guarantee minimal PATH & PYTHONPATH
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    repo_src = str(cfg.cwd / "src")
    env["PYTHONPATH"] = f"{repo_src}:{env.get('PYTHONPATH','')}"

    # Launch
    proc = await asyncio.create_subprocess_exec(
        *cfg.cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cfg.cwd),
        env=env,
        preexec_fn=preexec,
    )

    q: asyncio.Queue[Tuple[str, str]] = asyncio.Queue()
    t_out = asyncio.create_task(_read_lines(proc.stdout, q, "stdout"))
    t_err = asyncio.create_task(_read_lines(proc.stderr, q, "stderr"))

    first_byte_deadline = time.time() + cfg.first_byte_s
    last_activity = None

    async def killer(reason: str):
        pgid = None
        try:
            if cfg.use_process_group and proc.pid:
                pgid = os.getpgid(proc.pid)
        except Exception:
            pgid = None
        try:
            if pgid:
                os.killpg(pgid, signal.SIGTERM)
            elif proc.returncode is None:
                proc.terminate()
        except ProcessLookupError:
            pass
        await asyncio.sleep(cfg.grace_s)
        try:
            if pgid and proc.returncode is None:
                os.killpg(pgid, signal.SIGKILL)
            elif proc.returncode is None:
                proc.kill()
        except ProcessLookupError:
            pass
        raise TimeoutError(reason)

    try:
        while True:
            try:
                kind, line = await asyncio.wait_for(q.get(), timeout=0.2)
                last_activity = time.time()
                yield (kind, line)
            except asyncio.TimeoutError:
                # First byte grace
                if last_activity is None and time.time() > first_byte_deadline and cfg.idle_s:
                    # switch to idle timer
                    last_activity = 0.0  # mark that we've warned; fall through
                # Idle timeout
                if cfg.idle_s and last_activity is not None and last_activity != 0.0:
                    if time.time() - last_activity > cfg.idle_s:
                        await killer("idle timeout")
                # Hard timeout
                if time.time() - (proc._start_time if hasattr(proc, "_start_time") else 0) > cfg.hard_s:
                    await killer("hard timeout")
            if proc.returncode is not None and q.empty():
                break
        await asyncio.gather(t_out, t_err)
    finally:
        # Ensure process is gone
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        for t in (t_out, t_err):
            if not t.done():
                t.cancel()
```

**Usage example** (absolute path + prompt on argv; avoid stdin unless needed):

```python
async def demo():
    codex_bin = "/usr/local/bin/codex"  # or resolved earlier
    cfg = RunCfg(
        cmd=[codex_bin, "exec", "-C", str(Path.cwd()), "-e", "echo codex_ok"],
        cwd=Path.cwd(),
        env={
            "LITELLM_CODEX_RUN_ID": "demo_run",
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY",""),
        },
        first_byte_s=10, idle_s=30, hard_s=120, grace_s=2,
        use_process_group=True, use_pty=False,
    )
    async for kind, line in run_codex(cfg):
        print(kind, ":", line)

# asyncio.run(demo())
```

> If Codex **requires** a TTY for some flows, set `use_pty=True` and adapt to merge streams, or prefer the plain pipe path for structured stdout/stderr.

---

# 4) Exact litellm config to neutralize your failures

```yaml
# litellm_config.yaml (smoke profile)
model_list:
  - model_name: codex-agent
    litellm_params:
      model: codex/agent
      codex_binary_path: /abs/path/to/codex      # <- fill this with the probe result
      codex_default_args: ["--sandbox","read-only","--ask-for-approval","never"]
      codex_max_run_seconds: 120
      codex_idle_timeout_seconds: 30
      codex_first_byte_seconds: 10
      codex_graceful_shutdown_seconds: 2
      codex_max_concurrency: 2
      codex_allow_full_access: false
      codex_env:
        LITELLM_HTTPX: "1"
      artifacts_root: scripts/artifacts
      smoke_mode_allow_binary_override: true
      sanitize_data_urls: true
```

---

# 5) Map your failures → fixes

* **“run\_codex\_exec unavailable; set PYTHONPATH=./src”**
  Fix: set `PYTHONPATH="<repo_root>/src:${PYTHONPATH:-}"` in the agent env before spawn (see wrapper). Do **not** rely on shell RC files.

* **“codex CLI not found on PATH”**
  Fix: set `codex_binary_path` to an **absolute path**. Optionally set `CODEX_HOME` and prepend to `PATH` inside the agent env.

* **Child blocked/killed** (long-running)
  Fix: smokes use short, atomic runs; avoid autostarting uvicorn. Use smaller timeouts and prove signal handling with the wrapper.

* **Backend autostart failed (heavy deps/ports)**
  Fix: remove backend from smokes. If you must, bind to `127.0.0.1:8001` and make it optional behind an env toggle.

---

# 6) Answer sheet (how I’d respond to each of your bullets)

**Codex binary and path**

* Absolute path: **determine via probe**, then set `litellm_params.codex_binary_path`. Yes, hardcoding is recommended for the agent.
* `$CODEX_HOME`: usable if set; we’ll resolve `$CODEX_HOME/bin/codex` first.
* If neither works, the provider will refuse to start with a clear message.

**Environment inheritance**

* We will **not** assume `PYTHONPATH=./src`; we set it explicitly per run.
* We ignore user profile scripts; instead we add these exports inside the agent:

  * `PATH="$CODEX_HOME/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"`
  * `PYTHONPATH="<repo_root>/src:${PYTHONPATH:-}"`

**Process/sandbox restrictions**

* We’ll treat the environment as **no long servers**; smokes are CLI-only.
* We default to pipes; if Codex needs a TTY, we toggle PTY mode.
* We use `start_new_session=True` and group signals, with a config to disable.

**Networking/bind constraints**

* For smokes, **no server bind**. If needed, use `127.0.0.1:8001` and make it configurable.
* Outbound may be blocked; Codex failures will be surfaced cleanly.

**Signals and groups**

* Yes, we send SIGTERM then SIGKILL to the **group**; configurable fallback to process-only.

**Resource limits**

* We assume conservative `ulimit`; smokes run with concurrency 1–2. If limits are low, we’ll document increasing them.

**Approval/sandbox flags**

* Default **read-only**. Full-access only with `codex_allow_full_access=true` for dev/test.

**Diagnostics to run**
Everything you listed is already in `codex_env_probe.sh`. Run it and paste the output if anything’s still unclear.

---

# 7) Optional Make targets (just to lock this down)

```makefile
.PHONY: codex-probe codex-smoke-one

codex-probe:
	chmod +x scripts/smoke/codex_env_probe.sh
	./scripts/smoke/codex_env_probe.sh

# Minimal one-off CLI run proving spawn/stream
codex-smoke-one:
	python - <<'PY'
import os, asyncio, json
from pathlib import Path
from scripts.smoke.spawn_codex import RunCfg, run_codex  # adjust import path
codex = os.environ.get("CODEX_BIN","/abs/path/to/codex")  # set me
cfg = RunCfg(
    cmd=[codex, "exec", "-C", str(Path.cwd()), "-e", "echo codex_ok"],
    cwd=Path.cwd(),
    env={"LITELLM_CODEX_RUN_ID":"smoke_one","LITELLM_HTTPX":"1"},
    first_byte_s=5, idle_s=10, hard_s=30, grace_s=2, use_process_group=True)
async def main():
    async for kind, line in run_codex(cfg):
        print(kind, ":", line)
asyncio.run(main())
PY
```

---

If you drop in the probe + wrapper + config above, you’ll have **deterministic** subprocess behavior (no hidden PATH/PYTHONPATH surprises), and your smokes will pass even in constrained shells.


## From Perplexity
Here is a complete explanation of the LiteLLM Router hang issue caused by thread management, composed from analysis of the problem, diagnostics, and related known bugs:

***

## Complete Explanation of LiteLLM Router Hang Problem

### Context
LiteLLM is a Python SDK and proxy for routing requests to large language models (LLMs), managing load balancing, retries, and concurrency. Its core `Router` object handles requests asynchronously and spawns **background worker threads** for auxiliary functions like service logging, scheduling, telemetry, and health checks.

***

### The Problem
When using the `Router` in a short-lived Python script (e.g., a one-shot CLI program that calls `await router.acompletion(...)`), the script **never fully exits** after producing the expected response. This happens because:

- The `Router` creates **background threads** (e.g., in `service_logger_obj` or `scheduler`).
- These threads are started as **non-daemon threads**, meaning they block the Python interpreter from shutting down until they terminate.
- The `Router` class does **not** expose a `close()` or `aclose()` method to reliably shut down and join these threads.
- Background threads either do not honor shutdown signals promptly or are not stopped at all.
- Consequently, even when the main async call completes, the Python process remains alive, hanging indefinitely.

***

### Why Non-Daemon Threads Matter
In Python, threads can be daemon or non-daemon:

- **Non-daemon threads** keep the process alive until they complete or are explicitly joined.
- **Daemon threads** run in the background and do not prevent the interpreter from exiting.

LiteLLM’s internal threads being non-daemon means they implicitly **prevent the process exit** until these threads cease. Without explicit shutdown handling, this causes hangs.

***

### Diagnosis Summary
Testing and diagnostic scripts that:

- List active threads before and after calling `router.acompletion()`
- Monkey-patch `threading.Thread.__init__` to set `daemon=True` for all future threads before importing LiteLLM
- Attempt shutdown via internal attributes `service_logger_obj.shutdown()` or `scheduler.shutdown()` and thread `join()`

All confirm the root cause: background threads linger and block process exit unless daemonized or explicitly shut down.

***

### Attempts at Workarounds and Why They Fail

- Calling non-existent or partial shutdown methods on internal attributes only partially works or not at all.
- Clearing global callbacks reduces thread spawning but does not kill existing workers.
- Monkey-patching threading to default daemon threads sometimes helps but can fail if threads block on IO or are created by other means.
- Using subprocess isolation is the most reliable workaround currently.
- Forcing `os._exit(0)` kills everything abruptly, losing graceful cleanup.

***

### The Definitive Fix (Upstream Needed)
To properly fix this bug in LiteLLM:

1. **Daemonize all internal worker threads.** When creating internal threads in modules like `litellm/_service_logger.py` or `litellm/scheduler.py`, add `daemon=True` to each thread constructor, e.g.:

   ```python
   self.thread = threading.Thread(target=self._worker_loop, daemon=True)
   self.thread.start()
   ```

2. **Expose a `Router.close()` and/or `Router.aclose()` method** that:

   - Calls `.shutdown()`, `.stop()`, or equivalent methods on `service_logger_obj` and `scheduler`.
   - Joins background threads with timeouts to ensure they exit promptly.
   - Clears globally registered callbacks that might spawn threads.

3. **Modify worker loops** to honor stop/shutdown events or flags and exit cleanly once signaled.

4. **Optionally register cleanup handlers** (`atexit.register()` or context managers) so routers used in long-running processes shut down safely on exit.

***

### Effects of the Fix

- Scripts calling LiteLLM Router complete normal async calls, shut down background workers, and allow the Python interpreter process to exit cleanly.
- Prevents resource leaks from wandering threads that consume memory or CPU.
- Provides downstream users a clear API to deterministically close routers and avoid hanging behavior.

***

### Summary

The LiteLLM Router hanging issue is a **bug in thread management inside LiteLLM**:

- Background threads are non-daemon and not properly shut down.
- The Router class lacks a clean shutdown/close interface.
- Client scripts hang due to persistent worker threads blocking interpreter exit.

The fix requires:

- Making all LiteLLM internal threads daemon threads.
- Adding close/shutdown APIs to Router to stop and join these threads cleanly.
- Ensuring worker loops respect shutdown signals.

Until then, common faulty behaviors can be mitigated by monkey-patching daemon threads or running Router calls in subprocesses.

***

This problem and fix are documented in open LiteLLM GitHub issues and discussed in release notes as a known reliability improvement for Python SDK users.[1][2][4][11]

***

If further help is needed, guidance is available on implementing the monkey-patch or patching LiteLLM source to apply the daemonization and shutdown APIs.

[1](https://github.com/BerriAI/litellm/issues/11977)
[2](https://docs.litellm.ai/docs/routing)
[3](https://github.com/BerriAI/litellm/issues/12685)
[4](https://docs.litellm.ai/release_notes)
[5](https://dev.to/yigit-konur/everything-you-need-to-know-about-litellm-python-sdk-3kfk)
[6](https://www.reddit.com/r/HomeKit/comments/1bezjwb/perspective_how_i_improved_my_thread_network_tldr/)
[7](https://docs.litellm.ai/docs/router_architecture)
[8](https://docs.litellm.ai/docs/routing-load-balancing)
[9](https://docs.langwatch.ai/llms.txt)
[10](https://langfuse.com/docs/roadmap)
[11](https://github.com/BerriAI/litellm/issues/10114)