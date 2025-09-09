from __future__ import annotations

import os
from pathlib import Path


def load_ls_env(env_file: str = ".env.labelstudio") -> None:
    """Load LS_HOST, LS_REFRESH (and others) from a .env file if present.

    Simple parser: KEY=VALUE per line, ignores comments and blanks.
    Values are not quoted/escaped.
    """
    p = Path(env_file)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k and v and k not in os.environ:
            os.environ[k] = v

