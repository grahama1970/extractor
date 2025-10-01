#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""
Bundle specified Tabbed UI files into a single concatenated text file, with clear
file path headers and language fences for readability.

Default selection (as requested):
- prototypes/tabbed/html/src/pages/ClassicLayout.tsx
- prototypes/tabbed/html/src/index.css
- prototypes/tabbed/html/src/App.css
- prototypes/tabbed/html/src/components  (directory, recursive)
- prototypes/tabbed/html/index.html
- prototypes/tabbed/html/src/main.tsx

Output (default):
- scripts/artifacts/tabbed_ui_bundle.txt

Usage:
  python scripts/tools/bundle_tabbed_ui.py
  python scripts/tools/bundle_tabbed_ui.py --output scripts/artifacts/custom_bundle.txt
  python scripts/tools/bundle_tabbed_ui.py --root . \
    --paths prototypes/tabbed/html/src/pages/ClassicLayout.tsx \
            prototypes/tabbed/html/src/index.css \
            prototypes/tabbed/html/src/App.css \
            prototypes/tabbed/html/src/components \
            prototypes/tabbed/html/index.html \
            prototypes/tabbed/html/src/main.tsx

Notes:
- Recurses directories; filters to likely text/code files.
- Skips unreadable/binary files safely.
- Adds a clear delimiter and language code fence per file.
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, List, Tuple

DEFAULT_PATHS: List[str] = [
    "prototypes/tabbed/html/src/pages/ClassicLayout.tsx",
    "prototypes/tabbed/html/src/index.css",
    "prototypes/tabbed/html/src/App.css",
    "prototypes/tabbed/html/src/components",
    "prototypes/tabbed/html/index.html",
    "prototypes/tabbed/html/src/main.tsx",
]

DEFAULT_OUTPUT = "scripts/artifacts/tabbed_ui_bundle.txt"

# Extensions considered textual/code for directory recursion
ALLOW_EXT = {
    ".ts", ".tsx", ".js", ".jsx",
    ".css", ".scss",
    ".html", ".md",
    ".json", ".svg",
    ".txt",
}

LANG_BY_EXT = {
    ".ts": "ts",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
    ".md": "markdown",
    ".json": "json",
    ".svg": "xml",
    ".txt": "",
}


def guess_lang(path: Path) -> str:
    return LANG_BY_EXT.get(path.suffix.lower(), "")


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in ALLOW_EXT:
        return True
    try:
        # Heuristic: small files without NUL are probably text
        with open(path, "rb") as f:
            chunk = f.read(2048)
        return b"\x00" not in chunk
    except Exception:
        return False


def iter_files(root: Path, inputs: Iterable[str]) -> Iterable[Path]:
    """
    Yield files from the provided inputs; directories are recursed and filtered.
    """
    for p in inputs:
        ap = (root / p).resolve()
        if not ap.exists():
            print(f"[warn] Missing path: {p}", file=sys.stderr)
            continue
        if ap.is_file():
            if is_probably_text(ap):
                yield ap
            else:
                print(f"[skip] Non-text file: {ap}", file=sys.stderr)
        elif ap.is_dir():
            for fp in sorted(ap.rglob("*")):
                if fp.is_file() and is_probably_text(fp):
                    yield fp
        else:
            print(f"[skip] Not a regular file/dir: {ap}", file=sys.stderr)


def write_bundle(files: Iterable[Path], repo_root: Path, out_path: Path) -> Tuple[int, int]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    bytes_written = 0
    # Use timezone-aware UTC timestamp
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    header = f"# Tabbed UI bundle — generated {ts}\n# Root: {repo_root}\n\n"
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        out.write(header)
        bytes_written += len(header.encode("utf-8"))
        for fp in files:
            rel = fp.relative_to(repo_root)
            lang = guess_lang(fp)
            fence_open = f"```{lang}" if lang else "```"
            fence_close = "```"
            delim_top = "=" * 88
            delim_bot = "-" * 88
            block_header = (
                f"{delim_top}\n"
                f"FILE: {rel}\n"
                f"{delim_bot}\n"
                f"{fence_open}\n"
            )
            out.write(block_header)
            try:
                text = fp.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Fallback with errors replaced
                text = fp.read_text(encoding="utf-8", errors="replace")
            out.write(text.rstrip("\n"))
            out.write("\n")
            out.write(fence_close)
            out.write("\n\n")
            count += 1
    bytes_written = out_path.stat().st_size
    return count, bytes_written


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Bundle Tabbed UI source into a single text file.")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root (base for relative paths)",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        help="Explicit list of files/dirs to include (defaults to the requested set)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output file path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.root).resolve()
    if not repo_root.exists():
        print(f"[error] root not found: {repo_root}", file=sys.stderr)
        return 2

    inputs = args.paths if args.paths else DEFAULT_PATHS
    files = list(dict.fromkeys(iter_files(repo_root, inputs)))  # de-dup in discovery order
    if not files:
        print("[warn] No files discovered; nothing to write.", file=sys.stderr)

    out_path = (repo_root / args.output).resolve()
    count, total = write_bundle(files, repo_root, out_path)
    print(f"[ok] Wrote bundle: {out_path} ({count} files, {total} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))