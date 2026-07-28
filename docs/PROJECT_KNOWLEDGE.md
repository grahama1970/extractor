# Extractor Project Knowledge

Date: 2026-07-28

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

## Companion Repository Assumptions

- `grahama1970/pdf_oxide` is pinned from `pyproject.toml`.
- `grahama1970/tau` owns model-mediated enrichment when enrichment is enabled.
- The companion `agent-skills` extractor wrapper must remain a thin wrapper and should use
  `EXTRACTOR_COMMAND` when a clean installed command is being tested.

## Known Blockers And Dependencies

- Issues #25 through #31 are prerequisites for this current-state documentation.
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
