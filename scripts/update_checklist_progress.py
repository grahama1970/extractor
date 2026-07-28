#!/usr/bin/env python3
"""
Update a progress meter in a Markdown checklist by counting GitHub-style checkboxes.

Looks for markers in the target file:
    <!-- progress:start -->
    Progress: X/Y (Z%) [########............]
    <!-- progress:end -->

Usage:
    python scripts/update_checklist_progress.py \
        tools/gold_annotator_web/docs/tasks/00N_Tasks_Unified_Checklist.md

If no path is provided, defaults to the unified checklist.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


DEFAULT_PATH = Path("tools/gold_annotator_web/docs/tasks/00N_Tasks_Unified_Checklist.md")


def count_checkboxes(text: str) -> tuple[int, int]:
    """Count checked and unchecked checkboxes in a text block."""
    total = 0
    done = 0
    in_code = False
    fence_re = re.compile(r"^\s*```")
    box_re = re.compile(r"^- \[( |x|X)\]", re.ASCII)
    for line in text.splitlines():
        if fence_re.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        if box_re.match(line.strip()):
            total += 1
            if line.strip().startswith("- [x]") or line.strip().startswith("- [X]"):
                done += 1
    return done, total


def render_meter(done: int, total: int, width: int = 40) -> str:
    """Render a progress meter string for given progress."""
    pct = int(round((done / total) * 100)) if total else 0
    filled = int(round((pct / 100) * width))
    bar = "#" * filled + "." * (width - filled)
    return f"Progress: {done}/{total} ({pct}%) [{bar}]"


def update_progress_block(text: str, meter_line: str) -> str:
    """Update progress markers in text with a new meter line."""
    start = "<!-- progress:start -->"
    end = "<!-- progress:end -->"
    if start in text and end in text:
        pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
        replacement = f"{start}\n{meter_line}\n{end}"
        return pattern.sub(replacement, text, count=1)
    # If markers not present, insert after first heading line
    lines = text.splitlines()
    for i, ln in enumerate(lines[:10]):
        if ln.startswith("# "):
            insert_at = i + 1
            break
    else:
        insert_at = 0
    lines[insert_at:insert_at] = [start, meter_line, end, ""]
    return "\n".join(lines) + ("\n" if not text.endswith("\n") else "")


def main() -> int:
    """Return an exit code after processing a file from command line."""
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    original = path.read_text(encoding="utf-8")
    done, total = count_checkboxes(original)
    meter = render_meter(done, total)
    updated = update_progress_block(original, meter)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
    print(meter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
