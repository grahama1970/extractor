from __future__ import annotations

from src.contacts import normalize_contacts


CLARIFY_EXIT = 42


def _first_name(raw: str) -> str:
    raw = (raw or "").strip()
    return raw.split()[0].lower() if raw else ""


def main() -> int:
    inp = [
        {"Name": "  Ada   Lovelace ", "Email": " ADA@EXAMPLE.COM "},
        {"name": "Ada L.", "email": "ada@example.com"},
        {"name": "  Grace  Hopper", "email": "grace@example.com"},
        {"name": "", "email": "grace@example.com"},
        {"name": "Linus Torvalds", "email": "LINUS@EXAMPLE.COM"},
        {"name": "Linus", "email": "linus@example.com"},
        # Uncomment to test clarification:
        # {"name": "Eunice Example", "email": "eunice@example.com"},
    ]

    for c in inp:
        name = c.get("name") or c.get("Name") or ""
        if _first_name(name) == "eunice":
            print("CLARIFY: Found contact with first name 'Eunice' in input.")
            print("CLARIFY: What is Eunice's correct email address?")
            print("CLARIFY: What is Eunice's full name (preferred formatting)?")
            print("CLARIFY: Should Eunice be included in normalized output?")
            raise SystemExit(CLARIFY_EXIT)

    out = normalize_contacts(inp)

    exp = [
        {"name": "Ada Lovelace", "email": "ada@example.com"},
        {"name": "Grace Hopper", "email": "grace@example.com"},
        {"name": "Linus Torvalds", "email": "linus@example.com"},
    ]
    assert out == exp, f"\nGOT:\n{out}\n\nEXPECTED:\n{exp}\n"
    print("OK: gate_normalize_contacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
