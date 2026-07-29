#!/usr/bin/env python3
"""Train binary classifiers for OCR fragmentation repair detection (v4).

Strategy shift: instead of default threshold, optimize the decision threshold
per model to maximize F1 on a validation set. Also tries threshold tuning
for best precision at >= 50% recall.
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

DATA_PATH = os.environ.get(
    "FRAGMENTATION_FEATURES_PATH",
    str(
        Path.home()
        / "workspace/experiments/pi-mono/.pi/skills/create-table-classifier/data/fragmentation_features.jsonl"
    ),
)
MODEL_DIR = os.environ.get(
    "FRAGMENTATION_MODEL_DIR",
    str(
        Path.home()
        / "workspace/experiments/pi-mono/.pi/skills/create-table-classifier/models/fragmentation-repair"
    ),
)

NUMERIC_FEATURES = [
    "cell_len", "num_spaces", "num_words", "left_word_len", "right_word_len",
    "alpha_ratio", "has_space_in_middle", "is_uppercase", "has_underscore",
    "has_digit", "has_hyphen", "has_short_after_long", "has_unicode_math",
    "has_equals", "has_parens", "char_before_space_is_alpha",
    "char_after_space_is_alpha", "char_before_space_is_upper",
    "char_after_space_is_lower", "alpha_alpha_spaces",
]


def load_data():
    """Load JSON records from file, extracting numeric, text, and label features."""
    records = []
    with open(DATA_PATH) as f:
        for line in f:
            records.append(json.loads(line))
    X_num = np.array([[r[c] for c in NUMERIC_FEATURES] for r in records], dtype=np.float32)
    texts = [r["text"] for r in records]
    y = np.array([r["label"] for r in records], dtype=np.int32)
    return X_num, texts, y, records


def find_best_threshold(y_true, y_proba, min_recall=0.5):
    """Find threshold that maximizes F1, subject to recall >= min_recall."""
    from sklearn.metrics import f1_score, precision_score, recall_score
    best_f1 = 0
    best_thresh = 0.5
    best_prec = 0
    best_rec = 0
    for thresh in np.arange(0.05, 0.99, 0.01):
        y_pred = (y_proba >= thresh).astype(int)
        rec = recall_score(y_true, y_pred, zero_division=0)
        if rec < min_recall:
            continue
        f1 = f1_score(y_true, y_pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh
            best_prec = precision_score(y_true, y_pred, zero_division=0)
            best_rec = rec
    return best_thresh, best_f1, best_prec, best_rec


def main():
    """Run machine learning pipeline with stratified sampling and evaluation metrics."""
    from sklearn.model_selection import StratifiedShuffleSplit
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        classification_report, f1_score, precision_score, recall_score,
        average_precision_score,
    )
    from sklearn.preprocessing import StandardScaler
    from sklearn.feature_extraction.text import TfidfVectorizer
    from scipy.sparse import hstack, csr_matrix
    from imblearn.under_sampling import RandomUnderSampler
    from imblearn.over_sampling import SMOTE
    import joblib

    print("=" * 70)
    print("OCR Fragmentation Repair Classifier v4 - Threshold Optimized")
    print("=" * 70)

    X_num, texts, y, records = load_data()
    n_pos = int(y.sum())
    n_neg = int((y == 0).sum())
    print(f"\nDataset: {len(y)} samples (pos={n_pos}, neg={n_neg}, ratio=1:{n_neg // max(n_pos, 1)})")

    # Split: 60% train, 20% val (threshold tuning), 20% test
    sss1 = StratifiedShuffleSplit(n_splits=1, test_size=0.4, random_state=42)
    train_idx, valtest_idx = next(sss1.split(X_num, y))
    sss2 = StratifiedShuffleSplit(n_splits=1, test_size=0.5, random_state=42)
    val_idx_rel, test_idx_rel = next(sss2.split(X_num[valtest_idx], y[valtest_idx]))
    val_idx = valtest_idx[val_idx_rel]
    test_idx = valtest_idx[test_idx_rel]

    X_num_train, X_num_val, X_num_test = X_num[train_idx], X_num[val_idx], X_num[test_idx]
    texts_train = [texts[i] for i in train_idx]
    texts_val = [texts[i] for i in val_idx]
    texts_test = [texts[i] for i in test_idx]
    y_train_orig = y[train_idx]
    y_val = y[val_idx]
    y_test = y[test_idx]

    print(f"Train: {len(y_train_orig)} (pos={y_train_orig.sum()})")
    print(f"Val:   {len(y_val)} (pos={y_val.sum()})")
    print(f"Test:  {len(y_test)} (pos={y_test.sum()})")

    # TF-IDF
    print("\nBuilding TF-IDF...")
    tfidf = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(2, 4),
        max_features=2000, min_df=2, sublinear_tf=True,
    )
    X_tfidf_train = tfidf.fit_transform(texts_train)
    X_tfidf_val = tfidf.transform(texts_val)
    X_tfidf_test = tfidf.transform(texts_test)

    X_train_combined = hstack([csr_matrix(X_num_train), X_tfidf_train])
    X_val_combined = hstack([csr_matrix(X_num_val), X_tfidf_val])
    X_test_combined = hstack([csr_matrix(X_num_test), X_tfidf_test])

    # Resample training data
    n_pos_train = int(y_train_orig.sum())
    target_neg = n_pos_train * 10
    target_pos = target_neg // 3

    rus = RandomUnderSampler(sampling_strategy={0: target_neg, 1: n_pos_train}, random_state=42)
    X_under, y_under = rus.fit_resample(X_train_combined.toarray(), y_train_orig)

    smote = SMOTE(
        sampling_strategy={0: target_neg, 1: target_pos},
        random_state=42, k_neighbors=min(5, n_pos_train - 1),
    )
    X_train, y_train = smote.fit_resample(X_under, y_under)
    print(f"Resampled train: {len(y_train)} (pos={y_train.sum()}, neg={(y_train == 0).sum()})")

    X_val_dense = X_val_combined.toarray()
    X_test_dense = X_test_combined.toarray()

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val_dense)
    X_test_scaled = scaler.transform(X_test_dense)

    neg_c = (y_train == 0).sum()
    pos_c = y_train.sum()
    scale_pos = neg_c / max(pos_c, 1)

    models = {
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            min_samples_leaf=3, subsample=0.8, random_state=42,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=500, max_depth=10, min_samples_leaf=2,
            class_weight="balanced", random_state=42, n_jobs=-1,
        ),
        "logistic_regression": LogisticRegression(
            class_weight="balanced", max_iter=2000, C=0.5, random_state=42,
        ),
    }

    results = {}
    best_f1 = -1
    best_name = None

    for name, clf in models.items():
        print(f"\n{'=' * 60}")
        print(f"Training: {name}")
        print(f"{'=' * 60}")

        if name == "gradient_boosting":
            sw = np.where(y_train == 1, scale_pos, 1.0)
            clf.fit(X_train_scaled, y_train, sample_weight=sw)
        else:
            clf.fit(X_train_scaled, y_train)

        # Get probabilities on val and test
        y_val_proba = clf.predict_proba(X_val_scaled)[:, 1]
        y_test_proba = clf.predict_proba(X_test_scaled)[:, 1]

        # Default threshold (0.5)
        y_pred_default = clf.predict(X_test_scaled)
        f1_default = f1_score(y_test, y_pred_default, zero_division=0)
        prec_default = precision_score(y_test, y_pred_default, zero_division=0)
        rec_default = recall_score(y_test, y_pred_default, zero_division=0)

        # Optimize threshold on validation set
        best_thresh, val_f1, val_prec, val_rec = find_best_threshold(y_val, y_val_proba, min_recall=0.4)

        # Apply optimized threshold on test set
        y_pred_opt = (y_test_proba >= best_thresh).astype(int)
        f1_opt = f1_score(y_test, y_pred_opt, zero_division=0)
        prec_opt = precision_score(y_test, y_pred_opt, zero_division=0)
        rec_opt = recall_score(y_test, y_pred_opt, zero_division=0)
        ap = average_precision_score(y_test, y_test_proba) if y_test.sum() > 0 else 0.0

        tp = int(((y_pred_opt == 1) & (y_test == 1)).sum())
        fp = int(((y_pred_opt == 1) & (y_test == 0)).sum())
        fn = int(((y_pred_opt == 0) & (y_test == 1)).sum())

        print(f"\n  Default threshold (0.5):")
        print(f"    F1={f1_default:.4f}  Prec={prec_default:.4f}  Rec={rec_default:.4f}")
        print(f"\n  Optimized threshold ({best_thresh:.2f}) [tuned on val, min_recall=40%]:")
        print(f"    Val:  F1={val_f1:.4f}  Prec={val_prec:.4f}  Rec={val_rec:.4f}")
        print(f"    Test: F1={f1_opt:.4f}  Prec={prec_opt:.4f}  Rec={rec_opt:.4f}  AP={ap:.4f}")
        print(f"    TP={tp}  FP={fp}  FN={fn}")
        print(classification_report(
            y_test, y_pred_opt,
            target_names=["no_change", "should_merge"],
            zero_division=0,
        ))

        results[name] = {
            "f1": f1_opt, "precision": prec_opt, "recall": rec_opt,
            "avg_precision": ap, "threshold": float(best_thresh),
            "f1_default": f1_default, "precision_default": prec_default,
            "recall_default": rec_default,
            "model": clf, "tp": tp, "fp": fp, "fn": fn,
        }

        if f1_opt > best_f1:
            best_f1 = f1_opt
            best_name = name

    # ── Summary ────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("RESULTS SUMMARY (threshold-optimized)")
    print(f"{'=' * 70}")
    print(f"{'Model':<25} {'Thresh':>6} {'F1':>8} {'Prec':>8} {'Recall':>8} {'AP':>8}  {'TP':>4} {'FP':>5} {'FN':>4}")
    print("-" * 85)
    for name, r in results.items():
        marker = " *" if name == best_name else ""
        print(f"{name:<25} {r['threshold']:>6.2f} {r['f1']:>8.4f} {r['precision']:>8.4f} {r['recall']:>8.4f} {r['avg_precision']:>8.4f}  {r['tp']:>4} {r['fp']:>5} {r['fn']:>4}{marker}")

    print(f"\nComparison: default threshold (0.5)")
    print(f"{'Model':<25} {'F1':>8} {'Prec':>8} {'Recall':>8}")
    print("-" * 55)
    for name, r in results.items():
        print(f"{name:<25} {r['f1_default']:>8.4f} {r['precision_default']:>8.4f} {r['recall_default']:>8.4f}")

    # ── Save ───────────────────────────────────────────────────────
    os.makedirs(MODEL_DIR, exist_ok=True)
    best_clf = results[best_name]["model"]

    joblib.dump(best_clf, os.path.join(MODEL_DIR, "best_model.joblib"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, "scaler.joblib"))
    joblib.dump(tfidf, os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib"))

    for name, r in results.items():
        joblib.dump(r["model"], os.path.join(MODEL_DIR, f"{name}.joblib"))

    meta = {
        "model_type": best_name,
        "decision_threshold": results[best_name]["threshold"],
        "numeric_features": NUMERIC_FEATURES,
        "tfidf_params": {
            "analyzer": "char_wb", "ngram_range": [2, 4],
            "max_features": 2000, "min_df": 2,
        },
        "best_metrics": {
            "f1": results[best_name]["f1"],
            "precision": results[best_name]["precision"],
            "recall": results[best_name]["recall"],
            "avg_precision": results[best_name]["avg_precision"],
        },
        "training_stats": {
            "total_samples": int(len(y)),
            "positive_samples": n_pos,
            "negative_samples": n_neg,
            "train_size_original": int(len(y_train_orig)),
            "train_size_resampled": int(len(y_train)),
            "val_size": int(len(y_val)),
            "test_size": int(len(y_test)),
            "resampling": "undersample_10:1_then_SMOTE_3:1",
        },
        "all_model_results": {
            name: {k: v for k, v in r.items() if k != "model"}
            for name, r in results.items()
        },
    }

    with open(os.path.join(MODEL_DIR, "model_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nBest model ({best_name}, threshold={results[best_name]['threshold']:.2f}) saved to {MODEL_DIR}/")

    # Feature importances
    if hasattr(best_clf, "feature_importances_"):
        feat_names = NUMERIC_FEATURES + list(tfidf.get_feature_names_out())
        importances = best_clf.feature_importances_
        sorted_idx = np.argsort(importances)[::-1][:15]
        print(f"\nTop 15 features ({best_name}):")
        for i in sorted_idx:
            bar = "#" * int(importances[i] * 80)
            print(f"  {feat_names[i]:<35} {importances[i]:.4f}  {bar}")


if __name__ == "__main__":
    main()
