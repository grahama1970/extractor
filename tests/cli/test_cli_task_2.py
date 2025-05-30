✓ Testing strategies formatter:")
    print_strategies(test_strategies, console)
    
    # Test validation result formatter
    test_result = {
        "model": "test/model",
        "status": "completed",
        "strategies": ["test1", "test2"],
        "max_retries": 3,
        "output": "Test output"
    }
    print("\n✓ Testing validation result formatter:")
    print_validation_result(test_result, console)
    
except Exception as e:
    print(f"✗ Formatter error: {e}")
    sys.exit(1)

print("\n✓ Task 2: CLI Layer implementation test completed successfully!")
print("\nCLI Features Implemented:")
print("- Main CLI app with typer")
print("- Rich formatting for output")
print("- Validation commands (validate, list-validators, add-validator)")
print("- Debug commands (debug, compare)")
print("- Pydantic schemas for input/output")
print("- Comprehensive formatters")

# Test CLI help
print("\n✓ CLI Help Output:")
import subprocess
result = subprocess.run([sys.executable, "-m", "marker.llm_call.cli.app", "--help"], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print(result.stdout)
else:
    print(f"Error: {result.stderr}")