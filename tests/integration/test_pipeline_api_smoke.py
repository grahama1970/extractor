import json
from pathlib import Path
from typing import List


import extractor.pipeline.api as api


class DummyCompleted:
    returncode = 0


def _stub_run_factory(tmp_out: Path):
    """Create a stub for subprocess.run that emulates stage outputs."""

    def _stub_run(cmd: List[str], cwd=None, env=None, **kwargs):  # signature match used
        # Identify stage by script name in cmd[1]
        args = list(map(str, cmd))
        if "01_annotation_processor.py" in args[1]:
            # find -o output dir and create clean pdf
            out = Path(args[args.index("-o") + 1])
            anno_dir = out / "01_annotation_processor"
            anno_dir.mkdir(parents=True, exist_ok=True)
            # infer input pdf name
            pdf = Path(args[args.index("run") + 1])
            (anno_dir / f"{pdf.stem}_clean.pdf").write_bytes(b"%PDF-1.4\n%clean\n")
        elif "02_marker_extractor.py" in args[1]:
            out = Path(args[args.index("-o") + 1])
            blocks = out / "02_marker_extractor" / "json_output"
            blocks.mkdir(parents=True, exist_ok=True)
            (blocks / "02_marker_blocks.json").write_text(json.dumps({"blocks": []}))
        elif "03_suspicious_headers.py" in args[1]:
            out = Path(args[args.index("-o") + 1])
            verified = out / "03_suspicious_headers" / "json_output"
            verified.mkdir(parents=True, exist_ok=True)
            (verified / "03_verified_blocks.json").write_text(json.dumps({"blocks": []}))
        elif "04_section_builder.py" in args[1]:
            out = Path(args[args.index("-o") + 1])
            sections = out / "04_section_builder" / "json_output"
            sections.mkdir(parents=True, exist_ok=True)
            (sections / "04_sections.json").write_text(
                json.dumps({"sections": [{"title": "Test"}]})
            )
        return DummyCompleted()

    return _stub_run


def test_extract_sections_smoke(tmp_path, monkeypatch):
    # Prepare dummy PDF
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%dummy\n")

    # Stub subprocess.run used by api._run
    # The api module imports subprocess and calls subprocess.run directly
    import subprocess as subprocess_module

    monkeypatch.setattr(subprocess_module, "run", _stub_run_factory(tmp_path))

    # Run API against temp output dir
    out_dir = tmp_path / "results"
    sections, path = api.extract_sections(pdf, out_dir)

    assert path.exists(), "Sections JSON should exist"
    assert isinstance(sections, list) and sections, "Sections should be non-empty"
