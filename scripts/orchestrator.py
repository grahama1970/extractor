#!/usr/bin/env python3
import json
import asyncio
import os
import random
import string
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable
import threading
import urllib.request
import urllib.error
import shlex
import aiohttp

import typer
from loguru import logger

app = typer.Typer(
    help="General orchestrator: spawn N variants for any codebase, run episodes with plateau detection, log to ingest endpoints, and choose a champion."
)


def _rid(prefix: str) -> str:
    """Generate a unique ID with a prefix, timestamp, and random suffix."""
    return f"{prefix}-{int(time.time())}-{''.join(random.choices(string.ascii_lowercase+string.digits, k=4))}"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL data from path, skipping invalid lines."""
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def _slope(values: List[float]) -> float:
    """Calculate the average slope of sequential value differences."""
    n = len(values)
    if n < 2:
        return 0.0
    # simple diff average
    diffs = [values[i] - values[i - 1] for i in range(1, n)]
    return sum(diffs) / len(diffs)


@app.command()
def run(
    manifest: Optional[Path] = typer.Option(
        None, help="JSON manifest with codebase/N/ports/start-cmd/prompt and more"
    ),
    paper: Path = typer.Option(..., exists=True, help="PDF path (for logs only)"),
    transcript: Path = typer.Option(..., exists=True, help="Transcript JSON (for logs only)"),
    tasks: Path = typer.Option(..., exists=True, help="Tasks JSON file"),
    targets: Optional[List[str]] = typer.Option(
        None, help="Variant URLs, e.g. http://localhost:5173"
    ),
    variants: Optional[List[str]] = typer.Option(None, help="Variant names matching targets order"),
    instances: Optional[int] = typer.Option(
        None, help="Number of variants to generate when not using manifest/variants"
    ),
    episodes: int = typer.Option(10, help="Number of episodes per variant (max)"),
    parallel: int = typer.Option(3, help="[DEPRECATED] Use --max-concurrency"),
    max_concurrency: Optional[int] = typer.Option(
        None, help="Maximum variants to run simultaneously per episode"
    ),
    api_base: str = typer.Option("http://localhost:8000", help="Ingest API base"),
    out: Path = typer.Option(Path("logs/orchestrator"), help="Output dir for orchestrator logs"),
    epsilon: float = typer.Option(0.15, help="Plateau slope epsilon"),
    window: int = typer.Option(5, help="Plateau window size"),
    # Codex exec options
    use_codex: bool = typer.Option(
        False, "--use-codex", help="Run validator under 'codex exec' instead of plain subprocess"
    ),
    codex_bin: str = typer.Option("codex", help="Codex CLI binary"),
    yolo: bool = typer.Option(False, help="codex exec --dangerously-bypass-approvals-and-sandbox"),
    sandbox: Optional[str] = typer.Option(
        None, help="codex exec --sandbox value (e.g., workspace-write)"
    ),
    # Manifest-driven process launch
    autostart: bool = typer.Option(
        True, help="When manifest is provided, auto-start variant servers"
    ),
    start_cmd: Optional[str] = typer.Option(
        None, help="Command template to start one server (uses {codebase},{variant},{port})"
    ),
    codebase: Optional[Path] = typer.Option(None, help="Root directory of the codebase"),
    ports: Optional[List[int]] = typer.Option(
        None, help="Comma-separated list of ports for instances"
    ),
    health_path: str = typer.Option(
        "/classic", help="HTTP path to check for server health (when autostart is used)"
    ),
    health_timeout_s: float = typer.Option(60.0, help="Timeout in seconds for server healthchecks"),
    # Variant workspace + mutation
    clone_variants: bool = typer.Option(
        False, help="If set, clone the original codebase into per-variant workdirs"
    ),
    variants_root: Path = typer.Option(
        Path("workspace/variants"), help="Directory where per-variant clones are created"
    ),
    mutate_cmd: Optional[str] = typer.Option(
        None,
        help="Optional command template to mutate a variant clone (uses {variant_dir},{variant},{rules})",
    ),
    rules: Optional[Path] = typer.Option(
        None, help="Rules file (JSON/text) passed to mutate_cmd as {rules}"
    ),
    # Episode command override (harness agnostic)
    episode_cmd: Optional[str] = typer.Option(
        None,
        help="If set, run this command per episode instead of validator (uses {target},{api_base},{run_id},{episode_id},{variant},{tasks},{screenshot_dir})",
    ),
    # Optional MCP research + code review hooks (run under Codex exec to preserve MCP)
    research_topic: Optional[str] = typer.Option(
        None, help="If set, run scripts/codex_research.py with this topic before episodes"
    ),
    review_files: Optional[List[Path]] = typer.Option(
        None, help="If set, run scripts/codex_code_review.py on these files before episodes"
    ),
):
    """Run orchestrated episodes across variants and stop variants that plateau."""
    out.mkdir(parents=True, exist_ok=True)
    run_id = _rid("run")

    # Manifest mode: load and override parameters
    manifest_data: Dict[str, Any] = {}
    if manifest:
        logger.info(f"Loading manifest: {manifest}")
        manifest_data = json.loads(manifest.read_text())
        # Codebase & start command
        if not codebase and manifest_data.get("codebase"):
            codebase = Path(manifest_data["codebase"]).resolve()
        if not start_cmd and manifest_data.get("start_cmd"):
            start_cmd = manifest_data["start_cmd"]
        # Episode command override
        if not episode_cmd and manifest_data.get("episode_cmd"):
            episode_cmd = manifest_data["episode_cmd"]
        if not ports and manifest_data.get("ports"):
            ports = [int(p) for p in manifest_data["ports"]]
        if not variants and manifest_data.get("variants"):
            variants = [str(v) for v in manifest_data["variants"]]
        if not variants and manifest_data.get("instances"):
            n = int(manifest_data["instances"])
            variants = [f"v{i+1}" for i in range(n)]
        if manifest_data.get("targets"):
            targets = [str(u) for u in manifest_data["targets"]]
        else:
            # Derive targets from ports
            if ports:
                targets = [f"http://localhost:{p}" for p in ports]
        # Paper/transcript/tasks
        if manifest_data.get("paper"):
            Path(manifest_data["paper"]).resolve()
        if manifest_data.get("transcript"):
            Path(manifest_data["transcript"]).resolve()
        if manifest_data.get("tasks"):
            tasks = Path(manifest_data["tasks"]).resolve()
        # Health
        if manifest_data.get("health_path"):
            health_path = str(manifest_data["health_path"])  # type: ignore[assignment]
        if manifest_data.get("health_timeout_s"):
            try:
                health_timeout_s = float(manifest_data["health_timeout_s"])  # type: ignore[assignment]
            except Exception:
                pass
        # Codex policy
        codex_cfg = manifest_data.get("codex") or {}
        if codex_cfg:
            use_codex = codex_cfg.get("use", use_codex)
            codex_bin = codex_cfg.get("bin", codex_bin)
            yolo = codex_cfg.get("yolo", yolo)
            sandbox = codex_cfg.get("sandbox", sandbox)
        # API base
        if manifest_data.get("api_base"):
            api_base = manifest_data["api_base"]
        # Override run id if provided
        if manifest_data.get("run_id"):
            run_id = str(manifest_data["run_id"]) + "-" + _rid("run").split("-", 1)[1]
        # Autostart behavior
        if manifest_data.get("autostart") is not None:
            autostart = bool(manifest_data["autostart"])

    if not targets:
        raise typer.BadParameter(
            "No targets provided. Pass --targets or a manifest with ports/targets."
        )
    logger.info(f"Run {run_id} with {len(targets)} targets")

    if not variants or len(variants) != len(targets):
        variants = [f"v{i+1}" for i in range(len(targets))]

    # If variants not provided by manifest/flag, synthesize from instances
    if not variants:
        if instances is None:
            raise typer.BadParameter("Provide either --manifest, --variants or --instances")
        variants = [f"v{i+1}" for i in range(int(instances))]
    # Map each variant to its codebase directory (original or clone)
    variant_base_dir: Dict[str, Path] = {}
    if clone_variants:
        if not codebase:
            raise typer.BadParameter("--clone-variants requires --codebase")
        base = variants_root / _rid("run")
        base.mkdir(parents=True, exist_ok=True)
        from shutil import copytree, ignore_patterns

        ignores = ignore_patterns(
            ".git", ".venv", "node_modules", "dist", "build", variants_root.name
        )
        for v in variants:
            dst = base / v
            logger.info(f"Cloning codebase to {dst}")
            copytree(str(codebase), str(dst), dirs_exist_ok=True, ignore=ignores)
            variant_base_dir[v] = dst
            # Optional mutation step
            if mutate_cmd:
                cmd_tpl = mutate_cmd.format(
                    variant_dir=str(dst), variant=v, rules=(str(rules) if rules else "")
                )
                full_cmd = cmd_tpl
                if use_codex:
                    parts = [codex_bin, "exec"]
                    if yolo:
                        parts.append("--dangerously-bypass-approvals-and-sandbox")
                    if sandbox:
                        parts.extend(["--sandbox", sandbox])
                    parts.append("--")
                    full_cmd = " ".join(shlex.quote(p) for p in parts) + " " + full_cmd
                logger.info(f"Mutating {v}: {full_cmd}")
                try:
                    subprocess.run(
                        full_cmd,
                        shell=True,
                        check=False,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception as e:
                    logger.warning(f"Mutation command failed for {v}: {e}")
    else:
        # No clones: use original codebase for all variants if provided
        if codebase:
            for v in variants:
                variant_base_dir[v] = codebase

    scores: Dict[str, List[float]] = {v: [] for v in variants}
    plateaued: Dict[str, bool] = {v: False for v in variants}

    # -------------------------
    # Manifest autostart servers
    # -------------------------
    server_procs: List[subprocess.Popen] = []
    server_threads: List[threading.Thread] = []

    def _post_log_sync(stream: str, line: str, vname: str):
        payload = {
            "ts": time.time(),
            "run_id": run_id,
            "variant": vname,
            "episode_id": None,
            "stream": stream,
            "source": "server",
            "message": line.rstrip("\n"),
            "meta": {},
        }
        try:
            req = urllib.request.Request(
                api_base.rstrip("/") + "/ingest/log",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass

    def _spawn_server(vname: str, port: int, base_dir: Optional[Path] = None):
        assert start_cmd, "start_cmd is required for autostart"
        dir_for_variant = base_dir or variant_base_dir.get(vname) or codebase
        assert dir_for_variant, "codebase could not be resolved for server start"
        base_cmd = start_cmd.format(codebase=str(dir_for_variant), variant=vname, port=port)
        if use_codex:
            parts = [codex_bin, "exec"]
            if yolo:
                parts.append("--dangerously-bypass-approvals-and-sandbox")
            if sandbox:
                parts.extend(["--sandbox", sandbox])
            parts.append("--")
            # Join as a shell string so we can keep original quoting
            cmd = " ".join(shlex.quote(p) for p in parts) + " " + base_cmd
        else:
            cmd = base_cmd
        logger.info(f"Starting server for {vname} on {port}: {cmd}")
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        server_procs.append(proc)

        def _reader(stream_name: str, fh):
            try:
                for line in iter(fh.readline, ""):
                    _post_log_sync(stream_name, line, vname)
            except Exception:
                pass

        if proc.stdout:
            t1 = threading.Thread(target=_reader, args=("stdout", proc.stdout), daemon=True)
            t1.start()
            server_threads.append(t1)
        if proc.stderr:
            t2 = threading.Thread(target=_reader, args=("stderr", proc.stderr), daemon=True)
            t2.start()
            server_threads.append(t2)

    def _healthcheck(url: str, path: str = "/classic", timeout_s: float = 60.0) -> bool:
        deadline = time.time() + timeout_s
        target = url.rstrip("/") + path
        while time.time() < deadline:
            try:
                resp = urllib.request.urlopen(target, timeout=2)
                code = getattr(resp, "status", 200)
                if 200 <= code < 500:
                    return True
            except urllib.error.URLError:
                pass
            time.sleep(1.0)
        return False

    # If manifest autostart requested, start servers and wait for health
    if (manifest and autostart) or (autostart and start_cmd and (ports and targets is None)):
        assert ports and len(ports) == len(
            variants
        ), "ports must match number of variants when autostarting"
        for vname, port in zip(variants, ports):
            _spawn_server(vname, port, base_dir=variant_base_dir.get(vname))
        # Wait for health for each target
        if not targets:
            targets = [f"http://localhost:{p}" for p in ports]
        for url in targets:
            ok = _healthcheck(url, path=health_path, timeout_s=health_timeout_s)
            logger.info(f"Healthcheck {url}: {'OK' if ok else 'TIMEOUT'}")

    # -------------------------
    # Optional research and code review (via Codex exec)
    # -------------------------
    if research_topic:
        logger.info(f"Running research via Codex MCP: {research_topic}")
        if use_codex:
            from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec

            asyncio.run(
                run_codex_exec(
                    script_or_path="python",
                    codex_bin=codex_bin,
                    extra_args=[
                        "scripts/codex_research.py",
                        "run",
                        "--topic",
                        research_topic,
                        "--api-base",
                        api_base,
                        "--run-id",
                        run_id,
                    ],
                    bypass_approvals_and_sandbox=yolo,
                    sandbox_mode=sandbox,
                    stdout_capture_limit=512 * 1024,
                    stderr_capture_limit=256 * 1024,
                )
            )
        else:
            subprocess.run(
                [
                    "python",
                    "scripts/codex_research.py",
                    "run",
                    "--topic",
                    research_topic,
                    "--api-base",
                    api_base,
                    "--run-id",
                    run_id,
                ]
            )

    if review_files:
        logger.info(f"Running code review via Codex persona on {len(review_files)} files")
        file_args = [str(p) for p in review_files]
        if use_codex:
            from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec

            asyncio.run(
                run_codex_exec(
                    script_or_path="python",
                    codex_bin=codex_bin,
                    extra_args=[
                        "scripts/codex_code_review.py",
                        "run",
                        "--api-base",
                        api_base,
                        "--run-id",
                        run_id,
                    ]
                    + file_args,
                    bypass_approvals_and_sandbox=yolo,
                    sandbox_mode=sandbox,
                    stdout_capture_limit=1024 * 1024,
                    stderr_capture_limit=256 * 1024,
                )
            )
        else:
            subprocess.run(
                [
                    "python",
                    "scripts/codex_code_review.py",
                    "run",
                    "--api-base",
                    api_base,
                    "--run-id",
                    run_id,
                ]
                + file_args
            )

    # Concurrency limit (pool)
    concurrency = (
        max_concurrency
        if (max_concurrency and max_concurrency > 0)
        else (parallel if parallel and parallel > 0 else len(variants))
    )

    def _chunked(seq: Iterable[Any], n: int) -> Iterable[List[Any]]:
        buf: List[Any] = []
        for x in seq:
            buf.append(x)
            if len(buf) == n:
                yield buf
                buf = []
        if buf:
            yield buf

    for ep in range(1, episodes + 1):
        logger.info(f"Episode {ep}/{episodes}")
        tmp_files: List[Path] = []
        if episode_cmd:
            # Generic episode command (harness-agnostic). Expect it to print JSON with { ok, payload: { score, metrics, ... } }.
            pairs = [(v, t) for v, t in zip(variants, (targets or [])) if not plateaued[v]]
            for batch in _chunked(pairs, concurrency):
                procs: List[subprocess.Popen] = []
                episode_tmp: Dict[subprocess.Popen, Path] = {}
                for vname, target in batch:
                    episode_id = f"e-{ep:04d}"
                    tmp = out / f"{run_id}_{vname}_{episode_id}.json"
                    tmp_files.append(tmp)
                    cmd_str = episode_cmd.format(
                        target=target,
                        api_base=api_base,
                        run_id=run_id,
                        episode_id=episode_id,
                        variant=vname,
                        tasks=str(tasks),
                        screenshot_dir=str(Path("artifacts") / vname),
                    )
                    if use_codex:
                        parts = [codex_bin, "exec"]
                        if yolo:
                            parts.append("--dangerously-bypass-approvals-and-sandbox")
                        if sandbox:
                            parts.extend(["--sandbox", sandbox])
                        parts.append("--")
                        cmd_str = " ".join(shlex.quote(p) for p in parts) + " " + cmd_str
                    logger.info(cmd_str)
                    fp = open(tmp, "w")
                    proc = subprocess.Popen(
                        cmd_str, shell=True, stdout=fp, stderr=subprocess.PIPE, text=True
                    )
                    procs.append(proc)
                    episode_tmp[proc] = fp
                # Wait for batch
                for proc in procs:
                    _, err = proc.communicate()
                    try:
                        episode_tmp[proc].close()
                    except Exception:
                        pass
                    if err:
                        logger.warning(err)
        elif not use_codex:
            pairs = [(v, t) for v, t in zip(variants, targets)]
            for batch in _chunked([(v, t) for v, t in pairs if not plateaued[v]], concurrency):
                procs: List[subprocess.Popen] = []
                for vname, target in batch:
                    episode_id = f"e-{ep:04d}"
                    tmp = out / f"{run_id}_{vname}_{episode_id}.json"
                    tmp_files.append(tmp)
                    cmd = [
                        os.environ.get("PYTHON", "python"),
                        "scripts/validator_puppeteer.py",
                        "episode",
                        "--target",
                        target,
                        "--api-base",
                        api_base,
                        "--run-id",
                        run_id,
                        "--episode-id",
                        episode_id,
                        "--variant",
                        vname,
                        "--tasks-file",
                        str(tasks),
                        "--screenshot-dir",
                        str(Path("artifacts") / vname),
                    ]
                    logger.info(" ".join(cmd))
                    with open(tmp, "w") as fp:
                        proc = subprocess.Popen(cmd, stdout=fp, stderr=subprocess.PIPE)
                        procs.append(proc)
                # Wait for batch
                for proc in procs:
                    _, err = proc.communicate()
                    if err:
                        try:
                            logger.warning(err.decode(errors="ignore"))
                        except Exception:
                            logger.warning(str(err))
        else:
            # Run each variant under codex exec (validator or generic episode_cmd)
            from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec

            async def _run_one(vname: str, target: str, ep_id: str, out_path: Path):
                # Build command
                if episode_cmd:
                    cmd_str = episode_cmd.format(
                        target=target,
                        api_base=api_base,
                        run_id=run_id,
                        episode_id=ep_id,
                        variant=vname,
                        tasks=str(tasks),
                        screenshot_dir=str(Path("artifacts") / vname),
                    )
                    args = ["bash", "-lc", cmd_str]
                    script_or_path = "bash"
                else:
                    args = [
                        "scripts/validator_puppeteer.py",
                        "episode",
                        "--target",
                        target,
                        "--api-base",
                        api_base,
                        "--run-id",
                        run_id,
                        "--episode-id",
                        ep_id,
                        "--variant",
                        vname,
                        "--tasks-file",
                        str(tasks),
                        "--screenshot-dir",
                        str(Path("artifacts") / vname),
                    ]
                    script_or_path = "python"
                # Live log streaming to /ingest/log via callbacks
                session = aiohttp.ClientSession()
                log_url = api_base.rstrip("/") + "/ingest/log"
                rem_out = ""
                rem_err = ""

                async def _post_log(stream: str, line: str):
                    payload = {
                        "ts": time.time(),
                        "run_id": run_id,
                        "variant": vname,
                        "episode_id": ep_id,
                        "stream": stream,
                        "source": "codex",
                        "message": line.rstrip("\n"),
                        "meta": {},
                    }
                    try:
                        async with session.post(log_url, json=payload, timeout=5) as resp:
                            _ = await resp.text()
                    except Exception:
                        pass

                def _on_stdout(chunk: bytes):
                    nonlocal rem_out
                    try:
                        text = chunk.decode("utf-8", errors="replace")
                    except Exception:
                        text = str(chunk)
                    text = rem_out + text
                    lines = text.split("\n")
                    rem_out = lines[-1]
                    for ln in lines[:-1]:
                        asyncio.create_task(_post_log("stdout", ln))

                def _on_stderr(chunk: bytes):
                    nonlocal rem_err
                    try:
                        text = chunk.decode("utf-8", errors="replace")
                    except Exception:
                        text = str(chunk)
                    text = rem_err + text
                    lines = text.split("\n")
                    rem_err = lines[-1]
                    for ln in lines[:-1]:
                        asyncio.create_task(_post_log("stderr", ln))

                res = await run_codex_exec(
                    script_or_path=script_or_path,
                    codex_bin=codex_bin,
                    extra_args=args,
                    bypass_approvals_and_sandbox=yolo,
                    sandbox_mode=sandbox,
                    overall_timeout_s=900.0,
                    on_stdout_chunk=_on_stdout,
                    on_stderr_chunk=_on_stderr,
                    stdout_capture_limit=512 * 1024,
                    stderr_capture_limit=512 * 1024,
                )
                # Flush remaining partial lines
                if rem_out:
                    await _post_log("stdout", rem_out)
                if rem_err:
                    await _post_log("stderr", rem_err)
                # Write exact stdout to file for downstream parse
                out_path.write_text(res.stdout or "", encoding="utf-8")
                if res.returncode not in (0, None):
                    logger.warning(f"codex exec returned rc={res.returncode} for {vname}:{ep_id}")
                await session.close()

            coros = []
            for vname, target in zip(variants, targets):
                if plateaued[vname]:
                    logger.info(f"Variant {vname} plateaued; skipping")
                    continue
                episode_id = f"e-{ep:04d}"
                tmp = out / f"{run_id}_{vname}_{episode_id}.json"
                tmp_files.append(tmp)
                coros.append(_run_one(vname, target, episode_id, tmp))

            if coros:
                # Bounded concurrency
                async def _run_all_limited(coros_in: List[Any]):
                    sem = asyncio.Semaphore(concurrency)

                    async def _wrap(coro):
                        async with sem:
                            return await coro

                    await asyncio.gather(*[_wrap(c) for c in coros_in])

                asyncio.run(_run_all_limited(coros))

        # Collect scores and check plateaus
        err_signals: Dict[str, List[str]] = {}
        for tmp in tmp_files:
            try:
                data = json.loads(tmp.read_text())
                if data.get("ok"):
                    payload = data.get("payload", {})
                    vname = payload.get("variant")
                    sc = float(payload.get("score", 0.0))
                    scores[vname].append(sc)
                    # collect potential API/docs error signals
                    metrics = payload.get("metrics", {}) or {}
                    es = metrics.get("errors_sample") or []
                    if es:
                        err_signals.setdefault(vname, []).extend([str(x) for x in es])
            except Exception as e:
                logger.warning(f"Failed to parse {tmp}: {e}")

        for vname, hist in scores.items():
            if plateaued[vname]:
                continue
            if len(hist) >= window:
                s = _slope(hist[-window:])
                logger.info(f"Variant {vname} recent slope={s:.3f} (hist={hist[-window:]})")
                if abs(s) < epsilon:
                    plateaued[vname] = True
                    logger.info(f"Variant {vname} marked plateaued.")
                    # Auto-trigger research once per variant on plateau
                    try:
                        topic = f"Variant {vname} plateaued with recent scores {hist[-window:]}. Recommend UI mutations and heuristics grounded in pdf.js/shadcn docs."
                        if use_codex:
                            from extractor.pipeline.utils.deprecated_codex_call import (
                                run_codex_exec,
                            )

                            ts = int(time.time())
                            save_to = Path("data/research") / f"research_{run_id}_{vname}_{ts}.json"
                            docs_dir = Path("data/docs_summaries") / f"{run_id}_{vname}_{ts}"
                            asyncio.run(
                                run_codex_exec(
                                    script_or_path="python",
                                    codex_bin=codex_bin,
                                    extra_args=[
                                        "scripts/codex_research.py",
                                        "run",
                                        "--topic",
                                        topic,
                                        "--api-base",
                                        api_base,
                                        "--run-id",
                                        run_id,
                                        "--save-to",
                                        str(save_to),
                                        "--docs-dir",
                                        str(docs_dir),
                                    ],
                                    bypass_approvals_and_sandbox=yolo,
                                    sandbox_mode=sandbox,
                                    stdout_capture_limit=512 * 1024,
                                    stderr_capture_limit=256 * 1024,
                                )
                            )
                    except Exception as e:
                        logger.warning(f"Auto-research failed: {e}")

        # Auto-trigger research on API/docs-like error signals
        for vname, msgs in err_signals.items():
            if not msgs:
                continue
            # trigger on keywords that often imply docs/API issues
            key = " ".join(msgs[:3])[:400]
            topic = f"Investigate errors observed in {vname}: {key}. Provide fixes using pdf.js and related docs; suggest robust patterns."
            try:
                from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec

                ts = int(time.time())
                save_to = Path("data/research") / f"research_{run_id}_{vname}_errors_{ts}.json"
                docs_dir = Path("data/docs_summaries") / f"{run_id}_{vname}_errors_{ts}"
                asyncio.run(
                    run_codex_exec(
                        script_or_path="python",
                        codex_bin=codex_bin,
                        extra_args=[
                            "scripts/codex_research.py",
                            "run",
                            "--topic",
                            topic,
                            "--api-base",
                            api_base,
                            "--run-id",
                            run_id,
                            "--save-to",
                            str(save_to),
                            "--docs-dir",
                            str(docs_dir),
                        ],
                        bypass_approvals_and_sandbox=yolo,
                        sandbox_mode=sandbox,
                        stdout_capture_limit=512 * 1024,
                        stderr_capture_limit=256 * 1024,
                    )
                )
            except Exception as e:
                logger.warning(f"Auto-research(error-trigger) failed: {e}")

        if all(plateaued.values()):
            logger.info("All variants plateaued. Stopping early.")
            break

    # Summary
    best_v = None
    best_score = -1.0
    for vname, hist in scores.items():
        if hist:
            mx = max(hist)
            logger.info(f"Variant {vname} max score={mx:.2f}")
            if mx > best_score:
                best_score, best_v = mx, vname
    logger.info(f"Champion: {best_v} ({best_score:.2f})")
    print(json.dumps({"ok": True, "run_id": run_id, "scores": scores, "champion": best_v}))

    # Teardown servers if autostarted
    if server_procs:
        logger.info("Stopping autostarted servers...")
        for p in server_procs:
            try:
                p.terminate()
            except Exception:
                pass
        # Give them a moment, then kill if needed
        time.sleep(2.0)
        for p in server_procs:
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    app()
