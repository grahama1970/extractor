"""Integration tests for the Shadow-LEGO feedback loop.

Tests the full chain: S05 outcomes → harvest → train → promote → Tier 0.5.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add learn-datalake skill to path so we can import its modules
_LEARN_DATALAKE_ROOT = Path.home() / ".pi/skills/learn-datalake"
if str(_LEARN_DATALAKE_ROOT) not in sys.path:
    sys.path.insert(0, str(_LEARN_DATALAKE_ROOT))


@pytest.fixture
def tmp_data_root(tmp_path):
    """Create mock extraction output dirs with strategy outcomes."""
    pdf1_dir = tmp_path / "data" / "pdf_alpha"
    pdf1_dir.mkdir(parents=True)
    pdf2_dir = tmp_path / "data" / "pdf_beta"
    pdf2_dir.mkdir(parents=True)

    records_1 = [
        {
            "page_num": 1,
            "predicted_strategy": "lattice_default",
            "predicted_confidence": 0.75,
            "predicted_tier": "heuristic",
            "actual_best": "stream_default",
            "strategies_tried": ["lattice_default", "stream_default"],
            "fragmentation_scores": {"lattice_default": 80, "stream_default": 10},
            "s00_table_style": "borderless",
            "s00_domain": "scientific",
            "category": "scientific",
        },
        {
            "page_num": 2,
            "predicted_strategy": "lattice_default",
            "predicted_confidence": 0.80,
            "predicted_tier": "heuristic",
            "actual_best": "lattice_strong",
            "strategies_tried": ["lattice_default", "lattice_strong"],
            "fragmentation_scores": {"lattice_default": 30, "lattice_strong": 5},
            "s00_table_style": "bordered",
            "s00_domain": "defense",
            "category": "defense",
        },
    ]

    records_2 = [
        {
            "page_num": 1,
            "predicted_strategy": "stream_default",
            "predicted_confidence": 0.70,
            "predicted_tier": "heuristic",
            "actual_best": "stream_default",
            "strategies_tried": ["stream_default"],
            "fragmentation_scores": {"stream_default": 8},
            "s00_table_style": "borderless",
            "s00_domain": "scientific",
            "category": "scientific",
        },
    ]

    (pdf1_dir / "05_strategy_outcomes.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records_1) + "\n"
    )
    (pdf2_dir / "05_strategy_outcomes.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records_2) + "\n"
    )

    return tmp_path


@pytest.fixture
def mock_training_dir(tmp_path):
    """Return a mock training directory path for testing purposes."""
    return tmp_path / "training"


class TestHarvestTransforms:
    """Verify harvest transforms outcomes into a valid training JSONL file."""
    def test_harvest_transforms_outcomes_to_training_jsonl(self, tmp_data_root, tmp_path):
        """Verify harvest produces valid labels.jsonl with correct features."""
        from learn_datalake.orchestrator import harvest_strategy_outcomes

        training_dir = tmp_path / "training"
        with patch("learn_datalake.orchestrator.STRATEGY_TRAINING_DIR", training_dir), \
             patch("learn_datalake.orchestrator.STRATEGY_OUTCOMES_GLOB", "data/**/05_strategy_outcomes.jsonl"), \
             patch("learn_datalake.orchestrator.STRATEGY_OUTCOMES_EXTRA_DIRS", []):
            count = harvest_strategy_outcomes(data_root=tmp_data_root)

        assert count == 3  # 2 from pdf_alpha + 1 from pdf_beta

        labels_path = training_dir / "labels.jsonl"
        assert labels_path.exists()

        records = [json.loads(line) for line in labels_path.read_text().strip().splitlines()]
        assert len(records) == 3

        # Check feature structure
        for rec in records:
            assert "features" in rec
            assert "label" in rec
            assert "table_style_borderless" in rec["features"]
            assert "table_style_bordered" in rec["features"]
            assert "domain_scientific" in rec["features"]

    def test_harvest_deduplicates_by_pdf_page(self, tmp_path):
        """Duplicate (pdf_stem, page_num) entries should be deduped."""
        from learn_datalake.orchestrator import harvest_strategy_outcomes

        pdf_dir = tmp_path / "data" / "pdf_dup"
        pdf_dir.mkdir(parents=True)

        rec = {
            "page_num": 1,
            "actual_best": "stream_default",
            "s00_table_style": "borderless",
            "s00_domain": "scientific",
            "fragmentation_scores": {},
        }
        # Write same record twice
        (pdf_dir / "05_strategy_outcomes.jsonl").write_text(
            json.dumps(rec) + "\n" + json.dumps(rec) + "\n"
        )

        training_dir = tmp_path / "training"
        with patch("learn_datalake.orchestrator.STRATEGY_TRAINING_DIR", training_dir), \
             patch("learn_datalake.orchestrator.STRATEGY_OUTCOMES_GLOB", "data/**/05_strategy_outcomes.jsonl"), \
             patch("learn_datalake.orchestrator.STRATEGY_OUTCOMES_EXTRA_DIRS", []):
            count = harvest_strategy_outcomes(data_root=tmp_path)

        assert count == 1  # deduped


class TestTrainingGate:
    """Test training gate's data sufficiency."""
    def test_training_gate_rejects_insufficient_data(self, tmp_path):
        """<200 examples should skip training."""
        from learn_datalake.orchestrator import train_strategy_classifier

        training_dir = tmp_path / "training"
        training_dir.mkdir(parents=True)

        # Write only 5 records
        labels_path = training_dir / "labels.jsonl"
        for i in range(5):
            with open(labels_path, "a") as f:
                f.write(json.dumps({"features": {}, "label": "stream_default"}) + "\n")

        with patch("learn_datalake.orchestrator.STRATEGY_TRAINING_DIR", training_dir), \
             patch("learn_datalake.orchestrator.MIN_TRAINING_EXAMPLES", 200):
            result = train_strategy_classifier()

        assert result is None


