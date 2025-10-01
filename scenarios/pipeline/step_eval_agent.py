#!/usr/bin/env python3
"""Scenario: Agent evaluation of pipeline step output vs. gold standard.

Assesses "reasonable closeness" using an LLM (via the project's LiteLLM Router
helper). Non-deterministic by design; SKIP when model creds or files are
missing. Writes a compact JSON result and prints a one-line status.

Env
- STEP10_PATH            Path to candidate (e.g., Step 10 flattened JSON). If missing, tries to auto-discover latest.
- GOLD_PATH              Path to gold JSON. If missing, tries GOLD_DIR fallback.
- GOLD_DIR               Directory containing gold files (default data/gold), fallback name step10_flattened.json.
- EVAL_MODEL             Router model (default openai/gpt-4o-mini or LITELLM default).
- EVAL_ENFORCE           '1' to fail when below thresholds (default '0' for PRs).
- EVAL_THRESHOLD_OVERALL Overall minimum (default 0.8). Others: EVAL_T_STRUCT=0.75, EVAL_T_COVER=0.75, EVAL_T_SEM=0.70.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from ._eval_utils import summarize, structure_diff, shorten

ROOT = Path(__file__).resolve().parents[2]
ART_ROOT = Path(os.getenv("SCENARIOS_ARTIFACT_ROOT", ROOT / "scripts" / "artifacts"))
DATE_DIR = time.strftime("%Y-%m-%d")
SHA_DIR = os.getenv("GITHUB_SHA", "local")
OUT_JSON = ART_ROOT / DATE_DIR / SHA_DIR / "json"
OUT_LOGS = ART_ROOT / DATE_DIR / SHA_DIR / "logs"
OUT_JSON.mkdir(parents=True, exist_ok=True)
OUT_LOGS.mkdir(parents=True, exist_ok=True)


def _find_latest_step10() -> Path | None:
    cands = list(ROOT.glob("data/results/pipeline/**/10_arangodb_exporter/json_output/10_flattened_data.json"))
    cands += list(ROOT.glob("out_fast/**/10_arangodb_exporter/json_output/10_flattened_data.json"))
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _prompt(candidate_snip: str, gold_snip: str, diff_snip: str) -> str:
    return (
        "You are a rigorous evaluator. Compare the CANDIDATE JSON to the GOLD JSON and return ONLY a compact JSON object "
        "that follows this schema (no extra text):\n"
        "{\n  \"overall\": number (0..1),\n  \"structure_parity\": number (0..1),\n  \"entity_coverage\": number (0..1),\n  \"semantic_alignment\": number (0..1),\n  \"critical_issues\": string[],\n  \"non_critical_notes\": string[]\n}\n"
        "Instructions:\n"
        "- structure_parity: similarity of keys/shape (not exact order).\n"
        "- entity_coverage: presence of key items (sections/nodes/tables) implied by GOLD.\n"
        "- semantic_alignment: whether the meaning/content broadly matches.\n"
        "- critical_issues: blockers that make outputs unusable.\n"
        "- non_critical_notes: acceptable differences or minor drifts.\n"
        "- Return a valid JSON object ONLY.\n\n"
        f"GOLD (snippet):\n{gold_snip}\n\nCANDIDATE (snippet):\n{candidate_snip}\n\nDIFF (structural hints):\n{diff_snip}\n"
    )


def _call_router(model: str, content: str) -> dict | None:
    try:
        # Use project helper to route via LiteLLM Router
        sys.path.insert(0, str(ROOT / "src"))
        from extractor.pipeline.utils.litellm_call import litellm_call_sync  # type: ignore

        out = litellm_call_sync(
            name="step_eval_agent",
            prompts=[content],
            models=[model],
            response_json=True,
            temperature=0,
            extra_kwargs={"max_tokens": 512},
        )
        # litellm_call_sync returns list of dicts (per prompt)
        if isinstance(out, list) and out:
            payload = out[0].get("response")
            if isinstance(payload, dict):
                return payload
            # Some providers return text; try to parse
            if isinstance(payload, str):
                try:
                    return json.loads(payload)
                except Exception:
                    return None
        return None
    except Exception as e:
        print(f"SKIP: Router eval not available ({e})")
        return None


def main() -> None:
    # Locate candidate and gold
    cand_path = os.getenv("STEP10_PATH")
    if not cand_path:
        p = _find_latest_step10()
        if not p:
            print("SKIP: no candidate STEP10_PATH and no discoverable Step 10 output")
            sys.exit(0)
        cand_path = str(p)
    gold_path = os.getenv("GOLD_PATH")
    if not gold_path:
        gold_dir = Path(os.getenv("GOLD_DIR", "data/gold"))
        g = gold_dir / "step10_flattened.json"
        if not g.exists():
            print("SKIP: no GOLD_PATH and default gold not found")
            sys.exit(0)
        gold_path = str(g)

    try:
        cand_json = _load_json(Path(cand_path))
        gold_json = _load_json(Path(gold_path))
    except Exception as e:
        print(f"Scenario pipeline/step_eval_agent: FAIL (load) err={e}")
        sys.exit(1)

    # Build compact snippets
    cand_snip = shorten(json.dumps(summarize(cand_json), indent=2))
    gold_snip = shorten(json.dumps(summarize(gold_json), indent=2))
    diff_snip = shorten(json.dumps(structure_diff(cand_json, gold_json), indent=2))
    prompt = _prompt(cand_snip, gold_snip, diff_snip)

    model = os.getenv("EVAL_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL") or "openai/gpt-4o-mini"
    result = _call_router(model, prompt)
    if result is None:
        print("SKIP: agent evaluation unavailable (no model/Router) or parsing failed")
        sys.exit(0)

    # Thresholds
    t_overall = float(os.getenv("EVAL_THRESHOLD_OVERALL", "0.8"))
    t_struct = float(os.getenv("EVAL_T_STRUCT", "0.75"))
    t_cover = float(os.getenv("EVAL_T_COVER", "0.75"))
    t_sem = float(os.getenv("EVAL_T_SEM", "0.70"))
    enforce = (os.getenv("EVAL_ENFORCE", "0").lower() in {"1", "true", "yes"})

    def _get(k: str) -> float:
        try:
            return float(result.get(k, 0))
        except Exception:
            return 0.0

    overall = _get("overall")
    s = _get("structure_parity")
    c = _get("entity_coverage")
    sem = _get("semantic_alignment")
    crit = result.get("critical_issues", []) or []

    passed = (
        overall >= t_overall and s >= t_struct and c >= t_cover and sem >= t_sem and len(crit) == 0
    )
    status = "pass" if passed else "fail"

    summary = {
        "status": status,
        "model": model,
        "thresholds": {
            "overall": t_overall,
            "structure_parity": t_struct,
            "entity_coverage": t_cover,
            "semantic_alignment": t_sem,
        },
        "result": result,
        "candidate": str(cand_path),
        "gold": str(gold_path),
    }
    out_path = OUT_JSON / "step_eval_step10.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"Scenario pipeline/step_eval_agent (step10): {status} -> {out_path}")
    if enforce and not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
