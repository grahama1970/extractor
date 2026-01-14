---
description: Create a synthetic "Twin" fixture from a real PDF
---

This workflow guides you through the Mimicry process: Scanning a real PDF, reviewing the structural spec, and generating a safe synthetic twin for testing.

1. **Scan the Source PDF**
   Run the scanner to analyze fonts, layout, and structure. It produces a JSON spec and debug visuals.
   _Replace `path/to/real.pdf` with your actual PDF path._

   ```bash
   python3 tools/tasks_loop/utils/fixture_scanner.py \
     --pdf path/to/real.pdf \
     --output mimic_spec.json \
     --debug-visuals
   ```

2. **Review Debug Visuals**
   Check the generated images in `mimic_spec.json.parent/scanner_debug/` (e.g., `scanner_debug/page_1.png`).

   - **Red Boxes**: Headers
   - **Blue Boxes**: Body Text

   If the structure looks wrong (e.g., headers missed), edit `mimic_spec.json` manually to adjust titles or hierarchy.

3. **Generate the Twin Fixture**
   Create the synthetic fixture using the (potentially edited) spec.

   ```bash
   python3 tools/tasks_loop/utils/create_fixture_pdf.py \
     --spec mimic_spec.json \
     --name synthesis_mimic_twin
   ```

4. **Verify the Twin**
   The new fixture is at `tools/tasks_loop/fixtures/synthesis_mimic_twin/`.

   - `source.pdf`: The generated "Lorem Ipsum" PDF.
   - `SPEC.md`: The auto-generated contract.

   Run the pipeline against it to ensure it behaves as expected:

   ```bash
   python3 tools/tasks_loop/run_pipeline.py s04 --fixture synthesis_mimic_twin
   ```
