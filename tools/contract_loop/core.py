from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional


from .adapters.base import BaseAdapter
from .clarify import ClarifyError, ClarifyTimeout, run_clarification_flow
from .env_utils import ROOT, env_with_pythonpath
from .manifest import Manifest
from .utils import (
    ContractLoopError,
    assert_helping,
    compose_collaboration_bundle,
)

from .sanity_runner import run_preflight_sanity, SanityCheckError

DEFAULT_OUT = ROOT / "data" / "results" / "pipeline_contract"
JUDGE_SCHEMA = Path(__file__).resolve().parent / "judges" / "llm_judge.schema.json"
CLARIFY_EXIT_CODE = 4


class CommandResult:
    def __init__(self, returncode: int, logs: dict[str, Path] | None = None):
        self.returncode = returncode
        self.logs = logs or {}


def _stream_process_output(pipe, log_handle) -> None:
    if pipe is None:
        return
    for line in iter(pipe.readline, b""):
        if not line:
            break
        decoded = line.decode(errors="replace")
        print(decoded, end="")
        if log_handle:
            log_handle.write(decoded)
    if log_handle:
        log_handle.flush()
    pipe.close()


def run_cmd(
    cmd: list[str],
    env: dict,
    *,
    log_dir: Optional[Path] = None,
    capture: bool = False,
) -> CommandResult:
    print(">>", " ".join(cmd))

    stdout_handle = stderr_handle = None
    stdout_path = stderr_path = None

    if capture:
        if log_dir is None:
            raise ValueError("log_dir is required when capture=True")
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / "stdout.log"
        stderr_path = log_dir / "stderr.log"
        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")

    try:
        if capture:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout_thread = threading.Thread(
                target=_stream_process_output, args=(proc.stdout, stdout_handle), daemon=True
            )
            stderr_thread = threading.Thread(
                target=_stream_process_output, args=(proc.stderr, stderr_handle), daemon=True
            )
            stdout_thread.start()
            stderr_thread.start()
            proc.wait()
            stdout_thread.join()
            stderr_thread.join()
            rc = proc.returncode
        else:
            rc = subprocess.run(cmd, env=env).returncode

        logs = {}
        if capture and stdout_path and stderr_path:
            logs = {"stdout": stdout_path, "stderr": stderr_path}
        return CommandResult(rc, logs)
    finally:
        if stdout_handle:
            stdout_handle.close()
        if stderr_handle:
            stderr_handle.close()


def attempt_log_dir(out: Path, step_name: str, attempt: int) -> Path:
    return out / step_name / f"attempt_{attempt}"


def write_debug_summary(out: Path, entries: list[dict[str, str]]) -> None:
    if not entries:
        return
    lines = [
        "# Debug Run Summary",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Step | Attempt | Status | Logs |",
        "| --- | --- | --- | --- |",
    ]
    for entry in entries:
        log_cell = entry.get("logs") or "n/a"
        lines.append(f"| {entry['step']} | {entry['attempt']} | {entry['status']} | {log_cell} |")
    (out / "debug.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_fixture(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Fixture file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_fixture_pdf(fixture: dict, pdf_path: Optional[Path]) -> None:
    info = fixture.get("fixture", {}) if fixture else {}
    expected_hash = info.get("pdf_sha256")
    if expected_hash and pdf_path:
        actual_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        assert_helping(
            actual_hash == expected_hash,
            (
                f"fixture PDF hash mismatch: {actual_hash} != {expected_hash}\n"
                f"Expected PDF (reference): {info.get('pdf')}\n"
                f"Actual PDF: {pdf_path}"
            ),
        )


def judge_with_codex(prompt: str, model: Optional[str]) -> dict:
    if not JUDGE_SCHEMA.exists():
        raise FileNotFoundError(f"Judge schema missing: {JUDGE_SCHEMA}")
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)
    cmd = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--output-schema",
        str(JUDGE_SCHEMA),
        "--output-last-message",
        str(out_path),
        "-C",
        str(ROOT),
    ]
    if model:
        cmd.extend(["--model", model])
    rc = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        env=env_with_pythonpath(),
        timeout=120,
    ).returncode
    if rc != 0:
        raise RuntimeError(f"codex exec failed (rc={rc})")
    return json.loads(out_path.read_text(encoding="utf-8"))


def persist_judge_result(
    out: Path,
    step_name: str,
    attempt: int,
    result: dict,
    samples: list[str],
    prompt: str,
    model: Optional[str],
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    out_dir = out / step_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "judge_output.json").write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "step": step_name,
                "attempt": attempt,
                "model": model or "default",
                "prompt": prompt,
                "prompt_hash": prompt_hash,
                "samples": samples,
                "result": result,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    with (out / "judge_index.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": timestamp,
                    "step": step_name,
                    "attempt": attempt,
                    "ok": result.get("ok"),
                    "score": result.get("score"),
                    "issues": result.get("issues"),
                    "num_samples": len(samples),
                    "output_file": str((out_dir / "judge_output.json").relative_to(out)),
                    "prompt_hash": prompt_hash,
                }
            )
            + "\n"
        )


