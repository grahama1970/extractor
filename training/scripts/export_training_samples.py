#!/usr/bin/env python3
"""
export_training_samples.py

Transforms annotation events into calibrated training samples:
- Joins annotation events with recomputed or recorded feature snapshots.
- Validates against training sample schema.
- Deduplicates by sample_id, merges multiple events (keeps latest gold).
"""

from __future__ import annotations
import json, argparse, glob
from pathlib import Path
from typing import Dict, Any
import jsonschema

SCHEMA_EVENT = json.loads(Path("training/schemas/annotation_event.schema.json").read_text())
SCHEMA_SAMPLE = json.loads(Path("training/schemas/training_sample.schema.json").read_text())


def load_events(pattern: str):
    paths = glob.glob(pattern)
    for p in paths:
        with open(p, "r") as fh:
            for ln in fh:
                if ln.strip():
                    evt = json.loads(ln)
                    try:
                        jsonschema.validate(evt, SCHEMA_EVENT)
                        yield evt
                    except Exception as e:
                        print(f"[WARN] Skipping invalid annotation event: {e}")


def main(args):
    events = list(load_events(args.events))
    by_sample: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        if ev.get("object_type") != args.object_type:
            continue
        gl = ev.get("gold_label") or {}
        sample_id = f"{ev['doc_id']}:{ev['object_type']}:{ev['object_id']}"
        target = 1 if gl.get("structure_correct") else 0
        feat_snapshot = (
            ev.get("original_prediction", {}).get("feature_snapshot", {}) or {}
        )
        feats_hash = ev.get("original_prediction", {}).get("features_hash")
        existing = by_sample.get(sample_id, {})
        merged = {
            "sample_id": sample_id,
            "object_type": ev["object_type"],
            "target": target,
            "aux_targets": {"cell_accuracy": gl.get("cell_accuracy")},
            "features": feat_snapshot,
            "doc_metadata": {"doc_id": ev["doc_id"]},
            "model_versions": ev.get("model_versions") or {},
            "features_hash": feats_hash,
            "source_event_ids": list(set(existing.get("source_event_ids", []) + [ev["event_id"]])),
        }
        by_sample[sample_id] = merged

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        count = 0
        for sample in by_sample.values():
            try:
                jsonschema.validate(sample, SCHEMA_SAMPLE)
                fh.write(json.dumps(sample) + "\n")
                count += 1
            except Exception as e:
                print(f"[WARN] Skipping invalid training sample: {e}")
    print(f"Wrote {count} samples to {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="annotation_events/events.jsonl")
    ap.add_argument("--object-type", default="table")
    ap.add_argument("--out", default="training/derived/table_samples.jsonl")
    main(ap.parse_args())

