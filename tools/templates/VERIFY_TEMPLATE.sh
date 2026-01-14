#!/usr/bin/env bash
set -euo pipefail

# Verifier Template
# Keep this script deterministic and fast.
# The loop will rerun this many times.

# 1) compile / typecheck / lint as needed
python3 -m compileall -q src tools

# 2) run gates
python3 tools/gate_<task_name>.py

# 3) optional extra deterministic checks
# python3 -m pytest -q
# node --version >/dev/null
