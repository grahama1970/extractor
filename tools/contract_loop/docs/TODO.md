## Pending Enhancements

- Interactive annotations on clarifying forms:
  - Goal: let humans draw on section/table thumbnails (e.g., highlight a table
    boundary or mark missing rows) directly inside the Flask UI.
  - Status: future work; track implementation details (canvas component,
    serialization format, how annotations feed back into fixtures) here once the
    base clarifying form ships.
- Bundle contents include source-PDF slices per Task 3 (no IP constraints per
  Jan 2026 guidance).
- Sensitive-response storage: no additional controls needed yet, but revisit if
  requirements change; capture decision logs in manifest when that happens.
- Parallel subagents / async Codex coordination:
  - If we later have a use case that truly benefits from parallel Codex calls
    or async coordination (e.g., running multiple clarifying UIs simultaneously
    or working front-end/back-end in parallel), revisit the current sequential
    design. Task 2 is satisfied with streaming/logging, but this file should
    track requirements once parallelism becomes valuable.
- Core sanity-hooks enforcement:
  - DONE: `tools/contract_loop/sanity_runner.py` now runs the global checks plus
    every command listed in `SANITY_MATRIX.md` before the loop starts. The helper
    blocks with exit code 5 if any script fails.
  - Maintain `tools/contract_loop/docs/SANITY_MATRIX.md` so each pipeline step
    “owns” at least one sanity command. Consider allowing agents to declare
    step-specific scripts in YAML so the loop can reference them when scaffolding
    new stages.
- Contract-loop self-sanity:
  - DONE: `SANITY_MATRIX_CONTRACT.md` now tracks module-only checks (exec harness,
    bundle guardrails, clarify UI) and `SANITY_MATRIX.md` points to adapter-level
    matrices.
  - DONE: module sanity config lives in `sanity_config_contract.py`; project
    sanity config is now per-adapter (e.g., extractor).
  - DONE: sanity runner executes both matrices and loads project configs by
    adapter name.
- Bash-first clarifying-form scaffolding:
  - Document the "bash first" workflow from
    https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/ and
    mirror the pattern so agents can describe form schemas and preferred HTML
    widgets via shell scripts without introducing a heavy MCP stack.
  - Provide a helper script (e.g., `tools/contract_loop/scripts/new_form.sh`)
    that ingests a per-question schema (JSON/YAML) and scaffolds the desired
    HTML/TS form elements under `clarify-ui/`, making it easy to mix question
    types (radio, checkbox, textarea, upload, etc.) from Bash.
- Contract-loop formatted code reviews:
  - Mirror `src/extractor/pipeline/docs/COPILOT_REVIEW_REQUEST_EXAMPLE.md` with a
    contract-loop specific template (auto-populated sections for failing steps,
    manifest excerpts, log links). Capture the desired fields/format here before
    wiring it into Task 5 tooling.
