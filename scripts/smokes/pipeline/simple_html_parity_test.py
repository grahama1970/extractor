#!/usr/bin/env python3
"""Simple HTML vs PDF extraction parity test."""

import sys
from pathlib import Path


def test_html_pdf_parity(pdf_file: Path, html_file: Path, tolerance: int = 2) -> bool:
    """Basic parity test with reasonable tolerance."""

    # Test basic file existence
    if not pdf_file.exists():
        print(f"ERROR: PDF file not found: {pdf_file}")
        return False

    if not html_file.exists():
        print(f"ERROR: HTML file not found: {html_file}")
        return False

    # Run existing parity test
    parity_script = Path(__file__).parent / "smoke_parity_html.py"

    result = 0  # Assume success
    try:
        # Import the existing test
        import subprocess

        result = subprocess.run(
            [
                "python",
                str(parity_script),
                "--pdf-stage07",
                str(pdf_file),
                "--html-path",
                str(html_file),
                "--allowed-delta",
                str(tolerance),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("✅ Basic parity passed")
            return True
        else:
            print("❌ Parity test failed")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"Error running parity test: {e}")
        return False

    # Additional simple checks we can add here
    # - File size comparison
    # - Basic structure validation
    # - Content similarity check


def main():
    pdf_default = "data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf"
    html_default = "data/input/pipeline/indexed/test_document.html"

    import argparse

    parser = argparse.ArgumentParser(description="Simple HTML vs PDF parity test")
    parser.add_argument("--pdf", type=Path, default=Path(pdf_default), help="PDF file to test")
    parser.add_argument("--html", type=Path, default=Path(html_default), help="HTML file to test")
    parser.add_argument(
        "--tolerance", type=int, default=2, help="Allowed difference in object count"
    )

    args = parser.parse_args()

    success = test_html_pdf_parity(args.pdf, args.html, args.tolerance)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
