# TODO

## OCR language handling

- Current environment uses surya-ocr RecognitionPredictor without a `langs` parameter in `__call__`.
- For now, we assume English-only OCR and rely on the model’s defaults.
- Future: add per-image language control via a compatibility layer that switches to `run_ocr` or a wrapper when a project requires multi-language OCR. Detect availability at runtime and branch accordingly.

## Fast DOCX→PDF fallback

- Implemented a “fast fallback” path that skips heavy table/figure stages when converting DOCX→PDF for parity checks.
- Flags are wired through `structured_pipeline.run_structured_pipeline(..., fast_fallback_pdf=True)` to `run_all.run`.

