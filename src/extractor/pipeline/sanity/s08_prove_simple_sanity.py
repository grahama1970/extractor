"""Minimal sanity check for the simplified SciLLM Certainly/Lean4 path.

Runs a single certainly_prove_simple call using the paved path (no raw HTTP),
without repair loops. On failure, expects an optional LLM explanation.

Env (optional):
- CERTAINLY_BRIDGE_BASE / LEAN4_BRIDGE_BASE: bridge base URL (default http://127.0.0.1:8787)
- LEAN4_REQUIREMENT_TEXT: requirement text to prove (default "Nat.add_assoc")
- CERTAINLY_FLAGS: shlex-split flags list (default "--strategies direct,structured")
- LEAN4_MAX_SECONDS: max seconds for the proof (default 300)
- LEAN4_REQUEST_TIMEOUT: request timeout in seconds (default max_seconds + 60)
- LEAN4_REQUIRE_PROVED: "1" to fail if no proof is found
- LEAN4_REQUIRE_EXPLANATION: "1" to fail if explanation missing on failure
"""

from __future__ import annotations

import os
import shlex
import sys
from typing import Any, Dict, List

from dotenv import find_dotenv, load_dotenv
from scillm.extras.providers import certainly_prove_simple


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
    max_seconds = float(os.getenv("LEAN4_MAX_SECONDS", "300"))
    request_timeout_env = os.getenv("LEAN4_REQUEST_TIMEOUT")
    request_timeout = float(request_timeout_env) if request_timeout_env else max_seconds + 60.0
    require_proved = _env_bool("LEAN4_REQUIRE_PROVED", default=False)
    require_explanation = _env_bool("LEAN4_REQUIRE_EXPLANATION", default=False)

    items: List[Dict[str, Any]] = [{"requirement_text": requirement, "id": "sanity-1"}]

    print("=== SciLLM Certainly/Lean4 Simple Sanity ===")
    print(f"bridge_base: {api_base}")
    print(f"requirement: {requirement}")
    print(f"flags: {flags}")
    print(f"require_explanation: {require_explanation}")

    resp = certainly_prove_simple(
        items=items,
        api_base=api_base,
        flags=flags,
        max_seconds=max_seconds,
        request_timeout=request_timeout,
        session_id="sanity-simple",
        track_id="sanity-simple-1",
        require_proved=require_proved,
        explain_failures=True,
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
    status = first.get("status") or ""
    success = (
        bool(first.get("success") or first.get("proved") or first.get("ok")) or status == "proved"
    )
    lean_code = first.get("lean_code") or ""
    explanation = first.get("explanation") or ""
    stdout = first.get("stdout") or ""
    stderr = first.get("stderr") or ""

    print("✅ received certainly results")
    if summary:
        print(f"summary: {summary}")
    print(f"status: {status}")
    print(f"success: {success}")
    print(f"lean_code_bytes: {len(str(lean_code))}")
    if explanation:
        print(f"explanation: {str(explanation)[:300]}")
    if stderr:
        print(f"stderr: {str(stderr)[:300]}")
    if stdout:
        print(f"stdout: {str(stdout)[:300]}")

    if require_proved and not success:
        return 3
    if require_explanation and not success and not explanation:
        print("❌ explanation missing on failure")
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
