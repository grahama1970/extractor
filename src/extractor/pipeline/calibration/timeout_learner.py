"""Learned timeout prediction model for PDF extraction.

Trains a regression model on actual extraction times from the corpus
to predict appropriate timeouts based on document features.

The model learns coefficients for:
- Base timeout (intercept)
- Seconds per page
- Seconds per table
- Seconds per figure
- Seconds per section
- Multipliers for formulas, requirements, domain

Usage:
    from extractor.pipeline.calibration.timeout_learner import (
        collect_training_data,
        train_timeout_model,
        predict_timeout,
    )

    # Collect data
    df = collect_training_data(Path("/mnt/storage12tb/extractor_corpus"))

    # Train model
    model = train_timeout_model(df)

    # Predict
    features = TimeoutFeatures(page_count=26, table_pages=4, ...)
    timeout_s = predict_timeout(features, model)
"""

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional
import sys

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None


@dataclass
class TimeoutFeatures:
    """Features used to predict extraction timeout."""
    page_count: int = 1
    file_size_mb: float = 0.0
    table_pages: int = 0
    has_tables: bool = False
    has_figures: bool = False
    has_formulas: bool = False
    has_requirements: bool = False
    estimated_sections: int = 0
    domain: str = "general"  # scientific, engineering, government, etc.


@dataclass
class TimeoutModel:
    """Learned timeout prediction model.

    Timeout = base_timeout_s
              + page_count * sec_per_page
              + table_count * sec_per_table
              + figure_count * sec_per_figure
              + section_count * sec_per_section
              * formula_multiplier (if has_formulas)
              * requirements_multiplier (if has_requirements)
              * domain_multipliers[domain]
    """
    base_timeout_s: float = 30.0
    sec_per_page: float = 2.0
    sec_per_table: float = 15.0
    sec_per_figure: float = 3.0
    sec_per_section: float = 0.5
    formula_multiplier: float = 1.2
    requirements_multiplier: float = 1.3
    domain_multipliers: dict = field(default_factory=lambda: {
        "scientific": 1.2,
        "engineering": 1.1,
        "government": 1.0,
        "general": 1.0,
    })

    # Model metadata
    trained_on_samples: int = 0
    training_mae_s: float = 0.0
    training_r2: float = 0.0


def extract_source_from_path(result_dir: Path) -> str:
    """Extract source type from result directory name."""
    name = result_dir.name.lower()
    if name.startswith("arxiv") or "arxiv" in name:
        return "arxiv"
    elif name.startswith("nasa") or "nasa" in name:
        return "nasa"
    elif name.startswith("nist") or "nist" in name:
        return "nist"
    elif name.startswith("faa") or "faa" in name:
        return "faa"
    elif name.startswith("government"):
        return "government"
    elif name.startswith("standards") or name.startswith("ecss"):
        return "standards"
    elif name.startswith("engineering"):
        return "engineering"
    elif name.startswith("adversarial"):
        return "adversarial"
    else:
        return "other"


