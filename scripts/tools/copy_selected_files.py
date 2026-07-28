#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.16.0",
# ]
# ///
"""
Concatenate a curated set of project files into a single Markdown bundle for LLMs.

Features
- Uses Git to respect .gitignore exactly when available (authoritative).
- Graceful fallback when not in Git: best-effort ignore based on root .gitignore and common folders.
- Skips binaries/images; size guards to avoid oversized inputs.
- Flexible selection: include extra filename globs or extensions; exclude paths; opt-in to include ignored files.
- Clear file boundaries with Markdown fences for LLM-friendly ingestion.

Examples
  # Standard run (respects .gitignore if in Git)
  python copy_selected_files.py --root . --output bundle.txt

  # Include extra file types or special filenames (globs on names)
  python copy_selected_files.py --include-ext ".proto,Justfile,vite.config.ts"

  # Add extra explicit path excludes
  python copy_selected_files.py --extra-exclude-paths "misc/big_fixture.json,notes/tmp.txt"

  # Force include .gitignored files (audits)
  python copy_selected_files.py --include-ignored

  # Ignore .gitignore entirely (fallback walk only)
  python copy_selected_files.py --no-respect-gitignore
"""

from __future__ import annotations
import fnmatch
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple

import typer


# ---------------------------- Utility helpers ----------------------------


def _run_git(root: Path, args: Sequence[str], check: bool = False) -> tuple[int, str, str]:
    """Run a git command from a specific root and capture output."""
    cmd = ["git", "-C", str(root), *args]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.returncode, proc.stdout, proc.stderr


def _is_git_repo(root: Path) -> bool:
    """Check if a directory is a Git repository."""
    code, out, _ = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    return code == 0 and out.strip() == "true"


def _now_utc_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _posix_rel_path(path: Path, start: Path) -> str:
    """Return the POSIX path relative to the start directory."""
    return path.relative_to(start).as_posix()


def _read_text(path: Path, encoding: str = "utf-8") -> str:
    """Read text content from a file path, replacing encoding errors."""
    with path.open("r", encoding=encoding, errors="replace") as f:
        return f.read()


def _is_binary_by_content(path: Path, sample_bytes: int = 4096) -> bool:
    """Check if a file is binary by analyzing its initial content."""
    try:
        with path.open("rb") as f:
            chunk = f.read(sample_bytes)
        if b"\0" in chunk:
            return True
        # Heuristic: consider >30% of bytes outside typical text range as binary
        if not chunk:
            return False
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
        nontext = sum(b not in text_chars for b in chunk)
        return (nontext / len(chunk)) > 0.30
    except OSError:
        return True


# ---------------------------- Selection rules ----------------------------


DEFAULT_EXCLUDE_DIRS: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".output",
    ".svelte-kit",
    "coverage",
    ".cache",
    ".parcel-cache",
    ".turbo",
    ".vite",
    ".vercel",
    ".expo",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "artifacts",
}


DEFAULT_BINARY_EXTS: Set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".icns",
    ".bmp",
    ".tif",
    ".tiff",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".so",
    ".dylib",
    ".a",
    ".lib",
    ".exe",
    ".dll",
}


LANG_BY_EXT = {
    ".py": "python",
    ".rs": "rust",
    ".go": "go",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "ts",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".md": "markdown",
    ".txt": "text",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".xml": "xml",
    ".svg": "xml",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".dockerfile": "dockerfile",
    ".proto": "proto",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "cs",
}


def _lang_for_file(path: Path) -> str:
    """Determine language type based on file path or extension."""
    name = path.name.lower()
    if name == "dockerfile":
        return "dockerfile"
    return LANG_BY_EXT.get(path.suffix.lower(), "")


