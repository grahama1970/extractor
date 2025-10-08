"""
Deterministic / reproducibility mode utilities.

When PIPELINE_DETERMINISTIC=1 (or true/yes), the pipeline should:
- Use stable seeds for random, numpy, (optionally torch if installed)
- Cap opportunistic concurrency where ordering could drift
- Replace UUID/time-based fallbacks with stable hashes or counters
- Expose a simple predicate other modules can consult

This module is intentionally lightweight to avoid circular imports.
"""
from __future__ import annotations
import os
import random
import hashlib

_DET_ENV = {"1", "true", "yes", "on", "y"}


def deterministic_mode() -> bool:
    return os.getenv("PIPELINE_DETERMINISTIC", "0").lower() in _DET_ENV


def init_deterministic_seeds(extra_entropy: str | None = None) -> None:
    """
    Idempotently seed RNG sources. Safe to call multiple times.
    If extra_entropy provided, fold it into the seed hash for
    stable but distinct seed spaces across logical domains.
    """
    if not deterministic_mode():
        return
    basis = "pipeline_deterministic_seed"
    if extra_entropy:
        basis += f":{extra_entropy}"
    seed_int = int(hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12], 16) % (2**32)
    try:
        random.seed(seed_int)
    except Exception:
        pass
    try:
        import numpy as np  # type: ignore

        np.random.seed(seed_int % (2**32 - 1))
    except Exception:
        pass
    try:
        import torch  # type: ignore

        if hasattr(torch, "manual_seed"):
            torch.manual_seed(seed_int)
    except Exception:
        pass

