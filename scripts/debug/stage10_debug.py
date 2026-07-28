#!/usr/bin/env python3
"""Tiny debug runner for Stage 10 (pure Python import-and-call).

Usage (example):
  python scripts/debug/stage10_debug.py \
    --reflowed data/results/pipeline/07_reflow_section/json_output/07_reflowed.json \
    --summaries data/results/pipeline/09_section_summarizer/json_output/09_summaries.json \
    --out data/results/pipeline --skip-export
"""
import argparse
from pathlib import Path
from extractor.pipeline.steps import s10_arangodb_exporter as s10


def main():
    """Parse command-line arguments for the pipeline configuration."""
    p = argparse.ArgumentParser()
    p.add_argument("--reflowed", required=True, type=Path)
    p.add_argument("--summaries", required=True, type=Path)
    p.add_argument("--out", required=False, default=Path("data/results/pipeline"), type=Path)
    p.add_argument("--collection", default="pdf_objects")
    p.add_argument("--skip-export", action="store_true")
    p.add_argument("--skip-embeddings", action="store_true")
    p.add_argument("--fast-embeddings", action="store_true")
    args = p.parse_args()

    s10.run(
        reflowed_json=args.reflowed,
        summaries_json=args.summaries,
        output_dir=args.out,
        collection_name=args.collection,
        skip_export=args.skip_export,
        skip_embeddings=args.skip_embeddings,
        fast_embeddings=args.fast_embeddings,
    )


if __name__ == "__main__":
    main()