def _parse_csv_list(value: Optional[str]) -> List[str]:
    """Parse a comma-separated string into a list of stripped items."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_patterns(patterns: Iterable[str]) -> List[str]:
    """Normalize patterns by stripping whitespace and excluding comments."""
    norm: List[str] = []
    for p in patterns:
        p = p.strip()
        if not p or p.startswith("#"):
            continue
        norm.append(p)
    return norm


def _matches_any(path_rel: str, patterns: Sequence[str]) -> bool:
    # Try matching both on full relative path and the basename
    base = path_rel.split("/")[-1]
    for pat in patterns:
        # Support simple ".ext" include patterns
        if pat.startswith(".") and "." in base and base.endswith(pat):
            return True
        if "/" in pat:
            if fnmatch.fnmatch(path_rel, pat):
                return True
        else:
            if fnmatch.fnmatch(base, pat):
                return True
    return False


def _read_gitignore_patterns(root: Path) -> List[str]:
    """Extract and normalize Git ignore patterns from repository files."""
    patterns: List[str] = []
    gi = root / ".gitignore"
    if gi.is_file():
        patterns.extend(_normalize_patterns(_read_text(gi).splitlines()))
    # Also consider .git/info/exclude if present
    info_exclude = root / ".git" / "info" / "exclude"
    if info_exclude.is_file():
        patterns.extend(_normalize_patterns(_read_text(info_exclude).splitlines()))
    return patterns


def _ignored_by_patterns(path_rel: str, patterns: Sequence[str]) -> bool:
    # Naive best-effort: treat patterns as fnmatch globs relative to repo root
    # and directory suffixes ("dir/") as recursive dir ignores.
    for p in patterns:
        if p.endswith("/"):
            # directory pattern: ignore if path starts with that dir
            if path_rel.startswith(p[:-1]):
                return True
        else:
            if fnmatch.fnmatch(path_rel, p):
                return True
            # Also attempt basename match
            base = path_rel.split("/")[-1]
            if fnmatch.fnmatch(base, p):
                return True
    return False


# ---------------------------- Discovery ----------------------------


def discover_files(
    root: Path,
    respect_gitignore: bool,
    include_ignored: bool,
    extra_exclude_paths: Sequence[str],
) -> List[Path]:
    """Return a list of candidate files under root, relative to root.

    If inside a Git repo and respect_gitignore=True, uses git ls-files (authoritative).
    Otherwise, falls back to a best-effort os.walk with simple .gitignore glob handling.
    """
    root = root.resolve()

    # Git-based discovery
    if respect_gitignore and _is_git_repo(root):
        args = ["ls-files", "-co", "--exclude-standard"]
        if include_ignored:
            args = ["ls-files", "-coi", "--exclude-standard"]
        code, out, err = _run_git(root, args)
        if code != 0:
            print(
                f"Warning: git discovery failed, falling back to walk: {err.strip()}",
                file=sys.stderr,
            )
        else:
            rels = [line.strip() for line in out.splitlines() if line.strip()]
            # Filter: exclude paths containing any excluded directory at any depth
            rels = [
                r for r in rels if not any(part in DEFAULT_EXCLUDE_DIRS for part in r.split("/"))
            ]
            if extra_exclude_paths:
                rels = [r for r in rels if not _matches_any(r, extra_exclude_paths)]
            return [root / r for r in rels if (root / r).is_file()]

    # Fallback: os.walk with best-effort ignore handling
    ignore_patterns: List[str] = []
    if respect_gitignore:
        ignore_patterns = _read_gitignore_patterns(root)

    results: List[Path] = []
    for base, dirs, files in os.walk(root):
        # Prune excluded directories aggressively
        rel_base = _posix_rel_path(Path(base), root)
        # Rel path for base is "." for root; normalize
        if rel_base == ".":
            rel_base = ""

        # Prune default exclude dirs
        pruned_dirs = []
        for d in list(dirs):
            if d in DEFAULT_EXCLUDE_DIRS:
                pruned_dirs.append(d)
                continue
            full_rel = (Path(rel_base) / d).as_posix() if rel_base else d
            if respect_gitignore and _ignored_by_patterns(full_rel + "/", ignore_patterns):
                pruned_dirs.append(d)
        for d in pruned_dirs:
            if d in dirs:
                dirs.remove(d)

        for fname in files:
            rel = (Path(rel_base) / fname).as_posix() if rel_base else fname
            if extra_exclude_paths and _matches_any(rel, extra_exclude_paths):
                continue
            if respect_gitignore and _ignored_by_patterns(rel, ignore_patterns):
                continue
            results.append(root / rel)

    return [p for p in results if p.is_file()]


# ---------------------------- Filtering ----------------------------


@dataclass
class FilterOptions:
    """Filter files based on patterns, size limits, and large file allowance."""
    include_patterns: List[str]
    max_file_bytes: int
    allow_large: bool


def should_include_file(path: Path, rel: str, opts: FilterOptions) -> bool:
    # Include patterns bypass extension-based filtering only (not size or binary checks)
    matched_include = _matches_any(rel, opts.include_patterns) if opts.include_patterns else False

    # Skip binaries by extension first
    if path.suffix.lower() in DEFAULT_BINARY_EXTS and not matched_include:
        return False

    # Size guard
    try:
        size = path.stat().st_size
    except OSError:
        return False

    if not opts.allow_large and size > opts.max_file_bytes:
        return False

    # Content-based binary heuristic
    if _is_binary_by_content(path):
        return False

    return True


# ---------------------------- Concatenation ----------------------------


def write_bundle(
    root: Path,
    files: Sequence[Path],
    output: Path,
    encoding: str,
    max_total_bytes: int,
) -> Tuple[int, int]:
    """Write a Markdown-formatted bundle with code fences and headers.

    Returns (written_files_count, written_bytes_total).
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    written = 0

    # Compute Git metadata if available
    git_desc = ""
    if _is_git_repo(root):
        code, out, _ = _run_git(root, ["rev-parse", "--short", "HEAD"])
        rev = out.strip() if code == 0 else "unknown"
        code, out, _ = _run_git(root, ["status", "--porcelain"])
        dirty = "+dirty" if out.strip() else ""
        git_desc = f"{rev}{dirty}"

    header = textwrap.dedent(
        f"""
        # Project Bundle

        - Generated: {_now_utc_iso()}
        - Root: {root}
        - Git: {git_desc or 'n/a'}
        - Files: {len(files)}

        ---
        """
    ).lstrip("\n")

    header_bytes = header.encode(encoding, errors="replace")

    with output.open("w", encoding=encoding, errors="replace", newline="\n") as out_f:
        out_f.write(header)
        total_bytes += len(header_bytes)

        for p in files:
            rel = _posix_rel_path(p, root)
            try:
                content = _read_text(p, encoding=encoding)
            except Exception as e:  # noqa: BLE001
                # Skip unreadable files but make it visible in bundle
                msg = f"[SKIP unreadable: {rel}: {e}]\n\n"
                msg_b = msg.encode(encoding, errors="replace")
                if total_bytes + len(msg_b) > max_total_bytes:
                    break
                out_f.write(msg)
                total_bytes += len(msg_b)
                continue

            lang = _lang_for_file(p)
            fence_open = f"```{lang}\n" if lang else "```\n"
            fence_close = "```\n"

            # File header block
            file_header = f"\n\n====== BEGIN FILE: {rel} ======\n"
            file_footer = "\n====== END FILE ======\n"

            block = (
                file_header
                + fence_open
                + content
                + ("\n" if not content.endswith("\n") else "")
                + fence_close
                + file_footer
            )
            block_b = block.encode(encoding, errors="replace")

            if total_bytes + len(block_b) > max_total_bytes:
                break

            out_f.write(block)
            written += 1
            total_bytes += len(block_b)

    return written, total_bytes