def load_profile(result_dir: Path) -> Optional[dict]:
    """Load S00 profile from result directory."""
    profile_path = result_dir / "00_profile_detector" / "profile.json"
    if not profile_path.exists():
        return None
    try:
        with open(profile_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_manifest(result_dir: Path) -> Optional[dict]:
    """Load manifest.json from result directory."""
    manifest_path = result_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_timings(result_dir: Path) -> Optional[dict]:
    """Load and aggregate timings from timings.jsonl."""
    timings_path = result_dir / "timings.jsonl"
    if not timings_path.exists():
        return None

    timings = {}
    try:
        with open(timings_path) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    stage = entry.get("stage", "")
                    latency = entry.get("latency_ms", 0)
                    # Keep the last (most recent) run's timing
                    timings[stage] = latency
        return timings
    except (json.JSONDecodeError, IOError):
        return None


def extract_sample(result_dir: Path) -> Optional[dict]:
    """Extract a training sample from a result directory."""
    profile = load_profile(result_dir)
    manifest = load_manifest(result_dir)
    timings = load_timings(result_dir)

    # Need at least profile and some timing data
    if not profile:
        return None

    # Get source from path
    source = extract_source_from_path(result_dir)

    # Extract features from profile
    elements = profile.get("elements", {})
    hierarchy = profile.get("hierarchy", {})
    layout = profile.get("layout", {})

    # Calculate total duration
    total_ms = 0
    s05_ms = 0
    s04_ms = 0
    s07_ms = 0

    if manifest and "timings_ms" in manifest:
        tm = manifest["timings_ms"]
        total_ms = sum(tm.values())
        s05_ms = tm.get("05_table_extractor", 0)
        s04_ms = tm.get("04_section_builder", 0)
        s07_ms = tm.get("07_assemble_corpus", 0)
    elif timings:
        total_ms = sum(timings.values())
        s05_ms = timings.get("05_table_extractor", 0)
        s04_ms = timings.get("04_section_builder", 0)
        s07_ms = timings.get("07_assemble_corpus", 0)
    else:
        return None  # No timing data

    # Get actual counts from manifest
    counts = manifest.get("counts", {}) if manifest else {}

    return {
        "result_dir": str(result_dir.name),
        "source": source,
        "domain": profile.get("domain", "unknown"),

        # S00 features
        "page_count": profile.get("page_count", 0),
        "file_size_mb": profile.get("file_size_mb", 0.0),
        "estimated_sections": hierarchy.get("estimated_sections", 0),
        "table_pages": elements.get("table_pages", 0),
        "has_tables": elements.get("tables", False),
        "has_figures": elements.get("figures", False),
        "has_formulas": elements.get("formulas", False),
        "has_requirements": elements.get("requirements", False),
        "layout_columns": layout.get("columns", 1) if isinstance(layout, dict) else 1,

        # Actual counts
        "actual_tables": counts.get("tables05", 0),
        "actual_figures": counts.get("figures06", 0),
        "actual_sections": counts.get("sections04", 0),

        # Timings (in seconds)
        "total_duration_s": total_ms / 1000.0,
        "s05_table_duration_s": s05_ms / 1000.0,
        "s04_section_duration_s": s04_ms / 1000.0,
        "s07_assemble_duration_s": s07_ms / 1000.0,
        "estimated_timeout_s": profile.get("estimated_timeout_seconds", 300),
    }


def collect_training_data(corpus_dir: Path, verbose: bool = True) -> Optional[pd.DataFrame]:
    """Collect all training samples from the corpus."""
    if pd is None:
        print("pandas required: pip install pandas")
        return None

    results_dir = corpus_dir / "results"
    if not results_dir.exists():
        if verbose:
            print(f"Results directory not found: {results_dir}")
        return None

    samples = []
    total = 0
    skipped = 0

    for result_dir in sorted(results_dir.iterdir()):
        if not result_dir.is_dir():
            continue

        total += 1
        sample = extract_sample(result_dir)

        if sample:
            samples.append(sample)
            if verbose and len(samples) % 50 == 0:
                print(f"  Collected {len(samples)} samples...")
        else:
            skipped += 1

    if verbose:
        print(f"\nCollection complete:")
        print(f"  Total directories: {total}")
        print(f"  Valid samples: {len(samples)}")
        print(f"  Skipped: {skipped}")

    if not samples:
        return None

    return pd.DataFrame(samples)


def analyze_training_data(df: pd.DataFrame) -> None:
    """Print analysis of collected training data."""
    print("\n" + "="*60)
    print("TIMEOUT TRAINING DATA ANALYSIS")
    print("="*60)

    print(f"\nTotal samples: {len(df)}")

    print("\n--- By Source ---")
    source_stats = df.groupby("source").agg({
        "total_duration_s": ["count", "mean", "std", "min", "max"]
    }).round(1)
    print(source_stats)

    print("\n--- By Domain ---")
    domain_stats = df.groupby("domain").agg({
        "total_duration_s": ["count", "mean", "std"]
    }).round(1)
    print(domain_stats)

    print("\n--- Feature Correlations with Duration ---")
    numeric_cols = ["page_count", "file_size_mb", "actual_tables", "actual_figures",
                    "actual_sections", "table_pages"]
    for col in numeric_cols:
        if col in df.columns:
            corr = df[col].corr(df["total_duration_s"])
            print(f"  {col}: {corr:.3f}")

    print("\n--- Current S00 Estimation Accuracy ---")
    df["timeout_error_s"] = df["estimated_timeout_s"] - df["total_duration_s"]

    print(f"  Mean error: {df['timeout_error_s'].mean():.1f}s")
    print(f"  Median error: {df['timeout_error_s'].median():.1f}s")
    print(f"  Std dev: {df['timeout_error_s'].std():.1f}s")
    print(f"  Within 30s of actual: {(abs(df['timeout_error_s']) < 30).mean()*100:.1f}%")
    print(f"  Within 60s of actual: {(abs(df['timeout_error_s']) < 60).mean()*100:.1f}%")

    # Check for potential timeouts (where actual was close to estimate)
    potential_timeouts = df[df["total_duration_s"] > df["estimated_timeout_s"] * 0.9]
    print(f"\n  Potential timeouts (duration > 90% of estimate): {len(potential_timeouts)}")


def train_timeout_model(df: pd.DataFrame) -> TimeoutModel:
    """Train timeout prediction model using linear regression."""
    if np is None:
        raise ImportError("numpy required: pip install numpy")

    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    # Prepare features
    feature_cols = [
        "page_count",
        "table_pages",
        "actual_tables",
        "actual_figures",
        "actual_sections",
        "file_size_mb",
    ]

    # Add binary features
    df = df.copy()
    df["has_formulas_int"] = df["has_formulas"].astype(int)
    df["has_requirements_int"] = df["has_requirements"].astype(int)
    feature_cols.extend(["has_formulas_int", "has_requirements_int"])

    # Add domain dummies
    domain_dummies = pd.get_dummies(df["domain"], prefix="domain")
    X = pd.concat([df[feature_cols], domain_dummies], axis=1)
    y = df["total_duration_s"]

    # Train model
    model = Ridge(alpha=1.0)
    model.fit(X, y)

    # Extract coefficients
    coef_dict = dict(zip(X.columns, model.coef_))

    # Build TimeoutModel
    timeout_model = TimeoutModel(
        base_timeout_s=float(model.intercept_),
        sec_per_page=coef_dict.get("page_count", 2.0),
        sec_per_table=coef_dict.get("actual_tables", 15.0) + coef_dict.get("table_pages", 5.0),
        sec_per_figure=coef_dict.get("actual_figures", 3.0),
        sec_per_section=coef_dict.get("actual_sections", 0.5),
        formula_multiplier=1.0 + coef_dict.get("has_formulas_int", 0.0) / 50.0,  # Convert to multiplier
        requirements_multiplier=1.0 + coef_dict.get("has_requirements_int", 0.0) / 50.0,
        domain_multipliers={
            domain.replace("domain_", ""): 1.0 + coef_dict.get(domain, 0.0) / 100.0
            for domain in domain_dummies.columns
        },
        trained_on_samples=len(df),
    )

    # Compute training metrics
    y_pred = model.predict(X)
    timeout_model.training_mae_s = float(np.mean(np.abs(y - y_pred)))
    timeout_model.training_r2 = float(model.score(X, y))

    print(f"\nTraining complete:")
    print(f"  Samples: {len(df)}")
    print(f"  MAE: {timeout_model.training_mae_s:.1f}s")
    print(f"  R²: {timeout_model.training_r2:.3f}")

    return timeout_model


def predict_timeout(features: TimeoutFeatures, model: TimeoutModel) -> float:
    """Predict extraction timeout in seconds."""
    # Base calculation
    timeout = model.base_timeout_s
    timeout += features.page_count * model.sec_per_page
    timeout += features.table_pages * model.sec_per_table
    timeout += features.estimated_sections * model.sec_per_section

    # Multipliers
    if features.has_formulas:
        timeout *= model.formula_multiplier
    if features.has_requirements:
        timeout *= model.requirements_multiplier

    # Domain multiplier
    domain_mult = model.domain_multipliers.get(features.domain, 1.0)
    timeout *= domain_mult

    # Minimum and maximum bounds
    timeout = max(30.0, min(timeout, 1800.0))  # 30s to 30min

    return timeout


def save_timeout_model(model: TimeoutModel, path: Path) -> None:
    """Save timeout model to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(model), f, indent=2)


def load_timeout_model(path: Path) -> TimeoutModel:
    """Load timeout model from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return TimeoutModel(**data)


def validate_timeout_model(model: TimeoutModel, df: pd.DataFrame) -> dict:
    """Validate timeout model on test data."""
    if np is None:
        raise ImportError("numpy required: pip install numpy")

    predictions = []
    actuals = []
    errors = []
    worst = []

    for _, row in df.iterrows():
        features = TimeoutFeatures(
            page_count=row.get("page_count", 1),
            file_size_mb=row.get("file_size_mb", 0.0),
            table_pages=row.get("table_pages", 0),
            has_tables=row.get("has_tables", False),
            has_figures=row.get("has_figures", False),
            has_formulas=row.get("has_formulas", False),
            has_requirements=row.get("has_requirements", False),
            estimated_sections=row.get("actual_sections", row.get("estimated_sections", 0)),
            domain=row.get("domain", "general"),
        )

        predicted = predict_timeout(features, model)
        actual = row.get("total_duration_s", 0)

        predictions.append(predicted)
        actuals.append(actual)
        error = predicted - actual
        errors.append(error)

        worst.append({
            "source": row.get("source", "unknown"),
            "predicted": predicted,
            "actual": actual,
            "error": abs(error),
        })

    predictions = np.array(predictions)
    actuals = np.array(actuals)
    errors = np.array(errors)

    # Sort worst by error
    worst.sort(key=lambda x: x["error"], reverse=True)

    # Calculate metrics
    mae = np.mean(np.abs(errors))
    rmse = np.sqrt(np.mean(errors**2))

    # R² score
    ss_res = np.sum((actuals - predictions)**2)
    ss_tot = np.sum((actuals - np.mean(actuals))**2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "within_30s": float(np.mean(np.abs(errors) < 30)),
        "within_60s": float(np.mean(np.abs(errors) < 60)),
        "worst_predictions": worst[:10],
    }


def store_model_to_memory(model: TimeoutModel) -> bool:
    """Store learned model parameters in /memory for persistence."""
    try:
        import httpx

        problem = "Optimal timeout prediction for PDF extraction"
        solution = (
            f"Learned timeout model: base={model.base_timeout_s:.1f}s, "
            f"per_page={model.sec_per_page:.2f}s, per_table={model.sec_per_table:.2f}s, "
            f"per_figure={model.sec_per_figure:.2f}s, per_section={model.sec_per_section:.2f}s. "
            f"Trained on {model.trained_on_samples} samples with MAE={model.training_mae_s:.1f}s, R²={model.training_r2:.3f}."
        )

        payload = {
            "problem": problem,
            "solution": solution,
            "tags": ["Precision", "timeout-prediction", "learned-model"],
        }

        response = httpx.post(
            "http://127.0.0.1:8601/learn",
            json=payload,
            timeout=10.0,
        )

        return response.status_code == 200
    except Exception as e:
        print(f"Warning: Could not store model to memory: {e}")
        return False
