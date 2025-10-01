#!/usr/bin/env python3
"""
review_bundle.py — Generate a single-file review bundle with context notes.

Outputs a text file that begins with a concise "UX Review Notes" section,
followed by the latest contents of requested files, each wrapped in BEGIN/END
markers. Tabs are expanded to spaces for consistent rendering.

Usage examples:

  # Default files and destination
  python scripts/tools/review_bundle.py

  # Custom destination and explicit file list (space-separated)
  python scripts/tools/review_bundle.py \
    --out scripts/artifacts/ux_review_bundle_with_notes.txt \
    --files \
      prototypes/tabbed/html/src/components/ThumbnailRail.tsx \
      prototypes/tabbed/html/src/pages/ClassicLayout.tsx \
      prototypes/tabbed/html/src/components/ThumbnailStrip.tsx \
      prototypes/tabbed/html/src/components/SearchPanel.tsx \
      prototypes/tabbed/html/src/components/PdfCanvas.tsx \
      prototypes/tabbed/html/src/lib/pdf.ts

  # Provide a notes file or inline notes text
  python scripts/tools/review_bundle.py --notes-file scripts/artifacts/ux_review_notes.md
  python scripts/tools/review_bundle.py --notes "Left rail crop, root cause: row-height headroom; fix applied: +36 and width=220."

Exit codes: 0 on success; non-zero on error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime


DEFAULT_FILES = [
    "prototypes/tabbed/html/src/components/ThumbnailRail.tsx",
    "prototypes/tabbed/html/src/pages/ClassicLayout.tsx",
    "prototypes/tabbed/html/src/components/ThumbnailStrip.tsx",
    "prototypes/tabbed/html/src/components/SearchPanel.tsx",
    "prototypes/tabbed/html/src/components/PdfCanvas.tsx",
    "prototypes/tabbed/html/src/lib/pdf.ts",
]


def read_text_file(path: Path) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
        return txt.replace("\t", "    ")
    except FileNotFoundError:
        return f"[ERROR] File not found: {path}"
    except Exception as e:
        return f"[ERROR] Failed to read {path}: {e}"


def default_notes(files: list[str]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        "# UX Review Notes (Tabbed Classic)\n\n"
        f"- Generated: {now}\n"
        "- Scope: left-rail thumbnails, bottom filmstrip thumbnails, top toolbar/search tray.\n"
        "- Route: /main\n"
        f"- Files: {', '.join(files)}\n\n"
        "## Issues\n"
        "- Left rail: thumbnails cropped at bottom in some widths.\n"
        "- Filmstrip: cropped when height < itemWidth*4/3.\n"
        "- Toolbar: search tray overlapped toolbar content.\n\n"
        "## Root causes\n"
        "- ThumbnailRail.tsx: row height used outer width; not enough headroom for 3:4 image + padding + caption.\n"
        "- ClassicLayout.tsx: rail width could be tight with caption/padding.\n"
        "- ThumbnailStrip.tsx: height smaller than 3:4 for chosen width.\n"
        "- SearchPanel.tsx: z-index above toolbar.\n\n"
        "## Current repo changes\n"
        "- ThumbnailRail.tsx: height = round(max(1, (width-16)) * 4/3) + 36; 3:4 object-contain; active ring.\n"
        "- ClassicLayout.tsx: <ThumbnailRail width={220}/>; left Sidebar is shrink-0.\n"
        "- ThumbnailStrip.tsx: effectiveHeight = max(height, itemWidth*4/3 + 16).\n"
        "- SearchPanel.tsx: tray z-index lowered under toolbar.\n\n"
        "## Acceptance\n"
        "- Left rail: no cropping at width=220; active ring visible; canvas not squeezed.\n"
        "- Filmstrip: no cropping at itemWidth=100.\n"
        "- Toolbar: no overlap when Search opens.\n\n"
        "## Alternatives\n"
        "- Increase headroom further (+40) or remove caption under thumbs.\n"
        "- Revert only the four UI files to last-known-good.\n\n"
        "## Repro steps\n"
        "1) Load /main\n"
        "2) Toggle Thumbs between Left rail and Bottom filmstrip\n"
        "3) Resize left pane; scroll rail; verify no crop\n"
        "4) Open Search (Cmd/Ctrl+K); toolbar remains readable\n"
    )


def build_bundle(out_path: Path, files: list[str], notes_text: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("===== BEGIN UX REVIEW NOTES =====\n")
        f.write(notes_text.rstrip() + "\n")
        f.write("\n===== END UX REVIEW NOTES =====\n\n")
        for rel in files:
            p = Path(rel)
            f.write(f"===== BEGIN {rel} =====\n")
            f.write(read_text_file(p))
            f.write("\n\n")
            f.write(f"===== END {rel} =====\n\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate a single-file review bundle with notes.")
    ap.add_argument(
        "--out",
        default="scripts/artifacts/ux_review_bundle_with_notes.txt",
        help="Output file path (default: scripts/artifacts/ux_review_bundle_with_notes.txt)",
    )
    ap.add_argument(
        "--notes-file",
        default=None,
        help="Optional markdown file containing the review notes section to place at the top.",
    )
    ap.add_argument(
        "--notes",
        default=None,
        help="Inline notes text to place at the top when --notes-file is not provided.",
    )
    ap.add_argument(
        "--files",
        nargs="+",
        default=DEFAULT_FILES,
        help="List of files to include in the bundle (space-separated).",
    )
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    files = ns.files
    out_path = Path(ns.out)
    # Determine notes text
    if ns.notes_file:
        try:
            notes_text = Path(ns.notes_file).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"error: failed to read --notes-file: {e}", file=sys.stderr)
            return 2
    elif ns.notes:
        notes_text = str(ns.notes)
    else:
        notes_text = default_notes(files)

    try:
        build_bundle(out_path, files, notes_text)
    except Exception as e:
        print(f"error: failed to build bundle: {e}", file=sys.stderr)
        return 3

    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
bundle_ux_review.py — create a single review bundle (notes + files) for UX/code review.

Features:
- Inputs: direct file paths, glob patterns, --files-list, or --from-git <A..B> (diff).
- Deterministic separators: "===== BEGIN <path> =====" / "===== END <path> =====".
- Options: line numbers, tab expansion, CRLF -> LF, preview lines, zip output.
- Writes a JSON manifest with per-file byte offsets + line ranges (agent-friendly).
- Graceful git metadata collection (optional).
"""

