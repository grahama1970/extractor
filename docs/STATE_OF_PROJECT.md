# State Of The Extractor Project

Date: 2026-07-28

## Executive State

Extractor is being hardened around a zero-choice architecture:

> Give Extractor a supported file. Extractor decides how to extract it, uses
> `grahama1970/pdf_oxide` for PDFs, routes model work through `grahama1970/tau` when useful,
> and returns one truthful normalized result.

This is the current project-agent contract. Documentation that asks normal callers to choose
engines, modes, presets, table strategies, providers, Tau DAGs, or pipeline stages is stale.

## Implemented

- Canonical installed CLI: `extractor extract`.
- Normalized result envelope: `extractor.result.v1`.
- Deterministic PDF routing through the `pdf_oxide` provider boundary.
- Provider routing for supported non-PDF formats through the Extractor facade.
- Source-preserving recovery and artifact validation contracts.
- Thin companion skill wrapper that delegates to the canonical command.
- Clean-install gate in `scripts/ci_core.sh`.

## Broken Or Recently Repaired

- The old root console entrypoint imported legacy runtime modules too eagerly. Issue #31
  repaired this with `src/extractor/cli_app.py`.
- Previous CI workflows masked failures with best-effort checks. Issue #31 replaced them
  with a blocking clean-install contract.
- Older docs described Marker/PyMuPDF stages, direct provider configuration, presets, and
  mode selection as normal usage. This file now treats those as stale unless clearly marked
  maintainer-only or historical.

## Missing Or Not Established

- Live provider/model enrichment proof is not established by the offline gate.
- Database export proof is not established by the offline gate.
- Large-corpus performance and accuracy parity are not established without frozen benchmark
  manifests.
- Full historical documentation cleanup is not complete; only active current-state docs are
  in scope for the current contract.

## Current Proof Commands

```bash
uv run python scripts/check_docs_contract.py
uv run extractor --help
uv run extractor extract --help
bash scripts/ci_core.sh
```

The clean-install gate proves local deterministic behavior only. It does not prove live
provider credentials, external services, or paid model paths.

## Maintainer Diagnostics

Maintainers may inspect legacy stage modules, old reports, and historical benchmark artifacts
when repairing internals. Those diagnostics must not be presented as normal project-agent
quick starts.
