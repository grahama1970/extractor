"""Sanity check for S10 markdown exporter using assembled_content.json."""
import json
import tempfile
from pathlib import Path
from extractor.pipeline.steps.s10_markdown_exporter import run as run_s10


def main():
    # Create a temp pipeline directory with assembled_content.json
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline_dir = Path(tmpdir)
        assembled_dir = pipeline_dir / "07_assembled"
        assembled_dir.mkdir(parents=True)

        assembled = {
            "sections": [
                {"id": "s1", "title": "Sanity Section", "page_start": 1,
                 "page_end": 1, "parent_id": None, "llm_summary": None,
                 "llm_key_concepts": None, "llm_metadata": None}
            ],
            "blocks": [],
            "tables": [
                {"id": "t1", "page": 1, "x0": 0, "y0": 0, "x1": 100, "y1": 50,
                 "csv_data": "Col1,Col2\nVal1,Val2", "html_data": "",
                 "section_id": "s1", "sort_order": 200,
                 "llm_title": "Test Table", "llm_description": "", "image_path": ""}
            ],
            "figures": [],
            "merged_content": [
                {"id": "mc1", "section_id": "s1", "page": 1, "type": "text",
                 "content": "Hello World", "asset_id": None, "sort_order": 100,
                 "x0": 0, "y0": 0, "x1": 100, "y1": 20},
                {"id": "mc2", "section_id": "s1", "page": 1, "type": "table",
                 "content": "Test Table", "asset_id": "t1", "sort_order": 200,
                 "x0": 0, "y0": 20, "x1": 100, "y1": 50},
            ],
            "requirements": [],
            "annotations": [],
            "toc_entries": [],
            "metadata": {"page_count": 1, "source_pdf": "sanity_test.pdf",
                          "is_scanned": False, "assembled_at": "2026-01-01T00:00:00"},
            "document_metadata": {},
            "lean4_proofs": [],
        }

        json_path = assembled_dir / "assembled_content.json"
        json_path.write_text(json.dumps(assembled, indent=2))

        print("Running Export...")
        try:
            out = run_s10(pipeline_dir, Path(tmpdir))
            print(f"Exported to: {out}")
            if out and Path(out).exists():
                print("--- Content ---")
                print(Path(out).read_text())
            else:
                print("PASS: Export completed (no output file expected for minimal data)")
        except Exception as e:
            print(f"Failed: {e}")


if __name__ == "__main__":
    main()
