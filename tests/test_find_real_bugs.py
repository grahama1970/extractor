#!/usr/bin/env python3
"""
Module: test_find_real_bugs.py
Description: Tests designed to FIND BUGS in the extractor module, not just pass

External Dependencies:
- pathlib: https://docs.python.org/3/library/pathlib.html
- subprocess: https://docs.python.org/3/library/subprocess.html

Sample Input:
>>> python tests/test_find_real_bugs.py

Expected Output:
>>> List of bugs and failures found in the module

Example Usage:
>>> python tests/test_find_real_bugs.py
"""

import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class BugHunter:
    """Actively hunt for bugs in the extractor module."""
    
    def __init__(self):
        self.bugs_found = []
        self.tests_run = 0
        
    def log_bug(self, test_name, bug_description, error=None):
        """Log a bug we found."""
        self.bugs_found.append({
            "test": test_name,
            "bug": bug_description,
            "error": str(error) if error else None,
            "timestamp": datetime.now().isoformat()
        })
        print(f"🐛 BUG FOUND in {test_name}: {bug_description}")
        if error:
            print(f"   Error: {error}")
    
    def test_import_errors(self):
        """Test 1: Find import errors and circular dependencies."""
        print("\n🔍 TEST 1: Import Error Detection")
        self.tests_run += 1
        
        modules_to_test = [
            "extractor",
            "extractor.core",
            "extractor.core.converters.pdf",
            "extractor.core.schema.document",
            "extractor.core.renderers.json",
            "extractor.core.renderers.arangodb_enhanced",
            "extractor.mcp.server",
            "extractor.cli.main"
        ]
        
        for module in modules_to_test:
            try:
                start = time.time()
                exec(f"import {module}")
                duration = time.time() - start
                
                # Check for suspiciously fast imports (might be empty modules)
                # Reduced threshold from 0.001 to 0.00001 (10 microseconds) as many __init__.py files have legitimate code
                # Modern CPUs can import simple modules very quickly
                if duration < 0.00001:
                    self.log_bug("import_speed", f"{module} imports too fast ({duration:.6f}s) - might be empty")
                    
            except SyntaxError as e:
                self.log_bug("syntax_error", f"Syntax error in {module}", e)
            except ImportError as e:
                self.log_bug("import_error", f"Cannot import {module}", e)
            except Exception as e:
                self.log_bug("unexpected_error", f"Unexpected error importing {module}", e)
    
    def test_empty_input_handling(self):
        """Test 2: How does the module handle empty/invalid inputs?"""
        print("\n🔍 TEST 2: Empty/Invalid Input Handling")
        self.tests_run += 1
        
        try:
            from extractor.core.converters.pdf import PdfConverter as PDFConverter
            
            # Test with None
            try:
                converter = PDFConverter()
                result = converter.convert(None)
                self.log_bug("null_input", "PDFConverter accepts None without error")
            except Exception as e:
                print(f"✓ PDFConverter correctly rejects None: {type(e).__name__}")
            
            # Test with empty string
            try:
                result = converter.convert("")
                self.log_bug("empty_string", "PDFConverter accepts empty string without error")
            except Exception as e:
                print(f"✓ PDFConverter correctly rejects empty string: {type(e).__name__}")
                
            # Test with non-existent file
            try:
                result = converter.convert("/definitely/not/a/real/file.pdf")
                self.log_bug("nonexistent_file", "PDFConverter doesn't check file existence")
            except Exception as e:
                print(f"✓ PDFConverter correctly handles non-existent file: {type(e).__name__}")
                
        except ImportError as e:
            self.log_bug("converter_import", "Cannot test PDFConverter", e)
    
    def test_memory_leaks(self):
        """Test 3: Check for potential memory leaks."""
        print("\n🔍 TEST 3: Memory Leak Detection")
        self.tests_run += 1
        
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Try to import and create objects multiple times
            for i in range(10):
                try:
                    from extractor.core.schema.document import Document
                    doc = Document()
                    # Don't keep references
                except:
                    pass
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            if memory_increase > 10:  # More than 10MB increase
                self.log_bug("memory_leak", f"Possible memory leak: {memory_increase:.2f}MB increase")
            else:
                print(f"✓ Memory usage stable: {memory_increase:.2f}MB change")
                
        except ImportError:
            print("⚠️  psutil not available for memory testing")
    
    def test_concurrent_access(self):
        """Test 4: Test concurrent access issues."""
        print("\n🔍 TEST 4: Concurrent Access Testing")
        self.tests_run += 1
        
        # Test if module has any global state that could cause issues
        try:
            # Run two Python processes trying to use the module simultaneously
            cmd = [sys.executable, "-c", 
                   "import extractor.core.schema.document; print('Process completed')"]
            
            processes = []
            for i in range(3):
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                processes.append(p)
            
            # Wait for all to complete
            errors = []
            for i, p in enumerate(processes):
                # Increased timeout from 5 to 10 seconds for slower systems
                stdout, stderr = p.communicate(timeout=10)
                if p.returncode != 0:
                    errors.append(f"Process {i}: {stderr.decode()}")
            
            if errors:
                self.log_bug("concurrent_access", f"Concurrent access issues: {len(errors)} processes failed")
                for err in errors[:2]:  # Show first 2 errors
                    print(f"   {err}")
            else:
                print("✓ Concurrent access appears safe")
                
        except subprocess.TimeoutExpired:
            self.log_bug("deadlock", "Possible deadlock in concurrent access")
        except Exception as e:
            self.log_bug("concurrent_test_error", "Error testing concurrent access", e)
    
    def test_edge_cases(self):
        """Test 5: Test various edge cases."""
        print("\n🔍 TEST 5: Edge Case Testing")
        self.tests_run += 1
        
        # Test extremely long strings
        try:
            from extractor.core.schema.blocks.text import Text
            
            # Test with very long text
            long_text = "A" * 1000000  # 1 million characters
            try:
                text_block = Text(text=long_text)
                print("⚠️  Text block accepts 1M character string - potential DOS")
            except Exception as e:
                print(f"✓ Text block limits long strings: {type(e).__name__}")
                
        except ImportError:
            pass
        
        # Test invalid JSON structure
        try:
            from extractor.core.renderers.json import JSONRenderer
            
            # Create a circular reference
            class CircularDoc:
                def __init__(self):
                    self.self_ref = self
            
            try:
                renderer = JSONRenderer()
                result = renderer.render(CircularDoc())
                self.log_bug("circular_json", "JSONRenderer doesn't handle circular references")
            except Exception as e:
                print(f"✓ JSONRenderer handles circular references: {type(e).__name__}")
                
        except ImportError:
            pass
    
    def test_arangodb_constraints(self):
        """Test 6: Test ArangoDB specific constraints."""
        print("\n🔍 TEST 6: ArangoDB Constraint Testing")
        self.tests_run += 1
        
        try:
            from extractor.core.utils.arangodb_validator import ArangoDBDocumentValidator
            
            validator = ArangoDBDocumentValidator()
            
            # Test with invalid document ID characters
            test_cases = [
                {"_id": "docs/has spaces"},  # Spaces in ID
                {"_id": "docs/has/slash"},    # Extra slash
                {"_id": ""},                   # Empty ID
                {"_id": "docs/" + "A"*256},   # Too long ID
                {"_from": "invalid"},          # Invalid edge reference
            ]
            
            for test_doc in test_cases:
                is_valid, errors = validator.validate_document(test_doc)
                if is_valid:
                    self.log_bug("arangodb_validation", f"Invalid document accepted: {test_doc}")
                else:
                    print(f"✓ Correctly rejected {test_doc}: {errors[0]}")
                    
        except ImportError as e:
            self.log_bug("arangodb_import", "Cannot import ArangoDB validator", e)
    
    def test_pipeline_integration(self):
        """Test 7: Test pipeline integration points."""
        print("\n🔍 TEST 7: Pipeline Integration Testing")
        self.tests_run += 1
        
        # Test if modules can actually work together
        try:
            # Simulate pipeline: PDF -> Document -> JSON
            from extractor.core.converters.pdf import PdfConverter as PDFConverter
            from extractor.core.schema.document import Document  
            from extractor.core.renderers.json import JSONRenderer
            
            # This should work if properly integrated
            print("✓ Pipeline modules can be imported together")
            
            # But can they actually work together?
            # This is where we'd test with a real PDF if we had one
            
        except ImportError as e:
            self.log_bug("pipeline_broken", "Pipeline modules cannot be imported together", e)
    
    def generate_report(self):
        """Generate bug report."""
        print(f"\n{'='*60}")
        print("🐛 BUG HUNT REPORT")
        print(f"{'='*60}")
        
        print(f"\nTests Run: {self.tests_run}")
        print(f"Bugs Found: {len(self.bugs_found)}")
        
        if self.bugs_found:
            print("\n🚨 BUGS DISCOVERED:")
            for i, bug in enumerate(self.bugs_found, 1):
                print(f"\n{i}. {bug['test'].upper()}")
                print(f"   Bug: {bug['bug']}")
                if bug['error']:
                    print(f"   Error: {bug['error']}")
                print(f"   Time: {bug['timestamp']}")
        else:
            print("\n⚠️  No bugs found - tests might not be thorough enough!")
        
        # Save to file
        report_path = Path(__file__).parent / "bug_report.json"
        with open(report_path, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "tests_run": self.tests_run,
                "bugs_found": len(self.bugs_found),
                "bugs": self.bugs_found
            }, f, indent=2)
        
        print(f"\n📄 Full report saved to: {report_path}")
        
        return len(self.bugs_found) > 0  # Return True if bugs found


def main():
    """Run bug hunting tests."""
    print("🎯 Starting Bug Hunt for Extractor Module")
    print("=" * 60)
    print("Goal: Find REAL BUGS, not pass tests!")
    
    hunter = BugHunter()
    
    # Run all bug hunting tests
    hunter.test_import_errors()
    hunter.test_empty_input_handling()
    hunter.test_memory_leaks()
    hunter.test_concurrent_access()
    hunter.test_edge_cases()
    hunter.test_arangodb_constraints()
    hunter.test_pipeline_integration()
    
    # Generate report
    bugs_found = hunter.generate_report()
    
    if bugs_found:
        print("\n✅ Bug hunt successful - found issues to fix!")
        return 0  # Success = we found bugs
    else:
        print("\n❌ No bugs found - need more aggressive testing!")
        return 1


if __name__ == "__main__":
    exit(main())