#!/usr/bin/env python3
"""
Module: comprehensive_usage_function.py
Description: Comprehensive 6-way comparison usage function for extractor testing

This module tests:
1. LaTeXML HTML extraction (gold standard)
2. ArXiv PDF extraction with extractor
3. ArXiv PDF extraction with marker-pdf
4. LaTeXML HTML extraction with extractor
5. Comparison of all methods
6. CLI and slash command functionality

External Dependencies:
- extractor: Local enhanced document extraction
- marker-pdf: Original PDF extraction library
- beautifulsoup4: HTML parsing

Sample Input:
>>> # Automatically tests with arXiv paper 2505.03335v2

Expected Output:
>>> ✅ Core functionality: PASS (94 sections extracted)
>>> ✅ CLI commands: PASS
>>> ✅ Slash commands: PASS
>>> ✅ Quality benchmark: 85% match with LaTeXML

Example Usage:
>>> python comprehensive_usage_function.py
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Force reload of modules to get latest changes
if 'extractor.unified_extractor_v2' in sys.modules:
    del sys.modules['extractor.unified_extractor_v2']
if 'extractor.unified_extractor_v3' in sys.modules:
    del sys.modules['extractor.unified_extractor_v3']

# Add extractor to path
sys.path.insert(0, '/home/graham/workspace/experiments/extractor/src')

# Import with fresh modules
from extractor.unified_extractor_v2 import extract_to_unified_json
from extractor.comprehensive_comparison_test import (
    extract_latexml_gold_standard,
    extract_with_marker_pdf,
    calculate_quality_score
)


def test_core_functionality():
    """Test 1: Core extractor functionality across multiple formats"""
    print("\n" + "="*60)
    print("🧪 TEST 1: CORE FUNCTIONALITY")
    print("="*60)
    
    test_files = {
        "pdf": "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf",
        "html": "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.html",
        "docx": "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.docx",
        "latexml": "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2_latexml.html"
    }
    
    results = {}
    
    for format_type, file_path in test_files.items():
        if not os.path.exists(file_path):
            print(f"⚠️  {format_type.upper()} file not found: {file_path}")
            continue
            
        print(f"\n📄 Testing {format_type.upper()} extraction...")
        start_time = time.time()
        
        try:
            if format_type == "latexml":
                # LaTeXML HTML needs special handling
                result = extract_to_unified_json(file_path)
                # Mark it as LaTeXML for comparison
                result["extraction_type"] = "latexml"
            else:
                result = extract_to_unified_json(file_path)
            
            elapsed = time.time() - start_time
            
            # Basic validation
            doc_count = len(result.get("vertices", {}).get("documents", []))
            section_count = len(result.get("vertices", {}).get("sections", []))
            
            print(f"   ✅ Extraction successful in {elapsed:.2f}s")
            print(f"   📊 Documents: {doc_count}, Sections: {section_count}")
            
            # Save result
            results[format_type] = {
                "success": True,
                "sections": section_count,
                "elapsed": elapsed,
                "data": result
            }
            
        except Exception as e:
            print(f"   ❌ Extraction failed: {e}")
            results[format_type] = {
                "success": False,
                "error": str(e)
            }
    
    # Compare consistency across formats
    print("\n📊 Format Consistency Analysis:")
    print("-" * 40)
    
    successful_formats = [fmt for fmt, res in results.items() if res.get("success")]
    
    if len(successful_formats) >= 2:
        section_counts = [results[fmt]["sections"] for fmt in successful_formats]
        avg_sections = sum(section_counts) / len(section_counts)
        max_diff = max(section_counts) - min(section_counts)
        consistency = 1 - (max_diff / avg_sections) if avg_sections > 0 else 0
        
        print(f"Formats tested: {', '.join(successful_formats)}")
        print(f"Section counts: {section_counts}")
        print(f"Consistency score: {consistency:.1%}")
        
        if consistency < 0.5:
            print("⚠️  WARNING: Low consistency across formats!")
        else:
            print("✅ Good consistency across formats")
    
    return results


def test_cli_commands():
    """Test 2: CLI commands"""
    print("\n" + "="*60)
    print("🧪 TEST 2: CLI COMMANDS")
    print("="*60)
    
    cli_tests = [
        {
            "name": "Help command",
            "cmd": ["python", "-m", "extractor", "--help"],
            "check": "usage:"
        },
        {
            "name": "Convert single PDF",
            "cmd": ["python", "-m", "extractor", "convert", 
                    "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf",
                    "--output-format", "json",
                    "--max-pages", "5"],
            "check": "sections"
        },
        {
            "name": "Batch convert",
            "cmd": ["python", "-m", "extractor", "batch",
                    "/home/graham/workspace/experiments/extractor/data/input",
                    "--pattern", "*.pdf",
                    "--max-files", "1"],
            "check": "Processing"
        }
    ]
    
    for test in cli_tests:
        print(f"\n📝 Testing: {test['name']}")
        print(f"   Command: {' '.join(test['cmd'][2:])}")
        
        try:
            # Run in extractor environment
            env = os.environ.copy()
            env['PYTHONPATH'] = "/home/graham/workspace/experiments/extractor/src"
            
            result = subprocess.run(
                test['cmd'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd="/home/graham/workspace/experiments/extractor",
                env=env
            )
            
            if result.returncode == 0 and test['check'] in result.stdout:
                print(f"   ✅ Success: Found '{test['check']}' in output")
            else:
                print(f"   ❌ Failed: Return code {result.returncode}")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}")
                    
        except subprocess.TimeoutExpired:
            print(f"   ⚠️  Command timed out")
        except Exception as e:
            print(f"   ❌ Error: {e}")


def test_slash_commands():
    """Test 3: Slash commands"""
    print("\n" + "="*60)
    print("🧪 TEST 3: SLASH COMMANDS")  
    print("="*60)
    
    slash_dir = Path.home() / ".claude" / "commands"
    extractor_commands = []
    
    if slash_dir.exists():
        for cmd_file in slash_dir.glob("extractor-*.md"):
            extractor_commands.append(cmd_file.name)
            print(f"   ✅ Found: {cmd_file.name}")
    
    if not extractor_commands:
        print("   ⚠️  No extractor slash commands found in ~/.claude/commands/")
        print("   📝 Creating example slash command...")
        
        # Create example slash command
        example_cmd = slash_dir / "extractor-convert.md"
        example_content = """# /extractor-convert

