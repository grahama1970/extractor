from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agent_runner import AgentRunner
from .contracts import CommandCheck, Contract, FileContainsCheck
from .env_utils import ROOT


@dataclass
class GateResult:
    ok: bool
    failure_report_path: Path
    evidence_paths: list[str]


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_") or "cmd"


def _run_command(
    cmd: CommandCheck,
    *,
    cwd: Path,
    log_path: Path,
) -> dict[str, Any]:
    if isinstance(cmd.cmd, str):
        exec_cmd = ["bash", "-lc", cmd.cmd]
    else:
        exec_cmd = [str(c) for c in cmd.cmd]
    result = subprocess.run(
        exec_cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=cmd.timeout_sec,
    )
    log_path.write_text(
        (result.stdout or "") + (result.stderr or ""), encoding="utf-8"
    )
    return {
        "name": cmd.name,
        "cmd": cmd.cmd,
        "cwd": str(cwd),
        "exit_code": result.returncode,
        "log_path": str(log_path),
    }


def _check_contains(check: FileContainsCheck, *, root: Path) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    path = root / check.path
    if not path.exists():
        failures.append(
            {"kind": "file_missing", "path": str(path), "missing": check.contains}
        )
        return failures
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [needle for needle in check.contains if needle not in text]
    if missing:
        failures.append(
            {"kind": "file_contains", "path": str(path), "missing": missing}
        )
    if check.regex:
        for pattern in check.regex:
            if not re.search(pattern, text, flags=re.MULTILINE):
                failures.append(
                    {"kind": "file_regex", "path": str(path), "missing": [pattern]}
                )
    return failures


def run_deterministic_checks(contract: Contract, run_root: Path) -> tuple[bool, list[dict[str, Any]], list[str]]:
    failures: list[dict[str, Any]] = []
    evidence_paths: list[str] = []
    gate_dir = run_root / "gate"
    gate_dir.mkdir(parents=True, exist_ok=True)

    for cmd in contract.deterministic.commands:
        name = _safe_name(cmd.name)
        log_path = gate_dir / f"command_{name}.log"
        result = _run_command(cmd, cwd=ROOT if not cmd.cwd else (ROOT / cmd.cwd), log_path=log_path)
        evidence_paths.append(str(log_path))
        if result["exit_code"] != 0:
            failures.append(
                {
                    "kind": "command",
                    "name": cmd.name,
                    "exit_code": result["exit_code"],
                    "log_path": result["log_path"],
                }
            )

    for path in contract.deterministic.files_exist:
        target = ROOT / path
        if not target.exists():
            failures.append({"kind": "file_missing", "path": str(target)})
        else:
            evidence_paths.append(str(target))

    for check in contract.deterministic.files_contain:
        failures.extend(_check_contains(check, root=ROOT))
        evidence_paths.append(str(ROOT / check.path))

    ok = len(failures) == 0
    return ok, failures, evidence_paths


def _default_llm_prompt() -> str:
    return (
        "You are a contract auditor. Use the failure_report JSON below to decide "
        "if the contract is fully satisfied. If deterministic checks failed, ok "
        "must be false. If all deterministic checks passed but work is still missing, "
        "ok must be false. Return JSON only with keys ok, notes, next_actions."
    )


def run_llm_gate(
    contract: Contract,
    *,
    runner: AgentRunner,
    failure_report: dict[str, Any],
    run_root: Path,
    iteration: int,
) -> tuple[bool, dict[str, Any], Path]:
    gate_dir = run_root / "gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    log_path = gate_dir / f"llm_gate_iter_{iteration:02d}.jsonl"
    output_path = gate_dir / f"llm_gate_iter_{iteration:02d}.json"
    schema_path = (
        Path(contract.llm_gate.schema)
        if contract.llm_gate.schema
        else ROOT / "tools" / "contract_loop" / "judges" / "contract_gate.schema.json"
    )

    prompt = contract.llm_gate.prompt or _default_llm_prompt()
    payload = json.dumps(failure_report, indent=2)
    full_prompt = f"{prompt}\n\nfailure_report.json:\n{payload}\n"
    handle = runner.start(
        full_prompt,
        schema_path=schema_path,
        output_path=output_path,
        log_path=log_path,
        model=contract.llm_gate.model,
        timeout_sec=contract.llm_gate.timeout_sec,
    )

    try:
        raw_text = output_path.read_text(encoding="utf-8")
        # Try parsing directly first
        try:
            llm_result = json.loads(raw_text)
        except json.JSONDecodeError:
            # Fallback: strip markdown code fences if present
            text = raw_text.strip()
            fence_start = text.find("```")
            if fence_start >= 0:
                text = text[fence_start:]
                nl = text.find("\n")
                if nl != -1:
                    text = text[nl+1:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            llm_result = json.loads(text)
    except Exception as exc:
        llm_result = {"ok": False, "notes": f"Failed to parse LLM gate output: {exc}"}

    ok = bool(llm_result.get("ok"))
    return ok, llm_result, output_path


def run_gate(
    contract: Contract,
    *,
    runner: AgentRunner,
    run_root: Path,
    iteration: int,
) -> GateResult:
    det_ok, det_failures, evidence_paths = run_deterministic_checks(contract, run_root)
    report = {
        "contract_passed": False,
        "iteration": iteration,
        "task_id": contract.task_id,
        "title": contract.title,
        "deterministic": {
            "ok": det_ok,
            "failures": det_failures,
            "evidence_paths": evidence_paths,
        },
    }

    llm_ok, llm_result, llm_output_path = run_llm_gate(
        contract,
        runner=runner,
        failure_report=report,
        run_root=run_root,
        iteration=iteration,
    )
    report["llm_gate"] = {
        "ok": llm_ok,
        "result": llm_result,
        "output_path": str(llm_output_path),
    }

    report["contract_passed"] = bool(det_ok and llm_ok)
    failure_report_path = run_root / "gate" / f"failure_report_iter_{iteration:02d}.json"
    failure_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return GateResult(
        ok=bool(report["contract_passed"]),
        failure_report_path=failure_report_path,
        evidence_paths=evidence_paths,
    )


__all__ = ["GateResult", "run_gate"]
