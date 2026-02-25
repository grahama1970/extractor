#!/usr/bin/env python3
"""Continuous failure pattern collector for PDF extraction hardening.

Monitors extraction results and collects failure patterns for:
1. Training the classifier model
2. Storing in memory for future recall
3. Prioritizing fixes based on frequency

This is the foundation of the continuous learning service.

Usage:
    # Run once to analyze current results
    python scripts/failure_collector.py --corpus /mnt/storage12tb/extractor_corpus

    # Watch mode (daemon) - continuously monitors for new results
    python scripts/failure_collector.py --corpus /mnt/storage12tb/extractor_corpus --watch
"""

import argparse
import json
import logging
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)


class FailureCollector:
    """Collects and categorizes extraction failures."""

    # Known failure patterns to detect
    PATTERNS = {
        "table_under_extraction": {
            "indicator": lambda r: r.get("tables") == "UNDER_EXTRACTED",
            "severity": "HIGH",
            "fix_hint": "Camelot/PyMuPDF table detection threshold may need adjustment",
        },
        "figure_under_extraction": {
            "indicator": lambda r: r.get("figures") == "UNDER_EXTRACTED",
            "severity": "MEDIUM",
            "fix_hint": "Image extraction boundaries need refinement",
        },
        "quality_review_required": {
            "indicator": lambda r: r.get("quality") == "REVIEW_REQUIRED",
            "severity": "MEDIUM",
            "fix_hint": "Multiple issues detected - check individual stages",
        },
        "extraction_failed": {
            "indicator": lambda r: r.get("status") == "FAILED",
            "severity": "CRITICAL",
            "fix_hint": "Pipeline crashed - check error logs",
        },
        "symbol_fonts": {
            "indicator": lambda r: r.get("pdf", "").endswith(".pdf"),  # Check content for \\uf0
            "severity": "HIGH",
            "fix_hint": "Unicode normalization needed for symbol fonts",
        },
    }

    def __init__(self, corpus_dir: Path):
        self.corpus_dir = corpus_dir
        self.results_dir = corpus_dir / "results"
        self.patterns_file = corpus_dir / "failure_patterns.json"
        self.patterns: dict[str, list] = defaultdict(list)

    def load_batch_results(self) -> list[dict]:
        """Load all batch results."""
        results = []
        summary_file = self.results_dir / "batch_summary.jsonl"

        if summary_file.exists():
            with open(summary_file) as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))

        return results

    def analyze_result(self, result: dict) -> list[str]:
        """Detect patterns in a single result."""
        detected = []

        for pattern_name, pattern_def in self.PATTERNS.items():
            try:
                if pattern_def["indicator"](result):
                    detected.append(pattern_name)
            except Exception:
                pass

        return detected

    def collect_patterns(self) -> dict[str, Any]:
        """Collect all failure patterns from batch results."""
        results = self.load_batch_results()
        log.info(f"Analyzing {len(results)} extraction results")

        pattern_counts = Counter()
        pattern_examples: dict[str, list] = defaultdict(list)

        for result in results:
            detected = self.analyze_result(result)
            for pattern in detected:
                pattern_counts[pattern] += 1
                if len(pattern_examples[pattern]) < 10:  # Keep top 10 examples
                    pattern_examples[pattern].append({
                        "pdf": result.get("pdf"),
                        "quality": result.get("quality"),
                        "tables": result.get("tables"),
                        "figures": result.get("figures"),
                    })

        # Build report
        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_results": len(results),
            "patterns": {},
        }

        for pattern_name, count in pattern_counts.most_common():
            pattern_def = self.PATTERNS.get(pattern_name, {})
            report["patterns"][pattern_name] = {
                "count": count,
                "percentage": round(100 * count / len(results), 1) if results else 0,
                "severity": pattern_def.get("severity", "UNKNOWN"),
                "fix_hint": pattern_def.get("fix_hint", ""),
                "examples": pattern_examples[pattern_name],
            }

        return report

    def save_patterns(self, report: dict):
        """Save patterns to JSON file."""
        with open(self.patterns_file, "w") as f:
            json.dump(report, f, indent=2)
        log.info(f"Saved patterns to {self.patterns_file}")

    def print_report(self, report: dict):
        """Print human-readable report."""
        print("\n" + "=" * 60)
        print("FAILURE PATTERN ANALYSIS")
        print("=" * 60)
        print(f"Total documents: {report['total_results']}")
        print(f"Analysis time: {report['timestamp']}")
        print()

        if not report["patterns"]:
            print("No failure patterns detected!")
            return

        print("Patterns found (sorted by frequency):")
        print("-" * 60)

        for pattern_name, data in sorted(
            report["patterns"].items(),
            key=lambda x: x[1]["count"],
            reverse=True
        ):
            severity_color = {
                "CRITICAL": "🔴",
                "HIGH": "🟠",
                "MEDIUM": "🟡",
                "LOW": "🟢",
            }.get(data["severity"], "⚪")

            print(f"\n{severity_color} {pattern_name}")
            print(f"   Count: {data['count']} ({data['percentage']}%)")
            print(f"   Fix hint: {data['fix_hint']}")

            if data["examples"]:
                print("   Examples:")
                for ex in data["examples"][:3]:
                    print(f"     - {ex['pdf']}")

        print("\n" + "=" * 60)

    def generate_fix_priority(self, report: dict) -> list[dict]:
        """Generate prioritized list of fixes to implement."""
        priority_list = []

        severity_weight = {"CRITICAL": 100, "HIGH": 50, "MEDIUM": 20, "LOW": 5}

        for pattern_name, data in report["patterns"].items():
            score = data["count"] * severity_weight.get(data["severity"], 1)
            priority_list.append({
                "pattern": pattern_name,
                "score": score,
                "count": data["count"],
                "severity": data["severity"],
                "fix_hint": data["fix_hint"],
            })

        priority_list.sort(key=lambda x: x["score"], reverse=True)
        return priority_list

    def watch(self, interval: int = 60):
        """Watch mode - continuously monitor for new results."""
        log.info(f"Starting watch mode (checking every {interval}s)")
        last_count = 0

        while True:
            results = self.load_batch_results()
            current_count = len(results)

            if current_count > last_count:
                log.info(f"New results detected: {current_count - last_count} new")
                report = self.collect_patterns()
                self.save_patterns(report)
                self.print_report(report)
                last_count = current_count

            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Collect PDF extraction failure patterns")
    parser.add_argument("--corpus", type=Path, required=True, help="Corpus directory")
    parser.add_argument("--watch", action="store_true", help="Watch mode - continuous monitoring")
    parser.add_argument("--interval", type=int, default=60, help="Watch interval in seconds")
    args = parser.parse_args()

    collector = FailureCollector(args.corpus)

    if args.watch:
        collector.watch(args.interval)
    else:
        report = collector.collect_patterns()
        collector.save_patterns(report)
        collector.print_report(report)

        # Show fix priorities
        priorities = collector.generate_fix_priority(report)
        if priorities:
            print("\nFIX PRIORITY LIST:")
            print("-" * 60)
            for i, item in enumerate(priorities[:5], 1):
                print(f"{i}. [{item['severity']}] {item['pattern']}")
                print(f"   Score: {item['score']}, Count: {item['count']}")
                print(f"   Hint: {item['fix_hint']}")


if __name__ == "__main__":
    main()
