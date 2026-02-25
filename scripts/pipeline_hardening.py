#!/usr/bin/env python3
"""
Pipeline Hardening - Learn from N documents and iteratively harden the extractor.

This script implements the dynamic fix-test loop workflow for ALL file types:
1. Analyze 1000+ documents for failure patterns (PDF, DOCX, HTML, XML, PPTX, etc.)
2. Prioritize patterns by frequency
3. Fix highest-impact patterns
4. Re-analyze to verify fixes
5. Store lessons to memory
6. Repeat until hardened

Supported formats: PDF, DOCX, PPTX, XLSX, HTML, XML, Markdown, RST, EPUB, TXT, JSON, Images

Usage:
    # Phase 1: Initial analysis (any file type)
    python scripts/pipeline_hardening.py analyze /path/to/docs --output analysis.json

    # Phase 2: Run extractor on all documents, collect failures
    python scripts/pipeline_hardening.py run-batch /path/to/docs --output batch_results.json

    # Phase 3: Iterative hardening loop (interactive)
    python scripts/pipeline_hardening.py harden batch_results.json

    # Phase 4: Store lessons from hardening session
    python scripts/pipeline_hardening.py learn-session session_log.json

    # Quick start guide
    python scripts/pipeline_hardening.py quick-start
"""

import asyncio
import json
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

app = typer.Typer(help="Pipeline hardening through bulk document analysis")

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    # Documents
    ".pdf", ".docx", ".doc", ".odt",
    ".pptx", ".ppt", ".odp",
    ".xlsx", ".xls", ".xlsm", ".ods", ".csv",
    # Web/Markup
    ".html", ".htm", ".xml",
    ".md", ".markdown", ".rst",
    # Data
    ".json", ".jsonl", ".txt", ".text",
    # Books
    ".epub",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".svg",
}


def get_supported_files(path: Path, recursive: bool = True) -> list[Path]:
    """Get all supported files from a directory."""
    pattern = "**/*" if recursive else "*"
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(path.glob(f"{pattern}{ext}"))
        files.extend(path.glob(f"{pattern}{ext.upper()}"))
    return sorted(set(files))


def get_file_type(path: Path) -> str:
    """Get file type category from path."""
    ext = path.suffix.lower()
    type_map = {
        ".pdf": "pdf",
        ".docx": "docx", ".doc": "docx", ".odt": "docx",
        ".pptx": "pptx", ".ppt": "pptx", ".odp": "pptx",
        ".xlsx": "spreadsheet", ".xls": "spreadsheet", ".xlsm": "spreadsheet",
        ".ods": "spreadsheet", ".csv": "spreadsheet",
        ".html": "html", ".htm": "html",
        ".xml": "xml",
        ".md": "markdown", ".markdown": "markdown",
        ".rst": "rst",
        ".json": "json", ".jsonl": "json",
        ".txt": "txt", ".text": "txt",
        ".epub": "epub",
        ".png": "image", ".jpg": "image", ".jpeg": "image",
        ".gif": "image", ".bmp": "image", ".tiff": "image",
        ".webp": "image", ".svg": "image",
    }
    return type_map.get(ext, "unknown")

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class HardeningConfig:
    """Configuration for hardening session."""
    max_workers: int = 8
    batch_size: int = 100
    sample_size: int = 50  # For quick pattern analysis
    pattern_threshold: float = 0.05  # Pattern must affect >5% of PDFs to prioritize
    memory_skill_path: Path = Path.home() / ".claude/skills/memory/run.sh"
    extractor_path: Path = Path(__file__).parent.parent

# ============================================================================
# PHASE 1: BULK ANALYSIS
# ============================================================================

