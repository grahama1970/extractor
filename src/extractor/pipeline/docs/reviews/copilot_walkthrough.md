# Pipeline Refactoring Walkthrough for Copilot Review

## Objective

Refactor all pipeline step files to under 800 lines so they can be fully read by LLMs in a single pass, enabling better code understanding and more accurate edits.

## Completed Work

### Step File Line Counts (All Under 800)

| Step File                  | Before | After   |
| -------------------------- | ------ | ------- |
| 07_reflow_section.py       | 5,412  | **794** |
| 05_table_extractor.py      | 2,431  | **682** |
| 03_suspicious_headers.py   | 1,566  | **463** |
| 09a_pdf_annotator.py       | 1,392  | **137** |
| 06b_layout_sketcher.py     | 1,574  | **470** |
| 01_annotation_processor.py | 1,488  | **263** |
| 04_section_builder.py      | 1,426  | **152** |
| 08_lean4_theorem_prover.py | 1,379  | **154** |
| 11_arango_create_graph.py  | 1,237  | **788** |
| 02_marker_extractor.py     | 1,049  | **457** |
| 10_arangodb_exporter.py    | 918    | **595** |
| 09_section_summarizer.py   | 877    | **126** |
| 14_report_generator.py     | 834    | **718** |

**Total: 9,180 lines** (reduced from ~24,000)

### New Utility Packages Created

Large functions extracted to `src/extractor/pipeline/utils/`:

| Package                     | Contains                                 | Source    |
| --------------------------- | ---------------------------------------- | --------- |
| `reflow/section_reflow.py`  | `reflow_section_with_llm` (~2,500 lines) | Stage 07  |
| `reflow/runner.py`          | Stage 07 `run()`                         | Stage 07  |
| `tables/runner.py`          | `extract_tables_from_page`, `run()`      | Stage 05  |
| `headers/runner.py`         | `process_pdf_pipeline`, `Config`         | Stage 03  |
| `visuals/runner.py`         | Stage 09a `run()`                        | Stage 09a |
| `layout/sketcher.py`        | `_build_section_sketch`, `run()`         | Stage 06b |
| `prover/runner.py`          | Stage 08 `run()`                         | Stage 08  |
| `sections/runner.py`        | `build_sections_from_blocks`, `run()`    | Stage 04  |
| `annotations/runner.py`     | `process_pdf_pipeline`, helpers          | Stage 01  |
| `arango/graph_runner.py`    | Stage 11 `run()`                         | Stage 11  |
| `arango/exporter_runner.py` | Stage 10 `run()`                         | Stage 10  |
| `marker_runner.py`          | Stage 02 `run()`                         | Stage 02  |
| `summarizer_runner.py`      | Stage 09 summarization                   | Stage 09  |
| `report_runner.py`          | Stage 14 `run()`                         | Stage 14  |

### Verification

```bash
# All 14 step files import successfully
python3 -c "
import importlib
stages = ['01_annotation_processor', '02_marker_extractor', '03_suspicious_headers',
          '04_section_builder', '05_table_extractor', '06_figure_extractor',
          '06a_title_caption_enricher', '06b_layout_sketcher', '07_reflow_section',
          '08_lean4_theorem_prover', '09_section_summarizer', '10_arangodb_exporter',
          '11_arango_create_graph', '14_report_generator']
for s in stages:
    importlib.import_module(f'extractor.pipeline.steps.{s}')
print('All 14 step files import successfully')
"
```

**Result: 14/14 pass**

## Review Request

Please review the refactored codebase for:

1. **Import correctness** - Are all imports from utility packages wired correctly?
2. **Missing dependencies** - Any functions referenced but not imported?
3. **Runtime correctness** - Will the pipeline execute correctly with these changes?
4. **Code organization** - Is the utility package structure logical?

## Key Files to Review

- `src/extractor/pipeline/steps/*.py` - The refactored step files
- `src/extractor/pipeline/utils/*/runner.py` - Extracted run functions
- `src/extractor/pipeline/utils/reflow/section_reflow.py` - Largest extraction

## Branch

`feature/merge-metadata-prop` - Pushed to origin
