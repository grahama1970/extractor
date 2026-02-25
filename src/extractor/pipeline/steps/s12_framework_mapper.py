#!/usr/bin/env python3
"""
Stage-12: Framework Control Mapper — Extract control references from chunks.

Architecture (3-tier, progressively refined):
  Tier 1 — Regex: Wide net, high recall. Catches anything that *looks* like
           a control ID. Intentionally loose. ~1ms/chunk.
  Tier 2 — RapidFuzz: Match regex candidates against the actual sparta_controls
           catalog (7K+ controls). Handles typos, case mismatch, partial IDs.
           ~10ms/chunk.
  Tier 3 — Classifier: (future) Trained from Shadow-LEGO agreement data via
           /create-classifier. Plugged in when training data is sufficient.

Input:
- 10_arangodb_exporter/json_output/10_flattened_data.json

Output:
- 12_framework_mapper/json_output/12_framework_map.json

Side effects:
- Upserts chunk_control_edges in ArangoDB (memory database)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

STEP_NAME = "12_framework_mapper"

# ---------------------------------------------------------------------------
# Requirement detection — RFC 2119 modals + structural heuristics
# ---------------------------------------------------------------------------
_MODAL_PATTERN = re.compile(
    r"\b(shall|must|will|required to|is required)\b", re.IGNORECASE
)
# Asset types that are inherently requirement-like
_REQUIREMENT_ASSET_TYPES = {"Requirement", "Table", "Equation"}


def is_requirement_chunk(item: Dict[str, Any]) -> bool:
    """Determine if a chunk represents a requirement (explicit or implicit).

    A chunk is a requirement if ANY of:
    - asset_type is Requirement, Table, or Equation
    - object_type is Requirement
    - Text contains SHALL/MUST/WILL (RFC 2119 modals)
    - is_table_row flag is set
    - Has a req_id field from s08
    """
    # Structural markers from s08
    asset_type = item.get("asset_type", "") or item.get("object_type", "")
    if asset_type in _REQUIREMENT_ASSET_TYPES:
        return True
    if item.get("is_table_row"):
        return True
    if item.get("req_id"):
        return True

    # Data dict may have nested type info
    data = item.get("data") or {}
    if data.get("type") in _REQUIREMENT_ASSET_TYPES:
        return True
    if data.get("req_id"):
        return True

    # RFC 2119 modal verbs in text
    text = item.get("text_content", "") or item.get("text", "")
    if text and _MODAL_PATTERN.search(text):
        return True

    return False


# ---------------------------------------------------------------------------
# Tier 1: Regex — intentionally WIDE. False positives are expected.
# Tier 2 (rapidfuzz) filters them against the real catalog.
# ---------------------------------------------------------------------------
CANDIDATE_PATTERNS: List[re.Pattern] = [
    # NIST SP 800-53 families: AC-2, AC-2(3), SI-7(1), etc.
    re.compile(r"\b([A-Z]{2}-\d{1,3}(?:\(\d{1,2}\))?)"),
    # CWE: CWE-787, CWE-79, etc.
    re.compile(r"\b(CWE-\d{1,5})\b"),
    # ATT&CK techniques: T1078, T1078.001
    re.compile(r"\b(T\d{4}(?:\.\d{3})?)\b"),
    # SPARTA threats: SV-SP-1, SV-AC-3(2), SV-MA-1
    re.compile(r"\b(SV-[A-Z]{2}-\d+(?:\(\d+\))?)"),
    # SPARTA techniques/tactics: REC-0001, DE-0010.03, ST0001, etc.
    re.compile(r"\b((?:REC|DE|EX|EXF|IMP|PER|LM|RD|IA|ST)\d{4}(?:\.\d{2})?)\b"),
    re.compile(r"\b((?:REC|DE|EX|EXF|IMP|PER|LM|RD)-\d{4}(?:\.\d{2})?)\b"),
    # SPARTA countermeasures: CM0001, CM0008
    re.compile(r"\b(CM\d{4})\b"),
    # D3FEND: D3-SPE, D3-AI, D3-FEVM
    re.compile(r"\b(D3-[A-Z]{2,8})\b"),
    # D3FEND artifacts: d3f:DigitalArtifact (less common in docs but worth catching)
    re.compile(r"\b(d3f:[A-Za-z]+)\b"),
    # ESA: ESA-T2040
    re.compile(r"\b(ESA-[A-Z]\d{4})\b"),
    # ISO controls: A.5.1, A.8.2 (only if preceded by "ISO" context)
    re.compile(r"\b(A\.\d{1,2}\.\d{1,2})\b"),
    # CAPEC: CAPEC-123
    re.compile(r"\b(CAPEC-\d{1,5})\b"),
]

# Minimum rapidfuzz score to accept a match
FUZZ_THRESHOLD = int(os.getenv("FUZZ_THRESHOLD", "85"))
# Score bump for exact matches (skip fuzz entirely)
EXACT_MATCH_CONFIDENCE = 1.0
FUZZ_MATCH_CONFIDENCE_BASE = 0.70


def _edge_key(chunk_key: str, control_key: str) -> str:
    """Deterministic edge key from chunk + control."""
    raw = f"{chunk_key}:{control_key}"
    return hashlib.md5(raw.encode()).hexdigest()


def _context_window(text: str, match_start: int, match_end: int, window: int = 200) -> str:
    """Extract surrounding context around a match."""
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)
    return text[start:end].strip()


# ---------------------------------------------------------------------------
# Control catalog — loaded once from ArangoDB, cached for the run
# ---------------------------------------------------------------------------
class ControlCatalog:
    """In-memory control catalog for Tier 2 matching.

    Loads all control_id → _key mappings from sparta_controls.
    Builds a set for O(1) exact lookups and a list for rapidfuzz matching.
    """

    def __init__(self):
        self._exact: Dict[str, str] = {}       # control_id → _key (case-normalized)
        self._ids: List[str] = []               # all control_ids for fuzz matching
        self._framework: Dict[str, str] = {}    # control_id → source_framework

    def load_from_db(self, db) -> int:
        """Load catalog from ArangoDB. Returns count of controls loaded."""
        try:
            cursor = db.aql.execute(
                "FOR c IN sparta_controls RETURN {k: c._key, id: c.control_id, fw: c.source_framework}",
                batch_size=5000,
            )
            for row in cursor:
                cid = row.get("id")
                if not cid:
                    continue
                key = row.get("k")
                self._exact[cid] = key
                # Also store uppercase for case-insensitive exact match
                self._exact[cid.upper()] = key
                self._ids.append(cid)
                fw = row.get("fw", "")
                if fw:
                    self._framework[cid] = fw
        except Exception as e:
            logger.warning(f"Failed to load control catalog: {e}")
        return len(self._ids)

    def exact_match(self, candidate: str) -> Optional[Tuple[str, str, float]]:
        """Try exact match (case-insensitive). Returns (control_id, _key, confidence) or None."""
        key = self._exact.get(candidate)
        if key:
            return (candidate, key, EXACT_MATCH_CONFIDENCE)
        key = self._exact.get(candidate.upper())
        if key:
            return (candidate.upper(), key, EXACT_MATCH_CONFIDENCE)
        return None

    def fuzzy_match(self, candidate: str, threshold: int = FUZZ_THRESHOLD) -> Optional[Tuple[str, str, float]]:
        """Tier 2: rapidfuzz match against catalog. Returns (control_id, _key, confidence) or None."""
        if not self._ids:
            return None
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            logger.warning("rapidfuzz not installed — skipping fuzzy matching (pip install rapidfuzz)")
            return None

        result = process.extractOne(
            candidate.upper(),
            self._ids,
            scorer=fuzz.ratio,
            score_cutoff=threshold,
        )
        if result is None:
            return None

        matched_id, score, _idx = result
        key = self._exact.get(matched_id)
        if key is None:
            return None

        # Confidence scales linearly from FUZZ_MATCH_CONFIDENCE_BASE at threshold to 0.95 at 100
        confidence = FUZZ_MATCH_CONFIDENCE_BASE + (score - threshold) / (100 - threshold) * 0.25
        return (matched_id, key, min(confidence, 0.95))

    def resolve(self, candidate: str) -> Optional[Tuple[str, str, float, str]]:
        """Resolve a regex candidate to a catalog control.

        Returns (control_id, _key, confidence, method) or None.
        """
        # Try exact first (fast path)
        exact = self.exact_match(candidate)
        if exact:
            cid, key, conf = exact
            return (cid, key, conf, "exact")

        # Try parent for enhancement controls: AC-2(3) → AC-2
        base_id = re.sub(r"\(\d+\)$", "", candidate)
        if base_id != candidate:
            exact = self.exact_match(base_id)
            if exact:
                cid, key, conf = exact
                # Lower confidence — we matched parent, not the specific enhancement
                return (cid, key, conf * 0.85, "parent_exact")

        # Fall back to fuzzy
        fuzzy = self.fuzzy_match(candidate)
        if fuzzy:
            cid, key, conf = fuzzy
            return (cid, key, conf, "fuzzy")

        return None

    def get_framework(self, control_id: str) -> str:
        """Get framework for a control_id."""
        return self._framework.get(control_id, "UNKNOWN")


# ---------------------------------------------------------------------------
# Tier 1: Regex extraction (wide net)
# ---------------------------------------------------------------------------
def extract_candidates(text: str) -> List[Dict[str, Any]]:
    """Tier 1: Extract all candidate control references via regex.

    Intentionally loose — Tier 2 filters false positives.
    Returns list of {candidate, span, context_window}.
    """
    results: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, int]] = set()

    for pattern in CANDIDATE_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1) if match.lastindex else match.group(0)
            candidate = raw.strip()

            dedup_key = (candidate.upper(), match.start())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            results.append({
                "candidate": candidate,
                "span": (match.start(), match.end()),
                "context_window": _context_window(text, match.start(), match.end()),
            })

    return results


# ---------------------------------------------------------------------------
# Edge creation — two types based on whether chunk is a requirement
# ---------------------------------------------------------------------------
def build_chunk_control_edge(
    chunk_key: str,
    control_id: str,
    control_key: str,
    framework: str,
    confidence: float,
    method: str,
    context_window: str,
    now: int,
) -> Dict[str, Any]:
    """Build a chunk_control_edge (evidence: document references a control)."""
    return {
        "_key": _edge_key(chunk_key, control_key),
        "_from": f"datalake_chunks/{chunk_key}",
        "_to": f"sparta_controls/{control_key}",
        "edge_type": "references",
        "control_id": control_id,
        "framework": framework,
        "context_window": context_window[:500],
        "confidence": confidence,
        "extraction_method": method,
        "validated_by": None,
        "created_at": now,
    }


def build_requirement_control_edge(
    chunk_key: str,
    control_id: str,
    control_key: str,
    framework: str,
    confidence: float,
    method: str,
    context_window: str,
    now: int,
) -> Dict[str, Any]:
    """Build a requirement_control_edge (claim: requirement implements a control)."""
    return {
        "_key": _edge_key(chunk_key, control_key),
        "_from": f"datalake_chunks/{chunk_key}",
        "_to": f"sparta_controls/{control_key}",
        "edge_type": "implements",
        "control_id": control_id,
        "framework": framework,
        "context_window": context_window[:500],
        "confidence": confidence,
        "extraction_method": method,
        "lean4_status": "pending",
        "proof_id": None,
        "validated_by": None,
        "created_at": now,
    }


def build_proof_job(
    chunk_key: str,
    control_id: str,
    control_key: str,
    framework: str,
    requirement_text: str,
    now: int,
) -> Dict[str, Any]:
    """Queue a lean4 proof job for a requirement→control pair."""
    job_key = _edge_key(f"proof_{chunk_key}", control_key)
    return {
        "_key": job_key,
        "source_type": "requirement_control",
        "requirement_chunk": f"datalake_chunks/{chunk_key}",
        "control_id": control_id,
        "control_ref": f"sparta_controls/{control_key}",
        "framework": framework,
        "requirement_text": requirement_text[:2000],
        "status": "pending",
        "priority": 1 if framework in ("NIST", "SPARTA") else 2,
        "created_at": now,
        "attempts": 0,
    }


# ---------------------------------------------------------------------------
# ArangoDB connection
# ---------------------------------------------------------------------------
def _get_memory_db():
    """Get memory ArangoDB connection."""
    try:
        from arango import ArangoClient

        hosts = os.getenv("ARANGO_HOST") or os.getenv("ARANGO_URL", "http://localhost:8529")
        if not hosts.startswith("http"):
            hosts = f"http://{hosts}:{os.getenv('ARANGO_PORT', '8529')}"
        db_name = os.getenv("MEMORY_ARANGO_DB") or os.getenv("ARANGO_DB", "memory")
        user = os.getenv("ARANGO_USER", "root")
        password = os.getenv("ARANGO_PASSWORD") or os.getenv("ARANGO_PASS", "openSesame")

        client = ArangoClient(hosts=hosts)
        return client.db(db_name, username=user, password=password)
    except Exception as e:
        logger.warning(f"Cannot connect to memory ArangoDB: {e}")
        return None


# ---------------------------------------------------------------------------
# Pipeline step entry point
# ---------------------------------------------------------------------------
def run(
    pipeline_dir: Path,
    output_dir: Path = None,
    preset_config: dict = None,
    shadow_sample_rate: float = None,
) -> Optional[Path]:
    """Extract framework control references and create chunk→control edges.

    Tier 1 (regex) → Tier 2 (rapidfuzz vs catalog) → edges.
    Tier 3 (classifier) plugs in when training data available.
    """
    if shadow_sample_rate is None:
        shadow_sample_rate = float(os.getenv("SHADOW_SAMPLE_RATE", "0.10"))

    # Find input
    input_path = pipeline_dir / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if not input_path.exists():
        logger.warning(f"Input not found: {input_path}")
        return None

    if output_dir is None:
        output_dir = pipeline_dir / STEP_NAME
    json_out = output_dir / "json_output"
    json_out.mkdir(parents=True, exist_ok=True)

    logger.info(f"[{STEP_NAME}] Loading flattened data from {input_path}")
    data = json.loads(input_path.read_text())

    items = data if isinstance(data, list) else data.get("items", data.get("chunks", []))
    if not items:
        logger.warning(f"[{STEP_NAME}] No items in flattened data")
        return None

    logger.info(f"[{STEP_NAME}] Processing {len(items)} items for control extraction")

    # Load control catalog from ArangoDB
    db = _get_memory_db()
    catalog = ControlCatalog()
    if db is not None:
        n = catalog.load_from_db(db)
        logger.info(f"[{STEP_NAME}] Loaded {n} controls into catalog for matching")

        # Ensure edge collections exist
        for ecoll in ["chunk_control_edges", "requirement_control_edges"]:
            if not db.has_collection(ecoll):
                db.create_collection(ecoll, edge=True)
    else:
        logger.info(f"[{STEP_NAME}] No ArangoDB — regex-only mode (no validation or edges)")

    # Process each chunk: Tier 1 (regex) → Tier 2 (catalog resolve)
    now = int(time.time())
    output_items: List[Dict[str, Any]] = []
    chunk_edge_batch: List[Dict[str, Any]] = []
    req_edge_batch: List[Dict[str, Any]] = []
    proof_job_batch: List[Dict[str, Any]] = []
    total_chunk_edges = 0
    total_req_edges = 0
    total_proof_jobs = 0
    stats = {
        "chunks_processed": 0,
        "chunks_with_candidates": 0,
        "chunks_with_matches": 0,
        "requirement_chunks": 0,
        "total_candidates": 0,
        "exact_matches": 0,
        "parent_exact_matches": 0,
        "fuzzy_matches": 0,
        "unmatched": 0,
        "frameworks": {},
    }

    for item in items:
        chunk_key = item.get("_key", "")
        text = item.get("text_content", "") or item.get("text", "")
        if not text or not chunk_key:
            continue

        stats["chunks_processed"] += 1
        is_req = is_requirement_chunk(item)
        if is_req:
            stats["requirement_chunks"] += 1

        # Tier 1: wide-net regex
        candidates = extract_candidates(text)
        if not candidates:
            continue

        stats["chunks_with_candidates"] += 1
        stats["total_candidates"] += len(candidates)

        # Tier 2: resolve each candidate against catalog
        chunk_has_match = False
        seen_controls: Set[str] = set()  # dedup per chunk

        for cand in candidates:
            resolved = catalog.resolve(cand["candidate"])
            if resolved is None:
                stats["unmatched"] += 1
                continue

            control_id, control_key, confidence, method = resolved

            # Dedup: one edge per (chunk, control) pair
            if control_id in seen_controls:
                continue
            seen_controls.add(control_id)

            chunk_has_match = True
            stats[f"{method}_matches"] = stats.get(f"{method}_matches", 0) + 1

            framework = catalog.get_framework(control_id)
            stats["frameworks"][framework] = stats["frameworks"].get(framework, 0) + 1

            output_items.append({
                "chunk_key": chunk_key,
                "control_id": control_id,
                "control_key": control_key,
                "framework": framework,
                "confidence": round(confidence, 3),
                "method": method,
                "is_requirement": is_req,
                "context_window": cand["context_window"][:500],
                "candidate_raw": cand["candidate"],
            })

            if db is not None:
                # ALWAYS create chunk_control_edge (evidence)
                chunk_edge_batch.append(build_chunk_control_edge(
                    chunk_key, control_id, control_key,
                    framework, confidence, method,
                    cand["context_window"], now,
                ))

                # ALSO create requirement_control_edge + proof_job if requirement
                if is_req:
                    req_edge_batch.append(build_requirement_control_edge(
                        chunk_key, control_id, control_key,
                        framework, confidence, method,
                        cand["context_window"], now,
                    ))
                    proof_job_batch.append(build_proof_job(
                        chunk_key, control_id, control_key,
                        framework, text, now,
                    ))

        if chunk_has_match:
            stats["chunks_with_matches"] += 1

        # Flush chunk_control_edges in batches
        if db is not None and len(chunk_edge_batch) >= 1000:
            try:
                db.collection("chunk_control_edges").import_bulk(
                    chunk_edge_batch, on_duplicate="replace"
                )
                total_chunk_edges += len(chunk_edge_batch)
            except Exception as e:
                logger.warning(f"chunk_control_edges batch failed: {e}")
            chunk_edge_batch = []

        # Flush requirement_control_edges in batches
        if db is not None and len(req_edge_batch) >= 1000:
            try:
                db.collection("requirement_control_edges").import_bulk(
                    req_edge_batch, on_duplicate="replace"
                )
                total_req_edges += len(req_edge_batch)
            except Exception as e:
                logger.warning(f"requirement_control_edges batch failed: {e}")
            req_edge_batch = []

        # Flush proof_jobs in batches
        if db is not None and len(proof_job_batch) >= 500:
            try:
                db.collection("proof_jobs").import_bulk(
                    proof_job_batch, on_duplicate="ignore"
                )
                total_proof_jobs += len(proof_job_batch)
            except Exception as e:
                logger.warning(f"proof_jobs batch failed: {e}")
            proof_job_batch = []

    # Flush remaining batches
    if db is not None:
        for batch, coll, counter_name in [
            (chunk_edge_batch, "chunk_control_edges", "chunk"),
            (req_edge_batch, "requirement_control_edges", "req"),
            (proof_job_batch, "proof_jobs", "proof"),
        ]:
            if batch:
                dup_mode = "ignore" if coll == "proof_jobs" else "replace"
                try:
                    db.collection(coll).import_bulk(batch, on_duplicate=dup_mode)
                    if counter_name == "chunk":
                        total_chunk_edges += len(batch)
                    elif counter_name == "req":
                        total_req_edges += len(batch)
                    else:
                        total_proof_jobs += len(batch)
                except Exception as e:
                    logger.warning(f"Final {coll} batch failed: {e}")

    # Log summary
    logger.info(
        f"[{STEP_NAME}] Done: "
        f"{stats['chunks_with_matches']}/{stats['chunks_processed']} chunks matched, "
        f"{stats['requirement_chunks']} requirement chunks, "
        f"{stats['total_candidates']} candidates → "
        f"{stats['exact_matches']} exact + "
        f"{stats.get('parent_exact_matches', 0)} parent + "
        f"{stats['fuzzy_matches']} fuzzy + "
        f"{stats['unmatched']} unmatched"
    )
    if total_chunk_edges:
        logger.info(f"[{STEP_NAME}] Created {total_chunk_edges} chunk_control_edges (evidence)")
    if total_req_edges:
        logger.info(f"[{STEP_NAME}] Created {total_req_edges} requirement_control_edges (claims)")
    if total_proof_jobs:
        logger.info(f"[{STEP_NAME}] Queued {total_proof_jobs} proof_jobs for lean4")
    for fw, cnt in sorted(stats["frameworks"].items(), key=lambda x: -x[1]):
        logger.info(f"[{STEP_NAME}]   {fw}: {cnt}")

    # Write output
    output_path = json_out / "12_framework_map.json"
    output_data = {
        "step": STEP_NAME,
        "stats": stats,
        "chunk_control_edges_created": total_chunk_edges,
        "requirement_control_edges_created": total_req_edges,
        "proof_jobs_queued": total_proof_jobs,
        "items": output_items,
    }
    output_path.write_text(json.dumps(output_data, indent=2))
    logger.info(f"[{STEP_NAME}] Output: {output_path}")

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract framework control references from chunks")
    parser.add_argument(
        "--input", "-i", type=Path,
        help="Path to 10_flattened_data.json (or pipeline_dir containing it)",
    )
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output directory")
    parser.add_argument(
        "--shadow-sample-rate", type=float, default=0.10,
        help="Fraction of chunks for Shadow-LEGO validation (default: 0.10)",
    )
    parser.add_argument(
        "--fuzz-threshold", type=int, default=None,
        help=f"RapidFuzz score threshold (default: {FUZZ_THRESHOLD})",
    )
    args = parser.parse_args()

    if args.fuzz_threshold is not None:
        os.environ["FUZZ_THRESHOLD"] = str(args.fuzz_threshold)

    input_path = args.input
    if input_path and input_path.is_file():
        pipeline_dir = input_path.parent.parent.parent
    elif input_path:
        pipeline_dir = input_path
    else:
        logger.error("--input is required")
        raise SystemExit(1)

    result = run(
        pipeline_dir=pipeline_dir,
        output_dir=args.output,
        shadow_sample_rate=args.shadow_sample_rate,
    )
    if result:
        logger.info(f"Success: {result}")
    else:
        logger.error("Framework mapping failed")
        raise SystemExit(1)
