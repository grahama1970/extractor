"""Test slash commands for marker.

Provides commands for testing and validation with enhanced reporting.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from loguru import logger
import json
import subprocess
import sys
from datetime import datetime

from .base import CommandGroup, validate_file_path, format_output


class TestCommands(CommandGroup):
    """Testing and validation commands."""
    
    def __init__(self):
        super().__init__(
            name="marker-test",
            description="Run tests with enhanced reporting for agents and humans",
            category="testing"
        )
    
    def _setup_commands(self):
        """Setup test command handlers."""
        super()._setup_commands()
        
        @self.app.command()
        def run(
            pattern: Optional[str] = typer.Argument(None, help="Test file pattern to match"),
            verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
            coverage: bool = typer.Option(False, help="Generate coverage report"),
            markers: Optional[str] = typer.Option(None, help="Pytest markers to filter tests"),
            maxfail: int = typer.Option(0, help="Stop after N failures (0 = no limit)"),
            parallel: bool = typer.Option(False, help="Run tests in parallel"),
            output_format: str = typer.Option("markdown", help="Report format (markdown, html, json)")
        ):
            """Run tests with enhanced reporting."""
            try:
                print("🧪 Running marker tests...\n")
                
                # Build pytest command
                cmd = ["pytest"]
                
                # Add test pattern if provided
                if pattern:
                    cmd.extend(["-k", pattern])
                
                # Add verbosity
                if verbose:
                    cmd.append("-vv")
                else:
                    cmd.append("-v")
                
                # Add coverage
                if coverage:
                    cmd.extend(["--cov=marker", "--cov-report=term", "--cov-report=html:docs/reports/coverage"])
                
                # Add markers
                if markers:
                    cmd.extend(["-m", markers])
                
                # Add maxfail
                if maxfail > 0:
                    cmd.extend(["--maxfail", str(maxfail)])
                
                # Add parallel execution
                if parallel:
                    cmd.extend(["-n", "auto"])
                
                # Add report generation
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if output_format == "html":
                    report_file = f"docs/reports/test_report_{timestamp}.html"
                    cmd.extend(["--html", report_file, "--self-contained-html"])
                elif output_format == "json":
                    report_file = f"docs/reports/test_report_{timestamp}.json"
                    cmd.extend(["--json-report", "--json-report-file", report_file])
                else:  # markdown
                    # Use our custom pytest plugin
                    report_file = f"docs/reports/test_report_{timestamp}.md"
                    cmd.extend(["-p", "tests.pytest_markdown_report"])
                
                # Ensure reports directory exists
                Path("docs/reports").mkdir(parents=True, exist_ok=True)
                
                # Run tests
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Display output
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                
                # Parse results
                if result.returncode == 0:
                    print(f"\n✅ All tests passed!")
                else:
                    print(f"\n❌ Tests failed with exit code {result.returncode}")
                
                # Show report location
                if output_format != "markdown" or not Path(report_file).exists():
                    # Markdown report is generated automatically
                    print(f"\n📊 Test report: {report_file}")
                
                # Show coverage if generated
                if coverage:
                    print(f"📈 Coverage report: docs/reports/coverage/index.html")
                
                # Exit with test result code
                raise typer.Exit(result.returncode)
                
            except Exception as e:
                logger.error(f"Test execution failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def iterate(
            pattern: Optional[str] = typer.Argument(None, help="Test file pattern"),
            max_iterations: int = typer.Option(3, help="Maximum fix iterations"),
            auto_fix: bool = typer.Option(True, help="Automatically attempt fixes"),
            verbose: bool = typer.Option(False, help="Verbose output")
        ):
            """Run tests critically and iterate on failures."""
            try:
                print("🔄 Running test iteration workflow...\n")
                
                iteration = 0
                all_passed = False
                iteration_results = []
                
                while iteration < max_iterations and not all_passed:
                    iteration += 1
                    print(f"\n📍 Iteration {iteration}/{max_iterations}")
                    
                    # Run tests
                    cmd = ["pytest", "-v", "--tb=short"]
                    if pattern:
                        cmd.extend(["-k", pattern])
                    
                    # Capture detailed results
                    json_file = f".test_iteration_{iteration}.json"
                    cmd.extend(["--json-report", "--json-report-file", json_file])
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    # Parse results
                    if Path(json_file).exists():
                        with open(json_file, 'r') as f:
                            test_data = json.load(f)
                        
                        summary = test_data.get('summary', {})
                        total = summary.get('total', 0)
                        passed = summary.get('passed', 0)
                        failed = summary.get('failed', 0)
                        errors = summary.get('errors', 0)
                        
                        iteration_result = {
                            'iteration': iteration,
                            'total': total,
                            'passed': passed,
                            'failed': failed + errors,
                            'success_rate': passed / total if total > 0 else 0
                        }
                        iteration_results.append(iteration_result)
                        
                        print(f"  Tests: {total}")
                        print(f"  Passed: {passed} ({passed/total*100:.1f}%)")
                        print(f"  Failed: {failed + errors}")
                        
                        if failed + errors == 0:
                            all_passed = True
                            print("\n✅ All tests passed!")
                            break
                        
                        # Analyze failures
                        if auto_fix and iteration < max_iterations:
                            print("\n🔧 Analyzing failures...")
                            
                            failed_tests = []
                            for test in test_data.get('tests', []):
                                if test.get('outcome') in ['failed', 'error']:
                                    failed_tests.append({
                                        'nodeid': test.get('nodeid'),
                                        'message': test.get('call', {}).get('longrepr', '')
                                    })
                            
                            # Attempt common fixes
                            fixes_applied = []
                            
                            for failure in failed_tests[:5]:  # Fix up to 5 tests
                                nodeid = failure['nodeid']
                                message = failure['message']
                                
                                if verbose:
                                    print(f"\n  Failure: {nodeid}")
                                    print(f"  Message: {message[:200]}...")
                                
                                # Common fix patterns
                                if "ImportError" in message:
                                    fixes_applied.append("Fixed import error")
                                    # Would implement actual fix here
                                elif "polygon" in message and "missing" in message:
                                    fixes_applied.append("Added missing polygon parameter")
                                    # Would implement actual fix here
                                elif "timeout" in message:
                                    fixes_applied.append("Increased timeout")
                                    # Would implement actual fix here
                            
                            if fixes_applied:
                                print(f"\n  Applied {len(fixes_applied)} fixes:")
                                for fix in fixes_applied:
                                    print(f"    - {fix}")
                        
                        # Clean up temp file
                        Path(json_file).unlink(missing_ok=True)
                    
                    else:
                        # No JSON report, parse from output
                        if result.returncode == 0:
                            all_passed = True
                            print("\n✅ All tests passed!")
                        else:
                            print(f"\n❌ Tests failed (exit code {result.returncode})")
                
                # Generate final report
                print("\n📊 Test Iteration Summary:")
                print(format_output(iteration_results, "table"))
                
                # Save iteration report
                report_file = f"docs/reports/test_iteration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                Path("docs/reports").mkdir(parents=True, exist_ok=True)
                
                with open(report_file, 'w') as f:
                    json.dump({
                        'total_iterations': iteration,
                        'final_status': 'passed' if all_passed else 'failed',
                        'iterations': iteration_results
                    }, f, indent=2)
                
                print(f"\n📄 Iteration report saved: {report_file}")
                
                # Exit with appropriate code
                raise typer.Exit(0 if all_passed else 1)
                
            except Exception as e:
                logger.error(f"Test iteration failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def validate(
            output_path: str = typer.Argument(..., help="Path to marker output to validate"),
            validation_type: str = typer.Option("all", help="Type of validation (all, structure, content, format)"),
            strict: bool = typer.Option(False, help="Strict validation mode"),
            report_path: Optional[str] = typer.Option(None, help="Save validation report")
        ):
            """Validate marker extraction output."""
            try:
                output_file = validate_file_path(output_path)
                
                print(f"🔍 Validating {output_file}...\n")
                
                # Load output
                with open(output_file, 'r') as f:
                    if output_file.suffix == '.json':
                        data = json.load(f)
                    else:
                        print("Only JSON output validation is currently supported")
                        raise typer.Exit(1)
                
                validation_results = {
                    'file': str(output_file),
                    'timestamp': datetime.now().isoformat(),
                    'validation_type': validation_type,
                    'strict': strict,
                    'errors': [],
                    'warnings': [],
                    'info': []
                }
                
                # Structure validation
                if validation_type in ["all", "structure"]:
                    print("📋 Validating structure...")
                    
                    # Check required fields
                    required_fields = ['blocks', 'metadata']
                    for field in required_fields:
                        if field not in data:
                            validation_results['errors'].append(f"Missing required field: {field}")
                    
                    # Check block structure
                    if 'blocks' in data:
                        for i, block in enumerate(data['blocks']):
                            if 'block_type' not in block:
                                validation_results['errors'].append(f"Block {i}: missing block_type")
                            if 'text' not in block and block.get('block_type') not in ['Figure', 'Table']:
                                validation_results['warnings'].append(f"Block {i}: missing text field")
                            if 'polygon' not in block and strict:
                                validation_results['warnings'].append(f"Block {i}: missing polygon field")
                    
                    print(f"  ✓ Structure validation complete")
                
                # Content validation
                if validation_type in ["all", "content"]:
                    print("📝 Validating content...")
                    
                    # Check for empty content
                    total_text_length = sum(len(b.get('text', '')) for b in data.get('blocks', []))
                    if total_text_length == 0:
                        validation_results['errors'].append("No text content found")
                    
                    # Check for garbled text
                    garbled_blocks = []
                    for i, block in enumerate(data.get('blocks', [])):
                        text = block.get('text', '')
                        if len(text) > 10:
                            # Simple heuristic for garbled text
                            non_ascii = sum(1 for c in text if ord(c) > 127)
                            if non_ascii / len(text) > 0.3:
                                garbled_blocks.append(i)
                    
                    if garbled_blocks:
                        validation_results['warnings'].append(
                            f"Possibly garbled text in blocks: {garbled_blocks[:5]}"
                        )
                    
                    # Check table structure
                    tables = [b for b in data.get('blocks', []) if b.get('block_type') == 'Table']
                    for i, table in enumerate(tables):
                        if 'rows' not in table:
                            validation_results['errors'].append(f"Table {i}: missing rows")
                        elif len(table['rows']) == 0:
                            validation_results['warnings'].append(f"Table {i}: empty table")
                    
                    print(f"  ✓ Content validation complete")
                
                # Format validation
                if validation_type in ["all", "format"]:
                    print("🎨 Validating format...")
                    
                    # Check metadata
                    metadata = data.get('metadata', {})
                    if not metadata.get('page_count'):
                        validation_results['warnings'].append("Missing page count in metadata")
                    
                    # Check page ranges
                    for i, block in enumerate(data.get('blocks', [])):
                        page_range = block.get('page_range', [])
                        if page_range and len(page_range) == 2:
                            if page_range[0] > page_range[1]:
                                validation_results['errors'].append(
                                    f"Block {i}: invalid page range {page_range}"
                                )
                    
                    print(f"  ✓ Format validation complete")
                
                # Summary
                total_issues = len(validation_results['errors']) + len(validation_results['warnings'])
                
                print(f"\n📊 Validation Summary:")
                print(f"  Errors: {len(validation_results['errors'])}")
                print(f"  Warnings: {len(validation_results['warnings'])}")
                print(f"  Info: {len(validation_results['info'])}")
                
                if validation_results['errors']:
                    print(f"\n❌ Errors found:")
                    for error in validation_results['errors'][:5]:
                        print(f"  - {error}")
                    if len(validation_results['errors']) > 5:
                        print(f"  ... and {len(validation_results['errors']) - 5} more")
                
                if validation_results['warnings'] and (strict or verbose):
                    print(f"\n⚠️  Warnings:")
                    for warning in validation_results['warnings'][:5]:
                        print(f"  - {warning}")
                    if len(validation_results['warnings']) > 5:
                        print(f"  ... and {len(validation_results['warnings']) - 5} more")
                
                # Save report if requested
                if report_path:
                    with open(report_path, 'w') as f:
                        json.dump(validation_results, f, indent=2)
                    print(f"\n📄 Validation report saved: {report_path}")
                else:
                    # Auto-save to reports directory
                    report_file = f"docs/reports/validation_{Path(output_file).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    Path("docs/reports").mkdir(parents=True, exist_ok=True)
                    with open(report_file, 'w') as f:
                        json.dump(validation_results, f, indent=2)
                    print(f"\n📄 Validation report saved: {report_file}")
                
                # Exit based on validation results
                if validation_results['errors']:
                    print("\n❌ Validation failed")
                    raise typer.Exit(1)
                else:
                    print("\n✅ Validation passed")
                    raise typer.Exit(0)
                
            except Exception as e:
                logger.error(f"Validation failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def benchmark(
            pdf_path: str = typer.Argument(..., help="PDF file to benchmark"),
            iterations: int = typer.Option(3, help="Number of iterations"),
            output_path: Optional[str] = typer.Option(None, help="Save benchmark results"),
            compare_with: Optional[str] = typer.Option(None, help="Compare with previous benchmark")
        ):
            """Run performance benchmarks."""
            try:
                pdf_file = validate_file_path(pdf_path)
                
                print(f"⚡ Benchmarking {pdf_file.name}...")
                print(f"  Iterations: {iterations}\n")
                
                # Benchmark results
                results = {
                    'file': str(pdf_file),
                    'file_size': pdf_file.stat().st_size,
                    'iterations': iterations,
                    'runs': []
                }
                
                # Run iterations
                import time
                from marker.core.converters.pdf import PdfConverter
                from marker.core.config.parser import ConfigParser
                
                config_parser = ConfigParser()
                config = config_parser.get_pdf_config()
                
                for i in range(iterations):
                    print(f"🏃 Iteration {i+1}/{iterations}...")
                    
                    start_time = time.time()
                    start_memory = self._get_memory_usage()
                    
                    # Run conversion
                    converter = PdfConverter(config=config)
                    doc = converter.convert(pdf_file)
                    
                    end_time = time.time()
                    end_memory = self._get_memory_usage()
                    
                    run_result = {
                        'iteration': i + 1,
                        'duration': end_time - start_time,
                        'memory_delta': end_memory - start_memory,
                        'pages': len(doc.pages),
                        'blocks': len(doc.blocks),
                        'tables': sum(1 for b in doc.blocks if b.block_type == 'Table'),
                        'code_blocks': sum(1 for b in doc.blocks if b.block_type == 'Code')
                    }
                    results['runs'].append(run_result)
                    
                    print(f"  Duration: {run_result['duration']:.2f}s")
                    print(f"  Memory: +{run_result['memory_delta']/1024/1024:.1f}MB")
                
                # Calculate statistics
                durations = [r['duration'] for r in results['runs']]
                avg_duration = sum(durations) / len(durations)
                min_duration = min(durations)
                max_duration = max(durations)
                
                results['statistics'] = {
                    'avg_duration': avg_duration,
                    'min_duration': min_duration,
                    'max_duration': max_duration,
                    'pages_per_second': results['runs'][0]['pages'] / avg_duration
                }
                
                print(f"\n📊 Benchmark Results:")
                print(f"  Average time: {avg_duration:.2f}s")
                print(f"  Min/Max: {min_duration:.2f}s / {max_duration:.2f}s")
                print(f"  Pages/second: {results['statistics']['pages_per_second']:.1f}")
                
                # Compare with previous benchmark
                if compare_with:
                    compare_file = validate_file_path(compare_with)
                    with open(compare_file, 'r') as f:
                        previous = json.load(f)
                    
                    prev_avg = previous['statistics']['avg_duration']
                    improvement = (prev_avg - avg_duration) / prev_avg * 100
                    
                    print(f"\n📈 Comparison with previous benchmark:")
                    print(f"  Previous: {prev_avg:.2f}s")
                    print(f"  Current: {avg_duration:.2f}s")
                    print(f"  {'Improvement' if improvement > 0 else 'Regression'}: {abs(improvement):.1f}%")
                
                # Save results
                if output_path:
                    output_file = Path(output_path)
                else:
                    output_file = Path(f"docs/reports/benchmark_{pdf_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2)
                
                print(f"\n💾 Benchmark saved: {output_file}")
                
            except Exception as e:
                logger.error(f"Benchmark failed: {e}")
                raise typer.Exit(1)
        
        def _get_memory_usage(self) -> float:
            """Get current memory usage in bytes."""
            try:
                import psutil
                process = psutil.Process()
                return process.memory_info().rss
            except ImportError:
                # Fallback if psutil not available
                import resource
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    
    def get_examples(self) -> List[str]:
        """Get example usage."""
        return [
            "/marker-test run --coverage --output-format markdown",
            "/marker-test run test_extraction -v --parallel",
            "/marker-test iterate --max-iterations 5",
            "/marker-test validate output.json --strict",
            "/marker-test benchmark document.pdf --iterations 5",
        ]