def judge_llm_step(
    step_name: str,
    out: Path,
    fixture: dict,
    model: Optional[str],
    adapter: BaseAdapter,
    attempt: int = 1,
) -> None:
    expected = (fixture.get("steps") or {}).get(step_name) or {}
    judge = expected.get("judge") or {}
    if not judge.get("enabled", False):
        return

    samples = adapter.collect_llm_samples(step_name, out, fixture)
    min_samples = int(judge.get("min_samples", 1))
    assert_helping(len(samples) >= min_samples, f"{step_name}: samples >= {min_samples}")

    disallow = judge.get("disallow") or []
    for sample in samples:
        low = sample.lower()
        for phrase in disallow:
            if phrase.lower() in low:
                raise ContractLoopError(f"{step_name}: disallowed phrase '{phrase}' found")

    prompt = judge.get("prompt", "").strip()
    if not prompt:
        prompt = (
            "You are evaluating LLM outputs from a PDF extraction pipeline. "
            "Decide if the samples are coherent, relevant, and non-placeholder. "
            "Return JSON only."
        )
    sample_block = "\n\n".join([f"Sample {i+1}:\n{txt}" for i, txt in enumerate(samples)])
    full_prompt = f"{prompt}\n\n{sample_block}\n\nReturn JSON with fields ok, score, issues."
    result = judge_with_codex(full_prompt, model)
    try:
        persist_judge_result(out, step_name, attempt, result, samples, prompt, model)
    except Exception:
        pass
    ok = bool(result.get("ok"))
    if not ok:
        issues = result.get("issues")
        sample_snippets = "\n".join(samples[:2])
        raise ContractLoopError(
            f"{step_name}: codex judge failed ({issues})\nSamples:\n{sample_snippets}"
        )


@dataclass(frozen=True)
class Step:
    name: str
    module: str
    build_run_args: Callable[[Path, argparse.Namespace], list[str]]
    verify_cli: bool = True
    custom_verify: Optional[Callable[[Path, argparse.Namespace], None]] = None
    enabled: Optional[Callable[[argparse.Namespace], bool]] = None
    execute: bool = True
    output_paths: tuple[str, ...] = ()

    def is_enabled(self, args: argparse.Namespace) -> bool:
        return True if self.enabled is None else bool(self.enabled(args))


def verify_step(
    step: Step,
    out: Path,
    args: argparse.Namespace,
    env: dict,
    fixture: Optional[dict],
    adapter: BaseAdapter,
    attempt: int = 1,
    *,
    log_dir: Optional[Path] = None,
    capture_logs: bool = False,
) -> bool:
    try:
        log_target = log_dir / "verify" if (capture_logs and log_dir) else None
        if step.verify_cli:
            verify_cmd = [sys.executable, "-m", step.module]
            verify_cmd.extend(step.build_run_args(out, args))
            verify_cmd.append("--verify-only")
            verify_result = run_cmd(
                verify_cmd,
                env,
                capture=capture_logs,
                log_dir=log_target,
            )
            if verify_result.returncode != 0:
                return False
        if step.custom_verify:
            step.custom_verify(out, args)
        if fixture:
            adapter.verify_fixture_step(step.name, out, fixture)
            if args.llm_judge:
                judge_llm_step(step.name, out, fixture, args.llm_judge_model, adapter, attempt)
        if args.debug:
            adapter.verify_visuals(step.name, out, args, fixture)
        return True
    except Exception as exc:
        print(f"!! {step.name} verification failed: {exc}")
        return False


def run_step(
    step: Step,
    out: Path,
    args: argparse.Namespace,
    env: dict,
    fixture: Optional[dict],
    adapter: BaseAdapter,
    attempt: int = 1,
) -> bool:
    capture_logs = bool(args.debug)
    attempt_dir: Optional[Path] = None
    if capture_logs:
        attempt_dir = attempt_log_dir(out, step.name, attempt)
        attempt_dir.mkdir(parents=True, exist_ok=True)
    verify_log_dir = attempt_dir if capture_logs else None

    if args.verify_only:
        time.time()
        success = verify_step(
            step,
            out,
            args,
            env,
            fixture,
            adapter,
            attempt,
            log_dir=verify_log_dir,
            capture_logs=capture_logs,
        )
        # We don't record timing here because it's captured in run_contract_loop
        return success

    if step.execute:
        base_cmd = [sys.executable, "-m", step.module]
        base_cmd.extend(step.build_run_args(out, args))
        result = run_cmd(
            base_cmd,
            env,
            capture=capture_logs,
            log_dir=attempt_dir,
        )
        if result.returncode != 0:
            return False

    return verify_step(
        step,
        out,
        args,
        env,
        fixture,
        adapter,
        attempt,
        log_dir=verify_log_dir,
        capture_logs=capture_logs,
    )


