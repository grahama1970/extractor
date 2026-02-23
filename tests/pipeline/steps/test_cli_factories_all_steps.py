import importlib
from typing import List

import pytest
from typer.testing import CliRunner


# Steps with CLI interfaces (build_cli function)
STEPS_WITH_CLI: List[str] = [
    # Currently no steps expose build_cli() - they are library functions
    # invoked via run_pipeline.py, not standalone CLI tools.
    # Add step aliases here when/if CLI wrappers are implemented.
]

# Steps that are library-only (no CLI interface)
# These match steps exported from extractor.pipeline.steps.__init__.py
LIBRARY_ONLY_STEPS: List[str] = [
    "s01_annotation_processor",
    "s02_marker_extractor",
    "s03_suspicious_headers",
    "s04_section_builder",
    "s04a_layout_audit",
    "s05_table_extractor",
    "s06_figure_extractor",
    "s06b_figure_describer",
    "s07_duckdb_ingest",
    "s08_extract_requirements",
    "s08_lean4_theorem_prover",
    "s09_section_summarizer",
    "s10_markdown_exporter",
    "s14_report_generator",
]


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.parametrize("alias", STEPS_WITH_CLI or ["_placeholder"])
def test_build_cli_factory_exists_and_help(alias: str, runner: CliRunner) -> None:
    """Test that steps with CLI interfaces have working --help and debug-bundle."""
    if alias == "_placeholder":
        pytest.skip("No steps currently have build_cli() - they are library modules")
    mod = importlib.import_module("extractor.pipeline.steps")
    step = getattr(mod, alias)
    assert hasattr(step, "build_cli"), f"{alias} missing build_cli()"
    app = step.build_cli()
    # top-level help
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    # subcommand help for debug-bundle
    res2 = runner.invoke(app, ["debug-bundle", "--help"])
    assert res2.exit_code == 0


@pytest.mark.parametrize("alias", LIBRARY_ONLY_STEPS)
def test_library_step_has_run_and_sanity(alias: str) -> None:
    """Test that library-only steps have run() and sanity() functions."""
    mod = importlib.import_module("extractor.pipeline.steps")
    step = getattr(mod, alias)
    assert hasattr(step, "run"), f"{alias} missing run()"
    assert hasattr(step, "sanity"), f"{alias} missing sanity()"
