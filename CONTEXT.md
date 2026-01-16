# Project Context: Extractor

## Current Status (2026-01-16)

The Extractor has been successfully refactored into a **"Preset-First" Agentic Pipeline**. It no longer relies on a "Split Brain" architecture where detection was disconnected from execution.

### Completed Architectural Gaps

- **Healed "Split Brain"**: `s00_profile_detector` now runs at the start of every pipeline execution. It detects the document type and initializes a `preset_config`.
- **Context Propagation**: This `preset_config` is passed through the entire pipeline via `run_pipeline.py`.
- **Single Source of Truth**: `src/extractor/core/presets.py` is now auto-generated from `twin_config.yml` files in the `tools/tasks_loop/fixtures/` directory.
- **Adaptive Steps**:
  - `s04_section_builder`: Now uses `section_pattern` (regex) from the detected preset.
  - `s08b_lean4_theorem_prover`: Context-aware enablement (Scientific = ON, Engineering = OFF).
  - `s09_section_summarizer`: Custom prompts (e.g., scientific vs engineering) are selected based on the preset.

### Core Entrypoints

- **Run Pipeline**: `python -m extractor.pipeline --pdf <path> --out <dir>`
- **Compiler (Presets)**: `python tools/tasks_loop/utils/compile_presets.py` (Must run after modifying `twin_config.yml`)
- **Verification Loop**: `./tools/tasks_loop/loop.sh` (Runs gates and tasks).

## Outstanding Items & Blockers

1. **Local Dependencies (Migration Blocker)**: The `pyproject.toml` contains absolute file paths to local repositories (`litellm`, `fetcher`). These must be converted to relative paths or published versions before moving to `agent-skills`.
2. **Missing SKILL.md**: A formal `SKILL.md` for `pi-mono` integration is not yet created. The `README.md` contains the logic, but the agent-specific metadata is missing.
3. **Environment Parity**: The pipeline depends on `scillm` (lite-llm wrapper) and `fetcher`. Ensure these are available in any take-over environment.

## Logic Flow for Next Agent

- To add a new document type:
  1. Add a fixture to `tools/tasks_loop/fixtures/<name>/`.
  2. Define `preset_id` and `runtime` features in `twin_config.yml`.
  3. Run the compiler: `python tools/tasks_loop/utils/compile_presets.py`.
  4. The pipeline will now automatically detect and adapt to this new type.

## Active Task Document

Ongoing work is tracked in `tools/tasks_loop/tasks/`.
Latest completed tasks: `s08_context`, `refactor_presets`, `s09_prompt_tuning`.