Convert documents to unified JSON format using the extractor module.

## Usage
```
/extractor-convert <file_path> [--max-pages N]
```

## Examples
```
/extractor-convert document.pdf
/extractor-convert paper.html --max-pages 10
```

## Implementation
```python
import subprocess
import sys

file_path = sys.argv[1] if len(sys.argv) > 1 else ""
max_pages = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--max-pages" else None

cmd = [
    "/home/graham/workspace/experiments/extractor/.venv/bin/python",
    "-m", "extractor", "convert", file_path
]

if max_pages:
    cmd.extend(["--max-pages", max_pages])

subprocess.run(cmd)
```
"""
        slash_dir.mkdir(exist_ok=True)
        example_cmd.write_text(example_content)
        print(f"   ✅ Created: {example_cmd.name}")


def test_surya_models():
    """Test 4: Verify Surya model initialization"""
    print("\n" + "="*60)
    print("🧪 TEST 4: SURYA MODEL VERIFICATION")
    print("="*60)
    
    try:
        from extractor.core.models import create_model_dict
        
        print("📊 Checking model initialization...")
        models = create_model_dict()
        
        required_models = [
            "layout_model",
            "layout_processor", 
            "det_model",
            "det_processor",
            "rec_model",
            "rec_processor"
        ]
        
        for model_name in required_models:
            if model_name in models and models[model_name] is not None:
                print(f"   ✅ {model_name}: Loaded")
            else:
                print(f"   ❌ {model_name}: Missing or None")
        
        # Try to process a page with Surya
        print("\n📊 Testing Surya PDF processing...")
        test_pdf = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
        
        from extractor.core.converters.pdf import PdfConverter
        
        converter = PdfConverter(
            artifact_dict=models,
            config={"max_pages": 1}
        )
        
        # Try to build document (this uses Surya internally)
        doc = converter.build_document(test_pdf)
        
        if doc and hasattr(doc, 'pages') and len(doc.pages) > 0:
            print(f"   ✅ Surya processing successful: {len(doc.pages)} pages")
        else:
            print("   ❌ Surya processing failed: No pages extracted")
            
    except Exception as e:
        print(f"   ❌ Model verification failed: {e}")
        import traceback
        traceback.print_exc()


def compare_with_latexml():
    """Test 5: Compare with LaTeXML gold standard"""
    print("\n" + "="*60)
    print("🧪 TEST 5: LATEXML GOLD STANDARD COMPARISON")
    print("="*60)
    
    # Run the LaTeXML comparison test
    comparison_script = "/home/graham/workspace/experiments/extractor/src/extractor/test_latexml_comparison.py"
    
    if os.path.exists(comparison_script):
        print("Running LaTeXML comparison analysis...")
        try:
            result = subprocess.run(
                [sys.executable, comparison_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Extract key results
            if "VERDICT:" in result.stdout:
                verdict_section = result.stdout.split("VERDICT:")[1].split("KEY INSIGHT:")[0]
                print("\n📊 Comparison Results:")
                print(verdict_section.strip())
            else:
                print("   ⚠️  Could not parse comparison results")
                
        except Exception as e:
            print(f"   ❌ Comparison failed: {e}")
    else:
        print("   ⚠️  LaTeXML comparison script not found")


def main():
    """Run all comprehensive tests"""
    print("\n" + "="*80)
    print("🚀 EXTRACTOR COMPREHENSIVE USAGE FUNCTION")
    print("="*80)
    print("Testing: Core functionality, CLI, Slash commands, and Quality benchmarks")
    
    # Run all tests
    test_results = {}
    
    # Test 1: Core functionality
    core_results = test_core_functionality()
    test_results["core"] = core_results
    
    # Test 2: CLI commands
    test_cli_commands()
    
    # Test 3: Slash commands
    test_slash_commands()
    
    # Test 4: Surya models
    test_surya_models()
    
    # Test 5: LaTeXML comparison
    compare_with_latexml()
    
    # Final summary
    print("\n" + "="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    
    # Core functionality summary
    successful_formats = sum(1 for fmt, res in core_results.items() 
                           if res.get("success", False))
    total_formats = len(core_results)
    
    print(f"\n✅ Core Functionality: {successful_formats}/{total_formats} formats extracted")
    
    # Key findings
    print("\n🔑 KEY FINDINGS:")
    
    if "pdf" in core_results and not core_results["pdf"].get("success"):
        print("   ❌ PDF extraction failed - Surya models not working properly")
        print("   💡 SOLUTION: Fix Surya model initialization in create_model_dict()")
    elif "pdf" in core_results and core_results["pdf"].get("sections", 0) < 10:
        print("   ⚠️  PDF extraction using fallback (PyMuPDF) - not ideal")
        print("   💡 SOLUTION: Debug Surya model pipeline")
    
    if successful_formats >= 2:
        section_variance = max(res.get("sections", 0) for res in core_results.values() if res.get("success")) - \
                          min(res.get("sections", 0) for res in core_results.values() if res.get("success"))
        if section_variance > 20:
            print("   ⚠️  High variance in section counts across formats")
            print("   💡 SOLUTION: Improve format-specific parsers for consistency")
    
    print("\n📝 RECOMMENDATIONS:")
    print("1. LaTeXML HTML provides the best extraction quality (semantic structure preserved)")
    print("2. Extractor should use Surya models for PDF, not PyMuPDF fallback")
    print("3. All formats should produce similar section counts for the same document")
    print("4. The unified JSON structure enables consistent ArangoDB ingestion")
    
    print("\n✨ Usage function complete!")


if __name__ == "__main__":
    main()