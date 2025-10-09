#!/usr/bin/env python3
"""
train_table_calibrator.py

Trains a calibrated binary classifier for table structural correctness.
"""

from __future__ import annotations
import json, argparse, os, random
from pathlib import Path
from typing import List
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score

FEATURE_ORDER_DEFAULT = [
  "fragmentation",
  "header_jaccard_max",
  "numeric_stability",
  "row_count",
  "col_count",
  "strategy_diversity",
  "merge_type_header_body",
  "foreign_numeric_ratio",
]


def load_samples(path: str):
    X, y, doc_ids = [], [], []
    with open(path, "r") as fh:
        for ln in fh:
            obj = json.loads(ln)
            feats = obj["features"]
            vec = [feats.get(f, 0) for f in FEATURE_ORDER_DEFAULT]
            X.append(vec)
            y.append(obj["target"])
            doc_ids.append(obj.get("doc_metadata", {}).get("doc_id", ""))
    return np.array(X), np.array(y), doc_ids


def doc_level_split(doc_ids: List[str], test_ratio=0.2, seed=42):
    unique = list(sorted(set(doc_ids)))
    random.Random(seed).shuffle(unique)
    split = int(len(unique) * (1 - test_ratio))
    if split <= 0:
        return set(unique), set()
    train_docs = set(unique[:split])
    hold_docs = set(unique[split:])
    return train_docs, hold_docs


def reliability_curve(y_true, y_prob, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    curve = []
    for i in range(bins):
        lo, hi = edges[i], edges[i+1]
        mask = (y_prob >= lo) & (y_prob < hi) if i < bins - 1 else (y_prob >= lo) & (y_prob <= hi)
        if mask.sum() == 0:
            curve.append({"bin": i, "range": [float(lo), float(hi)], "count": 0, "empirical": None})
        else:
            emp = float(y_true[mask].mean())
            curve.append({"bin": i, "range": [float(lo), float(hi)], "count": int(mask.sum()), "empirical": emp})
    return curve


def main(args):
    X, y, doc_ids = load_samples(args.samples)
    if len(y) < 20:
        raise SystemExit("Not enough samples (<20) to train calibrator.")
    train_docs, hold_docs = doc_level_split(doc_ids, test_ratio=0.2, seed=args.seed)
    train_mask = np.array([d in train_docs for d in doc_ids])
    hold_mask = ~train_mask if len(hold_docs) > 0 else np.array([False]*len(doc_ids))

    X_train, y_train = X[train_mask], y[train_mask]
    X_hold, y_hold = (X[hold_mask], y[hold_mask]) if hold_mask.any() else (np.array([]), np.array([]))

    base = LogisticRegression(max_iter=400, class_weight="balanced")
    clf = CalibratedClassifierCV(base, cv=5, method="isotonic")
    clf.fit(X_train, y_train)
    prob_train = clf.predict_proba(X_train)[:, 1]
    if len(y_hold) > 0:
        prob_hold = clf.predict_proba(X_hold)[:, 1]
    else:
        prob_hold = np.array([])

    metrics = {
        "dataset": {
            "train_samples": int(len(y_train)),
            "holdout_samples": int(len(y_hold)),
        },
        "train_metrics": {
            "auc": float(roc_auc_score(y_train, prob_train)),
            "brier": float(brier_score_loss(y_train, prob_train)),
            "accuracy": float(accuracy_score(y_train, (prob_train >= 0.5).astype(int))),
        },
        "holdout_metrics": {
            "auc": float(roc_auc_score(y_hold, prob_hold)) if len(y_hold) > 0 else None,
            "brier": float(brier_score_loss(y_hold, prob_hold)) if len(y_hold) > 0 else None,
            "accuracy": float(accuracy_score(y_hold, (prob_hold >= 0.5).astype(int))) if len(y_hold) > 0 else None,
        },
        "reliability_curve": reliability_curve(y_hold, prob_hold) if len(y_hold) > 0 else [],
        "feature_order": FEATURE_ORDER_DEFAULT,
        "model_hash": None,
        "git_commit": os.getenv("EXTRACTOR_GIT_COMMIT"),
        "schema_version": "table_calibrator_metrics@1.0.0",
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    import pickle, hashlib
    model_blob = {
        "model": clf,
        "feature_order": FEATURE_ORDER_DEFAULT,
        "created": args.version,
        "git_commit": metrics["git_commit"],
    }
    model_path = out_dir / "model.pkl"
    with open(model_path, "wb") as fh:
        pickle.dump(model_blob, fh)
    metrics["model_hash"] = "sha256:" + hashlib.sha256(model_path.read_bytes()).hexdigest()

    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "feature_order.json").write_text(json.dumps(FEATURE_ORDER_DEFAULT, indent=2), encoding="utf-8")
    print("Saved model + metrics to", out_dir)
    print(json.dumps(metrics.get("holdout_metrics"), indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default="training/derived/table_samples.jsonl")
    ap.add_argument("--out-dir", default="training/models/table_calibrator/2025.10.0")
    ap.add_argument("--version", default="2025.10.0")
    ap.add_argument("--seed", type=int, default=42)
    main(ap.parse_args())

