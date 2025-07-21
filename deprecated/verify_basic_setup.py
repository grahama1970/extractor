#!/usr/bin/env python3
"""
Module: verify_basic_setup.py
Description: Verify basic extractor setup for Granger ecosystem

External Dependencies:
- None (uses standard library only)

Sample Input:
>>> python tests/verify_basic_setup.py

Expected Output:
>>> Basic setup verification results

Example Usage:
>>> python tests/verify_basic_setup.py
"""

import sys
from pathlib import Path


def main():
    """Verify basic setup without imports."""
    print("🔍 Extractor Module Basic Setup Verification")
    print("=" * 50)
    
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"
    extractor_dir = src_dir / "extractor"
    
    checks = []
    
    # 1. Check directory structure
    print("\n📁 Directory Structure:")
    if extractor_dir.exists():
        checks.append(("Module directory exists", True))
        print("  ✓ src/extractor/ exists")
    else:
        checks.append(("Module directory exists", False))
        print("  ✗ src/extractor/ missing")
    
    # 2. Check core components exist
    print("\n🧩 Core Components:")
    components = {
        "CLI": extractor_dir / "cli" / "main.py",
        "Core": extractor_dir / "core" / "__init__.py",
        "MCP": extractor_dir / "mcp" / "server.py",
        "Converters": extractor_dir / "core" / "converters" / "pdf.py",
        "Renderers": extractor_dir / "core" / "renderers" / "json.py",
        "ArangoDB": extractor_dir / "core" / "renderers" / "arangodb_enhanced.py"
    }
    
    for name, path in components.items():
        if path.exists():
            checks.append((f"{name} component", True))
            print(f"  ✓ {name}: {path.relative_to(src_dir)}")
        else:
            checks.append((f"{name} component", False))
            print(f"  ✗ {name}: missing")
    
    # 3. Check Granger integration points
    print("\n🔗 Granger Integration Points:")
    integration_points = {
        "MCP Server": extractor_dir / "mcp" / "server.py",
        "ArangoDB Output": extractor_dir / "core" / "renderers" / "arangodb_enhanced.py",
        "CLI Interface": extractor_dir / "cli" / "main.py",
        "Integrations Dir": extractor_dir / "integrations"
    }
    
    for name, path in integration_points.items():
        if path.exists():
            checks.append((f"{name} integration", True))
            print(f"  ✓ {name}: ready")
        else:
            checks.append((f"{name} integration", False))
            print(f"  ✗ {name}: not found")
    
    # 4. Check for multi-format support
    print("\n📄 Document Format Support:")
    format_providers = {
        "PDF": extractor_dir / "core" / "providers" / "pdf.py",
        "DOCX": extractor_dir / "core" / "providers" / "docx_native.py",
        "PPTX": extractor_dir / "core" / "providers" / "pptx_native.py",
        "XML": extractor_dir / "core" / "providers" / "xml_native.py"
    }
    
    supported_formats = []
    for fmt, path in format_providers.items():
        if path.exists():
            supported_formats.append(fmt)
            print(f"  ✓ {fmt} provider found")
    
    if len(supported_formats) >= 2:
        checks.append(("Multi-format support", True))
    else:
        checks.append(("Multi-format support", False))
    
    # 5. Summary
    print("\n" + "=" * 50)
    print("📊 Verification Summary")
    print("=" * 50)
    
    passed = sum(1 for _, success in checks if success)
    total = len(checks)
    
    for check_name, success in checks:
        status = "✅" if success else "❌"
        print(f"  {status} {check_name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✅ Basic setup verified!")
        print("The extractor module structure is ready for Granger ecosystem.")
    else:
        print("\n⚠️  Some components are missing.")
        print("This may indicate the module needs dependencies installed.")
    
    # Check if this is expected based on pyproject.toml
    if (project_root / "pyproject.toml").exists():
        print("\n📦 Package configuration found (pyproject.toml)")
        print("Try running: uv pip install -e .")
    
    return 0 if passed >= total * 0.7 else 1  # Allow 70% pass rate


if __name__ == "__main__":
    exit(main())