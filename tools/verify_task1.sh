#!/usr/bin/env bash
set -euo pipefail

python3 -m compileall -q src
python3 tools/gate_normalize_contacts.py
