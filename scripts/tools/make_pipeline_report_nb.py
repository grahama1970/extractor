#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "nbformat>=5.9.0",
# ]
# ///
from __future__ import annotations
import nbformat as nbf
from pathlib import Path


def md(text: str):
    """Create a new markdown cell from text."""
    return nbf.v4.new_markdown_cell(text)


def code(src: str):
    """Create a new Jupyter Notebook code cell from source."""
    return nbf.v4.new_code_cell(src)


def main() -> int:
    """Create a Jupyter notebook with a verification report structure."""
    nb = nbf.v4.new_notebook()
    nb.cells = [
        md(
            """# Extractor Pipeline — Verification Report (Read‑Only)\n\nThis notebook reads existing artifacts (Stages 04–09) and prints concise metrics and PASS/FAIL checks.\nNo pipeline logic is executed; it only reads JSON files and the environment."""
        ),
        code(
            "from pathlib import Path\nimport json, os, re\n\nRUN_ROOT = Path('data/results/pipeline')\nART = {\n  'sections': RUN_ROOT / '04_section_builder/json_output/04_sections.json',\n  'tables': RUN_ROOT / '05_table_extractor/json_output/05_tables.json',\n  'figures': RUN_ROOT / '06_figure_extractor/json_output/06_figures.json',\n  'enriched_tables': RUN_ROOT / '06a_title_caption_enricher/json_output/05_tables.enriched.json',\n  'enriched_figures': RUN_ROOT / '06a_title_caption_enricher/json_output/06_figures.enriched.json',\n  'reflowed': RUN_ROOT / '07_reflow_section/json_output/07_reflowed.json',\n  'reqs': RUN_ROOT / '07_requirements_miner/json_output/07_requirements.json',\n  'theorems': RUN_ROOT / '08_lean4_theorem_prover/json_output/08_theorems.json',\n}\n\ndef _read_json(p: Path):\n    try:\n        return json.loads(p.read_text()) if p.exists() else None\n    except Exception as e:\n        print('read-failed', p, e); return None\n"
        ),
        md("## Quick Slices"),
        code(
            "sec = _read_json(ART['sections']); rf = _read_json(ART['reflowed']); rq = _read_json(ART['reqs']); th = _read_json(ART['theorems'])\nprint('sections:', bool(sec))\nprint('reflow:', rf.get('status') if isinstance(rf, dict) else rf)\nprint('requirements:', len((rq or {}).get('requirements', [])) if isinstance(rq, dict) else 0)\nprint('proofs.stats:', (th or {}).get('statistics'))\n"
        ),
        md("## Verification Checklist"),
        code(
            "from pathlib import Path as _P\nsummary={'stages':{},'env':{},'warnings':[]}\n# env\nbase=os.environ.get('CHUTES_API_BASE',''); key=os.environ.get('CHUTES_API_KEY','')\nsummary['env']={'CHUTES_API_BASE_ok': base.endswith('/v1'), 'CHUTES_API_KEY_present': len(key)>10}\nprint('CHUTES_API_BASE_ok=', summary['env']['CHUTES_API_BASE_ok'])\nprint('CHUTES_API_KEY_present=', summary['env']['CHUTES_API_KEY_present'])\n# 06a\net=_read_json(ART['enriched_tables']); ef=_read_json(ART['enriched_figures'])\nsummary['stages']['06a_enriched']=bool(isinstance(et,list) and et and isinstance(ef,list) and ef)\nprint('06a_enriched=', summary['stages']['06a_enriched'])\n# 07\nrf=_read_json(ART['reflowed']) or {}\nsummary['stages']['07_completed']= rf.get('status')=='Completed' and (rf.get('section_count') or 0)>0\nsrc_files=rf.get('source_files') or {}\nsummary['stages']['07_consumed_enriched']=str(src_files.get('tables','')).endswith('05_tables.enriched.json')\nprint('07_completed=', summary['stages']['07_completed'])\nprint('07_consumed_enriched=', summary['stages']['07_consumed_enriched'])\n# 07.5\nrq=_read_json(ART['reqs']) or {}; reqs=rq.get('requirements', rq if isinstance(rq,list) else [])\nweak=[r for r in reqs if str(r.get('modality','')).lower() in {'should','may','might','could','can'}]\nsummary['stages']['07_requirements']={'count':len(reqs),'strict_modal': len(weak)==0}\nprint('07_requirements.count=', len(reqs)); print('07_requirements.strict=', len(weak)==0)\n# 08\nth=_read_json(ART['theorems']) or {}; st=th.get('statistics') or {}\nsummary['stages']['08_proofs']={'present': bool(st), 'successful_proofs': st.get('successful_proofs'), 'total': st.get('total_requirements_found')}\nprint('08_proofs=', summary['stages']['08_proofs'])\n# save\n_P('scripts/artifacts').mkdir(parents=True, exist_ok=True)\n(_P('scripts/artifacts')/'pipeline_verification.json').write_text(json.dumps(summary, indent=2))\nsummary\n"
        ),
    ]

    out = Path("scripts/notebooks/pipeline_report_exec.ipynb")
    out.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
