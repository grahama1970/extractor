# Extractor

Extractor is the zero-choice document extraction facade for supported files. Give it one
file and it chooses the extraction route, uses `grahama1970/pdf_oxide` for PDFs, delegates
model-mediated enrichment to `grahama1970/tau` when that is useful, and returns one truthful
`extractor.result.v1` envelope.

## Normal Quick Start

```bash
uv run extractor extract \
  data/input/twins/preset_twin/preset_twin.pdf \
  --out local/extractor-run \
  --offline \
  --format json
```

Normal callers provide a supported file and an output directory. They do not choose PDF
engines, `fast` versus `accurate`, presets, table strategies, models/providers, Tau DAGs,
or pipeline stages.

## Supported Inputs

The current facade supports local files with these extensions:

- PDF
- DOCX
- HTML and HTM
- XML and ReqIF
- Markdown and text
- JSON and JSONL
- PPTX
- XLSX and ODS
- EPUB
- RST
- PNG, JPG, JPEG, TIFF, and BMP

Unsupported extensions return a truthful `blocked` envelope instead of pretending extraction
worked.

## Result Contract

Every normal extraction emits `extractor.result.v1`.

Status values:

- `complete`: required artifacts exist, validate, and match their recorded hashes.
- `degraded`: extraction returned useful normalized output while recording a bounded
  degradation, such as skipped optional enrichment.
- `blocked`: extraction did not run because a precondition is missing or the input is not
  supported.
- `failed`: extraction ran but required artifacts are missing, invalid, or hash-mismatched.

The envelope includes source lineage, hashes, diagnostics, artifact records, and an explicit
offline flag. Consumers must inspect the envelope status instead of assuming success from
process exit alone.

## Architecture Boundary

Extractor keeps the public surface small and the internals inspectable:

| Boundary | Owns |
| --- | --- |
| Extractor | Facade, route selection, recovery, artifact validation, normalized result envelope |
| `grahama1970/pdf_oxide` | Deterministic PDF extraction |
| `grahama1970/tau` | All model-mediated enrichment |
| agent-skills `extractor` | Thin wrapper that invokes the canonical installed command |

Maintainer diagnostics and legacy stage commands are documented separately. They are not
normal caller choices.

## Canonical CLI

```bash
uv run extractor --help
uv run extractor extract --help
```

The installed console command is `extractor`. The `extract` subcommand is the canonical
entrypoint for project agents and downstream automation.

## Current State

- Current architecture and non-claims: [docs/PROJECT_KNOWLEDGE.md](docs/PROJECT_KNOWLEDGE.md)
- Current project status: [docs/STATE_OF_PROJECT.md](docs/STATE_OF_PROJECT.md)
- Normal happy path: [docs/03_guides/HAPPYPATH_GUIDE.md](docs/03_guides/HAPPYPATH_GUIDE.md)
- Smoke and proof commands: [docs/SMOKES_GUIDE.md](docs/SMOKES_GUIDE.md)
- External review request: [REVIEW_REQUEST.md](REVIEW_REQUEST.md)

Historical accuracy and performance numbers in older reports are not established release
claims unless they point to a frozen benchmark manifest with source commit, corpus, command,
environment, and result hashes.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
