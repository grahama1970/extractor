import importlib
from typing import List

import pytest
from typer.testing import CliRunner


STEP_ALIASES: List[str] = [
    "s01_annotation_processor",
    "s02_marker_extractor",
    "s03_suspicious_headers",
    "s04_section_builder",
    "s05_table_extractor",
    "s06_figure_extractor",
    "s07_reflow_section",
    "s08_lean4_theorem_prover",
    "s10_arangodb_exporter",
    "s11_arango_create_graph",
    "s12_insert_annotations",
]


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.parametrize("alias", STEP_ALIASES)
def test_build_cli_factory_exists_and_help(alias: str, runner: CliRunner) -> None:
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

