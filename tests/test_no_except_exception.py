from pathlib import Path

REQUIRED_FILES = {
    '01_annotation_processor.py',
    '02_marker_extractor.py',
    '03_suspicious_headers.py',
    '04_section_builder.py',
    '04a_layout_audit.py',
    '05_table_extractor.py',
    '06_figure_extractor.py',
    '06b_layout_sketcher.py',
    '07_reflow_section.py',
    '07_requirements_miner.py',
    '09_section_summarizer.py',
    '09a_pdf_annotator.py',
    '09b_audit.py',
    '10_arangodb_exporter.py',
    'deprecated_codex_call.py',
}

UTIL_DIRS = (
    'src/extractor/pipeline/utils',
)

# Temporary allowlist for utils we haven't hardened yet; shrink as we clean
UTIL_ALLOWLIST = {
    # still to harden
    'src/extractor/pipeline/utils/debug_utils.py',
    'src/extractor/pipeline/utils/image_io.py',
    'src/extractor/pipeline/utils/json_utils.py',
    'src/extractor/pipeline/utils/response_utils.py',
    'src/extractor/pipeline/utils/step_sanity.py',
    'src/extractor/pipeline/utils/chutes_text.py',
    'src/extractor/pipeline/utils/scillm_client.py',
    'src/extractor/pipeline/utils/diagnostics.py',
    'src/extractor/pipeline/utils/async_processing.py',
    'src/extractor/pipeline/utils/scillm_router.py',
    'src/extractor/pipeline/utils/pdf_preflight.py',
    'src/extractor/pipeline/utils/metrics_logger.py',
    'src/extractor/pipeline/utils/preflight.py',
    'src/extractor/pipeline/utils/figure_extractor_utils.py',
    'src/extractor/pipeline/utils/sanity_utils.py',
    'src/extractor/pipeline/utils/unified_conversion.py',
    'src/extractor/pipeline/utils/table_extractor_utils.py',
    'src/extractor/pipeline/utils/model_params.py',
    'src/extractor/pipeline/utils/vision.py',
    'src/extractor/pipeline/utils/hybrid_search.py',
    'src/extractor/pipeline/utils/image_helpers.py',
    'src/extractor/pipeline/utils/table_quality_metrics.py',
    'src/extractor/pipeline/utils/chutes_curl.py',
    'src/extractor/pipeline/utils/llm_utils.py',
    'src/extractor/pipeline/utils/prompt_builder.py',
    'src/extractor/pipeline/utils/embeddings.py',
    'src/extractor/pipeline/utils/log_utils.py',
    'src/extractor/pipeline/utils/ann_index.py',
    'src/extractor/pipeline/utils/verifier.py',
    'src/extractor/pipeline/utils/annotations.py',
    'src/extractor/pipeline/utils/litellm_call.py',
    'src/extractor/pipeline/utils/page_geometry_cache.py',
    'src/extractor/pipeline/utils/section_builder_utils.py',
}

def _find_bad(files):
    bad = []
    for p in files:
        lines = p.read_text().splitlines()
        for idx, line in enumerate(lines):
            if line.lstrip().startswith('#'):
                continue
            if 'except Exception' in line:
                next_lines = lines[idx+1:idx+3]
                joined = ' '.join(next_lines)
                if 'log_stage_error' not in joined or 'raise' not in joined:
                    bad.append((str(p), idx+1, line.strip()))
    return bad


def test_broad_except_must_log_and_raise_in_required_steps():
    root = Path('src/extractor/pipeline/steps')
    files = [p for p in root.rglob('*.py') if p.name in REQUIRED_FILES]
    bad = _find_bad(files)
    if bad:
        details = '\n'.join(f"{f}:{i}: {l}" for f,i,l in bad)
        raise AssertionError('Broad except must log & raise in required steps:\n'+details)


def test_broad_except_must_log_and_raise_in_utils():
    files = []
    for d in UTIL_DIRS:
        files.extend(Path(d).rglob('*.py'))
    files = [p for p in files if str(p) not in UTIL_ALLOWLIST]
    bad = _find_bad(files)
    if bad:
        details = '\n'.join(f"{f}:{i}: {l}" for f,i,l in bad)
        raise AssertionError('Broad except must log & raise in pipeline utils:\n'+details)
