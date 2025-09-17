#!/usr/bin/env python3
import sys
from pathlib import Path


REQUIRED_PHRASE = "Return ONLY a JSON"
FORBIDDEN = "```"


def lint_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{path}: failed to read ({e})"]

    if REQUIRED_PHRASE not in text:
        errors.append(f"{path}: missing required phrase: '{REQUIRED_PHRASE}'")
    if FORBIDDEN in text:
        errors.append(f"{path}: contains forbidden code fences '```'")
    return errors


def main() -> int:
    prompts_root = Path("prompts")
    if not prompts_root.exists():
        print("No prompts directory; nothing to lint.")
        return 0

    errors: list[str] = []
    for p in prompts_root.rglob("*"):
        if p.is_file() and p.suffix in {".txt", ".md"}:
            errors.extend(lint_file(p))

    if errors:
        print("Prompt lint errors:")
        for e in errors:
            print(" -", e)
        return 1
    print("Prompt lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

