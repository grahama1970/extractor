from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .agent_runner import AgentFactory, RunHandle
from .contracts import Contract, load_contract, parse_contract_index
from .env_utils import ROOT
from .gate import run_gate
from .write_latest_status import write_latest_status


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_schema() -> Path:
    return ROOT / "tools" / "contract_loop" / "judges" / "agent_task.schema.json"


def _build_resume_prompt(failure_report: dict) -> str:
    report_json = json.dumps(failure_report, indent=2)
    return (
        "Contract failed. Fix ONLY what is required and rerun the checks. "
        "Use the failure_report.json below to decide the minimal changes. "
        "Return your final response as JSON per the output schema.\n\n"
        f"failure_report.json:\n{report_json}\n"
    )


def _write_status(run_root: Path, payload: dict) -> None:
    status_path = run_root / "status.json"
    status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _refresh_latest_status() -> None:
    log_root = ROOT / "logs" / "contract_loop"
    output_path = log_root / "latest_status.json"
    try:
        write_latest_status(log_root=log_root, output_path=output_path)
    except Exception as exc:  # pragma: no cover - best-effort status update
        print(f"⚠️  Failed to update latest status: {exc}")


def _run_contract(contract: Contract, *, contracts_root: Path, runner_name: str) -> int:
    runner = AgentFactory.create(runner_name)
    run_root = ROOT / "logs" / "contract_loop" / contract.task_id / _timestamp()
    run_root.mkdir(parents=True, exist_ok=True)

    schema_path = (
        Path(contract.agent.output_schema) if contract.agent.output_schema else _default_schema()
    )
    prompt = contract.prompt
    handle: RunHandle | None = None

    _write_status(
        run_root,
        {
            "task_id": contract.task_id,
            "title": contract.title,
            "status": "running",
            "iteration": 0,
            "contract_path": str(contracts_root),
            "runner": runner.name,
        },
    )

    for iteration in range(1, contract.max_iters + 1):
        output_path = run_root / "agent" / f"iter_{iteration:02d}_output.json"
        log_path = run_root / "agent" / f"iter_{iteration:02d}.jsonl"
        if handle is None:
            handle = runner.start(
                prompt,
                schema_path=schema_path,
                output_path=output_path,
                log_path=log_path,
                model=contract.agent.model,
                timeout_sec=contract.agent.timeout_sec,
            )
        else:
            handle = runner.resume(
                handle,
                prompt,
                schema_path=schema_path,
                output_path=output_path,
                log_path=log_path,
                model=contract.agent.model,
                timeout_sec=contract.agent.timeout_sec,
            )

        gate_result = run_gate(
            contract,
            runner=runner,
            run_root=run_root,
            iteration=iteration,
        )
        _write_status(
            run_root,
            {
                "task_id": contract.task_id,
                "title": contract.title,
                "status": "passed" if gate_result.ok else "failed",
                "iteration": iteration,
                "failure_report": str(gate_result.failure_report_path),
                "runner": runner.name,
            },
        )

        if gate_result.ok:
            print(f"✅ Contract satisfied for {contract.task_id} (iteration {iteration}).")
            _refresh_latest_status()
            return 0

        if iteration >= contract.max_iters:
            print(f"❌ Contract failed after {iteration} iterations: {contract.task_id}")
            _refresh_latest_status()
            return 2

        failure_report = json.loads(gate_result.failure_report_path.read_text(encoding="utf-8"))
        prompt = _build_resume_prompt(failure_report)

    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run contract loop task files.")
    parser.add_argument(
        "--contracts-root",
        type=Path,
        default=Path("contracts/contract_loop"),
        help="Directory containing CONTRACT.md and per-task JSON files.",
    )
    parser.add_argument(
        "--contract-index",
        type=Path,
        default=None,
        help="Override CONTRACT.md path.",
    )
    parser.add_argument(
        "--runner",
        type=str,
        default=None,
        help="Agent runner to use (codex, claude, opencode, generic). Defaults to CONTRACT_LOOP_RUNNER or codex.",
    )
    args = parser.parse_args()

    contracts_root = args.contracts_root
    contract_index = args.contract_index or (contracts_root / "CONTRACT.md")

    # Determine runner
    runner_name = args.runner or os.environ.get("CONTRACT_LOOP_RUNNER", "claude")

    contract_paths = parse_contract_index(contract_index)
    if not contract_paths:
        print(f"No contract files listed in {contract_index}")
        return 0

    for contract_path in contract_paths:
        contract = load_contract(contract_path)
        result = _run_contract(contract, contracts_root=contracts_root, runner_name=runner_name)
        _refresh_latest_status()
        if result != 0:
            return result

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
