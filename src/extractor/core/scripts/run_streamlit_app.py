"""
Module: run_streamlit_app.py
Description: Functions for run streamlit app operations

External Dependencies:
- None (uses only standard library)

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

import subprocess
import os
import sys


def streamlit_app_cli():
    argv = sys.argv[1:]
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(cur_dir, "streamlit_app.py")
    cmd = ["streamlit", "run", app_path, "--server.fileWatcherType", "none", "--server.headless", "true"]
    if argv:
        cmd += ["--"] + argv
    subprocess.run(cmd, env={**os.environ, "IN_STREAMLIT": "true"})
