#!/usr/bin/env python3
import sys
import fitz

def main():
    try:
        doc = fitz.open("fixtures/camelot_fixture.pdf")
        print(f"OK: Opened PDF with {len(doc)} pages")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
