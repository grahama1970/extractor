from __future__ import annotations

import subprocess
from typing import Iterable, List, Sequence, Set

import importlib.util
from .env_utils import ROOT, env_with_pythonpath
from .sanity_config_contract import (
    CONTRACT_SANITY_COMMANDS,
    SanityCommand,
)


class SanityCheckError(RuntimeError):
    """Raised when a required sanity script fails."""


def _format_cmd(cmd: Sequence[str]) -> str:
    return " ".join(cmd)


def _collect_step_commands(
    step_names: Set[str] | None, step_map: dict[str, list[SanityCommand]]
) -> List[SanityCommand]:
    commands: List[SanityCommand] = []
    include_all = not step_names
    for step, entries in step_map.items():
        if not include_all and step not in step_names:
            continue
        for entry in entries:
            commands.append(entry)
    return commands


def _load_project_sanity(
    adapter_name: str,
) -> tuple[List[SanityCommand], dict[str, list[SanityCommand]]]:
    config_path = ROOT / "tools" / "contract_loop" / "adapters" / adapter_name / "sanity_config.py"
    if not config_path.exists():
        raise SanityCheckError(
            f"Missing project sanity config at {config_path}. "
            "Add PROJECT_SANITY_COMMANDS and STEP_SANITY_COMMANDS."
        )
    spec = importlib.util.spec_from_file_location(
        f"contract_loop_sanity_{adapter_name}", str(config_path)
    )
    if not spec or not spec.loader:
        raise SanityCheckError(f"Unable to load sanity config: {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    project_commands = getattr(module, "PROJECT_SANITY_COMMANDS", None)
    step_commands = getattr(module, "STEP_SANITY_COMMANDS", None)
    if not isinstance(project_commands, list) or not isinstance(step_commands, dict):
        raise SanityCheckError(
            f"Invalid sanity config in {config_path}; expected PROJECT_SANITY_COMMANDS list "
            "and STEP_SANITY_COMMANDS dict."
        )
    return project_commands, step_commands


def run_preflight_sanity(step_names: Iterable[str] | None = None, *, adapter_name: str) -> None:
    """Run global + per-step sanity scripts before starting the contract loop."""

    normalized_steps = set(step_names or [])
    env = env_with_pythonpath()
    commands: List[SanityCommand] = list(CONTRACT_SANITY_COMMANDS)

    project_commands, step_map = _load_project_sanity(adapter_name)
    commands.extend(project_commands)
    commands.extend(_collect_step_commands(normalized_steps, step_map))
    if not commands:
        return

    import shlex

    for command in commands:
        print(f"[sanity] {command.name}: {_format_cmd(command.cmd)}")

        # Wrap command to run inside the virtual environment
        cmd_str = shlex.join(command.cmd)
        wrapped_cmd = f"source .venv/bin/activate && {cmd_str}"

        result = subprocess.run(
            ["bash", "-c", wrapped_cmd],
            cwd=ROOT,
            env=env,
        )
        if result.returncode != 0:
            raise SanityCheckError(
                f"Sanity command '{command.name}' failed with exit code {result.returncode}."
            )
