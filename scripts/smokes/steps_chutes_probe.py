#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
# ]
# ///

"""
Probe pipeline steps for SciLLM/Chutes readiness.

Outputs JSON and Markdown summaries under scripts/artifacts/.
Does not require live network credentials; if SCILLM/OPENAI keys are
missing, marks sanity checks as skipped.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional
import urllib.request

from dotenv import load_dotenv, find_dotenv

ROOT = Path(__file__).resolve().parents[2]
STEPS_DIR = ROOT / "src" / "extractor" / "pipeline" / "steps"
ART_DIR = ROOT / "scripts" / "artifacts"
ART_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class StepRecord:
    """Store metadata for a processing step including status and dependencies."""
    name: str
    path: str
    import_ok: bool
    uses_litellm: bool
    uses_scillm: bool
    env_ok: bool
    sanity_ok: Optional[bool]
    note: str = ""


def _env_ok() -> bool:
    # Best-effort .env load so local runs work without exporting
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
    except Exception:
        pass
    base = (
        os.getenv("SCILLM_API_BASE", "http://localhost:4010") or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
    )
    key = os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123") or os.getenv("OPENAI_API_KEY")
    return bool(base and key)


def _scan_text(p: Path) -> tuple[bool, bool]:
    """Check file text for litellm and scillm library usage."""
    txt = p.read_text(encoding="utf-8", errors="ignore")
    uses_litellm = "litellm_call" in txt or "normalize_model_alias" in txt
    uses_scillm = "scillm_client" in txt
    return uses_litellm, uses_scillm


def _sanity_call() -> bool:
    # OpenAI-compatible HTTP path (no litellm dependency)
    try:
        base = (
            os.getenv("SCILLM_API_BASE", "http://localhost:4010")
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
        )
        key = os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123") or os.getenv("OPENAI_API_KEY")
        if not base or not key:
            return False
        model = (
            os.getenv("CHUTES_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL") or "openai/gpt-4o-mini"
        )
        req = urllib.request.Request(
            f"{base.rstrip('/')}/chat/completions",
            data=json.dumps(
                {
                    "model": model,
                    "messages": [{"role": "user", "content": 'Return only {"ok": true} as JSON.'}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                }
            ).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = (((data or {}).get("choices") or [{}])[0].get("message") or {}).get(
            "content"
        ) or ""
        obj = json.loads((content or "").strip())
        return bool(isinstance(obj, dict) and obj.get("ok") is True)
    except Exception:
        return False


def main(
    output_json: Path = ART_DIR / "steps_chutes_report.json",
    output_md: Path = ART_DIR / "steps_chutes_report.md",
) -> int:
    """Generate steps report in JSON and Markdown formats."""
    steps: List[StepRecord] = []
    env_ok = _env_ok()

    for p in sorted(STEPS_DIR.glob("*.py")):
        if p.name == "__init__.py":
            continue
        uses_litellm, uses_scillm = _scan_text(p)
        import_ok = True
        note = ""
        try:
            # import module to ensure import-time guards work
            mod_name = f"extractor.pipeline.steps.{p.stem}"
            __import__(mod_name)
        except Exception as e:
            import_ok = False
            note = f"import failed: {type(e).__name__}: {e}"
        sanity_ok: Optional[bool] = None
        if env_ok and uses_litellm:
            sanity_ok = _sanity_call()
        rec = StepRecord(
            name=p.stem,
            path=str(p.relative_to(ROOT)),
            import_ok=import_ok,
            uses_litellm=uses_litellm,
            uses_scillm=uses_scillm,
            env_ok=env_ok,
            sanity_ok=sanity_ok,
            note=note,
        )
        steps.append(rec)

    # Save JSON
    payload: Dict[str, object] = {
        "env_ok": env_ok,
        "steps": [asdict(s) for s in steps],
    }
    output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Save Markdown summary
    lines = []
    lines.append("# SciLLM/Chutes Readiness — Pipeline Steps")
    lines.append("")
    lines.append(f"Env OK: {'✅' if env_ok else '❌'} (needs SCILLM/OPENAI base+key)")
    lines.append("")
    lines.append("| step | import | litellm | scillm | sanity | note |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for s in steps:
        lines.append(
            f"| {s.name} | {'✅' if s.import_ok else '❌'} | {'✅' if s.uses_litellm else '—'} | "
            f"{'✅' if s.uses_scillm else '—'} | "
            f"{('✅' if s.sanity_ok else ('❌' if s.sanity_ok is False else '—'))} | {s.note} |"
        )
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(output_md))
    print(str(output_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
