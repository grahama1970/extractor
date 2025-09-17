import os
import sys
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

import memory.arxiv_extract_cli as cli


runner = CliRunner()


def invoke(args: list[str], catch_exceptions: bool = False, **env: str):
    app = cli.build_cli()
    return runner.invoke(app, args, catch_exceptions=catch_exceptions, env=env or None)


def test_cli_requires_input():
    result = invoke(["run"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "Either --pdf or --arxiv-id must be supplied" in result.output


def test_cli_runs_pipeline_for_local_pdf(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_text("content")
    results_dir = tmp_path / "results"

    captured = {}

    def fake_run(cmd, check, env):
        captured.update(cmd=cmd, check=check, env=env)
        class Dummy:
            returncode = 0

        return Dummy()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = invoke(
        [
            "run",
            "--pdf",
            str(pdf),
            "--results",
            str(results_dir),
            "--session",
            "mysession",
            "--lean4-cli",
            "lean-cmd",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    expected_cmd = [
        sys.executable,
        "src/extractor/pipeline/run_all.py",
        "run",
        "--pdf",
        str(pdf),
        "--results",
        str(results_dir),
        "--session",
        "mysession",
        "--lean4-cli",
        "lean-cmd",
    ]
    assert captured["cmd"] == expected_cmd
    assert captured["check"] is True
    assert "PYTHONPATH" in captured["env"]
    assert str(Path.cwd() / "src") in captured["env"]["PYTHONPATH"].split(os.pathsep)
    assert results_dir.exists()


def test_cli_downloads_arxiv_pdf(tmp_path, monkeypatch):
    downloaded = tmp_path / "1234.5678.pdf"
    downloaded.write_text("pdf data")
    results_dir = tmp_path / "results"

    def fake_download(arxiv_id: str) -> Path:
        assert arxiv_id == "1234.5678"
        return downloaded

    captured = {}

    def fake_run(cmd, check, env):
        captured.update(cmd=cmd, check=check, env=env)
        class Dummy:
            returncode = 0

        return Dummy()

    monkeypatch.setattr(cli, "_download_arxiv_pdf", fake_download)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = invoke(
        [
            "run",
            "--arxiv-id",
            "1234.5678",
            "--results",
            str(results_dir),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert any(str(downloaded) == part for part in captured["cmd"])
    assert "--session" in captured["cmd"]
    session_index = captured["cmd"].index("--session") + 1
    assert captured["cmd"][session_index] == f"arxiv-{downloaded.stem}"


def test_cli_propagates_pipeline_failure(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_text("content")

    def failing_run(cmd, check, env):
        raise subprocess.CalledProcessError(returncode=42, cmd=cmd)

    monkeypatch.setattr(cli.subprocess, "run", failing_run)

    with pytest.raises(SystemExit) as exc:
        invoke([
            "run",
            "--pdf",
            str(pdf),
            "--results",
            str(tmp_path / "results"),
        ], catch_exceptions=False)

    assert exc.value.code == 42
