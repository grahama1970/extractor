"""Minimal sanity check for the SciLLM Certainly/Lean4 bridge.

Runs a single certainly_prove call using the paved path (no raw HTTP) and
optionally asserts that Lean code is present (to catch stub/echo mode).

Env (optional):
- CERTAINLY_BRIDGE_BASE / LEAN4_BRIDGE_BASE: bridge base URL (default http://127.0.0.1:8787)
- LEAN4_REQUIREMENT_TEXT: requirement text to prove (default "Nat.add_assoc")
- CERTAINLY_FLAGS: shlex-split flags list (default "--strategies direct,structured")
- LEAN4_MAX_SECONDS: max seconds for the proof (default 120)
- LEAN4_REQUIRE_PROVED: "1" to fail if no proof is found
- LEAN4_REQUIRE_CODE: "1" to fail if lean_code is missing (detects stub/echo mode)
"""

from __future__ import annotations

import os
import shlex
import sys
from typing import Any, Dict, List

from dotenv import find_dotenv, load_dotenv
from scillm.extras.providers import certainly_prove


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _extract_results(resp: Any) -> List[Dict[str, Any]]:
    payload = getattr(resp, "additional_kwargs", {}) or {}
    certainly = payload.get("certainly", {}) if isinstance(payload, dict) else {}
    results = certainly.get("results") if isinstance(certainly, dict) else None
    if isinstance(results, list):
        return results
    return []


def main() -> int:
    if not load_dotenv(find_dotenv()):
        print("Warning: .env not found; continuing with process environment.", file=sys.stderr)

    api_base = (
        os.getenv("CERTAINLY_BRIDGE_BASE")
        or os.getenv("LEAN4_BRIDGE_BASE")
        or "http://127.0.0.1:8787"
    )
    requirement = os.getenv("LEAN4_REQUIREMENT_TEXT", "Nat.add_assoc")
    flags_env = os.getenv("CERTAINLY_FLAGS", "--strategies direct,structured")
    flags = shlex.split(flags_env) if flags_env else None
    max_seconds = float(os.getenv("LEAN4_MAX_SECONDS", "120"))
    require_proved = _env_bool("LEAN4_REQUIRE_PROVED", default=False)
    require_code = _env_bool("LEAN4_REQUIRE_CODE", default=False)

    items: List[Dict[str, Any]] = [
        {"requirement_text": requirement, "id": "sanity-1"}
    ]

    print("=== SciLLM Certainly/Lean4 Sanity ===")
    print(f"bridge_base: {api_base}")
    print(f"requirement: {requirement}")
    print(f"flags: {flags}")
    print(f"require_code: {require_code}")

    resp = certainly_prove(
        items=items,
        api_base=api_base,
        flags=flags,
        max_seconds=max_seconds,
        session_id="sanity",
        track_id="sanity-1",
        require_proved=require_proved,
    )

    summary = ""
    try:
        summary = resp.choices[0].message.get("content")  # type: ignore[attr-defined]
    except Exception:
        summary = ""

    results = _extract_results(resp)

    if not results:
        print("❌ no certainly results returned")
        if summary:
            print(f"summary: {summary}")
        return 2

    first = results[0] if isinstance(results, list) and results else {}
    success = bool(first.get("success") or first.get("proved") or first.get("ok"))
    lean_code = first.get("lean_code") or first.get("code") or ""
    stdout = first.get("stdout") or first.get("proof") or first.get("error") or ""

    print("✅ received certainly results")
    if summary:
        print(f"summary: {summary}")
    print(f"success: {success}")
    print(f"lean_code_bytes: {len(str(lean_code))}")
    if stdout:
        print(f"stdout: {str(stdout)[:300]}")

    if require_code and not lean_code:
        print("❌ lean_code missing (likely stub/echo mode or CLI not running)")
        return 4
    if require_proved and not success:
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
