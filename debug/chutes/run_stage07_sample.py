#!/usr/bin/env python3
from __future__ import annotations

import os, json
from pathlib import Path
from ._preflight import ensure_env
from extractor.pipeline.steps._07b_paragraph_polish import run as run07b
from extractor.pipeline.steps._07c_table_title_infer import run as run07c
from extractor.pipeline.steps._07d_figure_caption_refine import run as run07d
from importlib.util import spec_from_file_location, module_from_spec


def load_07e():
    p = Path('src/extractor/pipeline/steps/07e_assemble_reflow.py')
    spec = spec_from_file_location('s07e', str(p))
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def main():
    ensure_env()
    base = Path('data/results/pipeline')
    canon = base/'07a_section_canonicalizer/json_output/07a_canonical.json'
    out_dir = Path('debug/artifacts'); out_dir.mkdir(parents=True, exist_ok=True)
    # Cap items and enable logging
    os.environ.setdefault('STAGE07_MAX_ITEMS','5')
    os.environ.setdefault('STAGE07_GLOBAL_CONCURRENCY','2')
    os.environ.setdefault('STAGE07_REQUEST_TIMEOUT','120')
    os.environ.setdefault('STAGE07_NUM_RETRIES','2')
    os.environ.setdefault('LITELLM_FILE_LOG','1')
    os.environ.setdefault('LOG_DIR','data/results/pipeline/logs')

    run07b(canonical_json=canon, output_dir=base, verified03_json=None)
    run07c(canonical_json=canon, output_dir=base, verified03_json=None)
    run07d(canonical_json=canon, output_dir=base, verified03_json=None)
    mod07e = load_07e()
    mod07e.run(
        canonical_json=base/'07a_section_canonicalizer/json_output/07a_canonical.json',
        polish_json=base/'07b_paragraph_polish/07b_paragraph_polish.json',
        table_titles_json=base/'07c_table_title_infer/07c_table_title_infer.json',
        figure_caps_json=base/'07d_figure_caption_refine/07d_figure_caption_refine.json',
        output_dir=base
    )
    (out_dir/'stage07_live_sample.json').write_text(json.dumps({'ok':True,'paths':{
        'polish': str(base/'07b_paragraph_polish/07b_paragraph_polish.json'),
        'titles': str(base/'07c_table_title_infer/07c_table_title_infer.json'),
        'captions': str(base/'07d_figure_caption_refine/07d_figure_caption_refine.json'),
        'reflow': str(base/'07e_assemble_reflow/json_output/07e_reflowed.json'),
    }}, indent=2))
    print('stage07 sample complete')


if __name__ == '__main__':
    main()