def analyze_document_safe(file_path: Path) -> dict:
    """Analyze any document for failure patterns - catches all exceptions."""
    try:
        from extractor.self_healing_extractor import extract, _detect_file_type
        from extractor.failure_detector import detect_failure_pattern, detect_content_issues

        file_type = _detect_file_type(file_path)
        patterns = []

        # Try extraction
        result = extract(
            file_path,
            max_retries=1,  # Just detect, don't retry
            use_memory=False,  # Don't hit memory during bulk analysis
            ask_on_failure=False,  # Don't ask during bulk
        )

        if result.success:
            # Check content quality
            issues = detect_content_issues(result.content, file_type)
            for issue in issues:
                patterns.append((issue.name, issue.description))
        else:
            # Classify the failure
            if result.error_pattern:
                patterns.append((result.error_pattern, result.error or ""))

        return {
            "path": str(file_path),
            "file_type": file_type,
            "success": result.success,
            "patterns": patterns,
            "block_count": result.content.get("block_count", 0) if result.success else 0,
        }

    except Exception as e:
        return {
            "path": str(file_path),
            "file_type": get_file_type(file_path),
            "success": False,
            "patterns": [("analysis_error", str(e))],
            "error": str(e),
        }


def analyze_pdf_safe(pdf_path: Path) -> dict:
    """Legacy wrapper for PDF-only analysis."""
    return analyze_document_safe(pdf_path)


@app.command()
def analyze(
    path: Path = typer.Argument(..., help="Directory with documents"),
    output: Path = typer.Option("hardening_analysis.json", "-o", "--output"),
    workers: int = typer.Option(8, "-w", "--workers", help="Parallel workers"),
    sample: Optional[int] = typer.Option(None, "-s", "--sample", help="Sample N files only"),
    file_type: Optional[str] = typer.Option(None, "-t", "--type", help="Filter by type (pdf, docx, html, etc.)"),
):
    """
    Phase 1: Analyze all documents for failure patterns.

    Supports: PDF, DOCX, PPTX, XLSX, HTML, XML, Markdown, RST, EPUB, TXT, JSON, Images

    This is fast - just pattern detection, minimal extraction.
    """
    # Get all supported files
    all_files = get_supported_files(path)

    # Filter by type if specified
    if file_type:
        all_files = [f for f in all_files if get_file_type(f) == file_type.lower()]

    if sample and sample < len(all_files):
        import random
        all_files = random.sample(all_files, sample)
        logger.info(f"Sampling {sample} files from total")

    if not all_files:
        logger.error(f"No supported files found in {path}")
        raise typer.Exit(1)

    # Count by type
    type_counts = Counter(get_file_type(f) for f in all_files)
    logger.info(f"Analyzing {len(all_files)} files with {workers} workers")
    logger.info(f"File types: {dict(type_counts)}")

    results = []
    pattern_counts = Counter()
    type_pattern_counts: dict[str, Counter] = {}

    t0 = time.monotonic()

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(analyze_document_safe, f): f for f in all_files}

        for i, future in enumerate(as_completed(futures)):
            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{len(all_files)}")

            result = future.result()
            results.append(result)

            ftype = result.get("file_type", "unknown")
            if ftype not in type_pattern_counts:
                type_pattern_counts[ftype] = Counter()

            for pattern, _ in result.get("patterns", []):
                pattern_counts[pattern] += 1
                type_pattern_counts[ftype][pattern] += 1

    elapsed = time.monotonic() - t0

    # Generate report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(all_files),
        "files_by_type": dict(type_counts),
        "files_with_issues": len([r for r in results if r.get("patterns")]),
        "success_count": len([r for r in results if r.get("success")]),
        "failure_count": len([r for r in results if not r.get("success")]),
        "analysis_time_seconds": round(elapsed, 1),
        "pattern_frequency": {
            pattern: {
                "count": count,
                "percentage": round(count / len(all_files) * 100, 1),
            }
            for pattern, count in pattern_counts.most_common()
        },
        "patterns_by_type": {
            ftype: dict(counts.most_common())
            for ftype, counts in type_pattern_counts.items()
        },
        "results": results,
    }

    output.write_text(json.dumps(report, indent=2))

    # Summary
    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE: {len(all_files)} files in {elapsed:.1f}s")
    print(f"{'='*60}")

    print(f"\nFile types analyzed:")
    for ftype, count in type_counts.most_common():
        print(f"  {ftype}: {count}")

    success_rate = report['success_count'] / len(all_files) * 100
    print(f"\nSuccess rate: {report['success_count']}/{len(all_files)} ({success_rate:.1f}%)")
    print(f"Files with issues: {report['files_with_issues']}")

    print(f"\nTop patterns (all types):")
    for pattern, data in list(report["pattern_frequency"].items())[:10]:
        print(f"  {pattern}: {data['count']} ({data['percentage']}%)")

    print(f"\nResults saved to: {output}")


