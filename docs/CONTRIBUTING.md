# Contributing — CLI and Lint Quickstart

Single CLI Surface
- Use one command for all extractions (PDF + structured formats):
  - PDF (fast text-only):
    ```bash
    python -m src.cli extract path/to/input.pdf out_dir --mode fast
    ```
  - PDF (accurate, normalized artifacts):
    ```bash
    python -m src.cli extract path/to/input.pdf out_dir --mode accurate
    ```
  - Structured (HTML/DOCX/PPTX/XLSX/EPUB/RST/XML/MD):
    ```bash
    python -m src.cli extract path/to/input.html out_dir
    ```

Linting (Ruff)
- Fast checks for safe classes (unused imports/vars, simple style):
  ```bash
  ruff check src --select F401,F541,E702,E712,F841
  ```
- Auto-fix where safe:
  ```bash
  ruff check src --select F401,F541,E702,E712,F841 --fix
  ```
- Notes:
  - Prototypes and artifacts are excluded via pyproject.toml.
  - Some demo helpers and re-export modules use per-file ignores to keep signal clean.

Smokes (non‑UI)
- Quick confidence:
  ```bash
  PYTHONPATH=src python scripts/smokes/pipeline/smoke_cli_fast_pdf.py
  PYTHONPATH=src python scripts/smokes/pipeline/smoke_cli_structured_all.py
  PYTHONPATH=src python scripts/smokes/pipeline/smoke_stage05_strategy_quality.py
  PYTHONPATH=src python scripts/smokes/pipeline/smoke_meta_parity_all_formats.py
  ```
