#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


def _load(path: Path) -> Dict[str, Any] | None:
    """Load JSON from a file path, returning None on failure."""
    if not path.exists():
        return None
    txt = path.read_text(encoding="utf-8", errors="ignore")
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            return obj
        # If the file contains a raw JSON string value
        if isinstance(obj, str):
            try:
                return json.loads(obj)
            except Exception:
                return {"raw": obj}
        return None
    except json.JSONDecodeError:
        # Try to parse nested JSON in a string-only file
        try:
            return json.loads(txt.strip())
        except Exception:
            return {"raw": txt.strip()}


def main() -> None:
    """Load JSON data from specified paths based on command-line arguments."""
    base = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path("data/results/pipeline/07_reflow_section/logs")
    )
    section = sys.argv[2] if len(sys.argv) > 2 else "section_0"
    strict_p = base / f"response_strict_{section}.json"
    compact_p = base / f"response_strict_compact_{section}.json"
    strict = _load(strict_p) or {}
    compact = _load(compact_p) or {}

    def _blocks(obj: Dict[str, Any]) -> int:
        """Return block count from reflowed_json, 0 if missing, -1 on error."""
        try:
            return int(len(((obj.get("reflowed_json") or {}).get("blocks") or [])))
        except Exception:
            return -1

    diff = {
        "section": section,
        "strict_path": str(strict_p),
        "compact_path": str(compact_p),
        "strict_blocks": _blocks(strict),
        "compact_blocks": _blocks(compact),
        "strict_title": (
            (strict.get("reflowed_json") or {}).get("title")
            if isinstance(strict.get("reflowed_json"), dict)
            else None
        ),
        "compact_title": (
            (compact.get("reflowed_json") or {}).get("title")
            if isinstance(compact.get("reflowed_json"), dict)
            else None
        ),
        "notes": "Counts are indicative; inspect logs for full details.",
    }

    outdir = Path("scripts/artifacts")
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"07_{section}_diff_compact_vs_strict.json"
    out.write_text(json.dumps(diff, indent=2), encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