# ============================================================================
# PHASE 2: BATCH PIPELINE EXECUTION
# ============================================================================

def run_extraction_on_file(file_path: Path, output_dir: Path) -> dict:
    """Run the self-healing extractor on any file."""
    file_output = output_dir / file_path.stem
    file_output.mkdir(parents=True, exist_ok=True)

    try:
        from extractor.self_healing_extractor import extract

        result = extract(
            file_path,
            max_retries=3,
            use_memory=True,  # Use memory for learning
            ask_on_failure=False,  # Don't ask during batch
            timeout_seconds=300,
        )

        # Save output
        if result.success:
            output_file = file_output / "extracted.json"
            with open(output_file, "w") as f:
                json.dump(result.content, f, indent=2, default=str)

        return {
            "path": str(file_path),
            "file_type": result.file_type,
            "success": result.success,
            "output_dir": str(file_output),
            "block_count": result.content.get("block_count", 0) if result.success else 0,
            "attempts": result.attempts,
            "fix_applied": result.fix_applied,
            "learned": result.learned,
            "error": result.error,
            "error_pattern": result.error_pattern,
        }

    except Exception as e:
        return {
            "path": str(file_path),
            "file_type": get_file_type(file_path),
            "success": False,
            "error": str(e),
        }


def run_pipeline_on_pdf(pdf_path: Path, output_dir: Path) -> dict:
    """Legacy wrapper - now uses universal extractor."""
    return run_extraction_on_file(pdf_path, output_dir)


@app.command()
def run_batch(
    path: Path = typer.Argument(..., help="Directory with documents"),
    output: Path = typer.Option("batch_results.json", "-o", "--output"),
    output_dir: Path = typer.Option("hardening_output", "--output-dir"),
    workers: int = typer.Option(4, "-w", "--workers"),
    limit: Optional[int] = typer.Option(None, "-l", "--limit"),
    file_type: Optional[str] = typer.Option(None, "-t", "--type", help="Filter by type"),
):
    """
    Phase 2: Run extractor on all documents and collect results.

    Supports: PDF, DOCX, PPTX, XLSX, HTML, XML, Markdown, RST, EPUB, TXT, JSON, Images

    This runs the full self-healing extraction pipeline.
    """
    # Get all supported files
    all_files = get_supported_files(path)

    # Filter by type if specified
    if file_type:
        all_files = [f for f in all_files if get_file_type(f) == file_type.lower()]

    if limit:
        all_files = all_files[:limit]

    if not all_files:
        logger.error(f"No supported files found in {path}")
        raise typer.Exit(1)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    type_counts = Counter(get_file_type(f) for f in all_files)
    logger.info(f"Running extraction on {len(all_files)} files...")
    logger.info(f"File types: {dict(type_counts)}")

    results = []
    successes = 0
    failures = 0
    lessons_learned = 0

    t0 = time.monotonic()

    # Run with ProcessPoolExecutor for parallel processing
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_extraction_on_file, f, output_dir): f for f in all_files}

        for i, future in enumerate(as_completed(futures)):
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(all_files)} ({successes} pass, {failures} fail)")

            result = future.result()
            results.append(result)

            if result.get("success"):
                successes += 1
            else:
                failures += 1

            if result.get("learned"):
                lessons_learned += 1

    elapsed = time.monotonic() - t0

    # Analyze results
    failure_patterns = Counter()
    fixes_applied = Counter()
    success_by_type = Counter()
    failure_by_type = Counter()

    for r in results:
        ftype = r.get("file_type", "unknown")
        if r.get("success"):
            success_by_type[ftype] += 1
        else:
            failure_by_type[ftype] += 1
            if r.get("error_pattern"):
                failure_patterns[r["error_pattern"]] += 1

        if r.get("fix_applied"):
            fixes_applied[r["fix_applied"]] += 1

    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(all_files),
        "files_by_type": dict(type_counts),
        "successes": successes,
        "failures": failures,
        "success_rate": round(successes / len(all_files) * 100, 1) if all_files else 0,
        "lessons_learned": lessons_learned,
        "elapsed_seconds": round(elapsed, 1),
        "success_by_type": dict(success_by_type),
        "failure_by_type": dict(failure_by_type),
        "failure_patterns": dict(failure_patterns.most_common()),
        "fixes_applied": dict(fixes_applied.most_common()),
        "results": results,
    }

    output.write_text(json.dumps(report, indent=2))

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE: {len(all_files)} files in {elapsed:.1f}s")
    print(f"{'='*60}")

    print(f"\nSuccess rate: {successes}/{len(all_files)} ({report['success_rate']}%)")
    print(f"Lessons learned: {lessons_learned}")

    if success_by_type:
        print(f"\nSuccess by type:")
        for ftype, count in success_by_type.most_common():
            total = type_counts[ftype]
            pct = count / total * 100 if total else 0
            print(f"  {ftype}: {count}/{total} ({pct:.1f}%)")

    if failure_patterns:
        print(f"\nTop failure patterns:")
        for pattern, count in failure_patterns.most_common(5):
            print(f"  {count}x: {pattern}")

    if fixes_applied:
        print(f"\nFixes applied:")
        for fix, count in fixes_applied.most_common():
            print(f"  {count}x: {fix}")

    print(f"\nResults saved to: {output}")


