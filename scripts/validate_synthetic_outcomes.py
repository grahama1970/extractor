#!/usr/bin/env python3
"""Validate strategy outcomes from synthetic PDFs against ground truth manifest.

Compares the actual_best strategy chosen by S05 against the expected_strategy_family
from the synthetic manifest. This is the key validation: synthetic PDFs have known
table structures, so we can measure whether the pipeline chooses the right strategy.

Usage:
    python scripts/validate_synthetic_outcomes.py [--verbose]
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "data" / "pdfs" / "synthetic" / "manifest.jsonl"
OUTPUT_BASE = Path(__file__).resolve().parent.parent / "data" / "output" / "synthetic_validation"


def load_manifest() -> dict:
    """Load manifest, keyed by filename stem."""
    manifest = {}
    for line in MANIFEST_PATH.read_text().strip().splitlines():
        rec = json.loads(line)
        stem = Path(rec["filename"]).stem
        manifest[stem] = rec
    return manifest


def load_outcomes() -> dict:
    """Load strategy outcomes from all extraction runs.

    Returns dict keyed by pdf_stem → list of page outcomes.
    """
    outcomes = defaultdict(list)
    for outcome_file in sorted(OUTPUT_BASE.glob("**/05_strategy_outcomes.jsonl")):
        # Derive pdf_stem from dir structure
        pdf_stem = outcome_file.parent.name
        for parent in outcome_file.parents:
            if parent.name == "05_table_extractor":
                pdf_stem = parent.parent.name
                break
        for line in outcome_file.read_text().strip().splitlines():
            if line.strip():
                outcomes[pdf_stem].append(json.loads(line))
    return dict(outcomes)


def strategy_to_family(strategy: str, actual_flavor: str = None) -> str:
    """Map a specific strategy to its family (lattice or stream).

    Uses actual_flavor field when available (emitted by S05 fix) to correctly
    classify agent_tuned/memory_learned by their Camelot flavor.
    """
    if actual_flavor:
        if "lattice" in actual_flavor:
            return "lattice"
        elif "stream" in actual_flavor:
            return "stream"
    if strategy.startswith("lattice"):
        return "lattice"
    elif strategy.startswith("stream"):
        return "stream"
    elif strategy in ("agent_tuned", "memory_learned"):
        # These are meta-strategies — check page_stats in caller
        return "unknown"
    return "unknown"


def border_style_to_family(border_style: str) -> str:
    """Derive expected strategy family from border style."""
    # Tables without internal grid lines → stream (Camelot lattice needs cell borders)
    stream_styles = {
        "borderless_plain", "borderless_topbot", "borderless_shaded",
        "borderless_zebra", "horizontal_only", "box_only",
    }
    if border_style in stream_styles:
        return "stream"
    return "lattice"


def get_expected_families(gt: dict) -> list:
    """Get expected strategy families for a manifest record.

    Single-table PDFs have 'expected_strategy_family'.
    Multi-table (mixed) PDFs have 'border_styles' array — derive per-table.
    """
    if "expected_strategy_family" in gt:
        return [gt["expected_strategy_family"]]
    if "border_styles" in gt:
        return [border_style_to_family(bs) for bs in gt["border_styles"]]
    return []


def main():
    """Run main application, loading data and reporting counts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest()
    outcomes = load_outcomes()

    print(f"Manifest: {len(manifest)} PDFs")
    print(f"Extracted: {len(outcomes)} PDFs with outcomes")
    print()

    if not outcomes:
        print("No outcomes found yet. Batch extraction still running?")
        sys.exit(0)

    # Compare
    correct = 0
    incorrect = 0
    unknown = 0
    total = 0
    skipped_mixed = 0

    mismatches = []
    agent_hint_overrides = 0  # agent_tuned/memory_learned bypassed prediction
    family_confusion = Counter()  # (expected, actual) pairs
    style_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})
    merge_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})
    domain_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})

    for pdf_stem, page_outcomes in outcomes.items():
        if pdf_stem not in manifest:
            continue

        gt = manifest[pdf_stem]
        expected_families = get_expected_families(gt)
        is_mixed = gt.get("table_style") == "mixed"

        if not expected_families:
            continue

        for page_outcome in page_outcomes:
            actual_best = page_outcome.get("actual_best", "")
            # Use actual_flavor field (emitted by S05 fix) when available
            actual_flavor = page_outcome.get("actual_flavor")
            actual_family = strategy_to_family(actual_best, actual_flavor)

            total += 1

            # Track when agent_tuned/memory_learned overrode the prediction
            if actual_best in ("agent_tuned", "memory_learned"):
                predicted = page_outcome.get("predicted_strategy", "")
                if strategy_to_family(predicted) != "unknown":
                    agent_hint_overrides += 1

            if actual_family == "unknown":
                # For pre-fix outcomes without actual_flavor:
                # Infer from S00 table_style — meta-strategies on bordered tables
                # used lattice flavor, borderless tables used stream flavor.
                # The S05 logging bug (stream_found hardcoded for meta-strategies)
                # makes page_stats unreliable for pre-fix outcomes.
                s00_style = page_outcome.get("s00_table_style", "")
                if actual_best in ("agent_tuned", "memory_learned") and s00_style == "bordered":
                    actual_family = "lattice"
                elif actual_best in ("agent_tuned", "memory_learned") and s00_style == "borderless":
                    actual_family = "stream"
                else:
                    # Fall back to page_stats
                    ps = page_outcome.get("page_stats", {})
                    if ps.get("lattice_found", 0) > 0 and ps.get("stream_found", 0) == 0:
                        actual_family = "lattice"
                    elif ps.get("stream_found", 0) > 0 and ps.get("lattice_found", 0) == 0:
                        actual_family = "stream"
                    else:
                        unknown += 1
                        continue

            # For mixed PDFs, accept if actual matches ANY expected family
            if is_mixed:
                expected_family = "mixed"
                is_correct = actual_family in set(expected_families)
            else:
                expected_family = expected_families[0]
                is_correct = actual_family == expected_family

            if is_correct:
                correct += 1
            else:
                incorrect += 1
                border_style = gt.get("border_style", ",".join(gt.get("border_styles", [])))
                merge_pattern = gt.get("merge_pattern", ",".join(gt.get("merge_patterns", [])))
                mismatches.append({
                    "pdf": pdf_stem,
                    "page": page_outcome.get("page_num"),
                    "expected": expected_family,
                    "actual_strategy": actual_best,
                    "actual_family": actual_family,
                    "s00_style": page_outcome.get("s00_table_style"),
                    "border_style": border_style,
                    "merge_pattern": merge_pattern,
                })

            family_confusion[(expected_family, actual_family)] += 1

            # Per-dimension accuracy
            style_accuracy[gt["table_style"]]["total"] += 1
            style_accuracy[gt["table_style"]]["correct"] += int(is_correct)
            merge_pat = gt.get("merge_pattern", "mixed")
            merge_accuracy[merge_pat]["total"] += 1
            merge_accuracy[merge_pat]["correct"] += int(is_correct)
            domain_accuracy[gt["domain"]]["total"] += 1
            domain_accuracy[gt["domain"]]["correct"] += int(is_correct)

    # Print results
    print("=" * 60)
    print("STRATEGY FAMILY ACCURACY (lattice vs stream)")
    print("=" * 60)
    accuracy = correct / total * 100 if total else 0
    print(f"  Correct:  {correct}/{total} ({accuracy:.1f}%)")
    print(f"  Wrong:    {incorrect}/{total}")
    print(f"  Unknown:  {unknown}/{total}")
    print(f"  Agent hint overrides: {agent_hint_overrides} (agent_tuned/memory_learned bypassed prediction)")
    print()

    print("Confusion matrix (expected → actual):")
    for (exp, act), count in sorted(family_confusion.items()):
        marker = "OK" if exp == act else "MISS"
        print(f"  {exp:>10} → {act:<10}: {count:4d}  [{marker}]")
    print()

    print("Accuracy by table style:")
    for style, stats in sorted(style_accuracy.items()):
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] else 0
        print(f"  {style:>12}: {stats['correct']}/{stats['total']} ({acc:.1f}%)")
    print()

    print("Accuracy by merge pattern:")
    for pat, stats in sorted(merge_accuracy.items()):
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] else 0
        print(f"  {pat:>15}: {stats['correct']}/{stats['total']} ({acc:.1f}%)")
    print()

    print("Accuracy by domain:")
    for dom, stats in sorted(domain_accuracy.items()):
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] else 0
        print(f"  {dom:>12}: {stats['correct']}/{stats['total']} ({acc:.1f}%)")
    print()

    if args.verbose and mismatches:
        print("MISMATCHES (expected family != actual family):")
        for m in mismatches[:20]:
            print(f"  {m['pdf']} p{m['page']}: expected={m['expected']}, "
                  f"got={m['actual_strategy']} ({m['actual_family']}), "
                  f"s00_style={m['s00_style']}, border={m['border_style']}")
        if len(mismatches) > 20:
            print(f"  ... and {len(mismatches) - 20} more")

    # Write summary JSON
    summary = {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "unknown": unknown,
        "agent_hint_overrides": agent_hint_overrides,
        "accuracy": accuracy,
        "n_pdfs_extracted": len(outcomes),
        "n_pdfs_in_manifest": len(manifest),
        "style_accuracy": {k: v["correct"] / v["total"] * 100 for k, v in style_accuracy.items() if v["total"]},
        "merge_accuracy": {k: v["correct"] / v["total"] * 100 for k, v in merge_accuracy.items() if v["total"]},
        "domain_accuracy": {k: v["correct"] / v["total"] * 100 for k, v in domain_accuracy.items() if v["total"]},
    }
    summary_path = OUTPUT_BASE / "validation_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
