#!/usr/bin/env bash
set -euo pipefail

python3 -m compileall -q src tools
python3 tools/gate_contacts_cli.py