# ============================================================================
# PHASE 3: INTERACTIVE HARDENING LOOP
# ============================================================================

@app.command()
def harden(
    analysis_file: Path = typer.Argument(..., help="Analysis JSON from phase 1 or 2"),
):
    """
    Phase 3: Interactive hardening loop.

    Shows top patterns and guides you through fixing them.
    """
    data = json.loads(analysis_file.read_text())

    patterns = data.get("pattern_frequency", {})
    if not patterns:
        # Try batch results format
        failure_reasons = data.get("failure_reasons", {})
        if failure_reasons:
            patterns = {k: {"count": v, "percentage": v/data.get("total", 1)*100}
                       for k, v in failure_reasons.items()}

    if not patterns:
        print("No patterns found in analysis file.")
        return

    print(f"\n{'='*60}")
    print("HARDENING SESSION")
    print(f"{'='*60}")
    print(f"\nPatterns to address (by impact):\n")

    for i, (pattern, info) in enumerate(patterns.items(), 1):
        if isinstance(info, dict):
            count = info.get("count", 0)
            pct = info.get("percentage", 0)
        else:
            count = info
            pct = count / data.get("total_pdfs", data.get("total", 1)) * 100

        print(f"{i}. {pattern}: {count} occurrences ({pct:.1f}%)")

    print(f"\n{'='*60}")
    print("WORKFLOW:")
    print("1. Pick a pattern to fix (start with highest frequency)")
    print("2. Implement fix in s02_pymupdf_extractor.py or s03_suspicious_headers.py")
    print("3. Re-run analysis to verify fix")
    print("4. Store lesson to memory")
    print("5. Repeat until satisfied")
    print(f"{'='*60}")

    # Interactive loop
    while True:
        print("\nOptions:")
        print("  [1-N] Show details for pattern N")
        print("  [r] Re-run analysis")
        print("  [l] Store lesson to memory")
        print("  [q] Quit")

        choice = input("\nChoice: ").strip().lower()

        if choice == 'q':
            break
        elif choice == 'r':
            print("Re-running analysis... (use 'analyze' command)")
            break
        elif choice == 'l':
            pattern = input("Pattern name: ").strip()
            solution = input("Solution (brief): ").strip()
            print(f"\nStoring lesson: {pattern} -> {solution}")
            # Would call memory skill here
            print("(Memory integration pending)")
        elif choice.isdigit():
            idx = int(choice) - 1
            pattern_list = list(patterns.items())
            if 0 <= idx < len(pattern_list):
                pattern, info = pattern_list[idx]
                print(f"\n--- Pattern: {pattern} ---")
                print(f"Details: {info}")
                # Show example PDFs with this pattern
                if "results" in data:
                    examples = [r["path"] for r in data["results"]
                               if any(p[0] == pattern for p in r.get("patterns", []))][:5]
                    if examples:
                        print(f"Example PDFs:")
                        for ex in examples:
                            print(f"  {ex}")


