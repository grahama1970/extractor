"""Gate Template: deterministic contract enforcement.

A gate should:
- be deterministic
- print helpful failure info (expected vs got)
- exit 0 on pass
- exit 1 on fail
- exit 42 for clarify-stop with CLARIFY lines printed
"""

from __future__ import annotations

import json
from pathlib import Path

CLARIFY_EXIT = 42


def main() -> int:
    # TODO: load sample input (or read output artifacts produced by the task)
    # Example:
    # inp = json.loads(Path("tools/sample_input.json").read_text(encoding="utf-8"))

    # TODO: compute or load actual output
    # got = ...

    # Optional clarify trigger:
    # if <deterministic_condition>:
    #     print("CLARIFY: ...")
    #     raise SystemExit(CLARIFY_EXIT)

    # TODO: compare with expected output / enforce invariants via asserts
    # exp = json.loads(Path("tools/expected_output.json").read_text(encoding="utf-8"))
    # assert got == exp, f"\nGOT:\n{got}\n\nEXPECTED:\n{exp}\n"

    print("OK: gate_<task_name>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
