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
