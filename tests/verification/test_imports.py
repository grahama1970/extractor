Import Test Results:")
    print(f"Duration: {duration:.3f} seconds")
    print(f"Successful imports: {len(successful_imports)}")
    print(f"Failed imports: {len(failed_imports)}")
    
    if failed_imports:
        print("\nFailed imports:")
        for module, error in failed_imports:
            print(f"  - {module}: {error}")
    
    # Assert all imports succeeded
    assert len(failed_imports) == 0, f"Failed to import {len(failed_imports)} modules"
    
    # Ensure test took realistic time (not mocked)
    assert duration > 0.1, f"Import test completed too quickly ({duration:.3f}s), possibly mocked"
    assert duration < 5.0, f"Import test took too long ({duration:.3f}s), possible issue"


def test_no_circular_imports():
    """Test that there are no circular imports in the codebase."""
    start_time = time.time()
    
    # Track import order to detect circular dependencies
    import_order = []
    original_import = __builtins__.__import__
    
    def tracking_import(name, *args, **kwargs):
        if name.startswith("marker"):
            import_order.append(name)
        return original_import(name, *args, **kwargs)
    
    # Temporarily replace import to track order
    __builtins__.__import__ = tracking_import
    
    try:
        # Import main entry points which should trigger most imports
        import marker.cli.main
        import marker.core.converters.pdf
        import marker.mcp.server
        
        # Check for duplicates which indicate circular imports
        seen = set()
        circular = []
        for module in import_order:
            if module in seen:
                circular.append(module)
            seen.add(module)
        
        duration = time.time() - start_time
        
        print(f"\nCircular Import Test Results:")
        print(f"Duration: {duration:.3f} seconds")
        print(f"Total imports tracked: {len(import_order)}")
        print(f"Circular imports found: {len(circular)}")
        
        if circular:
            print("\nCircular imports detected:")
            for module in circular:
                print(f"  - {module}")
        
        assert len(circular) == 0, f"Found {len(circular)} circular imports"
        assert duration > 0.2, f"Circular import test too fast ({duration:.3f}s), possibly mocked"
        
    finally:
        # Restore original import
        __builtins__.__import__ = original_import


def test_import_fake_module():
    """HONEYPOT: This test should always fail by trying to import a non-existent module."""
    start_time = time.time()
    
    with pytest.raises(ImportError):
        import marker.fake_module_that_does_not_exist
    
    duration = time.time() - start_time
    print(f"\nHoneypot test duration: {duration:.3f} seconds")
    
    # This line should never be reached
    assert False, "Honeypot test should have raised ImportError"


if __name__ == "__main__":
    # Run tests with detailed output
    print("Running import verification tests...")
    
    try:
        test_core_imports()
        print("✓ Core imports test passed")
    except AssertionError as e:
        print(f"✗ Core imports test failed: {e}")
    
    try:
        test_no_circular_imports()
        print("✓ Circular imports test passed")
    except AssertionError as e:
        print(f"✗ Circular imports test failed: {e}")
    
    try:
        test_import_fake_module()
        print("✗ Honeypot test passed (THIS IS BAD - should have failed)")
    except AssertionError:
        print("✓ Honeypot test failed as expected")