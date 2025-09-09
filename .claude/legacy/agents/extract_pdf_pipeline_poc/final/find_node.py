#!/usr/bin/env python3
import os
import subprocess

# Common node locations
locations = [
    "/usr/bin/node",
    "/usr/local/bin/node",
    "/home/graham/.nvm/versions/node/*/bin/node",
    "/home/graham/.local/bin/node",
    "/home/graham/.bun/bin/node",
    "/home/graham/.volta/bin/node",
    "/opt/node/bin/node"
]

print("Searching for node...")
for loc in locations:
    if "*" in loc:
        # Handle wildcards
        import glob
        matches = glob.glob(loc)
        for match in matches:
            if os.path.exists(match):
                print(f"Found: {match}")
    else:
        if os.path.exists(loc):
            print(f"Found: {loc}")

# Also check if bun itself can run JavaScript
print("\nChecking bun:")
bun_path = "/home/graham/.bun/bin/bun"
if os.path.exists(bun_path):
    print(f"Bun exists at: {bun_path}")
    # Try running claude with bun
    result = subprocess.run([bun_path, "/home/graham/.bun/bin/claude", "--help"], 
                          capture_output=True, text=True)
    print(f"Bun claude --help return code: {result.returncode}")
    if result.stdout:
        print(f"Stdout: {result.stdout[:200]}")
    if result.stderr:
        print(f"Stderr: {result.stderr[:200]}")