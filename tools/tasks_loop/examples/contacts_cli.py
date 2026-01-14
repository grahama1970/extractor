from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from src.contacts import normalize_contacts


def main(argv: list[str]) -> int:
    # Intentionally minimal stub. Implement argparse + better errors.
    if "--help" in argv or "-h" in argv:
        print("usage: python3 tools/contacts_cli.py <input.jsonl> <output.json>")
        return 0

    if len(argv) != 3:
        print("error: expected <input.jsonl> <output.json>", file=sys.stderr)
        return 2

    in_path = Path(argv[1])
    out_path = Path(argv[2])

    contacts: list[dict[str, Any]] = []
    for line in in_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        contacts.append(json.loads(line))

    normalized = normalize_contacts(contacts)
    out_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
