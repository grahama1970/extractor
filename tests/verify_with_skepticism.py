#!/usr/bin/env python3
"""
Module: verify_with_skepticism.py
Description: Skeptically verify tests with real interactions per TEST_VERIFICATION_TEMPLATE_GUIDE

External Dependencies:
- time: https://docs.python.org/3/library/time.html
- subprocess: https://docs.python.org/3/library/subprocess.html

Sample Input:
>>> python tests/verify_with_skepticism.py

Expected Output:
>>> Detailed verification report with timing and real interaction proof

Example Usage:
>>> python tests/verify_with_skepticism.py
"""

import time
import sys
import subprocess
from pathlib import Path
from datetime import datetime


class TestVerifier:
    """Skeptical test verifier following template guide."""
    
    def __init__(self):
        self.results = []
        self.loop_count = 1
        self.max_loops = 3
        
    def measure_import_time(self, module_path):
        """Measure actual import time to verify real loading."""
        start = time.time()
        try:
            cmd = [sys.executable, "-c", f"import {module_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            duration = time.time() - start
            
            if result.returncode == 0:
                return True, duration, None
            else:
                return False, duration, result.stderr
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            return False, duration, "Import timed out - possible infinite loop"
        except Exception as e:
            duration = time.time() - start
            return False, duration, str(e)
    
    def verify_file_io(self, file_path):
        """Verify real file I/O operations."""
        start = time.time()
        try:
            path = Path(file_path)
            if path.exists():
                size = path.stat().st_size
                duration = time.time() - start
                # Real file I/O should take > 0.001s
                if duration < 0.001:
                    return False, duration, "Too fast - likely cached"
                return True, duration, f"File size: {size} bytes"
            else:
                duration = time.time() - start
                return False, duration, "File does not exist"
        except Exception as e:
            duration = time.time() - start
            return False, duration, str(e)
    
    def verify_module_interaction(self):
        """Verify modules can actually interact."""
        print(f"\n{'='*60}")
        print(f"VERIFICATION LOOP #{self.loop_count}")
        print(f"{'='*60}")
        
        # 1. Test import times (should be > 0.01s for real modules)
        print("\n1. MODULE IMPORT VERIFICATION")
        modules_to_test = [
            ("extractor", 0.01),
            ("extractor.core.converters.pdf", 0.01),
            ("extractor.core.renderers.json", 0.01),
            ("extractor.core.renderers.arangodb_enhanced", 0.01)
        ]
        
        for module, min_time in modules_to_test:
            success, duration, error = self.measure_import_time(module)
            
            if success:
                if duration >= min_time:
                    status = "REAL"
                    confidence = 95
                else:
                    status = "SUSPICIOUS"
                    confidence = 30
                print(f"  ✓ {module}: {duration:.3f}s - {status}")
            else:
                status = "FAILED"
                confidence = 0
                print(f"  ✗ {module}: {error}")
            
            self.results.append({
                "test": f"import_{module}",
                "duration": duration,
                "status": status,
                "confidence": confidence,
                "evidence": error or f"Import took {duration:.3f}s"
            })
        
        # 2. Test file operations
        print("\n2. FILE I/O VERIFICATION")
        test_files = [
            "src/extractor/core/converters/pdf.py",
            "src/extractor/core/schema/document.py",
            "pyproject.toml"
        ]
        
        for file_path in test_files:
            success, duration, info = self.verify_file_io(file_path)
            
            if success and duration > 0.001:
                status = "REAL"
                confidence = 90
            else:
                status = "FAKE" if duration < 0.001 else "FAILED"
                confidence = 10 if duration < 0.001 else 0
            
            print(f"  {'✓' if success else '✗'} {file_path}: {duration:.3f}s - {info}")
            
            self.results.append({
                "test": f"file_io_{Path(file_path).name}",
                "duration": duration,
                "status": status,
                "confidence": confidence,
                "evidence": info
            })
        
        # 3. Cross-examination questions
        print("\n3. CROSS-EXAMINATION")
        
        # Check Python version
        py_version = sys.version_info
        print(f"  Q: What Python version? A: {py_version.major}.{py_version.minor}.{py_version.micro}")
        
        # Check working directory
        cwd = Path.cwd()
        print(f"  Q: What's the absolute path? A: {cwd}")
        
        # Check if in virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        print(f"  Q: In virtual environment? A: {'Yes' if in_venv else 'No'}")
        
        # 4. Honeypot check
        print("\n4. HONEYPOT VERIFICATION")
        honeypot_path = Path(__file__).parent / "test_honeypot.py"
        if honeypot_path.exists():
            # Try to run honeypot - should fail
            try:
                result = subprocess.run([sys.executable, str(honeypot_path)], 
                                      capture_output=True, text=True, timeout=5)
                if "failed" in result.stdout.lower() or result.returncode != 0:
                    print("  ✓ Honeypot tests correctly failing")
                    honeypot_status = "CORRECT"
                else:
                    print("  ✗ WARNING: Honeypot tests passing! Framework compromised!")
                    honeypot_status = "COMPROMISED"
            except:
                print("  ⚠️  Could not run honeypot tests")
                honeypot_status = "UNKNOWN"
        else:
            print("  ✗ No honeypot tests found")
            honeypot_status = "MISSING"
        
        return honeypot_status != "COMPROMISED"
    
    def calculate_confidence(self):
        """Calculate overall confidence score."""
        if not self.results:
            return 0
        
        total_confidence = sum(r["confidence"] for r in self.results)
        avg_confidence = total_confidence / len(self.results)
        
        # Check for red flags
        red_flags = []
        
        # All tests same duration?
        durations = [r["duration"] for r in self.results]
        if len(set(f"{d:.3f}" for d in durations)) == 1:
            red_flags.append("All tests have identical duration")
        
        # Any instant operations?
        if any(d < 0.001 for d in durations):
            red_flags.append("Some operations completed instantly")
        
        # Too perfect?
        if avg_confidence == 100:
            red_flags.append("Perfect confidence is suspicious")
        
        return avg_confidence, red_flags
    
    def generate_report(self):
        """Generate verification report."""
        print(f"\n{'='*60}")
        print("TEST VERIFICATION REPORT")
        print(f"{'='*60}")
        
        print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Loops Completed: {self.loop_count}/3")
        
        # Summary statistics
        real_count = sum(1 for r in self.results if r["status"] == "REAL")
        fake_count = sum(1 for r in self.results if r["status"] == "FAKE")
        failed_count = sum(1 for r in self.results if r["status"] == "FAILED")
        
        print(f"\nSummary Statistics:")
        print(f"- Total Tests: {len(self.results)}")
        print(f"- Real Tests: {real_count} ({real_count/len(self.results)*100:.1f}%)")
        print(f"- Fake Tests: {fake_count} ({fake_count/len(self.results)*100:.1f}%)")
        print(f"- Failed Tests: {failed_count} ({failed_count/len(self.results)*100:.1f}%)")
        
        # Confidence assessment
        avg_confidence, red_flags = self.calculate_confidence()
        print(f"- Average Confidence: {avg_confidence:.1f}%")
        
        if red_flags:
            print(f"\n🚨 RED FLAGS DETECTED:")
            for flag in red_flags:
                print(f"  - {flag}")
        
        # Evidence table
        print(f"\nEvidence Table:")
        print(f"{'Test Name':<30} {'Duration':<10} {'Status':<10} {'Confidence':<10}")
        print("-" * 60)
        
        for r in self.results:
            print(f"{r['test']:<30} {r['duration']:<10.3f} {r['status']:<10} {r['confidence']:<10}%")
        
        # Final verdict
        print(f"\n{'='*60}")
        if avg_confidence >= 90 and not red_flags:
            print("✅ FINAL VERDICT: Tests appear to use REAL interactions")
        elif avg_confidence >= 70:
            print("⚠️  FINAL VERDICT: Tests mostly real but some concerns")
        else:
            print("❌ FINAL VERDICT: Tests likely using FAKE/MOCK interactions")
        
        return avg_confidence >= 70


def main():
    """Run verification loops."""
    verifier = TestVerifier()
    
    for loop in range(1, 4):
        verifier.loop_count = loop
        
        if verifier.verify_module_interaction():
            verifier.generate_report()
            
            # If confidence is high enough, we're done
            confidence, _ = verifier.calculate_confidence()
            if confidence >= 90:
                print("\n✅ High confidence achieved - verification complete")
                return 0
        else:
            print(f"\n❌ Loop {loop} failed - framework may be compromised")
    
    # After 3 loops
    print("\n❌ ESCALATION: Unable to verify after 3 loops")
    return 1


if __name__ == "__main__":
    exit(main())