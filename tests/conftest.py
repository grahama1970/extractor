import os
import sys
from pathlib import Path
import pytest

# Ensure local 'src' is importable ahead of any installed 'extractor' package
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

def pytest_ignore_collect(path, config):
    p = str(path)
    root = str(config.rootpath)
    # Ignore legacy smokes and archived tests; live checks belong to scenarios/
    if p.startswith(root + '/tests/smoke'):
        return True
    if p.startswith(root + '/tests/.archive'):
        return True
    return False
