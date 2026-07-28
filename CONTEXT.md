# CONTEXT - Extractor Current Agent State

Last updated: 2026-07-28

## Active Goal

Iterate through extractor tickets until every applicable ticket is resolved or closed with
deterministic proof.

## Current Contract

Extractor exposes one normal project-agent command:

```bash
uv run extractor extract \
  data/input/twins/preset_twin/preset_twin.pdf \
  --out local/extractor-run \
  --offline \
  --format json
```

Normal callers do not choose engines, modes, presets, strategies, providers, Tau DAGs, or
pipeline stages. Extractor routes supported files and emits one `extractor.result.v1`
envelope.

## Current Proof Baseline

The latest deterministic gate is:

```bash
uv run python scripts/check_docs_contract.py
bash scripts/ci_core.sh
```

Issue #31 added `scripts/ci_core.sh`, which performs full collection, selected contract
tests, wheel build, clean venv install, clean installed PDF/DOCX extraction, and skill
wrapper delegation to the installed command.

## Active Implementation Paths

- Canonical CLI: `src/extractor/cli_app.py`
- Extraction facade: `src/extractor/application/extract_file.py`
- Provider registry: `src/extractor/core/providers/registry.py`
- PDF engine boundary: `src/extractor/core/providers/pdf.py`
- Result envelope and validation: `src/extractor/core/schema/extraction_result.py`
- Clean install gate: `scripts/ci_core.sh`
- Documentation gate: `scripts/check_docs_contract.py`

## Known Non-Claims

- Live provider/model enrichment is not established by the offline gates.
- Database export readiness is not established by the offline gates.
- Historical parity and performance numbers are not release claims unless tied to frozen
  benchmark manifests.
- Legacy pipeline stage commands remain maintainer diagnostics, not normal usage.

## Working Tree Note

This repository may contain unrelated local generated files under `local/`, `prototypes/`,
and ingestion state paths. Do not stage unrelated files when closing extractor tickets.
