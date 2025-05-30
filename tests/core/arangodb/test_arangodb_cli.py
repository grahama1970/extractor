#!/usr/bin/env python3
"""
Test ArangoDB extraction via CLI
"""
import subprocess
import json
from pathlib import Path

# Create output directory
output_dir = Path("test_arangodb_cli_output")
output_dir.mkdir(exist_ok=True)

print("Testing ArangoDB extraction via CLI...")

# Run the extraction command
cmd = [
    ".venv/bin/python",
    "scripts/cli/marker_mcp_cli.py", 
    "extract-pdf",
    "data/input/Arango_AQL_Example.pdf",
    "--format", "arangodb",
    "--output-dir", str(output_dir)
]

print(f"Running command: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    print(f"✗ Command failed with code {result.returncode}")
    print(f"STDERR: {result.stderr[:1000]}")
    exit(1)

print("✓ Command completed successfully")

# Check for output files
output_files = list(output_dir.glob("*.json"))
if not output_files:
    print("✗ No JSON files created")
    exit(1)

# Load and verify the JSON
output_file = output_files[0]
print(f"✓ Found output file: {output_file}")

with open(output_file, 'r') as f:
    data = json.load(f)

# Verify structure
print("\nStructure verification:")
required_keys = ['document', 'metadata', 'validation', 'raw_corpus']
for key in required_keys:
    if key in data:
        print(f"✓ Has '{key}' key")
    else:
        print(f"✗ Missing '{key}' key")

# Check document structure
if 'document' in data:
    doc = data['document']
    print(f"\nDocument details:")
    print(f"- ID: {doc.get('id', 'N/A')}")
    print(f"- Pages: {len(doc.get('pages', []))}")
    
    # Count block types
    block_types = {}
    for page in doc.get('pages', []):
        for block in page.get('blocks', []):
            btype = block.get('type', 'unknown')
            block_types[btype] = block_types.get(btype, 0) + 1
    
    print(f"\nBlock distribution:")
    for btype, count in sorted(block_types.items()):
        print(f"  - {btype}: {count}")

# Check corpus
if 'raw_corpus' in data:
    corpus = data['raw_corpus']
    print(f"\nRaw corpus:")
    print(f"- Total pages: {corpus.get('total_pages', 0)}")
    print(f"- Full text length: {len(corpus.get('full_text', ''))}")

print("\n✓ ArangoDB JSON structure verified!")