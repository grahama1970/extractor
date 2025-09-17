import json
from pathlib import Path

from typer.testing import CliRunner
from jsonschema import validate
import pytest


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_debug_bundle_minimal(tmp_path: Path, runner: CliRunner) -> None:
    from extractor.pipeline.steps import s14_report_generator as step

    # Build a minimal results map sufficient for report generation
    results = {
        "07_reflow_section": {
            "reflowed_sections": [
                {
                    "title": "Intro",
                    "level": 1,
                    "reflow_status": "success",
                    "reflowed": True,
                    "text_chunks": [],
                    "merged_tables": [],
                    "ocr_corrections": {},
                }
            ]
        },
        "06_figure_extractor": {"figure_count": 0, "figures": []},
    }

    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps({"results": results}))

    app = step.build_cli()
    res = runner.invoke(app, ["debug-bundle", str(bundle), "-o", str(tmp_path)], catch_exceptions=False)
    assert res.exit_code == 0
    final_json = tmp_path / "final_report.json"
    final_md = tmp_path / "final_report.md"
    assert final_json.exists()
    assert final_md.exists()

    # JSON schema validation
    schema_path = Path("schemas/final_report.schema.json")
    schema = json.loads(schema_path.read_text())
    payload = json.loads(final_json.read_text())
    validate(instance=payload, schema=schema)

    # Lightweight markdown snapshot of key headings
    md_text = final_md.read_text()
    assert "# PDF Extraction Pipeline Report" in md_text
    assert "## Pipeline Summary" in md_text
