# Extractor Project Knowledge

Date: 2026-07-29

## Current Architecture Decision

Extractor is a zero-choice facade for supported document extraction. A caller supplies a file
and an output directory; Extractor selects the route and returns a normalized
`extractor.result.v1` envelope.

Normal callers do not choose:

- PDF engines
- `fast` versus `accurate`
- presets
- table strategies
- models/providers
- Tau DAGs
- pipeline stages

## Canonical Entrypoint

```bash
uv run extractor extract \
  data/input/twins/preset_twin/preset_twin.pdf \
  --out local/extractor-run \
  --offline \
  --format json
```

CLI help:

```bash
uv run extractor --help
uv run extractor extract --help
```

## Internal Boundaries

| Component | Responsibility |
| --- | --- |
| Extractor | Facade, routing, source preservation, recovery, artifact validation, normalized envelope |
| `grahama1970/pdf_oxide` | Deterministic PDF extraction |
| `grahama1970/tau` | Model-mediated enrichment |
| agent-skills `extractor` | Thin wrapper around the installed canonical command |

Implementation details remain inspectable for maintainers, but they are not exposed as
choices to project agents.

## Active Implementation Paths

- `src/extractor/cli_app.py`
- `src/extractor/application/extract_file.py`
- `src/extractor/core/schema/extraction_result.py`
- `src/extractor/core/providers/registry.py`
- `src/extractor/core/providers/pdf.py`
- `scripts/ci_core.sh`
- `scripts/check_docs_contract.py`
- `tests/contracts/`

## Features And Deployment State

- `uv run extractor extract ... --offline --format json` is the current supported local
  extraction interface.
- `src/extractor/application/extract_file.py` is the source-backed facade that routes by file
  type, preserves the source digest, writes artifacts, and returns the normalized
  `extractor.result.v1` envelope.
- `src/extractor/core/schema/extraction_result.py` defines the result schema, including
  `source_sha256`, artifact records, diagnostics, and terminal status semantics.
- PDF extraction routes through the pinned `pdf_oxide` dependency from `pyproject.toml`; contract
  tests in `tests/contracts/test_pdf_routes_to_pdf_oxide.py` and
  `tests/contracts/test_pdf_oxide_result_mapping.py` assert the engine, pin, raw artifact, and
  normalized counts.
- The `agent-skills` extractor wrapper is intentionally thin and delegates to the installed
  `extractor` command rather than re-implementing extraction.
- The tabbed prototype lives under `prototypes/tabbed/html` and `prototypes/tabbed/api`; it is not
  the canonical extraction API.

## Advantages And Unique Capabilities

- Zero-choice facade: agents and callers do not choose engines, presets, stages, providers, or
  Tau DAGs for normal extraction.
- Deterministic offline path: fixture-backed PDF and document extraction can run without paid model
  calls or external service availability.
- Source preservation: every successful v1 result records the input `source_sha256` and required
  artifact hashes for downstream verification.
- Native PDF route: canonical PDFs use pinned `pdf_oxide`, with regression tests guarding engine
  selection and raw-to-normalized result mapping.
- Contract-first behavior: `tests/contracts/` checks the CLI, wrapper, status semantics, source
  preservation, no-op repair rejection, and dependency boundaries.

## Companion Repository Assumptions

- `grahama1970/pdf_oxide` is pinned from `pyproject.toml`.
- `grahama1970/tau` owns model-mediated enrichment when enrichment is enabled.
- The companion `agent-skills` extractor wrapper must remain a thin wrapper and should use
  `EXTRACTOR_COMMAND` when a clean installed command is being tested.

## Known Blockers And Dependencies

- Tickets #42 through #48 have been used to align the skill wrapper, project-state checks, docs, and
  memory recall.
- Ticket #49 tracks the remaining hardcoded `/home/graham` path cleanup in runtime/documentation
  surfaces.
- Live provider/model behavior still needs separate live proof before it can be advertised as
  ready.
- Database export behavior still needs separate endpoint/database proof before it can be
  advertised as ready.
- Historical docs may still contain stale architecture details; active quick starts must point
  to this current contract.

## Explicit Non-Claims

- No current documentation claims release-ready live model enrichment.
- No current documentation claims release-ready database export.
- No current documentation claims benchmark parity or performance without frozen manifests.
- No current documentation asks a normal project agent to select engines, modes, presets,
  strategies, providers, Tau DAGs, or stages.

## Latest Deterministic Proof Commands

```bash
uv run python scripts/check_docs_contract.py
bash scripts/ci_core.sh
```

Expected local proof scope:

- mocked: no
- live: no
- exercised: local docs contract, installed CLI help, full pytest collection, selected
  contract tests, wheel build, clean venv install, offline PDF/DOCX extraction, skill wrapper
  delegation
- remains unverified: paid/live model paths, database exports, external service availability
