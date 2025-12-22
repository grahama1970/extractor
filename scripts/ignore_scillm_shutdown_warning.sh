#!/usr/bin/env bash
# Helper: run a command and suppress the scillm/paved shutdown warning.

set -euo pipefail

cmd=("$@")
"${cmd[@]}" 2> >(grep -v "Task was destroyed but it is pending" >&2)
