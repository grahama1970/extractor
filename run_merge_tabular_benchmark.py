#!/usr/bin/env python3
"""
Tabular benchmark for merge/separate table classifier.

Loads merge_features.jsonl, trains gradient_boosting / random_forest /
logistic_regression, reports metrics, and saves the best model.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_PATH = Path(
    os.environ.get(
        "MERGE_FEATURES_PATH",
        Path.home()
        / "workspace/experiments/pi-mono/.pi/skills/create-table-classifier/data/merge_features.jsonl",
    )
)
MODEL_OUTPUT_DIR = Path(
    os.environ.get(
        "MERGE_CLASSIFIER_MODEL_DIR",
        Path.home()
        / "workspace/experiments/pi-mono/.pi/skills/create-table-classifier/models/merge-classifier-tabular",
    )
)

FEATURE_COLS = [
    "col_count_match",
    "width_ratio",
    "horizontal_iou",
    "title_has_continued",
    "same_section",
    "s05b_title_similarity",
    "gap_between_tables_px",
    "row_count_ratio",
]

LABEL_COL = "label"
SEED = 42
TEST_SIZE = 0.20

BACKBONES = {
    "gradient_boosting": lambda: GradientBoostingClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1, random_state=SEED
    ),
    "random_forest": lambda: RandomForestClassifier(
        n_estimators=200, max_depth=10, random_state=SEED
    ),
    "logistic_regression": lambda: LogisticRegression(
        max_iter=1000, random_state=SEED
    ),
}


def load_data(path: Path):
    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    print(f"Loaded {len(rows)} samples from {path}")

    X_raw = []
    y_raw = []
    for row in rows:
        feats = []
        for col in FEATURE_COLS:
            val = row.get(col, 0.0)
            if isinstance(val, bool):
                val = 1.0 if val else 0.0
            feats.append(float(val))
        X_raw.append(feats)
        y_raw.append(row[LABEL_COL])

    X = np.array(X_raw, dtype=np.float64)
    y = np.array(y_raw)
    return X, y, rows


def print_separator(title: str = ""):
    width = 70
    if title:
        print(f"\n{'=' * width}")
        print(f"  {title}")
        print(f"{'=' * width}")
    else:
        print(f"{'-' * width}")


def main():
    X, y, rows = load_data(DATA_PATH)

    labels = sorted(set(y))
    print(f"Labels: {labels}")
    for label in labels:
        count = sum(1 for yi in y if yi == label)
        print(f"  {label}: {count} ({100 * count / len(y):.1f}%)")

    print(f"\nFeatures ({len(FEATURE_COLS)}):")
    for i, col in enumerate(FEATURE_COLS):
        vals = X[:, i]
        print(f"  {col:30s}  min={vals.min():.4f}  max={vals.max():.4f}  mean={vals.mean():.4f}")

    # Stratified train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=SEED
    )
    print(f"\nSplit: train={len(X_train)}, test={len(X_test)}")
    for label in labels:
        tr = sum(1 for yi in y_train if yi == label)
        te = sum(1 for yi in y_test if yi == label)
        print(f"  {label}: train={tr}, test={te}")

    # Scale features for logistic regression
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    results = {}
    best_f1 = -1.0
    best_name = None
    best_model = None

    for name, factory in BACKBONES.items():
        print_separator(f"Training: {name}")

        clf = factory()

        if name == "logistic_regression":
            clf.fit(X_train_scaled, y_train)
            y_pred = clf.predict(X_test_scaled)
        else:
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        f1_macro = f1_score(y_test, y_pred, average="macro")
        f1_weighted = f1_score(y_test, y_pred, average="weighted")
        prec = precision_score(y_test, y_pred, average="macro")
        rec = recall_score(y_test, y_pred, average="macro")

        cm = confusion_matrix(y_test, y_pred, labels=labels)
        report = classification_report(y_test, y_pred, labels=labels, digits=4)

        results[name] = {
            "accuracy": acc,
            "f1_macro": f1_macro,
            "f1_weighted": f1_weighted,
            "precision_macro": prec,
            "recall_macro": rec,
            "confusion_matrix": cm.tolist(),
        }

        print(f"  Accuracy:          {acc:.4f}")
        print(f"  F1 (macro):        {f1_macro:.4f}")
        print(f"  F1 (weighted):     {f1_weighted:.4f}")
        print(f"  Precision (macro): {prec:.4f}")
        print(f"  Recall (macro):    {rec:.4f}")
        print(f"\n  Confusion Matrix (rows=actual, cols=predicted):")
        print(f"  Labels: {labels}")
        for i, row_vals in enumerate(cm):
            print(f"    {labels[i]:>10s}  {row_vals}")
        print(f"\n  Classification Report:\n{report}")

        if hasattr(clf, "feature_importances_"):
            importances = clf.feature_importances_
            sorted_idx = np.argsort(importances)[::-1]
            print("  Feature Importances:")
            for idx in sorted_idx:
                print(f"    {FEATURE_COLS[idx]:30s}  {importances[idx]:.4f}")

        if hasattr(clf, "coef_"):
            print("  Coefficients (absolute mean across classes):")
            coef_mean = np.abs(clf.coef_).mean(axis=0)
            sorted_idx = np.argsort(coef_mean)[::-1]
            for idx in sorted_idx:
                print(f"    {FEATURE_COLS[idx]:30s}  {coef_mean[idx]:.4f}")

        if f1_macro > best_f1:
            best_f1 = f1_macro
            best_name = name
            best_model = clf

    # Summary
    print_separator("BENCHMARK SUMMARY")
    print(f"{'Backbone':>25s}  {'Accuracy':>10s}  {'F1(macro)':>10s}  {'F1(wt)':>10s}  {'Precision':>10s}  {'Recall':>10s}")
    print("-" * 85)
    for name, metrics in results.items():
        marker = " <-- BEST" if name == best_name else ""
        print(
            f"{name:>25s}  {metrics['accuracy']:>10.4f}  {metrics['f1_macro']:>10.4f}  "
            f"{metrics['f1_weighted']:>10.4f}  {metrics['precision_macro']:>10.4f}  "
            f"{metrics['recall_macro']:>10.4f}{marker}"
        )

    # Save best model
    print_separator(f"Saving best model: {best_name}")
    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_OUTPUT_DIR / "model.joblib"
    scaler_path = MODEL_OUTPUT_DIR / "scaler.joblib"
    meta_path = MODEL_OUTPUT_DIR / "metadata.json"

    joblib.dump(best_model, model_path)
    joblib.dump(scaler, scaler_path)

    metadata = {
        "backbone": best_name,
        "features": FEATURE_COLS,
        "labels": list(labels),
        "test_size": TEST_SIZE,
        "seed": SEED,
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "total_samples": int(len(X)),
        "metrics": {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in results[best_name].items()
        },
        "all_results": {
            name: {k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()}
            for name, m in results.items()
        },
        "needs_scaling": best_name == "logistic_regression",
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"  Model saved to:    {model_path}")
    print(f"  Scaler saved to:   {scaler_path}")
    print(f"  Metadata saved to: {meta_path}")
    print(f"\nDone. Best model: {best_name} with F1(macro)={best_f1:.4f}")


if __name__ == "__main__":
    main()
