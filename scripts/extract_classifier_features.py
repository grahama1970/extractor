#!/usr/bin/env python3
"""Extract features from PDFs for classifier training.

Creates features.parquet and labels.jsonl for training a PDF extraction
classifier that predicts:
- CLEAN: Will extract perfectly
- FIXABLE: Known patterns, auto-fix available
- PROBLEMATIC: Needs manual review
- ADVERSARIAL: Edge case for test corpus

Usage:
    python scripts/extract_classifier_features.py \
        --corpus /mnt/storage12tb/extractor_corpus \
        --output /mnt/storage12tb/extractor_corpus/classifier
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def extract_pdf_features(pdf_path: Path) -> dict[str, Any]:
    """Extract features from a PDF for classification."""
    features = {
        "path": str(pdf_path),
        "file_size_kb": pdf_path.stat().st_size / 1024,
        "page_count": 0,
        "avg_chars_per_page": 0,
        "font_count": 0,
        "image_count": 0,
        "table_candidates": 0,  # Lines that look like table separators
        "unicode_complexity": 0,  # Non-ASCII character ratio
        "multi_column_likely": False,
        "has_toc": False,
        "avg_block_count": 0,
    }

    try:
        doc = fitz.open(pdf_path)
        features["page_count"] = len(doc)

        fonts = set()
        total_chars = 0
        total_unicode = 0
        total_images = 0
        total_blocks = 0
        table_lines = 0
        column_widths = []

        for page in doc:
            # Text analysis
            text = page.get_text()
            total_chars += len(text)
            total_unicode += sum(1 for c in text if ord(c) > 127)

            # Font analysis
            for font in page.get_fonts():
                fonts.add(font[3])  # Font name

            # Image analysis
            total_images += len(page.get_images())

            # Block analysis
            blocks = page.get_text("dict")["blocks"]
            total_blocks += len(blocks)

            # Column detection (simple heuristic)
            if blocks:
                x_positions = [b["bbox"][0] for b in blocks if b.get("type") == 0]
                if x_positions:
                    unique_x = len(set(round(x / 50) for x in x_positions))
                    if unique_x >= 2:
                        column_widths.append(unique_x)

            # Table line detection (horizontal/vertical lines)
            drawings = page.get_drawings()
            for d in drawings:
                if d.get("type") in ("l", "re"):  # line or rectangle
                    table_lines += 1

        # Compute aggregates
        features["font_count"] = len(fonts)
        features["image_count"] = total_images
        features["avg_chars_per_page"] = total_chars / max(1, features["page_count"])
        features["unicode_complexity"] = total_unicode / max(1, total_chars)
        features["avg_block_count"] = total_blocks / max(1, features["page_count"])
        features["table_candidates"] = table_lines
        features["multi_column_likely"] = any(w >= 2 for w in column_widths)
        features["has_toc"] = bool(doc.get_toc())

        doc.close()

    except Exception as e:
        log.warning(f"Failed to extract features from {pdf_path}: {e}")
        features["error"] = str(e)

    return features


def load_batch_results(results_dir: Path) -> dict[str, dict]:
    """Load extraction results from batch_summary.jsonl."""
    results = {}
    summary_file = results_dir / "batch_summary.jsonl"

    if summary_file.exists():
        with open(summary_file) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    results[entry["pdf"]] = entry

    return results


def derive_label(result: dict) -> str:
    """Derive classification label from extraction result."""
    if result.get("status") != "SUCCESS":
        return "ADVERSARIAL"

    quality = result.get("quality", "UNKNOWN")
    tables = result.get("tables", "UNKNOWN")
    figures = result.get("figures", "UNKNOWN")

    if quality == "REASONABLE" and tables == "OK" and figures == "OK":
        return "CLEAN"
    elif quality == "REVIEW_REQUIRED" and tables == "UNDER_EXTRACTED":
        return "FIXABLE"  # Table extraction needs improvement
    elif quality == "REVIEW_REQUIRED":
        return "PROBLEMATIC"
    else:
        return "UNKNOWN"


def main():
    parser = argparse.ArgumentParser(description="Extract PDF features for classifier training")
    parser.add_argument("--corpus", type=Path, required=True, help="Corpus directory")
    parser.add_argument("--output", type=Path, required=True, help="Output directory for features")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    # Load batch results for labels
    results = load_batch_results(args.corpus / "results")
    log.info(f"Loaded {len(results)} batch results")

    # Find all PDFs
    pdfs = list(args.corpus.glob("**/*.pdf"))
    log.info(f"Found {len(pdfs)} PDFs in corpus")

    # Extract features
    features_list = []
    labels_list = []

    for pdf in pdfs:
        rel_path = str(pdf.relative_to(args.corpus))

        # Skip intermediate results
        if "results/" in rel_path and "_clean.pdf" in rel_path:
            continue

        log.info(f"Processing: {rel_path}")
        features = extract_pdf_features(pdf)

        # Get label from results if available
        label = "UNKNOWN"
        if rel_path in results:
            label = derive_label(results[rel_path])

        features["label"] = label
        features_list.append(features)
        labels_list.append({"path": rel_path, "label": label})

    # Save features as JSON (can convert to parquet later)
    features_file = args.output / "features.json"
    with open(features_file, "w") as f:
        json.dump(features_list, f, indent=2)
    log.info(f"Saved features to {features_file}")

    # Save labels
    labels_file = args.output / "labels.jsonl"
    with open(labels_file, "w") as f:
        for entry in labels_list:
            f.write(json.dumps(entry) + "\n")
    log.info(f"Saved labels to {labels_file}")

    # Summary
    from collections import Counter

    label_counts = Counter(e["label"] for e in labels_list)
    log.info("Label distribution:")
    for label, count in label_counts.most_common():
        log.info(f"  {label}: {count}")


if __name__ == "__main__":
    main()
