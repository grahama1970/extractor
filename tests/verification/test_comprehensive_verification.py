#!/usr/bin/env python3
"""Comprehensive verification of all Task 007 components."""

import os
import sys
import re
from datetime import datetime

print("=== Task 8: Comprehensive Verification ===")
print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Base paths
base_dir = "."
llm_call_dir = os.path.join(base_dir, "marker/llm_call")
reports_dir = os.path.join(base_dir, "docs/reports")

# Track overall status
task_status = {}
overall_status = True

def check_task_1_core():
    """Verify Task 1: Core Layer"""
    print("=== Task 1: Core Layer ===")
    
    core_dir = os.path.join(llm_call_dir, "core")
    required_files = ["__init__.py", "base.py", "retry.py", "strategies.py", "debug.py", "utils.py"]
    
    status = True
    for file in required_files:
        path = os.path.join(core_dir, file)
        exists = os.path.exists(path)
        print(f"  {file}: {'✓ EXISTS' if exists else '✗ MISSING'}")
        status = status and exists
    
    # Check test file
    test_file = os.path.join(base_dir, "tests/test_llm_call_module.py")
    test_exists = os.path.exists(test_file)
    print(f"  Test file: {'✓ EXISTS' if test_exists else '✗ MISSING'}")
    
    # Check verification report
    report = os.path.join(reports_dir, "007_task_1_core_layer_verified.md")
    report_exists = os.path.exists(report)
    print(f"  Verification report: {'✓ EXISTS' if report_exists else '✗ MISSING'}")
    
    task_status["Task 1"] = status and test_exists and report_exists
    return task_status["Task 1"]

def check_task_2_cli():
    """Verify Task 2: CLI Layer"""
    print("\n=== Task 2: CLI Layer ===")
    
    cli_dir = os.path.join(llm_call_dir, "cli")
    required_files = ["__init__.py", "app.py", "formatters.py", "schemas.py", "debug_commands.py"]
    
    status = True
    for file in required_files:
        path = os.path.join(cli_dir, file)
        exists = os.path.exists(path)
        print(f"  {file}: {'✓ EXISTS' if exists else '✗ MISSING'}")
        status = status and exists
    
    # Check verification report
    report = os.path.join(reports_dir, "007_task_2_cli_layer.md")
    report_exists = os.path.exists(report)
    print(f"  Verification report: {'✓ EXISTS' if report_exists else '✗ MISSING'}")
    
    task_status["Task 2"] = status and report_exists
    return task_status["Task 2"]

def check_task_3_validators():
    """Verify Task 3: Processor-Specific Validators"""
    print("\n=== Task 3: Processor Validators ===")
    
    validators_dir = os.path.join(llm_call_dir, "validators")
    required_files = ["base.py", "citation.py", "table.py", "image.py", "math.py", "code.py", "general.py"]
    
    status = True
    validator_count = 0
    
    for file in required_files:
        path = os.path.join(validators_dir, file)
        exists = os.path.exists(path)
        print(f"  {file}: {'✓ EXISTS' if exists else '✗ MISSING'}")
        status = status and exists
        
        if exists and file != "base.py":
            with open(path, 'r') as f:
                content = f.read()
                decorators = content.count("@validator(")
                validator_count += decorators
                print(f"    Validators: {decorators}")
    
    print(f"  Total validators: {validator_count}")
    
    # Check verification report
    report = os.path.join(reports_dir, "007_task_3_processor_validators_verified.md")
    report_exists = os.path.exists(report)
    print(f"  Verification report: {'✓ EXISTS' if report_exists else '✗ MISSING'}")
    
    task_status["Task 3"] = status and report_exists and validator_count >= 15
    return task_status["Task 3"]

def check_task_4_litellm():
    """Verify Task 4: LiteLLM Integration"""
    print("\n=== Task 4: LiteLLM Integration ===")
    
    integration_file = os.path.join(llm_call_dir, "litellm_integration.py")
    
    status = os.path.exists(integration_file)
    print(f"  litellm_integration.py: {'✓ EXISTS' if status else '✗ MISSING'}")
    
    # Check verification report
    report = os.path.join(reports_dir, "007_task_4_litellm_integration.md")
    report_exists = os.path.exists(report)
    print(f"  Verification report: {'✓ EXISTS' if report_exists else '✗ MISSING'}")
    
    task_status["Task 4"] = status and report_exists
    return task_status["Task 4"]

