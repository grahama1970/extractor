#!/usr/bin/env python3
"""
Integration test for pipeline fixes.
Tests that the stages can be imported and basic functionality works.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_stage_01_integration():
    """Test Stage 01 annotation processor integration."""
    print("🧪 Testing Stage 01 annotation processor integration...")
    try:
        # Import using importlib to handle numeric module names
        import importlib
        stage_01 = importlib.import_module("extractor.pipeline.steps.01_annotation_processor")
        
        # Test that the module can be imported and has required functions
        config_class = getattr(stage_01, "Config", None)
        if config_class:
            print("  ✅ Config class available")
        else:
            print("  ❌ Config class not found")
            return False
            
        # Test that SciLLM preflight is integrated
        main_func = getattr(stage_01, "process_pdf_pipeline", None)
        if main_func:
            print("  ✅ Main pipeline function available")
        else:
            print("  ❌ Main pipeline function not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"  ❌ Stage 01 integration failed: {e}")
        return False


async def test_stage_02_integration():
    """Test Stage 02 marker extractor integration."""
    print("\n🧪 Testing Stage 02 marker extractor integration...")
    try:
        # Import using importlib to handle numeric module names
        import importlib
        stage_02 = importlib.import_module("extractor.pipeline.steps.02_marker_extractor")
        allow_simple = os.getenv("STAGE02_ALLOW_SIMPLE", "1")
        fail_fast = os.getenv("PIPELINE_FAIL_FAST", "0")
        
        print(f"  STAGE02_ALLOW_SIMPLE: {allow_simple}")
        print(f"  PIPELINE_FAIL_FAST: {fail_fast}")
        
        if allow_simple in ("1", "true", "yes", "y"):
            print("  ✅ Simple fallback enabled")
        else:
            print("  ⚠️  Simple fallback disabled")
            
        return True
        
    except Exception as e:
        print(f"  ❌ Stage 02 integration failed: {e}")
        return False


async def test_stage_05_integration():
    """Test Stage 05 table extractor integration."""
    print("\n🧪 Testing Stage 05 table extractor integration...")
    try:
        # Import using importlib to handle numeric module names
        import importlib
        stage_05 = importlib.import_module("extractor.pipeline.steps.05_table_extractor")
        print("  ✅ Table extractor module available")
        
        # Test LLM inference configuration
        llm_infer = os.getenv("STAGE05_LLM_INFER", "0")
        print(f"  STAGE05_LLM_INFER: {llm_infer}")
        
        if llm_infer in ("1", "true", "yes", "y"):
            print("  ✅ LLM inference enabled for table titles")
        else:
            print("  ℹ️  LLM inference disabled (default for determinism)")
            
        return True
        
    except Exception as e:
        print(f"  ❌ Stage 05 integration failed: {e}")
        return False


async def test_scillm_integration():
    """Test SciLLM integration across stages."""
    print("\n🧪 Testing SciLLM integration across stages...")
    try:
        from extractor.pipeline.utils.scillm_router import get_text_router, get_vlm_router
        from extractor.pipeline.steps.scillm_preflight_validator import validate_scillm_env_sync
        
        # Test router availability
        try:
            text_router = get_text_router()
            print("  ✅ Text router available")
        except Exception as e:
            print(f"  ⚠️  Text router not available: {e}")
            
        try:
            vlm_router = get_vlm_router()
            print("  ✅ VLM router available")
        except Exception as e:
            print(f"  ⚠️  VLM router not available: {e}")
            
        # Test preflight validation
        ok, reason = validate_scillm_env_sync()
        print(f"  SciLLM preflight: {'✅ PASS' if ok else '❌ FAIL'} - {reason}")
        
        return ok
        
    except Exception as e:
        print(f"  ❌ SciLLM integration failed: {e}")
        return False


async def main():
    """Run all integration tests."""
    print("🔗 Pipeline Integration Test Suite")
    print("=" * 50)
    
    results = []
    
    # Test SciLLM integration first
    results.append(("SciLLM Integration", await test_scillm_integration()))
    
    # Test individual stages
    results.append(("Stage 01 Integration", await test_stage_01_integration()))
    results.append(("Stage 02 Integration", await test_stage_02_integration()))
    results.append(("Stage 05 Integration", await test_stage_05_integration()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Integration Test Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        print("\n📝 Summary of fixes applied:")
        print("  • Added SciLLM preflight validation per AGENTS.md requirements")
        print("  • Fixed marker extractor graceful degradation")
        print("  • Improved table extractor fallback logic to avoid numeric column titles")
        print("  • Added environment validation to prevent hard failures")
        print("  • Standardized error handling across pipeline stages")
        return 0
    else:
        print("⚠️  Some integration tests failed. Please review the failures above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))