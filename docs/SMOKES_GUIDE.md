# Smoke Tests Guide

Extractor smokes are deterministic proof commands for the current zero-choice contract.

## Core Gate

```bash
bash scripts/ci_core.sh
```

The core gate:

- syncs development dependencies with `uv sync --frozen --group dev`;
- imports the canonical package and CLI;
- runs full pytest collection;
- runs the selected contract suite;
- builds the wheel;
- installs the wheel into a clean venv;
- runs offline PDF and DOCX extraction through the installed `extractor` command;
- runs the companion skill wrapper against that installed command.

## Documentation Gate

```bash
uv run python scripts/check_docs_contract.py
```

The documentation gate checks that active docs agree with the current contract, referenced
paths exist, license text matches package metadata, and normal quick starts do not expose
internal selection knobs.

## CLI Help Gate

```bash
uv run extractor --help
uv run extractor extract --help
```

These commands prove the installed canonical CLI parses and exposes the expected `extract`
subcommand.

## Evidence Scope

- mocked: no
- live: no, unless a separate live-provider gate says otherwise
- exercised: local package, local fixtures, deterministic providers, clean install, wrapper
  delegation
- not exercised: paid model calls, database services, external CI runners

## Maintainer-Only Smokes

Older stage, UI, database, and provider smokes may still be useful while repairing internals.
Keep them in maintainer sections or historical docs. Do not present them as the normal
project-agent happy path.
