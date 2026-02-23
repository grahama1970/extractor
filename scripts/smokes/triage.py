#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv, find_dotenv


SMOKE_SCRIPTS = {
    "03-text": Path("scripts/smokes/pipeline/smoke_stage03_header_text.py"),
    "07-text": Path("scripts/smokes/pipeline/smoke_stage07_text.py"),
    "07-vision": Path("scripts/smokes/pipeline/smoke_stage07_vision.py"),
    "09": Path("scripts/smokes/pipeline/smoke_stage09_summary.py"),
}


def _run(cmd: list[str], env: dict | None = None) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr


def _model_preference() -> str | None:
    # Prefer Gemini if key is present, else OpenAI, else None
    if os.getenv("GEMINI_API_KEY"):
        return os.getenv(
            "LITELLM_DEFAULT_MODEL", os.getenv("DEFAULT_LITELLM_MODEL", "gemini/gemini-2.5-flash")
        )
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv(
            "LITELLM_DEFAULT_MODEL", os.getenv("DEFAULT_LITELLM_MODEL", "openai/gpt-4o-mini")
        )
    return os.getenv("LITELLM_DEFAULT_MODEL", os.getenv("DEFAULT_LITELLM_MODEL"))


def triage(target: str) -> int:
    load_dotenv(find_dotenv())
    path = SMOKE_SCRIPTS.get(target)
    if not path or not path.exists():
        print(f"Unknown smoke target or missing script: {target}", file=sys.stderr)
        return 2

    # Base run
    rc, out, err = _run([sys.executable, str(path)])
    if rc == 0:
        print(out.strip() or f"OK: {target}")
        return 0

    print(f"Initial run failed for {target}. Attempting auto-fix…", file=sys.stderr)
    auto_fix = os.getenv("AUTO_FIX", "1").lower() in {"1", "true", "yes", "y"}
    auto_research = os.getenv("AUTO_RESEARCH", "0").lower() in {"1", "true", "yes", "y"}
    if not auto_fix:
        print(err or out, file=sys.stderr)
        return rc

    # Attempt 1: bump timeout and set explicit model if available
    model = _model_preference()
    args = [sys.executable, str(path)]
    # Each smoke script supports --timeout; some also accept --model
    if target in {"07-text", "07-vision", "03-text", "09"}:
        if model:
            args += ["--model", model]
        # bump timeout to a safer default
        args += ["--timeout", "60"]

    rc2, out2, err2 = _run(args)
    if rc2 == 0:
        print(out2.strip() or f"OK (after auto-fix): {target}")
        return 0

    if not auto_research:
        print(err2 or out2, file=sys.stderr)
        print(
            "Auto-fix attempt failed; leaving artifacts in logs/ for inspection.", file=sys.stderr
        )
        return rc2

    # Attempt 2 (research-guided): toggle compact prompt env or trim context, then re-run
    env = os.environ.copy()
    # These envs may alter shaping in step code if called; for smokes they are mostly inert, but safe
    env.setdefault("STAGE07_TRIM_CHARS", "3000")
    env.setdefault("STAGE07_COMPACT_PROMPT", "1")
    rc3, out3, err3 = _run(args, env=env)
    if rc3 == 0:
        print(out3.strip() or f"OK (after research fix): {target}")
        return 0

    print(err3 or out3, file=sys.stderr)
    print(
        "Research-guided attempt failed; please inspect logs/ and consider a prompt/rules/adapter tweak.",
        file=sys.stderr,
    )
    return rc3


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {Path(sys.argv[0]).name} <03-text|07-text|07-vision|09>")
        raise SystemExit(2)
    raise SystemExit(triage(sys.argv[1]))


if __name__ == "__main__":
    main()