def run_contract_loop(args: argparse.Namespace, adapter: BaseAdapter) -> int:
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    env = env_with_pythonpath()
    if args.debug:
        env["CONTRACT_LOOP_DEBUG_VISUALS"] = "1"
    fixture = load_fixture(args.fixture) if args.fixture else None
    if fixture:
        validate_fixture_pdf(fixture, args.pdf)

    steps = adapter.build_steps(args, fixture)
    enabled_steps = [s for s in steps if s.is_enabled(args)]
    try:
        run_preflight_sanity({s.name for s in enabled_steps}, adapter_name=adapter.name)
    except SanityCheckError as exc:
        print(f"!! Sanity check failed: {exc}")
        return 5

    # Task 1: Initialize Manifest
    manifest = Manifest(
        out,
        sys.argv,
        args.fixture,
        debug_info={
            "enabled": bool(args.debug),
            "no_clean_downstream": bool(args.no_clean_downstream),
            "no_rerun_upstream": bool(args.no_rerun_upstream),
        },
    )
    debug_entries: list[dict[str, str]] = []
    bundle_warn_bytes = int(getattr(args, "bundle_warn_mb", 50) * 1024 * 1024)
    bundle_fail_bytes = int(getattr(args, "bundle_max_mb", 100) * 1024 * 1024)

    def _create_bundle_or_fail(step_name: str, attempt: int, artifacts: list[str]) -> Optional[str]:
        if not args.debug:
            return None
        try:
            info = compose_collaboration_bundle(
                out,
                step_name,
                attempt,
                warn_bytes=bundle_warn_bytes,
                fail_bytes=bundle_fail_bytes,
            )
        except ContractLoopError as exc:
            print(f"!! Failed to create collaboration bundle: {exc}")
            raise

        rel_path = str(info.path.relative_to(out))
        artifacts.append(rel_path)
        size_mb = info.size_bytes / (1024 * 1024)
        if info.warned:
            warn_mb = getattr(args, "bundle_warn_mb", 50)
            print(
                f"⚠️ Collaboration bundle size {size_mb:.1f} MB exceeds warning "
                f"threshold ({warn_mb} MB)."
            )
        print(f"📦 Collaboration bundle ready: {rel_path} ({size_mb:.1f} MB)")
        return rel_path

    index_by_name = {s.name: i for i, s in enumerate(enabled_steps)}

    if args.start_step:
        start_idx = index_by_name.get(args.start_step)
        if start_idx is None:
            print(f"!! Unknown step: {args.start_step}")
            finalize_debug(out, debug_entries, bool(args.debug))
            return 2
        print(f"Validating upstream steps before starting at {args.start_step}...")
        for idx in range(start_idx):
            step = enabled_steps[idx]
            # We don't record upstream checks in the manifest as "attempts", just validation
            if not verify_step(step, out, args, env, fixture, adapter, attempt=1):
                print(f"!! Upstream step {step.name} failed verification")
                print(f"!! Cannot skip to {args.start_step} with invalid upstream state")
                finalize_debug(out, debug_entries, bool(args.debug))
                return 3
        enabled_steps = enabled_steps[start_idx:]
        index_by_name = {s.name: i for i, s in enumerate(enabled_steps)}

    if args.verify_only:
        for step in enabled_steps:
            print(f"== {step.name} ==")
            start_t = time.time()
            success = run_step(step, out, args, env, fixture, adapter, attempt=1)
            duration = time.time() - start_t
            artifacts = list(step.output_paths)
            logs_rel = None
            if args.debug:
                attempt_dir = attempt_log_dir(out, step.name, 1)
                if attempt_dir.exists():
                    logs_rel = str(attempt_dir.relative_to(out))
                    artifacts.append(logs_rel)

            if not success:
                clar_path, clarify_exit = _maybe_run_clarifications(
                    step.name, 1, adapter, args, out, manifest
                )
                if clarify_exit:
                    finalize_debug(out, debug_entries, bool(args.debug))
                    return clarify_exit
                if clar_path:
                    artifacts.append(clar_path)
                if args.debug:
                    try:
                        _create_bundle_or_fail(step.name, 1, artifacts)
                    except ContractLoopError:
                        finalize_debug(out, debug_entries, bool(args.debug))
                        return 2

            manifest.add_step_attempt(
                step.name,
                1,
                "success" if success else "failed",
                duration,
                artifacts,
            )

            if args.debug:
                debug_entries.append(
                    {
                        "step": step.name,
                        "attempt": 1,
                        "status": "success" if success else "failed",
                        "logs": logs_rel,
                    }
                )

            if not success:
                print(f"!! {step.name} verification failed")
                finalize_debug(out, debug_entries, bool(args.debug))
                return 1
        print("✅ Contract verification complete.")
        finalize_debug(out, debug_entries, bool(args.debug))
        return 0

    for target_index, target_step in enumerate(enabled_steps):
        print(f"== {target_step.name} ==")
        success = False
        for attempt in range(1, args.max_tries + 1):
            print(f"-- attempt {attempt}/{args.max_tries}")
            if not args.no_clean_downstream:
                adapter.clean_downstream(out, enabled_steps, target_index, index_by_name)

            ok = True
            start_idx = 0
            end_idx = target_index
            if args.no_rerun_upstream:
                start_idx = target_index

            for idx in range(start_idx, end_idx + 1):
                step = enabled_steps[idx]
                print(f"-- running {step.name}")

                start_t = time.time()
                step_ok = run_step(step, out, args, env, fixture, adapter, attempt=attempt)
                duration = time.time() - start_t
                artifacts = list(step.output_paths)
                logs_rel = None
                if args.debug:
                    attempt_dir = attempt_log_dir(out, step.name, attempt)
                    if attempt_dir.exists():
                        logs_rel = str(attempt_dir.relative_to(out))
                        artifacts.append(logs_rel)

                if not step_ok:
                    try:
                        _create_bundle_or_fail(step.name, attempt, artifacts)
                    except ContractLoopError:
                        finalize_debug(out, debug_entries, bool(args.debug))
                        return 2

                # Record manifest for the step
                manifest.add_step_attempt(
                    step.name,
                    attempt,
                    "success" if step_ok else "failed",
                    duration,
                    artifacts,
                )

                if args.debug:
                    debug_entries.append(
                        {
                            "step": step.name,
                            "attempt": attempt,
                            "status": "success" if step_ok else "failed",
                            "logs": logs_rel,
                        }
                    )

                if not step_ok:
                    ok = False
                    break

            if ok:
                success = True
                break
            if attempt < args.max_tries:
                print(f"!! retrying {target_step.name}")

        if not success:
            print(f"!! {target_step.name} failed after {args.max_tries} attempts")
            print("ACTION REQUIRED: provide clarifying answers before proceeding.")
            clar_path, clarify_exit = _maybe_run_clarifications(
                target_step.name, attempt, adapter, args, out, manifest
            )
            if clarify_exit:
                finalize_debug(out, debug_entries, bool(args.debug))
                return clarify_exit
            if args.debug:
                final_artifacts = list(target_step.output_paths)
                attempt_dir = attempt_log_dir(out, target_step.name, attempt)
                if attempt_dir.exists():
                    final_artifacts.append(str(attempt_dir.relative_to(out)))
                if clar_path:
                    final_artifacts.append(clar_path)
                try:
                    _create_bundle_or_fail(target_step.name, attempt, final_artifacts)
                except ContractLoopError:
                    finalize_debug(out, debug_entries, bool(args.debug))
                    return 2
            finalize_debug(out, debug_entries, bool(args.debug))
            return 2

    print("✅ Contract verification complete.")
    finalize_debug(out, debug_entries, bool(args.debug))
    return 0


