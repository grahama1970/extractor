from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class CommandCheck:
    name: str
    cmd: list[str] | str
    cwd: str | None = None
    timeout_sec: int | None = None


@dataclass(frozen=True)
class FileContainsCheck:
    path: str
    contains: list[str]
    regex: list[str] | None = None


@dataclass(frozen=True)
class DeterministicChecks:
    commands: list[CommandCheck]
    files_exist: list[str]
    files_contain: list[FileContainsCheck]


@dataclass(frozen=True)
class AgentConfig:
    model: str | None = None
    output_schema: str | None = None
    timeout_sec: int | None = None


@dataclass(frozen=True)
class LLMGateConfig:
    prompt: str | None = None
    schema: str | None = None
    model: str | None = None
    timeout_sec: int | None = None


@dataclass(frozen=True)
class Contract:
    task_id: str
    title: str
    prompt: str
    max_iters: int
    deterministic: DeterministicChecks
    agent: AgentConfig
    llm_gate: LLMGateConfig


CONTRACT_PATTERN = re.compile(r"Contract file:\s*`?([^`]+)`?", re.IGNORECASE)


def parse_contract_index(contract_md: Path) -> list[Path]:
    if not contract_md.exists():
        raise FileNotFoundError(f"Contract index not found: {contract_md}")
    lines = contract_md.read_text(encoding="utf-8").splitlines()
    contract_paths: list[Path] = []
    for line in lines:
        match = CONTRACT_PATTERN.search(line)
        if not match:
            continue
        raw_path = match.group(1).strip()
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = contract_md.parent / path
        contract_paths.append(path.resolve())
    return contract_paths


def _require_key(data: Dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"Contract missing required key '{key}'")
    return data[key]


def _load_commands(obj: dict[str, Any]) -> list[CommandCheck]:
    commands = obj.get("commands") or []
    results: list[CommandCheck] = []
    for entry in commands:
        if not isinstance(entry, dict):
            raise ValueError("Command entries must be objects")
        name = entry.get("name") or entry.get("cmd")
        cmd = entry.get("cmd")
        if not cmd:
            raise ValueError("Command entry missing cmd")
        results.append(
            CommandCheck(
                name=str(name),
                cmd=cmd,
                cwd=entry.get("cwd"),
                timeout_sec=entry.get("timeout_sec"),
            )
        )
    return results


def _load_files_contain(obj: dict[str, Any]) -> list[FileContainsCheck]:
    entries = obj.get("files_contain") or []
    results: list[FileContainsCheck] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("files_contain entries must be objects")
        path = entry.get("path")
        contains = entry.get("contains") or []
        if not path or not isinstance(contains, list) or not contains:
            raise ValueError("files_contain entries require path + contains list")
        results.append(
            FileContainsCheck(
                path=str(path),
                contains=[str(c) for c in contains],
                regex=[str(r) for r in entry.get("regex") or []] or None,
            )
        )
    return results


def load_contract(contract_path: Path) -> Contract:
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract file not found: {contract_path}")
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    task_id = str(_require_key(data, "task_id"))
    title = str(_require_key(data, "title"))
    prompt = str(_require_key(data, "prompt"))
    max_iters = int(data.get("max_iters", 3))

    det_block = data.get("deterministic_checks") or {}
    deterministic = DeterministicChecks(
        commands=_load_commands(det_block),
        files_exist=[str(p) for p in det_block.get("files_exist") or []],
        files_contain=_load_files_contain(det_block),
    )

    agent_block = data.get("agent") or {}
    agent = AgentConfig(
        model=agent_block.get("model"),
        output_schema=agent_block.get("output_schema"),
        timeout_sec=agent_block.get("timeout_sec"),
    )

    llm_block = data.get("llm_gate") or {}
    llm_gate = LLMGateConfig(
        prompt=llm_block.get("prompt"),
        schema=llm_block.get("schema"),
        model=llm_block.get("model"),
        timeout_sec=llm_block.get("timeout_sec"),
    )

    return Contract(
        task_id=task_id,
        title=title,
        prompt=prompt,
        max_iters=max_iters,
        deterministic=deterministic,
        agent=agent,
        llm_gate=llm_gate,
    )


__all__ = [
    "AgentConfig",
    "CommandCheck",
    "Contract",
    "DeterministicChecks",
    "FileContainsCheck",
    "LLMGateConfig",
    "load_contract",
    "parse_contract_index",
]
