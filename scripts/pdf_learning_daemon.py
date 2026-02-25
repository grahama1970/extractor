#!/usr/bin/env python3
"""Continuous PDF Learning Daemon.

A never-ending service that:
1. Watches for new PDFs in the corpus
2. Runs extraction pipeline on new documents
3. Collects failure patterns
4. Feeds patterns back for improvement

This is the foundation of the continuous improvement system.

Usage:
    # Run as daemon
    python scripts/pdf_learning_daemon.py \
        --corpus /mnt/storage12tb/extractor_corpus \
        --interval 300

    # Run with systemd (create service file)
    sudo systemctl start pdf-learning-daemon
"""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)


class PDFLearningDaemon:
    """Continuous PDF extraction and learning daemon."""

    def __init__(self, corpus_dir: Path, extractor_dir: Path):
        self.corpus_dir = corpus_dir
        self.extractor_dir = extractor_dir
        self.results_dir = corpus_dir / "results"
        self.processed_file = corpus_dir / ".processed_pdfs.json"
        self.processed: dict[str, dict] = {}

        # Subdirectories to watch
        self.watch_dirs = [
            corpus_dir / "adversarial",
            corpus_dir / "engineering",
            corpus_dir / "arxiv",
            corpus_dir / "incoming",  # For user-submitted PDFs
        ]

        self._load_processed()

    def _load_processed(self):
        """Load list of already processed PDFs."""
        if self.processed_file.exists():
            with open(self.processed_file) as f:
                self.processed = json.load(f)
        log.info(f"Loaded {len(self.processed)} processed PDF records")

    def _save_processed(self):
        """Save processed PDF records."""
        with open(self.processed_file, "w") as f:
            json.dump(self.processed, f, indent=2)

    def _hash_file(self, path: Path) -> str:
        """Generate hash of PDF file for change detection."""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def find_new_pdfs(self) -> list[Path]:
        """Find PDFs that haven't been processed or have changed."""
        new_pdfs = []

        for watch_dir in self.watch_dirs:
            if not watch_dir.exists():
                watch_dir.mkdir(parents=True, exist_ok=True)
                continue

            for pdf_path in watch_dir.glob("**/*.pdf"):
                str_path = str(pdf_path)
                file_hash = self._hash_file(pdf_path)

                if str_path not in self.processed:
                    new_pdfs.append(pdf_path)
                elif self.processed[str_path].get("hash") != file_hash:
                    # File has changed
                    new_pdfs.append(pdf_path)

        return new_pdfs

    def run_extraction(self, pdf_path: Path) -> dict:
        """Run extraction pipeline on a single PDF."""
        rel_path = pdf_path.relative_to(self.corpus_dir)
        safe_name = str(rel_path).replace("/", "_").replace(" ", "_").replace(".pdf", "")
        out_dir = self.results_dir / safe_name

        log.info(f"Extracting: {rel_path}")

        start_time = time.time()

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "extractor.pipeline.run_pipeline",
                    "--pdf", str(pdf_path),
                    "--out", str(out_dir),
                    "--summary-only",
                ],
                cwd=self.extractor_dir,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            status = "SUCCESS" if result.returncode == 0 else "FAILED"
            error = result.stderr if result.returncode != 0 else None

        except subprocess.TimeoutExpired:
            status = "TIMEOUT"
            error = "Extraction timed out after 10 minutes"

        except Exception as e:
            status = "ERROR"
            error = str(e)

        duration = time.time() - start_time

        # Extract quality metrics from report
        quality = "UNKNOWN"
        tables = "UNKNOWN"
        figures = "UNKNOWN"

        report_file = out_dir / "14_report_generator" / "json_output" / "final_report.json"
        if report_file.exists():
            try:
                with open(report_file) as f:
                    report = json.load(f)
                quality = report.get("statistics", {}).get("quality_signal", "UNKNOWN")
                tables = report.get("statistics", {}).get("assessment_comparison", {}).get("tables", {}).get("status", "UNKNOWN")
                figures = report.get("statistics", {}).get("assessment_comparison", {}).get("figures", {}).get("status", "UNKNOWN")
            except Exception:
                pass

        result_entry = {
            "pdf": str(rel_path),
            "status": status,
            "duration_sec": round(duration, 1),
            "quality": quality,
            "tables": tables,
            "figures": figures,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "error": error,
        }

        return result_entry

    def process_new_pdfs(self) -> list[dict]:
        """Process all new PDFs and return results."""
        new_pdfs = self.find_new_pdfs()

        if not new_pdfs:
            return []

        log.info(f"Found {len(new_pdfs)} new PDFs to process")
        results = []

        for pdf_path in new_pdfs:
            result = self.run_extraction(pdf_path)
            results.append(result)

            # Update processed record
            self.processed[str(pdf_path)] = {
                "hash": self._hash_file(pdf_path),
                "last_processed": result["timestamp"],
                "result": result,
            }

            # Append to summary
            summary_file = self.results_dir / "batch_summary.jsonl"
            with open(summary_file, "a") as f:
                f.write(json.dumps(result) + "\n")

            # Save processed after each file
            self._save_processed()

        return results

    def analyze_patterns(self) -> dict:
        """Analyze failure patterns from all results."""
        from collections import Counter

        problems = []
        for path, record in self.processed.items():
            result = record.get("result", {})
            if result.get("quality") != "REASONABLE" or result.get("tables") != "OK":
                problems.append(result)

        pattern_counts = Counter()
        for p in problems:
            if p.get("tables") == "UNDER_EXTRACTED":
                pattern_counts["table_under_extraction"] += 1
            if p.get("figures") == "UNDER_EXTRACTED":
                pattern_counts["figure_under_extraction"] += 1
            if p.get("status") == "FAILED":
                pattern_counts["extraction_failed"] += 1
            if p.get("status") == "TIMEOUT":
                pattern_counts["timeout"] += 1

        return {
            "total_processed": len(self.processed),
            "total_problems": len(problems),
            "patterns": dict(pattern_counts),
            "problem_rate": round(100 * len(problems) / max(1, len(self.processed)), 1),
        }

    def run(self, interval: int = 300):
        """Run the daemon loop."""
        log.info(f"Starting PDF Learning Daemon (interval: {interval}s)")
        log.info(f"Corpus: {self.corpus_dir}")
        log.info(f"Watching: {[str(d) for d in self.watch_dirs]}")

        while True:
            try:
                # Process new PDFs
                results = self.process_new_pdfs()

                if results:
                    log.info(f"Processed {len(results)} PDFs")

                    # Analyze patterns
                    analysis = self.analyze_patterns()
                    log.info(f"Pattern analysis: {analysis}")

                    # Save analysis
                    analysis_file = self.corpus_dir / "pattern_analysis.json"
                    with open(analysis_file, "w") as f:
                        json.dump(analysis, f, indent=2)

                else:
                    log.info("No new PDFs to process")

                # Sleep until next cycle
                log.info(f"Sleeping for {interval}s...")
                time.sleep(interval)

            except KeyboardInterrupt:
                log.info("Daemon stopped by user")
                break

            except Exception as e:
                log.error(f"Error in daemon loop: {e}")
                time.sleep(60)  # Short sleep on error


def main():
    parser = argparse.ArgumentParser(description="Continuous PDF Learning Daemon")
    parser.add_argument("--corpus", type=Path, required=True, help="Corpus directory")
    parser.add_argument("--extractor", type=Path, default=Path("/home/graham/workspace/experiments/extractor"),
                        help="Extractor project directory")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds")
    args = parser.parse_args()

    daemon = PDFLearningDaemon(args.corpus, args.extractor)
    daemon.run(args.interval)


if __name__ == "__main__":
    main()
