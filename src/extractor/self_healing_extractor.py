#!/usr/bin/env python3
"""
Self-Healing Universal Extractor - Extract ANY document with automatic failure recovery.

COGNITIVE LOAD: MINIMAL
=======================
One function. One call. It handles everything.

    from extractor.self_healing_extractor import extract
    result = extract("/path/to/file.pdf")  # or .docx, .html, .xml, .pptx, .md, etc.

That's it. The extractor:
1. Auto-detects file type
2. Attempts extraction
3. On failure: detects pattern, attempts fix, retries
4. On persistent failure: asks for help via /interview skill
5. Learns from fixes to memory for future extractions

Supported formats: PDF, DOCX, PPTX, XLSX, HTML, XML, Markdown, RST, EPUB, TXT, JSON, Images
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# Error pattern registry - maps error signatures to fix strategies
ERROR_PATTERNS = {
    # PDF patterns
    "FileDataError": {
        "description": "Corrupted or encrypted PDF",
        "fix_strategy": "decrypt_or_repair",
        "recoverable": True,
    },
    "EmptyFileError": {
        "description": "Empty or zero-byte file",
        "fix_strategy": "check_file_integrity",
        "recoverable": False,
    },
    "scanned_no_ocr": {
        "description": "Scanned PDF without text layer",
        "fix_strategy": "apply_ocr",
        "recoverable": True,
    },
    "password_protected": {
        "description": "Password-protected document",
        "fix_strategy": "request_password",
        "recoverable": True,
    },
    # DOCX patterns
    "BadZipFile": {
        "description": "Corrupted DOCX/PPTX/XLSX (invalid ZIP)",
        "fix_strategy": "repair_zip",
        "recoverable": True,
    },
    "XMLSyntaxError": {
        "description": "Malformed XML in document",
        "fix_strategy": "repair_xml",
        "recoverable": True,
    },
    # HTML patterns
    "encoding_error": {
        "description": "Character encoding issue",
        "fix_strategy": "detect_and_reencode",
        "recoverable": True,
    },
    "malformed_html": {
        "description": "Invalid HTML structure",
        "fix_strategy": "sanitize_html",
        "recoverable": True,
    },
    # General patterns
    "timeout": {
        "description": "Extraction timed out",
        "fix_strategy": "chunk_and_retry",
        "recoverable": True,
    },
    "memory_error": {
        "description": "Out of memory",
        "fix_strategy": "stream_process",
        "recoverable": True,
    },
    "unknown": {
        "description": "Unknown error",
        "fix_strategy": "ask_human",
        "recoverable": False,
    },
}


@dataclass
class ExtractionResult:
    """Result of extraction attempt."""

    success: bool
    file_path: str
    file_type: str
    content: dict = field(default_factory=dict)
    error: Optional[str] = None
    error_pattern: Optional[str] = None
    fix_applied: Optional[str] = None
    attempts: int = 1
    learned: bool = False  # Whether we stored a lesson from this


@dataclass
class HealingAttempt:
    """Record of a self-healing attempt."""

    pattern: str
    strategy: str
    success: bool
    error_before: str
    result_after: Optional[str] = None


def extract(
    file_path: str | Path,
    *,
    max_retries: int = 3,
    use_memory: bool = True,
    ask_on_failure: bool = True,
    timeout_seconds: int = 300,
) -> ExtractionResult:
    """
    Extract content from ANY document with automatic self-healing.

    This is THE function. One call extracts everything.

    Args:
        file_path: Path to any supported document
        max_retries: Maximum self-healing attempts (default: 3)
        use_memory: Query memory for known fixes (default: True)
        ask_on_failure: Use /interview skill if all fixes fail (default: True)
        timeout_seconds: Max time for extraction (default: 300)

    Returns:
        ExtractionResult with extracted content or error details

    Example:
        >>> result = extract("report.pdf")
        >>> if result.success:
        ...     print(result.content)
        >>> else:
        ...     print(f"Failed: {result.error}")
    """
    path = Path(file_path).resolve()

    # Validate file exists
    if not path.exists():
        return ExtractionResult(
            success=False,
            file_path=str(path),
            file_type="unknown",
            error=f"File not found: {path}",
            error_pattern="file_not_found",
        )

    # Detect file type
    file_type = _detect_file_type(path)
    logger.info(f"Extracting {file_type}: {path.name}")

    # Check memory for known issues with this file type
    known_fix = None
    if use_memory:
        known_fix = _recall_from_memory(file_type, str(path))
        if known_fix:
            logger.info(f"Memory: Found known fix for {file_type}: {known_fix}")

    # Attempt extraction with self-healing loop
    last_error = None
    healing_history: list[HealingAttempt] = []

    for attempt in range(1, max_retries + 1):
        logger.info(f"Extraction attempt {attempt}/{max_retries}")

        try:
            # Try extraction
            content = _extract_by_type(path, file_type, timeout_seconds)

            # Success!
            result = ExtractionResult(
                success=True,
                file_path=str(path),
                file_type=file_type,
                content=content,
                attempts=attempt,
            )

            # If we healed, store the lesson
            if healing_history and use_memory:
                successful_fix = healing_history[-1]
                _learn_to_memory(
                    file_type=file_type,
                    error_pattern=successful_fix.pattern,
                    fix_strategy=successful_fix.strategy,
                    success=True,
                )
                result.learned = True
                result.fix_applied = successful_fix.strategy

            return result

        except Exception as e:
            last_error = str(e)
            error_pattern = _classify_error(e)
            logger.warning(f"Attempt {attempt} failed: {error_pattern} - {last_error[:100]}")

            # Can we heal this?
            if attempt < max_retries:
                fix_strategy = _get_fix_strategy(error_pattern, known_fix)

                if fix_strategy and fix_strategy != "ask_human":
                    logger.info(f"Attempting fix: {fix_strategy}")
                    heal_success = _apply_fix(path, file_type, fix_strategy)

                    healing_history.append(
                        HealingAttempt(
                            pattern=error_pattern,
                            strategy=fix_strategy,
                            success=heal_success,
                            error_before=last_error,
                        )
                    )

                    if heal_success:
                        continue  # Retry with fix applied

    # All attempts failed
    logger.error(f"Extraction failed after {max_retries} attempts: {last_error}")

    # Ask for help?
    if ask_on_failure:
        help_response = _ask_for_help(path, file_type, last_error, healing_history)
        if help_response and help_response.get("manual_fix"):
            # Human provided a fix - try once more
            logger.info("Applying manual fix from interview...")
            try:
                content = _extract_by_type(path, file_type, timeout_seconds)
                result = ExtractionResult(
                    success=True,
                    file_path=str(path),
                    file_type=file_type,
                    content=content,
                    attempts=max_retries + 1,
                    fix_applied="manual_intervention",
                )

                # Store the lesson for future
                if use_memory and help_response.get("lesson"):
                    _learn_to_memory(
                        file_type=file_type,
                        error_pattern=_classify_error(Exception(last_error)),
                        fix_strategy=help_response["lesson"],
                        success=True,
                    )
                    result.learned = True

                return result
            except Exception as e:
                last_error = str(e)

    # Final failure
    result = ExtractionResult(
        success=False,
        file_path=str(path),
        file_type=file_type,
        error=last_error,
        error_pattern=_classify_error(Exception(last_error)) if last_error else "unknown",
        attempts=max_retries,
    )

    # Store failure pattern for learning
    if use_memory and last_error:
        _learn_to_memory(
            file_type=file_type,
            error_pattern=result.error_pattern or "unknown",
            fix_strategy="needs_investigation",
            success=False,
        )

    return result


def _detect_file_type(path: Path) -> str:
    """Detect file type from extension and content."""
    ext = path.suffix.lower().lstrip(".")

    # Extension mapping
    type_map = {
        # Documents
        "pdf": "pdf",
        "docx": "docx",
        "doc": "docx",
        "odt": "docx",
        "pptx": "pptx",
        "ppt": "pptx",
        "odp": "pptx",
        "xlsx": "spreadsheet",
        "xls": "spreadsheet",
        "xlsm": "spreadsheet",
        "ods": "spreadsheet",
        "csv": "spreadsheet",
        # Web/Markup
        "html": "html",
        "htm": "html",
        "xml": "xml",
        "md": "markdown",
        "markdown": "markdown",
        "rst": "rst",
        # Data
        "json": "json",
        "jsonl": "json",
        "txt": "txt",
        "text": "txt",
        # Books
        "epub": "epub",
        # Images
        "png": "image",
        "jpg": "image",
        "jpeg": "image",
        "gif": "image",
        "bmp": "image",
        "tiff": "image",
        "webp": "image",
        "svg": "image",
    }

    if ext in type_map:
        return type_map[ext]

    # Try content detection
    try:
        import filetype

        kind = filetype.guess(str(path))
        if kind:
            mime = kind.mime
            if "pdf" in mime:
                return "pdf"
            if "image" in mime:
                return "image"
            if "zip" in mime:
                # Could be DOCX/PPTX/XLSX
                return "docx"  # Will try OOXML detection
    except ImportError:
        pass

    # Fallback: try to read as text
    try:
        with open(path, "r", encoding="utf-8") as f:
            head = f.read(1024)
        if head.strip().startswith("<!DOCTYPE html") or "<html" in head.lower():
            return "html"
        if head.strip().startswith("<?xml") or head.strip().startswith("<"):
            return "xml"
        if head.strip().startswith("{") or head.strip().startswith("["):
            return "json"
        return "txt"
    except Exception:
        return "unknown"


def _extract_by_type(path: Path, file_type: str, timeout: int) -> dict:
    """Route to appropriate extractor based on file type."""
    from extractor.core.providers.registry import provider_from_filepath

    try:
        # Get the appropriate provider
        provider_class = provider_from_filepath(str(path))

        # Providers have different constructor signatures:
        # - Some take filepath (e.g., PdfProvider)
        # - Some take config dict (e.g., HTMLProvider)
        # - Some take nothing (standard pattern)
        # Try no-args first, then filepath
        try:
            provider = provider_class()
        except TypeError:
            # Constructor requires arguments - try with filepath
            provider = provider_class(str(path))

        # Extract document - pass filepath since all providers expect it
        doc = provider.extract_document(str(path))

        # Convert to unified format
        return _to_unified_format(doc, file_type)

    except Exception as e:
        # Re-raise with context
        raise RuntimeError(f"{file_type} extraction failed: {e}") from e


def _to_unified_format(doc: Any, file_type: str) -> dict:
    """Convert any document to unified output format."""
    # Handle different document types
    if hasattr(doc, "model_dump"):
        data = doc.model_dump()
    elif hasattr(doc, "dict"):
        data = doc.dict()
    elif isinstance(doc, dict):
        data = doc
    else:
        data = {"raw": str(doc)}

    # Extract blocks/content
    blocks = []

    def extract_blocks_recursive(node, depth=0):
        if isinstance(node, dict):
            if "block_type" in node or "type" in node:
                # Normalize type to lowercase (e.g., 'Text' -> 'text')
                raw_type = node.get("block_type", node.get("type", "unknown"))
                normalized_type = raw_type.lower() if isinstance(raw_type, str) else "unknown"
                blocks.append(
                    {
                        "type": normalized_type,
                        "text": node.get("text", node.get("content", "")),
                        "metadata": {
                            k: v
                            for k, v in node.items()
                            if k not in ("block_type", "type", "text", "content", "children")
                        },
                    }
                )
            for key, value in node.items():
                if key == "children" and isinstance(value, list):
                    for child in value:
                        extract_blocks_recursive(child, depth + 1)
                elif isinstance(value, (dict, list)):
                    extract_blocks_recursive(value, depth + 1)
        elif isinstance(node, list):
            for item in node:
                extract_blocks_recursive(item, depth + 1)

    extract_blocks_recursive(data)

    return {
        "file_type": file_type,
        "blocks": blocks,
        "block_count": len(blocks),
        "raw_data": data,
        "extracted_at": datetime.now().isoformat(),
    }


def _classify_error(error: Exception) -> str:
    """Classify an error into a known pattern."""
    error_str = str(error).lower()
    error_type = type(error).__name__

    # Check error type first
    if error_type in ERROR_PATTERNS:
        return error_type

    # Check error message patterns
    patterns = {
        "FileDataError": ["filedataerror", "cannot open", "not a pdf"],
        "EmptyFileError": ["empty file", "zero bytes", "no content"],
        "scanned_no_ocr": ["no text", "scanned", "image only"],
        "password_protected": ["password", "encrypted", "protected"],
        "BadZipFile": ["bad zip", "badzipfile", "not a zip", "corrupted zip"],
        "XMLSyntaxError": ["xml syntax", "parsing error", "malformed xml"],
        "encoding_error": ["encoding", "decode", "codec"],
        "malformed_html": ["html", "parser error"],
        "timeout": ["timeout", "timed out"],
        "memory_error": ["memory", "out of memory", "oom"],
    }

    for pattern_name, keywords in patterns.items():
        if any(kw in error_str for kw in keywords):
            return pattern_name

    return "unknown"


def _get_fix_strategy(error_pattern: str, known_fix: Optional[str] = None) -> Optional[str]:
    """Get the fix strategy for an error pattern."""
    # Use known fix from memory if available
    if known_fix:
        return known_fix

    # Look up in pattern registry
    pattern_info = ERROR_PATTERNS.get(error_pattern, ERROR_PATTERNS["unknown"])

    if pattern_info["recoverable"]:
        return pattern_info["fix_strategy"]

    return None


def _apply_fix(path: Path, file_type: str, strategy: str) -> bool:
    """Apply a fix strategy and return whether it might help."""
    logger.info(f"Applying fix strategy: {strategy}")

    try:
        if strategy == "decrypt_or_repair":
            return _try_decrypt_repair(path)
        elif strategy == "apply_ocr":
            return _try_apply_ocr(path)
        elif strategy == "repair_zip":
            return _try_repair_zip(path)
        elif strategy == "repair_xml":
            return _try_repair_xml(path)
        elif strategy == "detect_and_reencode":
            return _try_fix_encoding(path)
        elif strategy == "sanitize_html":
            return _try_sanitize_html(path)
        elif strategy == "chunk_and_retry":
            return True  # Just retry with smaller chunks
        elif strategy == "stream_process":
            return True  # Just retry with streaming
        else:
            logger.warning(f"Unknown fix strategy: {strategy}")
            return False
    except Exception as e:
        logger.error(f"Fix strategy {strategy} failed: {e}")
        return False


def _try_decrypt_repair(path: Path) -> bool:
    """Try to decrypt or repair a PDF."""
    try:
        import fitz

        doc = fitz.open(str(path))
        if doc.is_encrypted:
            # Try empty password first
            if doc.authenticate(""):
                # Save decrypted version
                temp_path = path.with_suffix(".decrypted.pdf")
                doc.save(str(temp_path))
                doc.close()
                # Replace original
                temp_path.replace(path)
                return True
        doc.close()
        return False
    except Exception:
        return False


def _try_apply_ocr(path: Path) -> bool:
    """Apply OCR to a scanned PDF."""
    # OCR would be applied during extraction, just signal to use OCR mode
    return True


def _try_repair_zip(path: Path) -> bool:
    """Try to repair a corrupted ZIP-based file."""
    try:
        import zipfile

        # Try to open and repack
        with zipfile.ZipFile(str(path), "r") as zf:
            temp_dir = path.parent / f".repair_{path.stem}"
            temp_dir.mkdir(exist_ok=True)
            zf.extractall(temp_dir)

            # Repack
            temp_path = path.with_suffix(".repaired" + path.suffix)
            with zipfile.ZipFile(str(temp_path), "w") as new_zf:
                for file in temp_dir.rglob("*"):
                    if file.is_file():
                        arcname = file.relative_to(temp_dir)
                        new_zf.write(file, arcname)

            # Cleanup
            import shutil

            shutil.rmtree(temp_dir)
            temp_path.replace(path)
            return True
    except Exception:
        return False


def _try_repair_xml(path: Path) -> bool:
    """Try to repair malformed XML."""
    try:
        from bs4 import BeautifulSoup

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Use BeautifulSoup to fix HTML/XML
        soup = BeautifulSoup(content, "lxml-xml")
        fixed = str(soup)

        with open(path, "w", encoding="utf-8") as f:
            f.write(fixed)

        return True
    except Exception:
        return False


def _try_fix_encoding(path: Path) -> bool:
    """Try to detect and fix encoding issues."""
    try:
        import chardet

        with open(path, "rb") as f:
            raw = f.read()

        detected = chardet.detect(raw)
        encoding = detected.get("encoding", "utf-8")

        # Re-encode to UTF-8
        content = raw.decode(encoding, errors="replace")

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return True
    except ImportError:
        # chardet not available, try common encodings
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
        for enc in encodings:
            try:
                with open(path, "r", encoding=enc) as f:
                    content = f.read()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def _try_sanitize_html(path: Path) -> bool:
    """Try to sanitize malformed HTML."""
    try:
        from bs4 import BeautifulSoup

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        soup = BeautifulSoup(content, "html.parser")
        fixed = str(soup)

        with open(path, "w", encoding="utf-8") as f:
            f.write(fixed)

        return True
    except Exception:
        return False


def _recall_from_memory(file_type: str, file_path: str) -> Optional[str]:
    """Check memory for known fixes."""
    try:
        memory_skill = Path.home() / ".claude/skills/memory/run.sh"
        if not memory_skill.exists():
            return None

        result = subprocess.run(
            [str(memory_skill), "recall", "--q", f"{file_type} extraction error fix"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("found") and data.get("items"):
                return data["items"][0].get("solution")
    except Exception as e:
        logger.debug(f"Memory recall failed: {e}")

    return None


def _learn_to_memory(
    file_type: str, error_pattern: str, fix_strategy: str, success: bool
) -> None:
    """Store a lesson in memory."""
    try:
        memory_skill = Path.home() / ".claude/skills/memory/run.sh"
        if not memory_skill.exists():
            return

        problem = f"{file_type} extraction: {error_pattern}"
        if success:
            solution = f"Fix: {fix_strategy}"
        else:
            solution = f"UNSOLVED: {fix_strategy} did not work, needs investigation"

        subprocess.run(
            [str(memory_skill), "learn", "--problem", problem, "--solution", solution],
            capture_output=True,
            text=True,
            timeout=10,
        )
        logger.info(f"Stored lesson to memory: {problem}")
    except Exception as e:
        logger.debug(f"Memory learn failed: {e}")


def _ask_for_help(
    path: Path, file_type: str, error: str, history: list[HealingAttempt]
) -> Optional[dict]:
    """Use /interview skill to ask for human help."""
    try:
        interview_skill = Path.home() / ".pi/skills/interview/run.sh"
        if not interview_skill.exists():
            interview_skill = (
                Path.home() / "workspace/experiments/pi-mono/.pi/skills/interview/run.sh"
            )

        if not interview_skill.exists():
            logger.warning("Interview skill not found, cannot ask for help")
            return None

        # Build the question
        attempts_summary = "\n".join(
            [f"  - {h.strategy}: {'success' if h.success else 'failed'}" for h in history]
        )

        question = f"""
