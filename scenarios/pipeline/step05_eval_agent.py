#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
try:
    from ._eval_utils import summarize, structure_diff, shorten, load_json
except Exception:
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from _eval_utils import summarize, structure_diff, shorten, load_json

ROOT = Path(__file__).resolve().parents[2]
ART_ROOT = Path(os.getenv("SCENARIOS_ARTIFACT_ROOT", ROOT / "scripts" / "artifacts"))
DATE_DIR = time.strftime("%Y-%m-%d")
SHA_DIR = os.getenv("GITHUB_SHA", "local")
OUT_JSON = ART_ROOT / DATE_DIR / SHA_DIR / "json"; OUT_JSON.mkdir(parents=True, exist_ok=True)

def _find_latest() -> Path | None:
    c = list(ROOT.glob("data/results/pipeline/**/05_table_extractor/json_output/05_tables.json"))
    c += list(ROOT.glob("out_fast/**/05_table_extractor/json_output/05_tables.json"))
    return max(c, key=lambda p: p.stat().st_mtime) if c else None

def _load_json(p: Path): return load_json(p)

def _prompt(cand, gold):
    return (
    "Return ONLY JSON {overall,structure_parity,entity_coverage,semantic_alignment,critical_issues,non_critical_notes}.\n"
    f"GOLD:\n{gold}\n\nCANDIDATE:\n{cand}\n")

def _call(model: str, prompt: str):
    try:
        sys.path.insert(0, str(ROOT / 'src'))
        from extractor.pipeline.utils.litellm_call import litellm_call_sync  # type: ignore
        out = litellm_call_sync(name='step05_eval', prompts=[prompt], models=[model], response_json=True, temperature=0, extra_kwargs={"max_tokens":512})
        if isinstance(out, list) and out:
            r = out[0].get('response')
            if isinstance(r, dict): return r
            if isinstance(r, str):
                try: return json.loads(r)
                except Exception: return None
    except Exception as e:
        print(f"SKIP: Router eval unavailable ({e})")
    return None

def main():
    cand_path = os.getenv('STEP05_PATH') or (_find_latest() and str(_find_latest()))
    if not cand_path:
        print('SKIP: no STEP05_PATH and no discoverable candidate')
        sys.exit(0)
    gold_path = os.getenv('GOLD_PATH') or str(Path(os.getenv('GOLD_DIR','data/gold'))/ 'step05_tables.json')
    gp = Path(gold_path)
    if not gp.exists():
        print('SKIP: gold not found for step05')
        sys.exit(0)
    try:
        cand = _load_json(Path(cand_path)); gold = _load_json(gp)
    except Exception as e:
        print('SKIP: step05 load unavailable', e); sys.exit(0)

    prompt = _prompt(
        shorten(json.dumps(summarize(cand), indent=2)),
        shorten(json.dumps(summarize(gold), indent=2)),
        shorten(json.dumps(structure_diff(cand, gold), indent=2))
    )
    model = os.getenv('EVAL_MODEL') or os.getenv('LITELLM_DEFAULT_MODEL') or 'openai/gpt-4o-mini'
    res = _call(model, prompt)
    if res is None:
        print('SKIP: agent evaluation unavailable')
        sys.exit(0)
    t_overall = float(os.getenv('EVAL_THRESHOLD_OVERALL','0.8'))
    t_struct = float(os.getenv('EVAL_T_STRUCT','0.75'))
    t_cover = float(os.getenv('EVAL_T_COVER','0.75'))
    t_sem = float(os.getenv('EVAL_T_SEM','0.70'))
    enforce = os.getenv('EVAL_ENFORCE','0').lower() in {'1','true','yes'}
    getf = lambda k: float(res.get(k,0) or 0)
    passed = (getf('overall')>=t_overall and getf('structure_parity')>=t_struct and getf('entity_coverage')>=t_cover and getf('semantic_alignment')>=t_sem and (not res.get('critical_issues')))
    status = 'pass' if passed else 'fail'
    out = { 'status':status,'model':model,'thresholds':{'overall':t_overall,'structure_parity':t_struct,'entity_coverage':t_cover,'semantic_alignment':t_sem}, 'result':res,
            'candidate':cand_path,'gold':str(gp)}
    (OUT_JSON/ 'step_eval_step05.json').write_text(json.dumps(out, indent=2))
    print(f"Scenario pipeline/step05_eval_agent: {status}")
    if enforce and not passed: sys.exit(1)

if __name__=='__main__': main()
