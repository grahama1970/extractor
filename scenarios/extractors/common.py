#!/usr/bin/env python3
"""Shared helpers for extractor feature scenarios.

Responsibilities
- Discover sample inputs for each provider/extension
- Run the provider to build a UnifiedDocument
- Optionally insert into ArangoDB when ARANGO_* env is configured
- Emit a compact JSON summary + log path under scripts/artifacts/

Env knobs
- SCENARIOS_ARTIFACT_ROOT: override artifact directory (default scripts/artifacts)
- EXTRACTOR_SAMPLE_DIR: override where to search for inputs (default data/)
- ARANGO_*: if present, we attempt insert into the 'documents' collection
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
import sys
import json
import time
from typing import Dict
import types


# Derive repo root from this file location
ROOT = Path(__file__).resolve().parents[2]
# Ensure local 'src' is importable when running scenarios directly
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def import_provider(module_filename: str, class_name: str):
    """Import a provider module by filename to avoid package __init__ side-effects.

    Example: import_provider('providers/markdown.py', 'MarkdownProvider')
    """
    import importlib.util as ilu

    # Provide a minimal stub for 'pdftext.schema.Reference' if missing,
    # so providers like image.py can import without the heavy dependency.
    if 'pdftext' not in sys.modules:
        pdftext_mod = types.ModuleType('pdftext')
        sys.modules['pdftext'] = pdftext_mod
        schema_mod = types.ModuleType('pdftext.schema')
        class Reference:  # minimal placeholder used for typing only
            def __init__(self, *args, **kwargs):
                pass
        schema_mod.Reference = Reference
        sys.modules['pdftext.schema'] = schema_mod

    mod_path = SRC_PATH / "extractor" / "core" / module_filename
    if not mod_path.exists():
        raise FileNotFoundError(str(mod_path))
    mod_name = f"scenario_{mod_path.stem}"
    spec = ilu.spec_from_file_location(mod_name, str(mod_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {mod_name}")
    module = ilu.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    cls = getattr(module, class_name)
    return cls
ART_ROOT = Path(os.getenv("SCENARIOS_ARTIFACT_ROOT", ROOT / "scripts" / "artifacts"))
ART_ROOT.mkdir(parents=True, exist_ok=True)
SAMPLE_ROOT = Path(os.getenv("EXTRACTOR_SAMPLE_DIR", ROOT / "data"))


def ts() -> str:
    return (
        datetime.utcnow()
        .isoformat(timespec="milliseconds")
        .replace(":", "-")
        .replace(".", "-")
        + "Z"
    )


def find_sample(*patterns: str) -> Optional[Path]:
    """Return the first existing sample path matching any glob under SAMPLE_ROOT.

    Examples
    >>> find_sample("input/2505.03335v2.md", "**/*.md")
    """
    # Prefer exact relative paths first
    for p in patterns:
        candidate = SAMPLE_ROOT / p
        if candidate.exists():
            return candidate
    # Fallback to globs
    for p in patterns:
        for path in SAMPLE_ROOT.glob(p):
            if path.is_file():
                return path
    return None


def arango_env_ready() -> bool:
    # Skip if templated env vars are unresolved
    def _env(name: str) -> Optional[str]:
        v = os.getenv(name)
        return v if v and not v.strip().startswith("${") else None

    url = _env("ARANGO_URL") or (
        (_env("ARANGO_HOST") and _env("ARANGO_PORT")) and "ok" or None
    )
    user = _env("ARANGO_USER") or _env("ARANGO_USERNAME")
    password = _env("ARANGO_PASS") or _env("ARANGO_PASSWORD")
    dbname = _env("ARANGO_DB") or _env("ARANGO_DATABASE")
    return bool(url and user and password and dbname)


@dataclass
class ScenarioResult:
    name: str
    ok: bool
    skipped: bool
    reason: str | None
    input_path: str | None
    provider: str | None
    source_type: str | None
    block_counts: Dict[str, int]
    heading_sample: list[str]
    arango_inserted: bool
    artifacts: Dict[str, str]


def summarise_unified(doc: Any) -> tuple[Dict[str, int], list[str]]:
    """Return simple distribution of block types + first few heading titles."""
    counts: Dict[str, int] = {}
    headings: list[str] = []
    try:
        for b in getattr(doc, "blocks", []) or []:
            t = getattr(b, "type", None)
            key = str(t).split(".")[-1] if t is not None else "Unknown"
            key = key.upper()
            counts[key] = counts.get(key, 0) + 1
            if key == "HEADING":
                title = str(getattr(b, "content", "")).strip()
                if title:
                    headings.append(title)
            if len(headings) >= 10:
                break
    except Exception:  # defensive – scenarios should never crash on summary
        pass
    return counts, headings


def try_arango_insert(doc: Any) -> bool:
    """Insert the UnifiedDocument into ArangoDB 'documents' when configured.

    Returns True on insert success, False on skip/failure.
    """
    if not arango_env_ready():
        logger.info("SKIP arango insert: ARANGO_* not configured")
        return False
    try:
        # Lazy import only when needed to keep scenarios light
        from extractor.core.utils.arango_setup import (
            connect_arango,
            ensure_database,
            ensure_collection,
        )
        from arango.exceptions import ArangoError  # type: ignore

        host = os.getenv("ARANGO_HOST", "localhost")
        port = int(os.getenv("ARANGO_PORT", 8529))
        user = os.getenv("ARANGO_USER", os.getenv("ARANGO_USERNAME", "root"))
        password = os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")
        db_name = os.getenv("ARANGO_DB", os.getenv("ARANGO_DATABASE", "marker"))
        collection = os.getenv("ARANGO_COLLECTION", "documents")

        client = connect_arango(host, port, user, password)
        if not client:
            return False
        db = ensure_database(client, db_name, user, password)
        if not db:
            return False
        ensure_collection(db, collection)

        # Ensure a stable Arango _key for the document
        try:
            src_path = getattr(doc, "source_path", None)
            eq = None
            if isinstance(src_path, str) and src_path:
                try:
                    eq = Path(src_path).stem
                except Exception:
                    eq = src_path
            # ensure_arango_key is a no-op if already set
            if hasattr(doc, "ensure_arango_key"):
                doc.ensure_arango_key(eq)  # type: ignore[attr-defined]
        except Exception:
            pass

        # Prefer using UnifiedDocument.to_arangodb() for a consistent shape
        try:
            payload: Dict[str, Any] = doc.to_arangodb()  # type: ignore[attr-defined]
        except Exception:
            # Fall back to vanilla model dump
            payload = doc.model_dump(by_alias=True, mode="json")  # type: ignore

        # Upsert by _key when available
        key = payload.get("_key") or payload.get("id")
        if key:
            payload.setdefault("_key", str(key))
        col = db.collection(collection)
        if key and col.has(payload["_key"]):
            col.update(payload)
        else:
            col.insert(payload)
        logger.success(f"Inserted document into ArangoDB/{collection}")
        return True
    except Exception as e:  # pragma: no cover – scenarios should never explode
        logger.warning(f"Arango insert skipped/failed: {e}")
        return False


def write_summary(name: str, result: ScenarioResult) -> Path:
    out = ART_ROOT / f"extractor_{name}_{ts()}.json"
    out.write_text(json.dumps(result.__dict__, indent=2))
    return out


def artifacts_root_for_run() -> Path:
    """Hierarchical artifact root including date and a local run id.

    This avoids collisions in CI and keeps artifacts discoverable.
    """
    date_dir = time.strftime("%Y-%m-%d")
    run_id = os.environ.get("GITHUB_SHA", "local")
    p = ART_ROOT / date_dir / run_id / "extractors"
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_unified_snapshot(provider_name: str, doc_id: str, unified_dict: Dict[str, Any]) -> str:
    root = artifacts_root_for_run()
    fname = f"{provider_name}__{doc_id}__unified.json"
    path = root / fname
    path.write_text(json.dumps(unified_dict, indent=2))
    return str(path)