from __future__ import annotations
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
import time
import zipfile
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Any, Optional

SEP_BEGIN_NOTES = "===== BEGIN UX REVIEW NOTES ====="
SEP_END_NOTES = "===== END UX REVIEW NOTES ====="
SEP_BEGIN_META = "===== BUNDLE METADATA ====="
SEP_END_META = "===== END BUNDLE METADATA ====="

DEFAULT_NOTES = """# UX Review Notes (Tabbed Classic)

- Scope: left-rail thumbnails, bottom filmstrip thumbnails, top toolbar/search tray.
- Route: /main
- Files: ThumbnailRail.tsx, ClassicLayout.tsx, ThumbnailStrip.tsx, SearchPanel.tsx, PdfCanvas.tsx, lib/pdf.ts

Issues
- Left rail: thumbnails cropped at bottom in some widths.
- Filmstrip: cropped when height < itemWidth*4/3.
- Toolbar: search tray overlapped toolbar content.

Root causes
- ThumbnailRail.tsx: row height used outer width; not enough headroom for 3:4 image + padding + caption.
- ClassicLayout.tsx: rail width 200 was tight with caption/padding.
- ThumbnailStrip.tsx: height smaller than 3:4 for chosen width.
- SearchPanel.tsx: z-index above toolbar.

Current repo changes
- ThumbnailRail.tsx: height = round(max(1, (width-16)) * 4/3) + 36; 3:4 object-contain, active ring.
- ClassicLayout.tsx: <ThumbnailRail width={220} />; left Sidebar is shrink-0.
- ThumbnailStrip.tsx: effectiveHeight = max(height, itemWidth*4/3 + 16).
- SearchPanel.tsx: tray z-index lowered under toolbar.

Acceptance
- Left rail: no cropping at width=220; active ring visible; canvas not squeezed.
- Filmstrip: no cropping at itemWidth=100.
- Toolbar: no overlap when Search opens.

Alternatives
- Increase headroom further (+40) or remove caption under thumbs.
- Revert only the four UI files to last-known-good.

Repro steps
1) Load /main
2) Toggle Thumbs between Left rail and Bottom filmstrip
3) Resize left pane; scroll rail; verify no crop
4) Open Search (Cmd/Ctrl+K); toolbar remains readable
"""

