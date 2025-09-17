import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.smoke


def test_pipeline_run_fast_json_and_final_report():
    # Use a tiny dummy PDF file; pipeline may fail, but the CLI should still emit a minimal final_report.json
    from extractor.pipeline.cli_mode import app as run_app

    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "dummy.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        out = Path(td) / "out"

        runner = CliRunner()
        res = runner.invoke(
            run_app,
            [
                "run",
                "--pdf",
                str(pdf),
                "--results",
                str(out),
                "--mode",
                "fast",
                "--json",
            ],
            catch_exceptions=False,
        )
        # Exit code may be non-zero if pipeline-happy errors on dummy PDF; that's acceptable for this smoke
        assert res.exit_code in (0, 1)
        payload = json.loads(res.stdout)
        assert isinstance(payload, dict) and "meta" in payload
        fr = out / "final_report.json"
        assert fr.exists(), "final_report.json should exist even on partial/failed runs"
        data = json.loads(fr.read_text())
        assert isinstance(data, dict) and "meta" in data and "items" in data and "errors" in data