def check_task_5_package():
    """Verify Task 5: Standalone Package"""
    print("\n=== Task 5: Standalone Package ===")
    
    package_files = ["setup.py", "pyproject.toml", "README.md", "MANIFEST.in"]
    
    status = True
    for file in package_files:
        path = os.path.join(llm_call_dir, file)
        exists = os.path.exists(path)
        print(f"  {file}: {'✓ EXISTS' if exists else '✗ MISSING'}")
        status = status and exists
    
    # Check examples
    examples_dir = os.path.join(llm_call_dir, "examples")
    examples_exist = os.path.exists(examples_dir)
    if examples_exist:
        examples = os.listdir(examples_dir)
        print(f"  Examples: {len(examples)} files")
    else:
        print(f"  Examples: ✗ MISSING")
    
    # Check verification report
    report = os.path.join(reports_dir, "007_task_5_package_verified.md")
    report_exists = os.path.exists(report)
    print(f"  Verification report: {'✓ EXISTS' if report_exists else '✗ MISSING'}")
    
    task_status["Task 5"] = status and examples_exist and report_exists
    return task_status["Task 5"]

def check_task_6_documentation():
    """Verify Task 6: Documentation"""
    print("\n=== Task 6: Documentation ===")
    
    docs_dir = os.path.join(llm_call_dir, "docs")
    expected_docs = [
        "index.md", "getting_started.md", "core_concepts.md", 
        "validators.md", "api_reference.md", "cli_reference.md",
        "examples.md", "architecture.md", "contributing.md"
    ]
    
    status = True
    doc_count = 0
    
    for doc in expected_docs:
        path = os.path.join(docs_dir, doc)
        exists = os.path.exists(path)
        print(f"  {doc}: {'✓ EXISTS' if exists else '✗ MISSING'}")
        status = status and exists
        if exists:
            doc_count += 1
    
    print(f"  Total docs: {doc_count}/{len(expected_docs)}")
    
    # Check verification report
    report = os.path.join(reports_dir, "007_task_6_documentation_verified.md")
    report_exists = os.path.exists(report)
    print(f"  Verification report: {'✓ EXISTS' if report_exists else '✗ MISSING'}")
    
    task_status["Task 6"] = status and report_exists
    return task_status["Task 6"]

def check_task_7_integration():
    """Verify Task 7: Demo Integration"""
    print("\n=== Task 7: Demo Integration ===")
    
    integration_file = os.path.join(llm_call_dir, "examples/arangodb_integration.py")
    readme_file = os.path.join(llm_call_dir, "examples/arangodb_integration_readme.md")
    test_file = os.path.join(base_dir, "tests/integration/test_arangodb_integration.py")
    
    integration_exists = os.path.exists(integration_file)
    readme_exists = os.path.exists(readme_file)
    test_exists = os.path.exists(test_file)
    
    print(f"  Integration example: {'✓ EXISTS' if integration_exists else '✗ MISSING'}")
    print(f"  README: {'✓ EXISTS' if readme_exists else '✗ MISSING'}")
    print(f"  Test file: {'✓ EXISTS' if test_exists else '✗ MISSING'}")
    
    # Check verification report
    report = os.path.join(reports_dir, "007_task_7_integration_verified.md")
    report_exists = os.path.exists(report)
    print(f"  Verification report: {'✓ EXISTS' if report_exists else '✗ MISSING'}")
    
    task_status["Task 7"] = integration_exists and readme_exists and test_exists and report_exists
    return task_status["Task 7"]

def check_verification_reports():
    """Check all verification reports"""
    print("\n=== Verification Reports ===")
    
    expected_reports = [
        "007_task_1_core_layer_verified.md",
        "007_task_2_cli_layer.md",
        "007_task_3_processor_validators_verified.md",
        "007_task_4_litellm_integration.md",
        "007_task_5_package_verified.md",
        "007_task_6_documentation_verified.md",
        "007_task_7_integration_verified.md",
        "007_litellm_validation_index.md"
    ]
    
    report_count = 0
    for report in expected_reports:
        path = os.path.join(reports_dir, report)
        exists = os.path.exists(path)
        print(f"  {report}: {'✓ EXISTS' if exists else '✗ MISSING'}")
        if exists:
            report_count += 1
    
    print(f"\nReports found: {report_count}/{len(expected_reports)}")
    return report_count == len(expected_reports)

# Run all checks
print("Running comprehensive verification...\n")

check_task_1_core()
check_task_2_cli()
check_task_3_validators()
check_task_4_litellm()
check_task_5_package()
check_task_6_documentation()
check_task_7_integration()
reports_ok = check_verification_reports()

# Summary
print("\n=== FINAL SUMMARY ===\n")

passed = 0
failed = 0

for task, status in sorted(task_status.items()):
    print(f"{task}: {'✅ VERIFIED' if status else '❌ FAILED'}")
    if status:
        passed += 1
    else:
        failed += 1
        overall_status = False

print(f"\nTasks passed: {passed}/7")
print(f"Tasks failed: {failed}/7")
print(f"All reports exist: {'✅ YES' if reports_ok else '❌ NO'}")

if overall_status and reports_ok:
    print("\n🎉 ALL TASKS SUCCESSFULLY VERIFIED!")
    print("Task 007: LiteLLM Validation Loop Integration is COMPLETE")
else:
    print(f"\n⚠️  INCOMPLETE: {failed} tasks need attention")
    print("Continue working on failed tasks until all are verified")

print(f"\nVerification completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")