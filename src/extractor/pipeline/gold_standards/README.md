# Gold Standards (Deterministic Parity)

Purpose
- Keep a lightweight, deterministic "gold" corpus that mirrors the canonical PDF flattening so we can test provider parity without re-parsing the PDF.
- Everything here is documentation and small helper scripts; large binaries stay under `data/input/parity_hand/` and `data/results/parity_smoke/`.

Canonical truth
- PDF: `data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf`
- Canonical flattened JSON (53 blocks):
  `data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json`
  - 52 text blocks, 1 table block (table index 51).

Clean artifacts (generated from canonical flat)
- `data/input/parity_hand/clean.html`
- `data/input/parity_hand/clean.md`
- `data/input/parity_hand/clean.json`
- Re-flattened count check: `data/input/parity_hand/reflat.json` (also 53 blocks, 1 table block).

How to regenerate clean artifacts
```bash
PYTHONPATH=src python -m extractor.pipeline.gold_standards.scripts.parity_emit_clean \
  --flat data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json \
  --outdir data/input/parity_hand

PYTHONPATH=src python -m extractor.pipeline.gold_standards.scripts.parity_reflatten_clean \
  --html data/input/parity_hand/clean.html \
  --out data/input/parity_hand/reflat.json

# Optional re-flatten for other emitted formats
PYTHONPATH=src python -m extractor.pipeline.gold_standards.scripts.parity_reflatten_clean \
  --docx data/input/parity_hand/clean.docx \
  --out data/input/parity_hand/reflat_docx.json

PYTHONPATH=src python -m extractor.pipeline.gold_standards.scripts.parity_reflatten_clean \
  --pptx data/input/parity_hand/clean.pptx \
  --out data/input/parity_hand/reflat_pptx.json

PYTHONPATH=src python -m extractor.pipeline.gold_standards.scripts.parity_reflatten_clean \
  --xlsx data/input/parity_hand/clean.xlsx \
  --out data/input/parity_hand/reflat_xlsx.json
```

Smokes (deterministic parity)
```bash
PYTHONPATH=src python scripts/smokes/pipeline/smoke_parity_canonical.py \
  --flat data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json

python scripts/smokes/pipeline/smoke_parity_clean.py \
  --pdf-flat data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json \
  --clean-flat data/input/parity_hand/reflat.json data/input/parity_hand/reflat_docx.json data/input/parity_hand/reflat_md.json data/input/parity_hand/reflat_rst.json \
  --threshold 0.95

# Optional: compare other reflattened formats (docx/pptx/xlsx) once generated
# e.g. python scripts/smokes/pipeline/smoke_parity_clean.py --pdf-flat ... --clean-flat data/input/parity_hand/reflat_docx.json
```

Notes on non-HTML formats
- docx now matches exactly by default (simple mode on by default; set `DOCX_SIMPLE_MODE=0` to use rich path).
- md/rst emit deterministic one-line-per-block with markers; parity matches (53 blocks).
- xml matches within threshold (0.962) using the generated `clean.xml` fixture (52 text + 1 table).
- epub now matches (53 blocks) via `parity_reflatten_epub.py` → `data/input/parity_hand/reflat_epub.json`.
- pptx/xlsx remain structure-first; reported via `smoke_parity_report.py` (not enforced).
- Docx provider parity: set `DOCX_SIMPLE_MODE=1` when running the CLI for deterministic one-paragraph-per-block behavior on gold fixtures.

Design notes
- One block per table (not per row) keeps counts aligned with the canonical flattening.
- Provider-based reparses are intentionally avoided here; use separate provider smokes when needed.
- If the canonical flattened JSON changes, regenerate clean artifacts and rerun the two smokes.

Future extensions
- Optional re-flatteners for docx/pptx/xlsx using the same one-table-one-block rule.
- A content/order diff smoke if we need visibility into exact deltas.
