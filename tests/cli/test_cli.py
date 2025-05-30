#!/usr/bin/env python3
"""
Test script for the new Marker Typer-based CLI

This script tests the various output formats and commands provided by the new CLI.
"""

import subprocess
import sys
import json
from pathlib import Path


def run_command(command: str) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, and stderr."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout, result.stderr


def test_version():
    """Test the version command."""
    print("\n=== Testing version command ===")
    code, stdout, stderr = run_command("python cli.py version")
    print(f"Exit code: {code}")
    print(f"Output:\n{stdout}")
    if stderr:
        print(f"Error:\n{stderr}")
    return code == 0


def test_help():
    """Test the help commands."""
    print("\n=== Testing help commands ===")
    
    # Main help
    print("\n-- Main help --")
    code, stdout, stderr = run_command("python cli.py --help")
    print(f"Output preview:\n{stdout[:500]}...")
    
    # Convert help
    print("\n-- Convert help --")
    code, stdout, stderr = run_command("python cli.py convert --help")
    print(f"Output preview:\n{stdout[:500]}...")
    
    # Convert single help
    print("\n-- Convert single help --")
    code, stdout, stderr = run_command("python cli.py convert single --help")
    print(f"Output preview:\n{stdout[:500]}...")
    
    return True


def test_single_conversion(pdf_path: str):
    """Test single PDF conversion with different output formats."""
    print(f"\n=== Testing single PDF conversion with {pdf_path} ===")
    
    formats = ["json", "dict", "table", "summary"]
    
    for fmt in formats:
        print(f"\n-- Testing {fmt} format --")
        cmd = f"python cli.py convert single {pdf_path} --output-format {fmt} --renderer json"
        code, stdout, stderr = run_command(cmd)
        
        print(f"Exit code: {code}")
        if code == 0:
            print(f"Output preview:\n{stdout[:500]}...")
        else:
            print(f"Error:\n{stderr}")
    
    return True


def test_batch_conversion(input_dir: str):
    """Test batch conversion."""
    print(f"\n=== Testing batch conversion with {input_dir} ===")
    
    cmd = f"python cli.py convert batch {input_dir} --output-format summary --max-files 2"
    code, stdout, stderr = run_command(cmd)
    
    print(f"Exit code: {code}")
    if code == 0:
        print(f"Output:\n{stdout}")
    else:
        print(f"Error:\n{stderr}")
    
    return code == 0


def find_test_pdf():
    """Find a test PDF in the project."""
    possible_paths = [
        "tests/test_files/*.pdf",
        "test_files/*.pdf",
        "**/*.pdf",
    ]
    
    for pattern in possible_paths:
        pdfs = list(Path(".").glob(pattern))
        if pdfs:
            return str(pdfs[0])
    
    return None


def main():
    """Run all tests."""
    print("=== Marker Typer CLI Test Suite ===")
    
    # Test version command
    if not test_version():
        print("Version test failed!")
        return 1
    
    # Test help commands
    if not test_help():
        print("Help test failed!")
        return 1
    
    # Find a test PDF
    test_pdf = find_test_pdf()
    if test_pdf:
        print(f"\nFound test PDF: {test_pdf}")
        test_single_conversion(test_pdf)
    else:
        print("\nNo test PDF found. Skipping conversion tests.")
        print("To test conversion, please run with a PDF file:")
        print("  python cli.py convert single your_file.pdf --output-format json")
    
    # Test batch conversion if we have PDFs
    if test_pdf:
        test_dir = Path(test_pdf).parent
        test_batch_conversion(str(test_dir))
    
    print("\n=== All tests completed ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())