Extraction failed for {file_type} file: {path.name}

Error: {error[:200]}

Attempted fixes:
{attempts_summary if attempts_summary else "  (none)"}

Options:
1. Skip this file
2. Provide a manual fix command
3. Mark for later investigation
"""

        result = subprocess.run(
            [str(interview_skill), "ask", "--question", question],
            capture_output=True,
            text=True,
            timeout=300,  # 5 min for human response
        )

        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        logger.debug(f"Interview skill failed: {e}")

    return None


# Convenience functions for specific file types
def extract_pdf(path: str | Path, **kwargs) -> ExtractionResult:
    """Extract PDF document."""
    return extract(path, **kwargs)


def extract_docx(path: str | Path, **kwargs) -> ExtractionResult:
    """Extract Word document."""
    return extract(path, **kwargs)


def extract_html(path: str | Path, **kwargs) -> ExtractionResult:
    """Extract HTML document."""
    return extract(path, **kwargs)


def extract_xml(path: str | Path, **kwargs) -> ExtractionResult:
    """Extract XML document."""
    return extract(path, **kwargs)


# CLI entry point
def main():
    """CLI for self-healing extractor."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Self-Healing Universal Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Extract any document
    python -m extractor.self_healing_extractor file.pdf
    python -m extractor.self_healing_extractor report.docx
    python -m extractor.self_healing_extractor data.xml

    # Batch extraction
    python -m extractor.self_healing_extractor *.pdf --output results/

    # No memory/interview (offline mode)
    python -m extractor.self_healing_extractor file.pdf --offline
""",
    )

    parser.add_argument("files", nargs="+", help="Files to extract")
    parser.add_argument("-o", "--output", help="Output directory", default=".")
    parser.add_argument("--offline", action="store_true", help="Disable memory/interview")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for file_path in args.files:
        result = extract(
            file_path,
            use_memory=not args.offline,
            ask_on_failure=not args.offline,
        )

        results.append(result)

        if result.success:
            # Save extracted content
            out_file = output_dir / f"{Path(file_path).stem}_extracted.json"
            with open(out_file, "w") as f:
                json.dump(result.content, f, indent=2, default=str)
            print(f"[OK] {file_path} -> {out_file}")
        else:
            print(f"[FAIL] {file_path}: {result.error}")

    # Summary
    success_count = sum(1 for r in results if r.success)
    print(f"\nExtracted: {success_count}/{len(results)} files")

    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