# ---------------------------- Typer CLI ----------------------------


def build_cli() -> typer.Typer:
    """Build a CLI application for bundling project files for LLMs."""
    app = typer.Typer(help="Concatenate selected project files into a single bundle for LLMs")

    @app.callback(invoke_without_command=True)
    def run(
        root: Path = typer.Option(Path("."), "--root", help="Project root to scan"),
        output: Path = typer.Option(
            Path("bundle.txt"),
            "--output",
            "-o",
            help="Output path for the concatenated bundle",
        ),
        include_ext: Optional[str] = typer.Option(
            None,
            "--include-ext",
            help="Comma-separated list of filename globs or extensions to force-include (e.g. '.proto,Justfile,vite.config.ts')",
        ),
        extra_exclude_paths: Optional[str] = typer.Option(
            None,
            "--extra-exclude-paths",
            help="Comma-separated relative path globs to exclude additionally",
        ),
        no_respect_gitignore: bool = typer.Option(
            False,
            "--no-respect-gitignore",
            help="Do not use .gitignore even if present; walk filesystem instead",
        ),
        include_ignored: bool = typer.Option(
            False,
            "--include-ignored",
            help="If in Git and respecting .gitignore, include ignored files too",
        ),
        max_file_bytes: int = typer.Option(
            512_000,
            "--max-file-bytes",
            help="Per-file size guard; files larger than this are skipped unless --allow-large",
        ),
        allow_large: bool = typer.Option(
            False,
            "--allow-large",
            help="Allow files larger than --max-file-bytes",
        ),
        max_total_bytes: int = typer.Option(
            10_000_000,
            "--max-total-bytes",
            help="Stop writing once total bytes in output reach this threshold",
        ),
        encoding: str = typer.Option(
            "utf-8", "--encoding", help="Encoding used to read files and write output"
        ),
        list_only: bool = typer.Option(
            False, "--list", help="List selected files and exit (no bundle writing)"
        ),
        dry_run: bool = typer.Option(
            False, "--dry-run", help="Do not write output, only print selection summary"
        ),
    ) -> None:
        """Create a bundle or list selected files."""

        root_resolved = root.resolve()
        include_patterns = _parse_csv_list(include_ext or "")
        extra_excludes = _parse_csv_list(extra_exclude_paths or "")

        files_all = discover_files(
            root=root_resolved,
            respect_gitignore=not no_respect_gitignore,
            include_ignored=include_ignored,
            extra_exclude_paths=extra_excludes,
        )

        fopts = FilterOptions(
            include_patterns=include_patterns,
            max_file_bytes=max_file_bytes,
            allow_large=allow_large,
        )

        selected: List[Path] = []
        for p in files_all:
            rel = _posix_rel_path(p, root_resolved)
            if should_include_file(p, rel, fopts):
                selected.append(p)

        selected.sort(key=lambda x: _posix_rel_path(x, root_resolved))

        if list_only or dry_run:
            typer.echo(f"Root: {root_resolved}")
            typer.echo(
                f"Git: {'yes' if _is_git_repo(root_resolved) else 'no'} (respect={not no_respect_gitignore}, include_ignored={include_ignored})"
            )
            typer.echo(f"Candidates: {len(files_all)}  -> Selected: {len(selected)}")
            for p in selected:
                typer.echo(_posix_rel_path(p, root_resolved))
            raise typer.Exit(0)

        written, total = write_bundle(
            root=root_resolved,
            files=selected,
            output=output,
            encoding=encoding,
            max_total_bytes=max_total_bytes,
        )
        typer.echo(f"Wrote {written} files to {output} ({total} bytes)")

    return app


app = build_cli()


def main() -> None:
    """Entry point for executable scripts."""
    app()


if __name__ == "__main__":
    # VS Code-friendly: running this file directly uses option defaults.
    main()