DEFAULT_FILES = [
    "prototypes/tabbed/html/src/components/ThumbnailRail.tsx",
    "prototypes/tabbed/html/src/pages/ClassicLayout.tsx",
    "prototypes/tabbed/html/src/components/ThumbnailStrip.tsx",
    "prototypes/tabbed/html/src/components/SearchPanel.tsx",
    "prototypes/tabbed/html/src/components/PdfCanvas.tsx",
    "prototypes/tabbed/html/src/lib/pdf.ts",
]

def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check, capture_output=True, text=True)

def git_info() -> Dict[str, str]:
    try:
        run(["git", "rev-parse", "--is-inside-work-tree"])
    except Exception:
        return {"repo": "(not a git repo)"}
    def safe(cmd: List[str]) -> str:
        try:
            return run(cmd).stdout.strip()
        except Exception:
            return ""
    repo_top = safe(["git", "rev-parse", "--show-toplevel"])
    branch = safe(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    sha = safe(["git", "rev-parse", "--short=12", "HEAD"])
    dirty = safe(["git", "status", "--porcelain=v1"])
    return {
        "repo": Path(repo_top).name if repo_top else "",
        "branch": branch,
        "commit": sha,
        "dirty_files": str(len(dirty.splitlines())) if dirty else "0",
    }

def files_from_git_range(diff_range: str, include_untracked: bool, path_globs: List[str]) -> List[str]:
    """Return changed files in diff_range (e.g., HEAD~1..HEAD). Optionally include untracked."""
    files: List[str] = []
    try:
        cp = run(["git", "diff", "--name-only", diff_range])
        files.extend([l for l in cp.stdout.splitlines() if l.strip()])
        if include_untracked:
            cp2 = run(["git", "ls-files", "--other", "--exclude-standard"], check=False)
            files.extend([l for l in cp2.stdout.splitlines() if l.strip()])
    except Exception:
        pass
    # If path_globs provided, filter
    if path_globs:
        from fnmatch import fnmatch
        files = [f for f in files if any(fnmatch(f, g) for g in path_globs)]
    # Keep only existing files
    return [f for f in files if Path(f).is_file()]

def expand_inputs(paths: List[str]) -> List[Path]:
    out: List[Path] = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        # support glob patterns
        if any(ch in p for ch in ["*", "?", "["]):
            out.extend(sorted(Path().glob(p)))
        else:
            out.append(Path(p))
    # de-dup while preserving order
    seen = set()
    uniq: List[Path] = []
    for p in out:
        rp = str(p.resolve()) if p.exists() else str(p)
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq

def normalize_text(s: str, expand_tabs: int | None, add_final_newline: bool) -> str:
    # Normalize CRLF -> LF, expand tabs if requested
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    if expand_tabs and expand_tabs > 0:
        s = s.expandtabs(expand_tabs)
    if add_final_newline and (not s.endswith("\n")):
        s += "\n"
    return s

def with_line_numbers(s: str, width: int = 6) -> str:
    lines = s.splitlines(True)  # keepends
    out = []
    ln = 1
    for L in lines:
        out.append(f"{ln:>{width}}  {L}")
        ln += 1
    return "".join(out)

def size_human(p: Path) -> str:
    try:
        n = p.stat().st_size
        for u in ["B", "KB", "MB", "GB"]:
            if n < 1024.0 or u == "GB":
                return f"{n:.1f} {u}" if u != "B" else f"{n} {u}"
            n /= 1024.0
    except Exception:
        return "(unknown)"
    return "(unknown)"

def build_metadata(bundle_path: Path, notes_path: Path, files: List[Path]) -> Dict[str, Any]:
    meta = {
        "generated_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "bundle_path": str(bundle_path),
        "notes_path": str(notes_path),
        "git": git_info(),
        "files": [
            {
                "path": str(f),
                "exists": f.is_file(),
                "size": size_human(f) if f.is_file() else None,
            }
            for f in files
        ],
    }
    return meta

def write_zip(zip_out: Path, paths: List[Path]) -> None:
    zip_out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in paths:
            if p.exists():
                zf.write(p, arcname=p.name)

def iter_stdin_lines() -> Iterable[str]:
    for line in sys.stdin:
        yield line.rstrip("\n")

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Create a review bundle (notes + files) with stable separators and a JSON manifest.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--bundle", default="scripts/artifacts/ux_review_bundle_with_notes.txt", type=Path)
    ap.add_argument("--notes", default="scripts/artifacts/ux_review_notes.md", type=Path)
    ap.add_argument("--notes-from", default=None, type=Path, help="Read notes markdown from this file instead of default text.")
    ap.add_argument("--notes-stdin", action="store_true", help="Read notes markdown from STDIN.")
    ap.add_argument("--files", nargs="*", help="Files or glob patterns to include. If omitted, uses defaults.")
    ap.add_argument("--files-list", type=Path, help="Path to a text file (one path per line) listing files to include.")
    ap.add_argument("--from-git", metavar="RANGE", help="Use git diff to collect changed files (e.g., HEAD~1..HEAD).")
    ap.add_argument("--git-include-untracked", action="store_true", help="When using --from-git, include untracked files.")
    ap.add_argument("--git-filter", nargs="*", default=[], help="Optional glob filters applied to git file list.")
    ap.add_argument("--line-nums", action="store_true", help="Include line numbers in file sections.")
    ap.add_argument("--tab-width", type=int, default=4, help="Spaces per tab (0 = no expansion).")
    ap.add_argument("--preview-lines", type=int, default=60)
    ap.add_argument("--zip-out", type=Path, default=None, help="Also write a .zip containing the bundle and notes.")
    ap.add_argument("--manifest", type=Path, default=None, help="Write JSON manifest with offsets and metadata.")
    ap.add_argument("--allow-missing", action="store_true", help="Do not fail if some files are missing; mark them in bundle.")
    args = ap.parse_args()

    # Collect notes text
    if args.notes_stdin:
        notes_text = normalize_text(sys.stdin.read(), args.tab_width, True)
    elif args.notes_from:
        if not args.notes_from.is_file():
            print(f"[ERROR] --notes-from not found: {args.notes_from}", file=sys.stderr)
            return 2
        notes_text = normalize_text(args.notes_from.read_text(encoding="utf-8", errors="replace"), args.tab_width, True)
    else:
        notes_text = normalize_text(DEFAULT_NOTES, args.tab_width, True)

    # Determine file list
    collected: List[str] = []
    if args.from_git:
        collected.extend(files_from_git_range(args.from_git, args.git_include_untracked, args.git_filter))
    if args.files_list:
        if not args.files_list.is_file():
            print(f"[ERROR] --files-list not found: {args.files_list}", file=sys.stderr)
            return 2
        collected.extend([l.strip() for l in args.files_list.read_text(encoding="utf-8").splitlines() if l.strip()])
    if args.files:
        collected.extend(args.files)
    if not collected:
        collected = DEFAULT_FILES

    files = expand_inputs(collected)

    # Prepare artifacts dir
    args.bundle.parent.mkdir(parents=True, exist_ok=True)
    args.notes.parent.mkdir(parents=True, exist_ok=True)

    # Write/refresh notes file on disk
    args.notes.write_text(notes_text, encoding="utf-8")

    # Build metadata (pre)
    meta = build_metadata(args.bundle, args.notes, files)

    # Assemble bundle with offsets
    manifest: Dict[str, Any] = {
        "metadata": meta,
        "sections": {
            "notes": {},
            "meta": {},
            "files": {}
        }
    }

    def w(s: str) -> bytes:
        return s.encode("utf-8")

    byte_offset = 0
    with args.bundle.open("wb") as out:
        # Notes
        out.write(w(SEP_BEGIN_NOTES + "\n"))
        start = byte_offset; byte_offset += len(w(SEP_BEGIN_NOTES + "\n"))
        out.write(w(notes_text))
        byte_offset += len(w(notes_text))
        out.write(w("\n" + SEP_END_NOTES + "\n\n"))
        end = byte_offset; byte_offset += len(w("\n" + SEP_END_NOTES + "\n\n"))
        manifest["sections"]["notes"] = {"begin": SEP_BEGIN_NOTES, "end": SEP_END_NOTES, "byte_start": start, "byte_end": end}

        # Metadata
        out.write(w(SEP_BEGIN_META + "\n"))
        mstart = byte_offset; byte_offset += len(w(SEP_BEGIN_META + "\n"))
        meta_lines = [
            f"Generated: {meta['generated_utc']}",
            f"Repo: {meta['git'].get('repo','')}",
            f"Branch: {meta['git'].get('branch','')}",
            f"Commit: {meta['git'].get('commit','')}",
            f"Dirty files: {meta['git'].get('dirty_files','')}",
            f"Bundle path: {meta['bundle_path']}",
            f"Notes path:  {meta['notes_path']}",
            "Files:",
        ]
        for f in files:
            if f.is_file():
                meta_lines.append(f"  - {f} ({size_human(f)})")
            else:
                meta_lines.append(f"  - {f} (MISSING)")
        meta_text = "\n".join(meta_lines) + "\n"
        out.write(w(meta_text))
        byte_offset += len(w(meta_text))
        out.write(w(SEP_END_META + "\n\n"))
        mend = byte_offset; byte_offset += len(w(SEP_END_META + "\n\n"))
        manifest["sections"]["meta"] = {"begin": SEP_BEGIN_META, "end": SEP_END_META, "byte_start": mstart, "byte_end": mend}

        # Files
        file_missing = []
        for f in files:
            begin_tag = f"===== BEGIN {f} ====="
            end_tag = f"===== END {f} ====="
            out.write(w(begin_tag + "\n"))
            fstart = byte_offset; byte_offset += len(w(begin_tag + "\n"))
            if f.is_file():
                raw = f.read_text(encoding="utf-8", errors="replace")
                norm = normalize_text(raw, args.tab_width if args.tab_width > 0 else None, True)
                if args.line_nums:
                    norm = with_line_numbers(norm)
                out.write(w(norm + "\n"))
                byte_offset += len(w(norm + "\n"))
            else:
                msg = f"[ERROR] File not found: {f}\n"
                out.write(w(msg + "\n"))
                byte_offset += len(w(msg + "\n"))
                file_missing.append(str(f))
            out.write(w(end_tag + "\n\n"))
            fend = byte_offset; byte_offset += len(w(end_tag + "\n\n"))
            manifest["sections"]["files"][str(f)] = {
                "begin": begin_tag, "end": end_tag,
                "byte_start": fstart, "byte_end": fend,
            }

    # Preview
    try:
        with args.bundle.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
        print(f"{args.bundle}  ({args.bundle.stat().st_size} bytes)")
        n = max(args.preview_lines, 0)
        if n:
            print(f"\nPreview (first {n} lines):\n")
            for L in lines[:n]:
                sys.stdout.write(L)
    except Exception as e:
        print(f"[WARN] Could not preview: {e}", file=sys.stderr)

    print(f"\n\nBundle path: {args.bundle}")

    # Optional zip
    if args.zip_out:
        write_zip(args.zip_out, [args.bundle, args.notes])
        print(f"Zip archive: {args.zip_out}")

    # Manifest
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Manifest written: {args.manifest}")

    # Exit code
    if not args.allow_missing:
        # fail if any missing file
        missing_any = any(not Path(p).is_file() for p in files)
        if missing_any:
            return 3
    return 0

if __name__ == "__main__":
    sys.exit(main())
