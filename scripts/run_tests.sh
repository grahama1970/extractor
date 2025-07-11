#!/bin/bash
"""
Run all Marker tests with proper organization and reporting
"""

set -e

echo "Running Marker Enhanced Tests with JSON Reporting..."
echo "=================================================="

# Ensure virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Virtual environment not activated. Activating .venv..."
    source .venv/bin/activate || { echo "❌ Failed to activate virtual environment"; exit 1; }
fi

# Clean up any previous test results
rm -f test-results.json test-results-*.json docs/reports/test_report_*.md

# Function to run tests and generate reports
run_test_suite() {
    local suite_name=$1
    local test_path=$2
    local json_file="test-results-${suite_name}.json"
    
    echo -e "\n🧪 Running ${suite_name} tests..."
    echo "----------------------------------------"
    
    # Run tests with JSON report output
    if pytest ${test_path} \
        --json-report \
        --json-report-file="${json_file}" \
        --json-report-summary \
        -v; then
        echo "✅ ${suite_name} tests passed"
    else
        echo "❌ ${suite_name} tests failed"
        # Continue running other test suites even if one fails
    fi
}

# Run test suites
run_test_suite "core" "tests/config/ tests/builders/ tests/converters/ tests/providers/ tests/renderers/ tests/schema/ tests/services/"
run_test_suite "features" "tests/features/"
run_test_suite "integration" "tests/test_e2e_workflow.py tests/test_regression_marker.py"

# Combine all JSON reports
echo -e "\n📊 Combining test results..."
python -c "
import json
import glob
from pathlib import Path

# Read all JSON reports
all_results = []
for json_file in glob.glob('test-results-*.json'):
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            all_results.append(data)
    except Exception as e:
        print(f'Warning: Could not read {json_file}: {e}')

# Combine results
if all_results:
    combined = {
        'created': all_results[0].get('created', ''),
        'duration': sum(r.get('duration', 0) for r in all_results),
        'exitcode': max(r.get('exitcode', 0) for r in all_results),
        'root': all_results[0].get('root', ''),
        'environment': all_results[0].get('environment', {}),
        'summary': {
            'total': sum(r.get('summary', {}).get('total', 0) for r in all_results),
            'passed': sum(r.get('summary', {}).get('passed', 0) for r in all_results),
            'failed': sum(r.get('summary', {}).get('failed', 0) for r in all_results),
            'skipped': sum(r.get('summary', {}).get('skipped', 0) for r in all_results),
            'xfailed': sum(r.get('summary', {}).get('xfailed', 0) for r in all_results),
            'xpassed': sum(r.get('summary', {}).get('xpassed', 0) for r in all_results),
            'error': sum(r.get('summary', {}).get('error', 0) for r in all_results),
        },
        'collectors': [],
        'tests': []
    }
    
    # Collect all tests
    for result in all_results:
        combined['collectors'].extend(result.get('collectors', []))
        combined['tests'].extend(result.get('tests', []))
    
    # Write combined results
    with open('test-results.json', 'w') as f:
        json.dump(combined, f, indent=2)
    
    print(f'✅ Combined {len(all_results)} test reports')
    print(f'📊 Total tests: {combined[\"summary\"][\"total\"]}')
    print(f'✅ Passed: {combined[\"summary\"][\"passed\"]}')
    print(f'❌ Failed: {combined[\"summary\"][\"failed\"]}')
else:
    print('❌ No test results found')
"

# Generate claude-test-reporter report
echo -e "\n📝 Generating test report..."
if [[ -f "test-results.json" ]]; then
    # Use claude-test-reporter if available
    if command -v claude-test-reporter &> /dev/null; then
        claude-test-reporter test-results.json
        echo "✅ Test report generated with claude-test-reporter"
    else
        echo "⚠️  claude-test-reporter not found in PATH, generating basic report..."
        
        # Generate basic markdown report
        python -c "
import json
from datetime import datetime
from pathlib import Path

# Create reports directory
reports_dir = Path('docs/reports')
reports_dir.mkdir(parents=True, exist_ok=True)

# Read test results
with open('test-results.json', 'r') as f:
    data = json.load(f)

# Generate report
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
report_path = reports_dir / f'test_report_{timestamp}.md'

summary = data.get('summary', {})
tests = data.get('tests', [])

content = f'''# Test Report - Marker Project
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- **Total Tests**: {summary.get('total', 0)}
- **Passed**: {summary.get('passed', 0)}
- **Failed**: {summary.get('failed', 0)}
- **Skipped**: {summary.get('skipped', 0)}
- **Duration**: {data.get('duration', 0):.2f}s

## Test Results

| Test Name | Status | Duration | Error |
|-----------|--------|----------|-------|
'''

for test in tests:
    name = test.get('nodeid', 'Unknown')
    outcome = test.get('outcome', 'unknown')
    duration = test.get('duration', 0)
    error = ''
    
    if outcome == 'failed' and 'call' in test:
        error = test['call'].get('longrepr', '').split('\\n')[0][:50] + '...' if test['call'].get('longrepr') else ''
    
    status_icon = '✅' if outcome == 'passed' else '❌' if outcome == 'failed' else '⏭️'
    content += f'| {name} | {status_icon} {outcome} | {duration:.3f}s | {error} |\\n'

# Write report
report_path.write_text(content)
print(f'✅ Report generated: {report_path}')
"
    fi
else
    echo "❌ No test results found to generate report"
fi

# Summary
echo -e "\n=================================================="
echo "Test run complete!"

# Exit with appropriate code
if [[ -f "test-results.json" ]]; then
    python -c "
import json
with open('test-results.json', 'r') as f:
    data = json.load(f)
    exit(data.get('exitcode', 1))
"
else
    exit 1
fi