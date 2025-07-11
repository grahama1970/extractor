"""Module docstring"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))



    #!/usr/bin/env python3
    """
    Generate a Markdown test report from pytest results.

    This script runs the test suite and generates a well-formatted Markdown report
    with test results, as required by CLAUDE.md.
    """

    import json
    import subprocess
    import sys
    from datetime import datetime
    from pathlib import Path
    from typing import Dict, List, Tuple
    import xml.etree.ElementTree as ET


    def run_tests_with_json(test_path: str = "tests/") -> Tuple[int, str]:
        """Run pytest and capture JSON output."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_output = f"test-results-{timestamp}.json"

        cmd = [
        "pytest",
        test_path,
        f"--json-report",
        f"--json-report-file={json_output}",
        "--tb=short",
        "-v"
        ]

        print(f"Running tests: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        return result.returncode, json_output


        def run_tests_with_xml(test_path: str = "tests/") -> Tuple[int, str]:
            """Run pytest and capture JUnit XML output."""
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            xml_output = f"test-results-{timestamp}.xml"

            cmd = [
            "pytest",
            test_path,
            f"--junit-xml={xml_output}",
            "--tb=short",
            "-v"
            ]

            print(f"Running tests: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            return result.returncode, xml_output


            def parse_junit_xml(xml_file: str) -> List[Dict[str, str]]:
                """Parse JUnit XML test results."""
                tree = ET.parse(xml_file)
                root = tree.getroot()

                test_results = []

                for testsuite in root.findall('.//testsuite'):
                    for testcase in testsuite.findall('testcase'):
                        test_name = testcase.get('name', 'Unknown')
                        classname = testcase.get('classname', 'Unknown')
                        time = float(testcase.get('time', 0))

                        # Determine status and error message
                        failure = testcase.find('failure')
                        error = testcase.find('error')
                        skipped = testcase.find('skipped')

                        if failure is not None:
                            status = 'Fail'
                            error_msg = failure.get('message', 'Test failed')
                            result = 'Failed'
                        elif error is not None:
                            status = 'Error'
                            error_msg = error.get('message', 'Test error')
                            result = 'Error'
                        elif skipped is not None:
                            status = 'Skip'
                            error_msg = skipped.get('message', 'Test skipped')
                            result = 'Skipped'
                        else:
                            status = 'Pass'
                            error_msg = ''
                            result = 'Success'

                            test_results.append({
                            'name': test_name,
                            'class': classname,
                            'result': result,
                            'status': status,
                            'duration': f"{time:.2f}s",
                            'error': error_msg
                            })

                            return test_results


                            def generate_markdown_report(test_results: List[Dict[str, str]],
                            output_file: str,
                            total_time: float = 0.0) -> None:
                                """Generate a Markdown report from test results."""
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                # Count results
                                total_tests = len(test_results)
                                passed = sum(1 for t in test_results if t['status'] == 'Pass')
                                failed = sum(1 for t in test_results if t['status'] == 'Fail')
                                errors = sum(1 for t in test_results if t['status'] == 'Error')
                                skipped = sum(1 for t in test_results if t['status'] == 'Skip')

                                with open(output_file, 'w') as f:
                                    # Header
                                    f.write(f"# Test Report - {timestamp}\n\n")

                                    # Summary
                                    f.write("## Summary\n\n")
                                    f.write(f"- **Total Tests**: {total_tests}\n")
                                    f.write(f"- **Passed**: {passed} ✅\n")
                                    f.write(f"- **Failed**: {failed} ❌\n")
                                    f.write(f"- **Errors**: {errors} \n")
                                    f.write(f"- **Skipped**: {skipped} ⏭️\n")
                                    f.write(f"- **Total Duration**: {total_time:.2f}s\n")
                                    f.write(f"- **Success Rate**: {(passed/total_tests*100 if total_tests > 0 else 0):.1f}%\n\n")

                                    # Test Results Table
                                    f.write("## Test Results\n\n")
                                    f.write("| Test Name | Description | Result | Status | Duration | Timestamp | Error Message |\n")
                                    f.write("|-----------|-------------|--------|--------|----------|-----------|---------------|\n")

                                    for test in test_results:
                                        # Extract description from test name
                                        test_name = test['name']
                                        if test_name.startswith('test_'):
                                            description = test_name[5:].replace('_', ' ').title()
                                        else:
                                            description = test_name.replace('_', ' ').title()

                                            # Format error message
                                            error_msg = test['error']
                                            if len(error_msg) > 50:
                                                error_msg = error_msg[:47] + "..."
                                                error_msg = error_msg.replace('\n', ' ').replace('|', '\\|')

                                                # Status emoji
                                                status_emoji = {
                                                'Pass': '✅ Pass',
                                                'Fail': '❌ Fail',
                                                'Error': ' Error',
                                                'Skip': '⏭️ Skip'
                                                }.get(test['status'], test['status'])

                                                f.write(f"| {test_name} | {description} | {test['result']} | {status_emoji} | {test['duration']} | {timestamp} | {error_msg} |\n")

                                                # Failed Tests Details
                                                if failed > 0 or errors > 0:
                                                    f.write("\n## Failed Tests Details\n\n")
                                                    for test in test_results:
                                                        if test['status'] in ['Fail', 'Error']:
                                                            f.write(f"### {test['name']}\n")
                                                            f.write(f"- **Class**: {test['class']}\n")
                                                            f.write(f"- **Status**: {test['status']}\n")
                                                            f.write(f"- **Error**: {test['error']}\n\n")

                                                            # Footer
                                                            f.write("\n---\n")
                                                            f.write(f"*Generated automatically by generate_test_report.py on {timestamp}*\n")


                                                            def main():
                                                                """Main function to run tests and generate report."""
                                                                # Check if XML file is provided as argument
                                                                if len(sys.argv) > 1:
                                                                    xml_file = sys.argv[1]
                                                                    if not Path(xml_file).exists():
                                                                        print(f"Error: XML file '{xml_file}' not found")
                                                                        # sys.exit() removed

                                                                        print(f"Parsing existing test results from: {xml_file}")
                                                                        test_results = parse_junit_xml(xml_file)
                                                                    else:
                                                                        # Run tests
                                                                        print("Running test suite...")
                                                                        return_code, xml_file = run_tests_with_xml()

                                                                        if not Path(xml_file).exists():
                                                                            print(f"Error: Test output file '{xml_file}' not found")
                                                                            # sys.exit() removed

                                                                            print(f"Parsing test results from: {xml_file}")
                                                                            test_results = parse_junit_xml(xml_file)

                                                                            # Generate report
                                                                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                                                            report_dir = Path("docs/reports")
                                                                            report_dir.mkdir(parents=True, exist_ok=True)

                                                                            report_file = report_dir / f"test_report_{timestamp}.md"

                                                                            print(f"Generating report: {report_file}")
                                                                            generate_markdown_report(test_results, str(report_file))

                                                                            print(f"✅ Test report generated: {report_file}")

                                                                            # Clean up temporary XML file
                                                                            if 'return_code' in locals():
                                                                                Path(xml_file).unlink()

                                                                                # Exit with test suite return code if we ran tests
                                                                                if 'return_code' in locals():
                                                                                    # sys.exit() removed


                                                                                    if __name__ == "__main__":
                                                                                        main()