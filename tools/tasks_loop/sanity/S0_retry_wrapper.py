#!/usr/bin/env python3
import sys
import random
import time

def main():
    """
    Simulate a flaky command that fails 66% of the time.
    This is used to verify the retry wrapper in run_pipeline.py.
    """
    # Check if a specific exit code is requested via env var
    # This allows deterministic testing if needed
    
    # Simple probability fail
    if random.random() < 0.66:
        print("❌ Simulating a crash/failure...")
        sys.exit(1)
        
    print("✅ Success! (Simulated)")
    sys.exit(0)

if __name__ == "__main__":
    main()
