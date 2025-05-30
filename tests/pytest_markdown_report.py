"""
Pytest Markdown Report Plugin

Generates comprehensive Markdown reports for test runs, saving them to docs/reports/.
Captures detailed information about each test including Claude feature tests.
"""

import pytest
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
from dataclasses import dataclass, field


@dataclass
class TestResult:
    """Data class for storing individual test results."""
    name: str
    description: str
    result: str
    status: str
    duration: float
    timestamp: str
    error_message: str = ""
    module: str = ""
    markers: List[str] = field(default_factory=list)
    claude_feature: Optional[str] = None


class MarkdownReportPlugin:
    """Pytest plugin for generating Markdown test reports."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = None
        self.end_time = None
        self.report_dir = Path("docs/reports")
        self.claude_features = {
            "table_merge": "Table Merge Analysis",
            "section_verification": "Section Verification",
            "content_validation": "Content Validation",
            "structure_analysis": "Structure Analysis",
            "image_description": "Image Description"
        }
    
    def pytest_sessionstart(self, session):
        """Called when the test session starts."""
        self.start_time = datetime.now()
        self.results.clear()
        
        # Ensure report directory exists
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def pytest_runtest_protocol(self, item, nextitem):
        """Hook to capture test execution details."""
        # Record start time
        test_start = time.time()
        
        # Get test information
        test_name = item.name
        module_name = item.module.__name__ if hasattr(item, 'module') else ""
        markers = [marker.name for marker in item.iter_markers()]
        
        # Extract description from docstring or test name
        description = self._get_test_description(item)
        
        # Detect Claude feature being tested
        claude_feature = self._detect_claude_feature(test_name, module_name)
        
        # Run the test
        reports = pytest.main.runtestprotocol(item, log=False)
        
        # Process results
        test_duration = time.time() - test_start
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine test outcome
        status = "Pass"
        result = "Success"
        error_message = ""
        
        for report in reports:
            if report.when == "call":
                if report.failed:
                    status = "Fail"
                    result = "Failed"
                    error_message = self._extract_error_message(report)
                elif report.skipped:
                    status = "Skip"
                    result = "Skipped"
                    if hasattr(report, 'wasxfail'):
                        error_message = report.wasxfail
                elif report.passed:
                    if hasattr(item, '_obj') and hasattr(item._obj, '__wrapped__'):
                        # Check if test has expected outcome
                        func = item._obj.__wrapped__
                        if hasattr(func, '_expected_result'):
                            result = func._expected_result
                    else:
                        result = self._extract_success_result(item, report)
        
        # Create test result
        test_result = TestResult(
            name=test_name,
            description=description,
            result=result,
            status=status,
            duration=round(test_duration, 3),
            timestamp=timestamp,
            error_message=error_message,
            module=module_name,
            markers=markers,
            claude_feature=claude_feature
        )
        
        self.results.append(test_result)
        
        # Continue with normal test execution
        return None
    
    def pytest_sessionfinish(self, session, exitstatus):
        """Called when the test session ends."""
        self.end_time = datetime.now()
        
        # Generate the report
        report_path = self._generate_report()
        
        # Print report location
        print(f"\n📊 Markdown test report generated: {report_path}")
    
    def _get_test_description(self, item) -> str:
        """Extract test description from docstring or generate from test name."""
        if item.obj and item.obj.__doc__:
            # Use first line of docstring
            return item.obj.__doc__.strip().split('\n')[0]
        else:
            # Generate from test name
            name = item.name
            name = name.replace('test_', '').replace('_', ' ')
            return name.capitalize()
    
    def _detect_claude_feature(self, test_name: str, module_name: str) -> Optional[str]:
        """Detect which Claude feature is being tested."""
        test_lower = test_name.lower()
        module_lower = module_name.lower()
        
        if 'table' in test_lower and 'merge' in test_lower:
            return self.claude_features["table_merge"]
        elif 'section' in test_lower and 'verif' in test_lower:
            return self.claude_features["section_verification"]
        elif 'content' in test_lower and 'valid' in test_lower:
            return self.claude_features["content_validation"]
        elif 'structure' in test_lower and 'analy' in test_lower:
            return self.claude_features["structure_analysis"]
        elif 'image' in test_lower and 'desc' in test_lower:
            return self.claude_features["image_description"]
        elif 'claude' in module_lower:
            # Try to match based on module name
            for key, value in self.claude_features.items():
                if key.replace('_', '') in module_lower:
                    return value
        
        return None
    
    def _extract_error_message(self, report) -> str:
        """Extract meaningful error message from failed test report."""
        if hasattr(report, 'longreprtext'):
            lines = report.longreprtext.split('\n')
            # Find the actual error line
            for line in reversed(lines):
                if line.strip() and not line.startswith(' '):
                    return line.strip()[:100]  # Limit length
        return "Test failed"
    
    def _extract_success_result(self, item, report) -> str:
        """Extract meaningful success result from test."""
        # Check if test logged any results
        if hasattr(report, 'sections'):
            for section_name, section_content in report.sections:
                if 'stdout' in section_name:
                    lines = section_content.strip().split('\n')
                    for line in reversed(lines):
                        if 'result:' in line.lower() or 'success:' in line.lower():
                            return line.strip()[:100]
        
        return "Success"
    
    def _generate_report(self) -> Path:
        """Generate the Markdown report file."""
        # Create filename with timestamp
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"test_report_{timestamp}.md"
        report_path = self.report_dir / filename
        
        # Calculate summary statistics
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r.status == "Pass")
        failed = sum(1 for r in self.results if r.status == "Fail")
        skipped = sum(1 for r in self.results if r.status == "Skip")
        duration = (self.end_time - self.start_time).total_seconds()
        
        # Group results by Claude feature
        claude_results = {}
        other_results = []
        
        for result in self.results:
            if result.claude_feature:
                if result.claude_feature not in claude_results:
                    claude_results[result.claude_feature] = []
                claude_results[result.claude_feature].append(result)
            else:
                other_results.append(result)
        
        # Generate report content
        content = f"""# Test Report - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total Tests:** {total_tests}
