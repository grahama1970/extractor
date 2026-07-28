# Happy Path Guide

The happy path is one supported file in, one truthful `extractor.result.v1` envelope out.

## Normal Quick Start

```bash
uv run extractor extract \
  data/input/twins/preset_twin/preset_twin.pdf \
  --out local/extractor-run \
  --offline \
  --format json
```

This command is the normal project-agent surface. Extractor owns route selection and internal
recovery.

## Caller Contract

The caller supplies:

- an input file;
- an output directory;
- whether optional network/model enrichment is disabled with `--offline`;
- the stdout presentation format.

The caller does not choose engines, modes, presets, table strategies, providers, Tau DAGs, or
pipeline stages.

## Expected Result

The command writes artifacts under the output directory and prints an `extractor.result.v1`
envelope. Consumers should read:

- `schema_version`;
- `status`;
- `source_sha256`;
- `artifacts`;
- `diagnostics.extra.offline`.

`complete` and `degraded` are usable extraction outcomes. `blocked` and `failed` require
operator attention.

## Maintainer Diagnostics

Maintainers can still inspect lower-level modules and historical stage artifacts while
repairing internals. Those commands are diagnostics, not the happy path. They should not be
copied into project-agent quick starts.

## Proof

```bash
uv run python scripts/check_docs_contract.py
uv run extractor --help
uv run extractor extract --help
```
