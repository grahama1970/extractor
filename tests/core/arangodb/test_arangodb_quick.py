=== Testing AQL Validator ===")
    aql_validator = AQLValidator()
    
    # Test 1: Valid basic query
    test1 = {"name": "Valid basic query"}
    test1["input"] = "FOR u IN users RETURN u"
    result1 = aql_validator.validate(test1["input"])
    test1["result"] = {"valid": result1.valid, "error": result1.error, "debug_info": result1.debug_info}
    test1["pass"] = result1.valid
    results["tests"].append(test1)
    print(f"✓ {test1['name']}: {'PASS' if test1['pass'] else 'FAIL'}")
    
    # Test 2: Invalid query (empty)
    test2 = {"name": "Invalid empty query"}
    test2["input"] = ""
    result2 = aql_validator.validate(test2["input"])
    test2["result"] = {"valid": result2.valid, "error": result2.error, "suggestions": result2.suggestions}
    test2["pass"] = not result2.valid  # Should be invalid
    results["tests"].append(test2)
    print(f"✓ {test2['name']}: {'PASS' if test2['pass'] else 'FAIL'}")
    
    # Test 3: Complex valid query
    test3 = {"name": "Complex valid query"}
    test3["input"] = "FOR u IN users FILTER u.age > 18 SORT u.name RETURN u"
    result3 = aql_validator.validate(test3["input"])
    test3["result"] = {"valid": result3.valid, "error": result3.error, "debug_info": result3.debug_info}
    test3["pass"] = result3.valid
    results["tests"].append(test3)
    print(f"✓ {test3['name']}: {'PASS' if test3['pass'] else 'FAIL'}")
    
    # Test 4: Too complex query
    test4 = {"name": "Too complex query"}
    test4["input"] = """
        FOR u IN users
        LET friends = (
            FOR f IN friends
            FILTER f.user_id == u._key
            FOR p IN profiles
            FILTER p._key == f.friend_id
            FOR c IN cities
            FILTER c._key == p.city_id
            RETURN {friend: p, city: c}
        )
        FOR f IN friends
        FILTER f.city.population > 1000000
        RETURN {user: u, friend: f}
    """
    result4 = aql_validator.validate(test4["input"])
    test4["result"] = {"valid": result4.valid, "error": result4.error, "suggestions": result4.suggestions}
    test4["pass"] = not result4.valid  # Should be invalid due to complexity
    results["tests"].append(test4)
    print(f"✓ {test4['name']}: {'PASS' if test4['pass'] else 'FAIL'}")
    
    # Test Document Validator
    print("\n=== Testing Document Validator ===")
    doc_validator = ArangoDocumentValidator()
    
    # Test 5: Valid document
    test5 = {"name": "Valid document"}
    test5["input"] = {
        "data": {
            "name": "John Doe",
            "email": "john@example.com"
        }
    }
    result5 = doc_validator.validate(test5["input"])
    test5["result"] = {"valid": result5.valid, "error": result5.error}
    test5["pass"] = result5.valid
    results["tests"].append(test5)
    print(f"✓ {test5['name']}: {'PASS' if test5['pass'] else 'FAIL'}")
    
    # Test 6: Invalid document
    test6 = {"name": "Invalid document"}
    test6["input"] = {"name": "John Doe"}  # Missing 'data' key
    result6 = doc_validator.validate(test6["input"])
    test6["result"] = {"valid": result6.valid, "error": result6.error, "suggestions": result6.suggestions}
    test6["pass"] = not result6.valid  # Should be invalid
    results["tests"].append(test6)
    print(f"✓ {test6['name']}: {'PASS' if test6['pass'] else 'FAIL'}")
    
    # City validation test
    print("\n=== Testing City Validation ===")
    # Check allowed_cities.txt
    cities_file = Path("allowed_cities.txt")
    if not cities_file.exists():
        print("ℹ Creating allowed_cities.txt for testing")
        with open(cities_file, "w") as f:
            f.write("New York\nLondon\nTokyo\nParis\nBerlin\nSingapore\n")
    
    with open(cities_file, "r") as f:
        allowed_cities = {city.strip() for city in f if city.strip()}
    
    # Test 7: Valid city
    test7 = {"name": "Valid city"}
    test7["input"] = "London"
    test7["result"] = {"valid": test7["input"] in allowed_cities}
    test7["pass"] = test7["result"]["valid"]
    results["tests"].append(test7)
    print(f"✓ {test7['name']}: {'PASS' if test7['pass'] else 'FAIL'}")
    
    # Test 8: Invalid city
    test8 = {"name": "Invalid city"}
    test8["input"] = "Chicago"
    test8["result"] = {"valid": test8["input"] in allowed_cities}
    test8["pass"] = not test8["result"]["valid"]  # Should be invalid
    results["tests"].append(test8)
    print(f"✓ {test8['name']}: {'PASS' if test8['pass'] else 'FAIL'}")
    
    # Summary
    passed = sum(1 for test in results["tests"] if test["pass"])
    total = len(results["tests"])
    results["summary"] = {
        "total": total,
        "passed": passed,
        "failed": total - passed
    }
    
    print(f"\n=== Test Summary ===")
    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"{'✅ All tests passed!' if passed == total else '❌ Some tests failed!'}")
    
    return results


def main():
    """Main function."""
    print(f"ArangoDB Integration Quick Test")
    print(f"Using module from: {MODULE_SOURCE}")
    
    # Run tests
    results = run_validation_tests()
    
    # Save results to file
    results_path = DEBUG_DIR / "arangodb_quick_test_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {results_path}")
    
    # Exit with appropriate code
    if results["summary"]["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()