def finalize_debug(out: Path, entries: list[dict[str, str]], enabled: bool) -> None:
    if enabled:
        write_debug_summary(out, entries)


def _print_plain_questions(step_name: str, questions) -> None:
    print("Clarifying questions:")
    for q in questions:
        prompt = getattr(q, "prompt", None) or str(q)
        print(f"- {prompt}")


def _maybe_run_clarifications(
    step_name: str,
    attempt: int,
    adapter: BaseAdapter,
    args: argparse.Namespace,
    out: Path,
    manifest: Manifest,
) -> tuple[Optional[str], Optional[int]]:
    questions = adapter.questions_for_step(step_name) or []
    if not questions:
        print("No clarifying questions defined for this step.")
        return None, None
    if not args.debug:
        _print_plain_questions(step_name, questions)
        return None, None
    try:
        clarify_path = run_clarification_flow(
            out,
            step_name,
            attempt,
            questions,
            args.clarify_timeout,
        )
    except ClarifyTimeout as exc:
        print(f"!! Clarifying UI timed out: {exc}")
        return None, CLARIFY_EXIT_CODE
    except ClarifyError as exc:
        print(f"!! Clarifying UI error: {exc}")
        return None, CLARIFY_EXIT_CODE
    except RuntimeError as exc:
        print(f"!! Clarifying UI error: {exc}")
        return None, CLARIFY_EXIT_CODE
    if clarify_path:
        rel = str(clarify_path.relative_to(out))
        manifest.record_clarification(step_name, attempt, rel)
        print(f"✅ Clarification responses saved to {rel}")
        return rel, None
    return None, None