class TestTrainingProduces:
    """Validate model and metrics generation from training data."""
    def test_training_produces_joblib_and_metrics(self, tmp_path):
        """With enough data, training should produce model.joblib + metrics.json."""
        from learn_datalake.orchestrator import train_strategy_classifier

        training_dir = tmp_path / "training"
        training_dir.mkdir(parents=True)
        model_dir = tmp_path / "models"

        # Generate 300 synthetic records with enough class diversity
        labels_path = training_dir / "labels.jsonl"
        import random
        random.seed(42)
        strategies = ["stream_default", "lattice_default", "lattice_strong"]
        with open(labels_path, "w") as f:
            for i in range(300):
                label = strategies[i % len(strategies)]
                f.write(json.dumps({
                    "features": {
                        "table_style_borderless": random.randint(0, 1),
                        "table_style_bordered": random.randint(0, 1),
                        "domain_scientific": random.randint(0, 1),
                        "domain_defense": random.randint(0, 1),
                        "has_borders": random.randint(0, 1),
                        "category": random.choice(["scientific", "defense", "general"]),
                    },
                    "label": label,
                }) + "\n")

        with patch("learn_datalake.orchestrator.STRATEGY_TRAINING_DIR", training_dir), \
             patch("learn_datalake.orchestrator.STRATEGY_MODEL_DIR", model_dir), \
             patch("learn_datalake.orchestrator.MIN_TRAINING_EXAMPLES", 200):
            metrics = train_strategy_classifier()

        assert metrics is not None
        assert "accuracy" in metrics
        assert "macro_f1" in metrics
        assert "model_path" in metrics
        assert (model_dir / "model.joblib").exists()
        assert (model_dir / "metrics.json").exists()


class TestPromotionGate:
    """Validate promotion gate behavior."""
    def test_promotion_gate_rejects_low_f1(self, tmp_path):
        """f1 < 0.85 should not promote."""
        from learn_datalake.orchestrator import check_promotion_gate

        model_dir = tmp_path / "models"
        model_dir.mkdir(parents=True)

        with patch("learn_datalake.orchestrator.STRATEGY_MODEL_DIR", model_dir):
            result = check_promotion_gate({"macro_f1": 0.60, "n_samples": 600})

        assert result is False
        assert not (model_dir / "PROMOTE_READY.md").exists()

    def test_promotion_gate_accepts_high_f1(self, tmp_path):
        """f1 >= 0.85 + n >= 500 should promote."""
        from learn_datalake.orchestrator import check_promotion_gate

        model_dir = tmp_path / "models"
        model_dir.mkdir(parents=True)

        with patch("learn_datalake.orchestrator.STRATEGY_MODEL_DIR", model_dir), \
             patch("learn_datalake.orchestrator.ASSISTANT_RUN", tmp_path / "nonexistent"):
            result = check_promotion_gate({"macro_f1": 0.90, "n_samples": 600})

        assert result is True
        assert (model_dir / "PROMOTE_READY.md").exists()

    def test_promotion_gate_rejects_insufficient_samples(self, tmp_path):
        """n_samples < 500 should not promote even with high f1."""
        from learn_datalake.orchestrator import check_promotion_gate

        model_dir = tmp_path / "models"
        model_dir.mkdir(parents=True)

        with patch("learn_datalake.orchestrator.STRATEGY_MODEL_DIR", model_dir):
            result = check_promotion_gate({"macro_f1": 0.95, "n_samples": 100})

        assert result is False


class TestStrategySelector:
    """Validate assistant availability in the tier05 strategy selector."""
    def test_tier05_assistant_returns_none_when_unavailable(self):
        """When /assistant is not present, _tier05_assistant returns None."""
        from extractor.pipeline.utils.tables.strategy_selector import _tier05_assistant

        with patch(
            "extractor.pipeline.utils.tables.strategy_selector._ASSISTANT_RUN",
            Path("/nonexistent/run.sh"),
        ):
            result = _tier05_assistant("bordered", "defense", True, "defense")

        assert result is None

    def test_tier05_assistant_parses_response(self):
        """When /assistant returns valid JSON, parse into StrategyPrediction."""
        from extractor.pipeline.utils.tables.strategy_selector import _tier05_assistant

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"prediction": "lattice_strong", "confidence": 0.92})

        with patch(
            "extractor.pipeline.utils.tables.strategy_selector._ASSISTANT_RUN",
            Path("/home/graham/.pi/skills/assistant/run.sh"),
        ), patch(
            "extractor.pipeline.utils.tables.strategy_selector.subprocess.run",
            return_value=mock_result,
        ):
            result = _tier05_assistant("bordered", "defense", True, "defense")

        assert result is not None
        assert result.strategy_name == "lattice_strong"
        assert result.confidence == 0.92
        assert result.tier == "classifier"
