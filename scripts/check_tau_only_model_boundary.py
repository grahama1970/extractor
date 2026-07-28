#!/usr/bin/env python3
"""Fail if active Extractor paths call model providers outside Tau."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


BANNED_PATTERNS = {
    "provider_import": re.compile(
        r"^\s*(?:from|import)\s+(?:openai|anthropic|google\.genai|litellm|scillm)\b",
        re.MULTILINE,
    ),
    "provider_env": re.compile(r"\b(?:CHUTES_[A-Z0-9_]+|SCILLM_API_BASE)\b"),
    "provider_completion": re.compile(r"\b(?:completion|acompletion)\s*\("),
}

ACTIVE_PREFIXES = (
    "src/cli.py",
    "src/extractor/application/",
    "src/extractor/integrations/",
)

LEGACY_ALLOWLIST_PREFIXES = (
    "src/llm_adapter/",
    "src/extractor/pipeline/",
    "src/extractor/core/services/",
    "src/extractor/core/providers/image.py",
    "src/extractor/core/providers/utils/initialize_litellm_cache.py",
    "src/extractor/core/scripts/server.py",
    "src/extractor/core/utils/summarization.py",
    "src/extractor/evals/",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="Files or directories to scan")
    args = parser.parse_args(argv)

    files = sorted(_iter_python_files([Path(p) for p in args.paths]))
    violations: list[str] = []
    legacy_hits = 0
    for file_path in files:
        rel = _rel(file_path)
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        matches = [
            name
            for name, pattern in BANNED_PATTERNS.items()
            if pattern.search(_strip_comments(text))
        ]
        if not matches:
            continue
        if _is_active(rel):
            violations.append(f"{rel}: {', '.join(matches)}")
        elif _is_legacy_allowed(rel):
            legacy_hits += 1
        else:
            violations.append(f"{rel}: {', '.join(matches)}")

    if violations:
        print("tau_boundary=fail")
        for violation in violations:
            print(violation)
        return 1

    print("tau_boundary=pass")
    print(f"files_scanned={len(files)}")
    print(f"legacy_allowed_hits={legacy_hits}")
    print("active_policy=no direct provider/model/SciLLM boundary outside Tau integration")
    return 0


def _iter_python_files(paths: list[Path]) -> set[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_dir():
            files.update(p for p in path.rglob("*.py") if _include(p))
        elif path.suffix == ".py" and _include(path):
            files.add(path)
    return files


def _include(path: Path) -> bool:
    parts = set(path.parts)
    return not ({".venv", "__pycache__", ".git"} & parts)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_active(rel: str) -> bool:
    return any(rel == prefix or rel.startswith(prefix) for prefix in ACTIVE_PREFIXES)


def _is_legacy_allowed(rel: str) -> bool:
    return any(rel.startswith(prefix) for prefix in LEGACY_ALLOWLIST_PREFIXES)


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
