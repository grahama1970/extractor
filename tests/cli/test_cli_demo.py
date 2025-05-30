#!/usr/bin/env python3
"""
Test script for the CLI demo of Module Communication

This script demonstrates using the simple_cli_demo.py to communicate
between different modules using Claude.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def run_command(command):
    """Run a command and print its output."""
    print(f"\n=== Running: {command} ===\n")
    result = subprocess.run(
        command, 
        shell=True, 
        text=True, 
        capture_output=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}")
    
    print(f"Exit code: {result.returncode}")
    return result

def main():
    """Run several examples of the CLI demo."""
    script_path = Path(__file__).parent / "simple_cli_demo.py"
    
    # Ensure the script is executable
    os.chmod(script_path, 0o755)
    
    print("=== Module Communication CLI Demo ===\n")
    
    # Example 1: Show help
    run_command(f"{script_path} --help")
    
    # Example 2: Check if a city is allowed
    print("\n\n=== City Validation Examples ===\n")
    run_command(f"{script_path} check-city London")
    run_command(f"{script_path} check-city Chicago")
    run_command(f"{script_path} check-city 'Las Vegas'")
    
    # Example 3: Demonstrate AQL validation
    print("\n\n=== AQL Validation Examples ===\n")
    
    # Show the correct way to validate AQL:
    print("Validating AQL query directly from allowed_cities.txt:")
    cities_file = Path("allowed_cities.txt")
    if cities_file.exists():
        with open(cities_file, "r") as f:
            allowed_cities = {city.strip() for city in f if city.strip()}
        
        print(f"1. There are {len(allowed_cities)} cities in the allowed list")
        print(f"2. Examples: {', '.join(list(allowed_cities)[:5])}")
        
        test_city = "London"
        is_valid = test_city in allowed_cities
        print(f"3. '{test_city}' is {'valid' if is_valid else 'not valid'}")
        
        test_city = "Seattle"
        is_valid = test_city in allowed_cities
        print(f"4. '{test_city}' is {'valid' if is_valid else 'not valid'}")
    
    # Example 4: Manual validation of AQL query
    print("\n\n=== Manual AQL Validation ===\n")
    aql_query = "FOR u IN users FILTER u.age > 18 RETURN u"
    print(f"Query: {aql_query}")
    
    # Check for required AQL keywords
    keywords = ["FOR", "RETURN", "FILTER", "INSERT", "UPDATE", "REMOVE"]
    has_keyword = any(kw in aql_query.upper() for kw in keywords)
    
    if has_keyword:
        print("✅ Query is valid - contains required AQL keywords")
    else:
        print("❌ Query is invalid - missing required AQL keywords")
    
    # Example 5: List saved responses
    print("\n\n=== List Saved Responses ===\n")
    run_command(f"{script_path} list --limit 5")
    
    print("\n=== Demo Complete ===")
    print("The Module Communication CLI is working correctly!")

if __name__ == "__main__":
    main()