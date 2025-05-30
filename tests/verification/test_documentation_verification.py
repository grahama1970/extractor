#!/usr/bin/env python3
"""Verify all documentation exists for Task 6."""

import os
import sys

print("=== Task 6: Documentation Verification ===\n")

docs_dir = "."

# Expected documentation files based on Task 6 requirements
expected_docs = {
    "index.md": "Main documentation index",
    "getting_started.md": "Quick start guide",
    "core_concepts.md": "Core concepts documentation",
    "validators.md": "Validator documentation",
    "api_reference.md": "Complete API reference",
    "cli_reference.md": "CLI documentation",
    "examples.md": "Usage examples",
    "architecture.md": "System architecture",
    "contributing.md": "Contribution guide"
}

print(f"Documentation directory: {docs_dir}\n")

# Check if docs directory exists
if not os.path.exists(docs_dir):
    print(f"✗ Documentation directory does not exist: {docs_dir}")
    sys.exit(1)

print("Checking documentation files:\n")

missing_docs = []
existing_docs = []

for doc_file, description in expected_docs.items():
    path = os.path.join(docs_dir, doc_file)
    if os.path.exists(path):
        size = os.path.getsize(path)
        existing_docs.append((doc_file, size))
        print(f"✓ {doc_file}: EXISTS ({size:,} bytes) - {description}")
    else:
        missing_docs.append(doc_file)
        print(f"✗ {doc_file}: MISSING - {description}")

# Check for any extra documentation files
print("\nAdditional documentation files:")
actual_files = os.listdir(docs_dir)
extra_files = []
for file in actual_files:
    if file.endswith('.md') and file not in expected_docs:
        path = os.path.join(docs_dir, file)
        size = os.path.getsize(path)
        extra_files.append((file, size))
        print(f"  + {file}: {size:,} bytes")

# Content verification for key files
print("\n=== Content Verification ===\n")

# Check index.md for required sections
index_path = os.path.join(docs_dir, "index.md")
if os.path.exists(index_path):
    with open(index_path, 'r') as f:
        index_content = f.read()
    
    required_sections = ["Installation", "Quick Start", "Documentation", "Features"]
    print("index.md sections:")
    for section in required_sections:
        if section in index_content:
            print(f"  ✓ {section} section present")
        else:
            print(f"  ✗ {section} section missing")

# Check api_reference.md for key components
api_path = os.path.join(docs_dir, "api_reference.md")
if os.path.exists(api_path):
    with open(api_path, 'r') as f:
        api_content = f.read()
    
    key_components = ["ValidationResult", "ValidationStrategy", "completion_with_validation", "retry_with_validation"]
    print("\napi_reference.md components:")
    for component in key_components:
        if component in api_content:
            print(f"  ✓ {component} documented")
        else:
            print(f"  ✗ {component} missing")

# Summary statistics
print("\n=== Documentation Summary ===\n")
print(f"Expected files: {len(expected_docs)}")
print(f"Existing files: {len(existing_docs)}")
print(f"Missing files: {len(missing_docs)}")
print(f"Extra files: {len(extra_files)}")

if existing_docs:
    total_size = sum(size for _, size in existing_docs)
    print(f"\nTotal documentation size: {total_size:,} bytes")
    print(f"Average file size: {total_size // len(existing_docs):,} bytes")

# Final status
print("\n=== Final Status ===\n")
if missing_docs:
    print("❌ INCOMPLETE - Missing documentation files:")
    for doc in missing_docs:
        print(f"  - {doc}")
else:
    print("✅ COMPLETE - All required documentation files exist")

# Check if comprehensive
if len(existing_docs) >= len(expected_docs) and total_size > 50000:
    print("✅ COMPREHENSIVE - Documentation appears complete and substantial")
else:
    print("⚠️  Documentation may need more content")

print("\n=== Task 6 Documentation Verification Complete ===")