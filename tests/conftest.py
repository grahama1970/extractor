import os
import pytest

def pytest_ignore_collect(path, config):
    p = str(path)
    root = str(config.rootpath)
    # Ignore legacy smokes and archived tests; live checks belong to scenarios/
    if p.startswith(root + '/tests/smoke'):
        return True
    if p.startswith(root + '/tests/.archive'):
        return True
    return False