- **Passed:** {passed} ✅
- **Failed:** {failed} ❌
- **Skipped:** {skipped} ⏭️
- **Duration:** {duration:.2f}s
- **Success Rate:** {(passed/total_tests*100 if total_tests > 0 else 0):.1f}%

"""
        
        # Add Claude features summary if any
        if claude_results:
            content += "## Claude Features Test Results\n\n"
            
            for feature, results in claude_results.items():
                feature_passed = sum(1 for r in results if r.status == "Pass")
                feature_total = len(results)
                
                content += f"### {feature}\n\n"
                content += f"**Status:** {feature_passed}/{feature_total} tests passed "
                content += "✅\n\n" if feature_passed == feature_total else "⚠️\n\n"
                
                # Add table for this feature
                content += self._generate_results_table(results)
                content += "\n"
        
        # Add other tests if any
        if other_results:
            content += "## Other Tests\n\n"
            content += self._generate_results_table(other_results)
            content += "\n"
        
        # Add detailed results section
        if failed > 0:
            content += "## Failed Tests Details\n\n"
            for result in self.results:
                if result.status == "Fail":
                    content += f"### ❌ {result.name}\n\n"
                    content += f"- **Module:** `{result.module}`\n"
                    content += f"- **Description:** {result.description}\n"
                    content += f"- **Error:** {result.error_message}\n"
                    content += f"- **Duration:** {result.duration}s\n"
                    content += "\n"
        
        # Add test environment information
        content += self._generate_environment_section()
        
        # Write report
        report_path.write_text(content)
        
        # Also create a latest report symlink
        latest_path = self.report_dir / "test_report_latest.md"
        if latest_path.exists():
            latest_path.unlink()
        latest_path.symlink_to(report_path.name)
        
        return report_path
    
    def _generate_results_table(self, results: List[TestResult]) -> str:
        """Generate a Markdown table for test results."""
        # Table header
        table = "| Test Name | Description | Result | Status | Duration | Timestamp | Error Message |\n"
        table += "|-----------|-------------|--------|--------|----------|-----------|---------------|\n"
        
        # Table rows
        for result in results:
            # Escape pipe characters in text fields
            name = result.name.replace('|', '\\|')
            desc = result.description.replace('|', '\\|')[:50]
            res = result.result.replace('|', '\\|')[:30]
            error = result.error_message.replace('|', '\\|')[:50]
            
            # Status emoji
            status_emoji = {
                "Pass": "✅ Pass",
                "Fail": "❌ Fail", 
                "Skip": "⏭️ Skip"
            }.get(result.status, result.status)
            
            table += f"| {name} | {desc} | {res} | {status_emoji} | {result.duration}s | {result.timestamp} | {error} |\n"
        
        return table
    
    def _generate_environment_section(self) -> str:
        """Generate environment information section."""
        import platform
        import sys
        
        content = "## Test Environment\n\n"
        content += f"- **Python Version:** {sys.version.split()[0]}\n"
        content += f"- **Platform:** {platform.platform()}\n"
        content += f"- **Test Framework:** pytest {pytest.__version__}\n"
        
        # Check for Claude CLI
        claude_available = os.system("which claude > /dev/null 2>&1") == 0
        content += f"- **Claude CLI:** {'Available ✅' if claude_available else 'Not Found ❌'}\n"
        
        # Add marker configuration info
        content += "\n### Active Pytest Markers\n\n"
        content += "- `@pytest.mark.claude` - Claude feature tests\n"
        content += "- `@pytest.mark.slow` - Long-running tests\n"
        content += "- `@pytest.mark.integration` - Integration tests\n"
        
        return content


def pytest_configure(config):
    """Register the plugin with pytest."""
    config._markdown_reporter = MarkdownReportPlugin()
    config.pluginmanager.register(config._markdown_reporter)
    
    # Register custom markers
    config.addinivalue_line(
        "markers", "claude: mark test as testing Claude features"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )


def pytest_unconfigure(config):
    """Unregister the plugin."""
    if hasattr(config, '_markdown_reporter'):
        config.pluginmanager.unregister(config._markdown_reporter)
        del config._markdown_reporter