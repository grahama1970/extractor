from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print("usage: python3 tools/table_count.py <pdf_path>")
        return 2

    pdf = Path(argv[1])
    if not pdf.exists():
        print(f"error: pdf not found: {pdf}", file=sys.stderr)
        return 2

    try:
        import camelot  # type: ignore
    except Exception as e:
        print(f"error: camelot not installed or failed to import: {e}", file=sys.stderr)
        return 2

    try:
        tables = camelot.read_pdf(str(pdf), pages="all")
    except Exception as e:
        print(f"error: failed to read pdf with camelot: {e}", file=sys.stderr)
        return 1

    print(json.dumps({"pdf": str(pdf), "tables_found": len(tables)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
