# Extractor Review Request

You are reviewing the extractor project for operational readiness and compliance.

Repository:
https://github.com/grahama1970/extractor

Branch to review:
`main`

Current focus:
Review the zero-choice Extractor architecture and its active documentation.

Review goal:
Assess what is broken, missing, aspirational, outstanding, or out of compliance with:

- `best-practices-python`
- `best-practices-skills`
- the extractor skill contract

Current contract:

> Give Extractor a supported file. Extractor decides how to extract it, uses
> `grahama1970/pdf_oxide` for PDFs, routes model work through `grahama1970/tau` when useful,
> and returns one truthful normalized result.

Known deterministic local evidence:

- `scripts/ci_core.sh` is the clean-install gate.
- `scripts/check_docs_contract.py` is the active documentation contract gate.
- Normal CLI surface:
  - `uv run extractor --help`
  - `uv run extractor extract --help`
  - `uv run extractor extract <file> --out <dir> --offline --format json`

Important constraints:

- Do not treat offline smoke success as live provider readiness.
- Do not recommend broad cleanup or deletion without per-file dependency evidence.
- Separate IMPLEMENTED, BROKEN, MISSING, ASPIRATIONAL, and OUTSTANDING.
- Prioritize narrow, ticket-sized repairs.
- Focus on root causes and proof gates, not generic refactoring advice.

Please return:

1. A concise readiness verdict.
2. Top 10 findings ordered by severity, with file/path references.
3. Which extractor claims are implemented versus aspirational/not established.
4. Which `best-practices-python` and `best-practices-skills` rules are violated.
5. A prioritized next-step ticket list, each with target files, current state, requested
   outcome, and required proof command.
6. What should explicitly not be done next.
