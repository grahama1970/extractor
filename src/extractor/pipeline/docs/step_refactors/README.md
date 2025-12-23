Here is a comprehensive `README.md` designed to orient the project agent (or dev team) on the architectural changes, the new directory structure, and where to find specific logic after the refactor.

---

# Pipeline Refactoring Guide

## 1\. Overview

We have transitioned the extraction pipeline from monolithic "God scripts" (where orchestration, logic, and IO were mixed) to a modular architecture based on **Separation of Concerns**.

**Old State:** Single files per stage (e.g., `07_reflow_section.py`) containing 4,000+ lines of mixed code.
**New State:** Thin Orchestrators in `steps/` and Domain Logic in `utils/{domain}/`.

## 2\. The New Architecture

### A. The Orchestrators (`extractor/pipeline/steps/`)

The files in this directory are now strictly for **configuration and flow control**. They:

- Parse CLI arguments and environment variables.
- Setup Logging (`loguru` sinks) and Diagnostics.
- Call high-level functions from `utils`.
- Handle top-level error catching and file I/O (reading/writing JSON).

### B. The Utilities (`extractor/pipeline/utils/`)

Logic is now grouped by **domain** rather than by **pipeline stage**.

| Utility Directory   | Purpose                                                                       |
| :------------------ | :---------------------------------------------------------------------------- |
| `utils/headers/`    | Heuristics for detecting/verifying headers (Stage 03).                        |
| `utils/sections/`   | Hierarchy building, numbering parsing, and tree construction (Stage 04).      |
| `utils/tables/`     | Camelot wrappers, Pandas metrics, stitching logic, and repairs (Stage 05).    |
| `utils/layout/`     | Geometry math (IoU), column detection, and Sketch DSL generation (Stage 06b). |
| `utils/reflow/`     | Complex prompt engineering, table merging, and text cleaning (Stage 07).      |
| `utils/prover/`     | Lean 4 CLI wrappers, Docker execution, and Remote API bridges (Stage 08).     |
| `utils/summarizer/` | Rolling window logic, checkpointing, and prompt generation (Stage 09).        |
| `utils/visuals/`    | PyMuPDF drawing commands, color palettes, and bbox geometry (Stage 09a).      |

---

## 3\. Refactor Breakdown by Stage

### Stage 03: Suspicious Header Verifier

- **Orchestrator:** `03_suspicious_headers.py`
- **Logic Location:** `utils/headers/`
- **Key Changes:**
  - Moved regex heuristics (bullet points, colons) to `heuristics.py` (deduplicated).
  - Moved `VerificationTask` and image rendering to `task.py`.
  - Moved LLM verification prompts to `llm.py`.

### Stage 04: Section Builder

- **Orchestrator:** `04_section_builder.py`
- **Logic Location:** `utils/sections/`
- **Key Changes:**
  - Moved numbering regex and title cleaning to `parsing.py`.
  - Moved the complex tree-building algorithm (`build_sections_from_blocks`) to `hierarchy.py`.
  - Moved PyMuPDF image extraction to `visuals.py`.

### Stage 05: Table Extractor

- **Orchestrator:** `05_table_extractor.py`
- **Logic Location:** `utils/tables/`
- **Key Changes:**
  - Moved Camelot strategy definitions to `extraction.py`.
  - Moved Pandas scoring and metrics generation to `metrics.py`.
  - Moved complex stitching and header reconstruction logic to `heuristics.py`.
  - Moved LLM-based repairs (split columns) to `assist.py`.

### Stage 06b: Layout Sketcher

- **Orchestrator:** `06b_layout_sketcher.py`
- **Logic Location:** `utils/layout/`
- **Key Changes:**
  - Moved pure math (IoU, Grid mapping, Normalization) to `geometry.py`.
  - Moved Column detection algorithms to `columns.py`.
  - Moved DSL generation (text representation of layout) to `formatting.py`.

### Stage 07: Section Reflow

- **Orchestrator:** `07_reflow_section.py`
- **Logic Location:** `utils/reflow/`
- **Key Changes:**
  - Moved the massive `_build_compact_prompt` functions to `prompts.py`.
  - Moved logical table merging and Pandas formatting to `tables.py`.
  - Moved SciLLM Router wrappers and JSON repair to `llm_helpers.py`.

### Stage 08: Lean 4 Prover

- **Orchestrator:** `08_lean4_theorem_prover.py`
- **Logic Location:** `utils/prover/`
- **Key Changes:**
  - Moved low-level CLI and Docker `subprocess` calls to `execution.py`.
  - Moved "Certainly" API bridge logic to `remote.py`.
  - Moved LLM requirement extraction prompts to `extraction.py`.

### Stage 09: Summarizer

- **Orchestrator:** `09_section_summarizer.py`
- **Logic Location:** `utils/summarizer/`
- **Key Changes:**
  - Moved `summarize_section` and prompt formatting to `generation.py`.
  - Moved the complex rolling window / checkpoint loop to `batching.py`.

### Stage 09a: PDF Annotator

- **Orchestrator:** `09a_pdf_annotator.py`
- **Logic Location:** `utils/visuals/`
- **Key Changes:**
  - Moved raw PyMuPDF drawing calls (`draw_rect`, `insert_text`) to `drawing.py`.
  - Moved coordinate transformations and BBox clamping to `geometry.py`.
  - Moved label string formatting to `formatting.py`.

---

## 4\. Common Tasks & Usage Guidelines

### How to add a new LLM Prompt

Do not add strings to the step files.

1.  Go to `utils/{domain}/prompts.py` (or `generation.py` / `extraction.py`).
2.  Define the prompt function there.
3.  Import it into the orchestrator.

### How to handle Bounding Boxes

Use the shared geometry utilities to ensure consistency (0,0 is top-left vs bottom-left).

- **Layout/Reflow:** Use `extractor.pipeline.utils.layout.geometry`.
- **Visuals/Annotation:** Use `extractor.pipeline.utils.visuals.geometry`.

### How to run the pipeline

The CLI commands remain **unchanged**. The refactor is purely internal structure.

```bash
# Example: Running Stage 07
python -m extractor.pipeline.steps.07_reflow_section \
    data/results/pipeline/04_sections.json \
    data/results/pipeline/05_tables.json \
    data/results/pipeline/06_figures.json \
    data/results/pipeline/
```

### Debugging

If an error stack trace points to `utils/...`, you know it's a logic error.
If an error stack trace points to `steps/...`, it is likely a configuration, file path, or environment variable error.
