Typer CLI Standard: Structure, Testing, and Debugging

Goals
- Consistent, testable, and debuggable Typer CLIs across the repo
- Zero import-time side effects to enable safe imports in tests/agents
- Fast, deterministic tests using pytest + CliRunner

Core Principles
- Separate logic from CLI:
  - Keep core logic in pure functions (no I/O, no globals)
  - Typer commands should be thin wrappers over those functions
- Build CLI via factory:
  - Expose `build_cli() -> typer.Typer` per CLI module
  - Do not create `app = Typer()` or configure logging at import time
  - In `if __name__ == "__main__": build_cli()()` boot the CLI
- Avoid import-time side effects:
  - No `.env` loading, logging configuration, Redis/DB connections, or HTTP on import
  - Perform environment/logging setup inside `build_cli()` (warn if `.env` missing; do not exit)
- Tests use CliRunner:
  - `runner.invoke(app, [args...], catch_exceptions=False)`
  - Monkeypatch external effects (subprocess, network, DB) and synthesize minimal files
  - Assert `exit_code`, `stdout`, and on-disk outputs

Repository Patterns
- Example minimal app and tests: `prototypes/cli_learnings/`
  - Logic: `make_greeting`, `add_numbers`
  - CLI: thin Typer commands calling logic
  - Tests: `test_logic.py` (pure), `test_hello.py` (CliRunner)

Pipeline CLIs
- `src/extractor/pipeline/api.py`:
  - Provides `build_cli()` for the core (01→04) pipeline wrapper
  - Tests: `tests/pipeline/api/test_cli.py` monkeypatches subprocess calls and creates minimal outputs
- Steps package (`src/extractor/pipeline/steps/`):
  - Numeric filenames (e.g., `09_section_summarizer.py`) are lazily accessible via aliases:
    - `from extractor.pipeline.steps import s09_section_summarizer as step`
  - Each step should expose `build_cli()` and avoid import-time side effects
  - Examples: `09_section_summarizer.py`, `14_report_generator.py`
  - Tests: `tests/pipeline/steps/test_09_section_summarizer_cli.py`, `test_14_report_generator_cli.py`

VS Code Debugging
- Prefer the Testing panel (beaker) to debug tests with breakpoints in both tests and source files
- Minimal interpreter setup: `.vscode/settings.json` sets `python.defaultInterpreterPath` and enables pytest
- If a manual CLI run must be debugged, either:
  - Insert `breakpoint()` temporarily and run `python -m package.module args...`, or
  - Create a one-off launch config; remove when done (avoid many launch.json entries)

Testing Guidance
- Location: Mirror source tree under `tests/` (core/, pipeline/, steps/, utils/, smoke/)
- Keep smoke tests minimal and non-flaky — they validate viability, not correctness
- For CLI tests:
  - Use `catch_exceptions=False` to surface errors to the debugger
  - Synthesize inputs/outputs in `tmp_path` and monkeypatch long-running or external calls

Migration Checklist (for any CLI module)
- [ ] Extract pure logic into functions (no I/O)
- [ ] Add `build_cli()` that wires Typer commands
- [ ] Move env/log configuration into `build_cli()` (no import-time side effects)
- [ ] Add `if __name__ == "__main__": build_cli()()`
- [ ] Add CliRunner tests under `tests/...` with monkeypatches and temp files