# ============================================================================
# PHASE 4: LEARN FROM SESSION
# ============================================================================

@app.command()
def learn_session(
    session_log: Path = typer.Argument(..., help="Session log JSON"),
    memory_path: Path = typer.Option(
        Path.home() / ".claude/skills/memory/run.sh",
        "--memory",
        help="Path to memory skill",
    ),
):
    """
    Phase 4: Store lessons learned from hardening session.
    """
    data = json.loads(session_log.read_text())

    lessons = data.get("lessons", [])

    for lesson in lessons:
        pattern = lesson.get("pattern")
        solution = lesson.get("solution")

        if memory_path.exists():
            subprocess.run([
                str(memory_path), "learn",
                "--problem", f"PDF extraction: {pattern}",
                "--solution", solution,
            ])
            print(f"Stored: {pattern}")
        else:
            print(f"Would store: {pattern} -> {solution}")


# ============================================================================
# QUICK START
# ============================================================================

@app.command()
def quick_start():
    """Show the recommended workflow for hardening with 1000+ documents."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║    UNIVERSAL EXTRACTOR HARDENING WORKFLOW (1000+ documents)      ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  SUPPORTED FORMATS:                                              ║
║  PDF, DOCX, PPTX, XLSX, HTML, XML, Markdown, RST, EPUB,         ║
║  TXT, JSON, Images (PNG, JPG, etc.)                              ║
║                                                                  ║
║  STEP 1: Point at your documents                                 ║
║  ────────────────────────────────                                ║
║  $ ls /path/to/docs/  # All formats auto-detected                ║
║                                                                  ║
║  STEP 2: Quick pattern analysis (fast)                           ║
║  ──────────────────────────────────────                          ║
║  $ python scripts/pipeline_hardening.py analyze /path/to/docs    ║
║      --output analysis.json --workers 8                          ║
║                                                                  ║
║  # Or filter by type:                                            ║
║  $ python scripts/pipeline_hardening.py analyze /path/to/docs    ║
║      --type pdf --output pdf_analysis.json                       ║
║                                                                  ║
║  STEP 3: Review patterns and prioritize                          ║
║  ───────────────────────────────────────                         ║
║  $ python scripts/pipeline_hardening.py harden analysis.json     ║
║                                                                  ║
║  STEP 4: Self-healing runs automatically!                        ║
║  ────────────────────────────────────────                        ║
║  The extractor now self-heals. Watch it learn:                   ║
║                                                                  ║
║  $ python scripts/pipeline_hardening.py run-batch /path/to/docs  ║
║      --output batch.json --limit 100                             ║
║                                                                  ║
║  STEP 5: Lessons stored automatically to /memory                 ║
║  ───────────────────────────────────────────────                 ║
║  Check lessons learned: See "lessons_learned" in output JSON     ║
║                                                                  ║
║  SIMPLE USAGE (for agents/humans):                               ║
║  ─────────────────────────────────                               ║
║  from extractor.self_healing_extractor import extract            ║
║  result = extract("/path/to/file.pdf")  # Any format works       ║
║                                                                  ║
║  If stuck, extractor uses /interview skill to ask for help.      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    app()
