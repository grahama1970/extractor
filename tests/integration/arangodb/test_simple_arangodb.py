Expected JSON structure fields:")
    print("- document (with id and pages)")
    print("- metadata (title, filepath, etc.)")
    print("- validation (corpus_validation)")
    print("- raw_corpus (full_text, pages, total_pages)")
    
    # Now test with CLI
    print("\nTesting with CLI command...")
    
except Exception as e:
    print(f"✗ Error importing ArangoDB renderer: {e}")
    import traceback
    traceback.print_exc()

# Try running marker with JSON output first
import subprocess

print("\nRunning marker with regular JSON output...")
result = subprocess.run([
    ".venv/bin/python", 
    "scripts/cli/marker_mcp_cli.py",
    "extract-pdf",
    "data/input/Arango_AQL_Example.pdf",
    "--format", "json",
    "--output-dir", "test_json_output"
], capture_output=True, text=True)

if result.returncode == 0:
    print("✓ JSON extraction completed")
else:
    print(f"✗ JSON extraction failed: {result.stderr}")

# Now try with arangodb format
print("\nRunning marker with ArangoDB format...")
result = subprocess.run([
    ".venv/bin/python", 
    "scripts/cli/marker_mcp_cli.py",
    "extract-pdf",
    "data/input/Arango_AQL_Example.pdf",
    "--format", "arangodb",
    "--output-dir", "test_arangodb_output"
], capture_output=True, text=True)

if result.returncode == 0:
    print("✓ ArangoDB extraction completed")
    # Check output
    output_files = list(Path("test_arangodb_output").glob("*"))
    print(f"Output files: {output_files}")
else:
    print(f"✗ ArangoDB extraction failed: {result.stderr[:500]}")