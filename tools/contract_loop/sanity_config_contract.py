from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SanityCommand:
    name: str
    cmd: List[str]
    step: str | None = None
    optional: bool = False


CONTRACT_SANITY_COMMANDS: List[SanityCommand] = [
    SanityCommand(
        name="contract_exec_harness",
        cmd=["uv", "run", "tools/contract_loop/scripts/sanity_contract_exec.py"],
    ),
    SanityCommand(
        name="contract_codex_auth",
        cmd=["uv", "run", "tools/contract_loop/scripts/sanity_contract_auth.py"],
    ),
    SanityCommand(
        name="contract_bundle_builder",
        cmd=["uv", "run", "tools/contract_loop/scripts/sanity_contract_bundle.py"],
    ),
    SanityCommand(
        name="contract_clarify_server",
        cmd=["uv", "run", "tools/contract_loop/scripts/sanity_contract_clarify.py"],
    ),
]


__all__ = ["SanityCommand", "CONTRACT_SANITY_COMMANDS"]
