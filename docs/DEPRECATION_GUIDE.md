# Deprecation & Archive Guide

We drastically simplified this repo. Deprecated files and directories are moved
(not deleted) into `.archive/deprecated/`. Each move is logged in
`.archive/deprecated/MANIFEST.md` with source, destination, and rationale.

Archive layout (top-level):
- `code/` — deprecated code trees (old pipelines, servers, handlers, etc.)
- `docs/` — deprecated docs (status/progress/critiques/reports/etc.)
- `data/` — deprecated data directories
- `assets/` — screenshots, static files
- `tests/` — tests that reference archived codepaths
- `scripts/` — one-off helper scripts not part of the current workflow
- `root_deprecated/` — the old `deprecated/` folder preserved verbatim

How to find things:
- Look up the original path in `MANIFEST.md` to see its new archived location.
- For pipeline docs/examples, use the simplified current docs under `docs/`
  and the curated `examples/` directory. The rest are under
  `.archive/deprecated/docs/`.

Restoring something temporarily:
- Prefer referencing directly from the archive rather than moving it back.
- If a temporary restore is necessary, copy the file to a temporary branch
  or into a sandbox directory (avoid replacing current files in place).

If you add new deprecations:
- Move items into the appropriate `.archive/deprecated/**` subdir
- Append an entry to `MANIFEST.md`
- Keep the simplified docs index (`docs/README.md`) up to date if needed
