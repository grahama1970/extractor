import json
from pathlib import Path

from extractor.pipeline.utils.gamified_contracts import (
    IterMetrics,
    IterSummary,
    DoneInfo,
    Scorecard,
)


def _read(p: Path):
    return json.loads(p.read_text())


def test_iter_and_summary_contracts(tmp_path: Path):
    fx = Path("tests/fixtures/gamified")
    metrics = IterMetrics.model_validate(_read(fx / "iter_01.json"))
    assert set(metrics.correctness.keys()) == {"S", "M", "L"}
    assert set(metrics.timings_ms.keys()) == {"S", "M", "L"}

    summary = IterSummary.model_validate(_read(fx / "iter_01_summary.json"))
    assert summary.iter == 1
    assert summary.metrics.approach == metrics.approach

    done = DoneInfo.model_validate(_read(fx / "done.json"))
    assert done.variant == metrics.approach


def test_scorecard_contract(tmp_path: Path):
    fx = Path("tests/fixtures/gamified")
    sc = Scorecard.model_validate(_read(fx / "scorecard.json"))
    sc.validate_winner()
    assert set(sc.scales) == {"S", "M", "L"}
    assert sc.winner is None or sc.winner in sc.approaches

