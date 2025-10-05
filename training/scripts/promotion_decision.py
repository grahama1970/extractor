#!/usr/bin/env python3
"""
promotion_decision.py

Compares a new calibrator metrics.json to a previous one and decides if promotion is warranted.

Rules (default):
- Promote if holdout AUC improves >= 0.01 OR holdout Brier improves (old - new)/old >= 0.05
- AND new holdout accuracy >= old accuracy - 0.01
- Minimum holdout samples threshold enforced (>= 30 unless --force)
"""

from __future__ import annotations
import json, argparse
from pathlib import Path


def load_metrics(p: str):
    return json.loads(Path(p).read_text())


def main(args):
    new = load_metrics(args.new)
    old = load_metrics(args.old) if args.old else None

    if old is None:
        print("No previous metrics provided—auto-promote (bootstrap).\nPROMOTE=1")
        return

    h_new = new.get("holdout_metrics") or {}
    h_old = old.get("holdout_metrics") or {}
    ds_new = new.get("dataset") or {}

    if not args.force and int(ds_new.get("holdout_samples", 0) or 0) < args.min_holdout:
        print("Insufficient holdout samples for promotion.\nPROMOTE=0")
        return

    auc_new, auc_old = h_new.get("auc"), h_old.get("auc")
    brier_new, brier_old = h_new.get("brier"), h_old.get("brier")
    acc_new, acc_old = h_new.get("accuracy"), h_old.get("accuracy")

    if None in (auc_new, auc_old, brier_new, brier_old, acc_new, acc_old):
        print("Missing metrics—cannot compare reliably.\nPROMOTE=0")
        return

    auc_gain = float(auc_new) - float(auc_old)
    brier_gain = (float(brier_old) - float(brier_new)) / float(brier_old) if float(brier_old) else 0.0
    acc_drop = float(acc_old) - float(acc_new)

    promote = False
    if auc_gain >= args.min_auc_gain or brier_gain >= args.min_brier_gain:
        if acc_drop <= args.max_accuracy_drop:
            promote = True

    decision = {"auc_gain": auc_gain, "brier_gain": brier_gain, "acc_drop": acc_drop, "promote": int(promote)}
    print(json.dumps(decision, indent=2))
    print(f"PROMOTE={int(promote)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True, help="Path to new metrics.json")
    ap.add_argument("--old", help="Path to previous metrics.json")
    ap.add_argument("--min-holdout", type=int, default=30)
    ap.add_argument("--min-auc-gain", type=float, default=0.01)
    ap.add_argument("--min-brier-gain", type=float, default=0.05)
    ap.add_argument("--max-accuracy-drop", type=float, default=0.01)
    ap.add_argument("--force", action="store_true")
    main(ap.parse_args())

