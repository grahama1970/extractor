#!/usr/bin/env python3
"""
Stage-10: ArangoDB Exporter — Sync Extracted Knowledge Graph.

Purpose:
- Reads the finalized `assembled_content.json` (Documents, Sections, Requirements).
- ALWAYS produces `10_flattened_data.json` for downstream composability (QRA, etc.)
- OPTIONALLY upserts nodes and edges into an ArangoDB Graph if credentials available.

Output (always produced):
- `10_arangodb_exporter/json_output/10_flattened_data.json` - Canonical flattened format

Schema (ArangoDB, optional):
- Nodes:
    - `documents`
    - `sections`
    - `requirements`
- Edges:
    - `has_section` (Document -> Section)
    - `has_requirement` (Section -> Requirement)

Configuration:
- Env vars: ARANGO_HOST, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD
- If not set, JSON is still produced but ArangoDB sync is skipped.
"""

import os
import re
import sys
import json
from typing import Any, Dict, Optional

import hashlib
from pathlib import Path
from loguru import logger
from rich.console import Console
from arango import ArangoClient
from extractor.pipeline.utils.step_sanity import run_step_sanity

# Initialize
console = Console()
STEP_NAME = "10_arangodb_exporter"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


def get_arango_client(db_name_alt: Optional[str] = None):
    # Support both ARANGO_HOST (code convention) and ARANGO_URL (shell convention)
    hosts = os.getenv("ARANGO_HOST") or os.getenv("ARANGO_URL", "http://localhost:8529")
    if not hosts.startswith("http"):
        hosts = f"http://{hosts}:{os.getenv('ARANGO_PORT', '8529')}"
    db_name = db_name_alt or os.getenv("ARANGO_DB", "extractor_graph")
    user = os.getenv("ARANGO_USER", "root")
    # Support both ARANGO_PASSWORD (code convention) and ARANGO_PASS (shell convention)
    password = os.getenv("ARANGO_PASSWORD") or os.getenv("ARANGO_PASS", "openSesame")

    client = ArangoClient(hosts=hosts)
    sys_db = client.db("_system", username=user, password=password)

    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)

    return client.db(db_name, username=user, password=password)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings from the standalone embedding service."""
    service_url = os.getenv("EMBEDDING_SERVICE_URL", "http://127.0.0.1:8602")
    try:
        import requests
        resp = requests.post(
            f"{service_url}/embed/batch",
            json={"texts": texts},
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()["vectors"]
    except Exception as e:
        logger.warning(f"Embedding service failed: {e}. Falling back to zero vectors.")
        # Fallback to zero vectors of size 384 (all-MiniLM-L6-v2 size)
        return [[0.0] * 384 for _ in texts]


def get_taxonomy_tags(texts_by_key: dict) -> dict:
    """Extract taxonomy bridge+collection tags per chunk using keyword-fast mode.

    Tries to import common.taxonomy from pi-mono skills for in-process speed.
    Falls back gracefully if unavailable — taxonomy is enrichment, not critical path.
    """
    pi_mono_skills = Path(os.path.expanduser("~/workspace/experiments/pi-mono/.pi/skills"))
    added = False
    if str(pi_mono_skills) not in sys.path:
        sys.path.insert(0, str(pi_mono_skills))
        added = True

    results = {}
    try:
        from common.taxonomy import extract_taxonomy_features, ContentType

        for key, text in texts_by_key.items():
            if not text or not text.strip():
                continue
            try:
                features = extract_taxonomy_features(
                    content_type=ContentType.OPERATIONAL,
                    title="",
                    description=text[:2000],
                    tags=[],
                    high_fidelity=False,  # Keyword-only, ~10ms per call
                )
                results[key] = {
                    "bridge_tags": features.get("bridge_attributes", []),
                    "collection_tags": features.get("collection_tags", {}),
                }
            except Exception:
                continue
    except ImportError:
        logger.info("Taxonomy extraction unavailable (common.taxonomy not found); skipping tags")
    finally:
        if added and str(pi_mono_skills) in sys.path:
            sys.path.remove(str(pi_mono_skills))

    return results


def ensure_datalake_collections(db):
    """Ensure datalake and codebase collections exist for unified search."""
    for col in ["datalake_docs", "datalake_chunks", "codebase_docs", "codebase_chunks"]:
        if not db.has_collection(col):
            db.create_collection(col)

    for edge_col in ["datalake_edges", "codebase_edges"]:
        if not db.has_collection(edge_col, edge=True):
            db.create_collection(edge_col, edge=True)


def ensure_sparta_collections(db):
    """Ensure sparta collections exist for actual SPARTA control text."""
    for col in ["sparta_chunks"]:
        if not db.has_collection(col):
            db.create_collection(col)
    for edge_col in ["sparta_edges"]:
        if not db.has_collection(edge_col, edge=True):
            db.create_collection(edge_col, edge=True)


def ensure_unified_memory_view(db):
    """Initialize or update a unified ArangoSearch view for all memory data sources."""
    view_name = "memory_unified_search"
    
    datalake_link = {
        "analyzers": ["text_en", "identity"],
        "fields": {
            "text": {"analyzers": ["text_en"]},
            "embedding": {"analyzers": ["identity"]},
            "bridge_tags": {"analyzers": ["identity"]},
            "taxonomy": {"analyzers": ["identity"]},
            "asset_type": {"analyzers": ["identity"]},
        },
        "includeAllFields": True,
        "storeValues": "id",
    }

    datalake_doc_link = {
        "analyzers": ["text_en", "identity"],
        "fields": {
            "source": {"analyzers": ["text_en", "identity"]},
            "domain": {"analyzers": ["identity"]},
            "detected_preset": {"analyzers": ["identity"]},
            "page_count": {"analyzers": ["identity"]},
            "table_count": {"analyzers": ["identity"]},
            "table_pages": {"analyzers": ["identity"]},
            "has_tables": {"analyzers": ["identity"]},
            "has_figures": {"analyzers": ["identity"]},
            "has_formulas": {"analyzers": ["identity"]},
            "has_requirements": {"analyzers": ["identity"]},
            "section_estimate": {"analyzers": ["identity"]},
            "layout_columns": {"analyzers": ["identity"]},
            "file_size_mb": {"analyzers": ["identity"]},
            "image_pages": {"analyzers": ["identity"]},
            # Document lineage — enables cross-version queries
            "document_family": {"analyzers": ["text_en", "identity"]},
            "revision": {"analyzers": ["identity"]},
            "revision_date": {"analyzers": ["identity"]},
        },
        "includeAllFields": True,
        "storeValues": "id",
    }

    properties = {
        "links": {
            "horus_lore_chunks": {
                "analyzers": ["text_en", "identity"],
                "fields": {
                    "text": {"analyzers": ["text_en"]},
                    "embedding": {"analyzers": ["identity"]},
                },
                "includeAllFields": True,
                "storeValues": "id",
            },
            "datalake_chunks": datalake_link,
            "datalake_docs": datalake_doc_link,
            "codebase_chunks": {
                "analyzers": ["text_en", "identity"],
                "fields": {
                    "text": {"analyzers": ["text_en"]},
                    "embedding": {"analyzers": ["identity"]},
                },
                "includeAllFields": True,
                "storeValues": "id",
            }
        }
    }

    if db.has_view(view_name):
        view = db.view(view_name)
        view.update_properties(properties)
        logger.info(f"Updated ArangoSearch view: {view_name} (Priority: Horus > Datalake > Codebase)")
    else:
        db.create_arangosearch_view(name=view_name, properties=properties)
        logger.info(f"Created Unified ArangoSearch view: {view_name}")

    # Dedicated datalake_chunks_search view for recall source
    dl_view_name = "datalake_chunks_search"
    dl_props = {"links": {"datalake_chunks": datalake_link}}
    if db.has_view(dl_view_name):
        db.view(dl_view_name).update_properties(dl_props)
        logger.info(f"Updated ArangoSearch view: {dl_view_name}")
    else:
        db.create_arangosearch_view(name=dl_view_name, properties=dl_props)
        logger.info(f"Created ArangoSearch view: {dl_view_name}")


def _extract_lineage(filename: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Extract document lineage metadata from filename and S00 profile.

    Parses standard document naming patterns to identify document family,
    revision, and revision date.  This enables Jennifer (NiWAC persona) to
    diff engineering deltas across document revisions in the graph.

    Recognised patterns (case-insensitive):
      MIL-STD-810H          → family=MIL-STD-810, revision=H
      DO-178C               → family=DO-178, revision=C
      AS9100 Rev D          → family=AS9100, revision=D
      RTCA_DO-160G_2010     → family=RTCA_DO-160, revision=G, date=2010
      SAE_ARP4754B_Rev1     → family=SAE_ARP4754B, revision=1
      AMS2759_Rev_F_2014    → family=AMS2759, revision=F, date=2014
      somefile_v2.3.pdf     → family=somefile, revision=2.3
    """
    lineage: Dict[str, Any] = {
        "document_family": None,
        "revision": None,
        "revision_date": None,
    }

    stem = Path(filename).stem if filename else ""
    if not stem:
        return lineage

    # --- Try structured patterns first (most specific → least) ---

    # Pattern 1: MIL-STD / DO / ARP style with trailing letter revision
    #   e.g. MIL-STD-810H, MIL-HDBK-217F, DO-178C, DO-160G
    m = re.match(
        r"^((?:MIL|DO|ARP|AS|RTCA|SAE|AMS|ASTM|IEEE|ISO|IEC|ANSI|NIST|FAA|NASA|ECSS)"
        r"[-_][\w-]+?)([A-Z])(?:[-_](\d{4}))?$",
        stem, re.IGNORECASE,
    )
    if m:
        lineage["document_family"] = m.group(1).upper()
        lineage["revision"] = m.group(2).upper()
        if m.group(3):
            lineage["revision_date"] = m.group(3)
        return lineage

    # Pattern 2: Explicit "Rev" marker — e.g. AS9100_Rev_D, AMS2759_Rev_F_2014
    m = re.search(
        r"^(.+?)[-_ ]+[Rr][Ee][Vv][-_ ]*([A-Za-z0-9.]+)(?:[-_ ]+(\d{4}))?",
        stem,
    )
    if m:
        lineage["document_family"] = m.group(1).strip("-_ ")
        lineage["revision"] = m.group(2)
        if m.group(3):
            lineage["revision_date"] = m.group(3)
        return lineage

    # Pattern 3: Version suffix — e.g. spec_v2.3, design_V4
    m = re.search(r"^(.+?)[-_ ]+[Vv](\d[\d.]*)$", stem)
    if m:
        lineage["document_family"] = m.group(1).strip("-_ ")
        lineage["revision"] = m.group(2)
        return lineage

    # Pattern 4: Trailing year — e.g. RTCA_DO-160_2010
    m = re.search(r"^(.+?)[-_ ]+(\d{4})$", stem)
    if m and 1950 <= int(m.group(2)) <= 2099:
        lineage["document_family"] = m.group(1).strip("-_ ")
        lineage["revision_date"] = m.group(2)
        return lineage

    # Fallback: use stem as family, no revision detected
    lineage["document_family"] = stem

    # Overlay anything S00 profile may already provide
    for key in ("document_family", "revision", "revision_date"):
        val = profile.get(key)
        if val and not lineage[key]:
            lineage[key] = val

    return lineage


def sync_to_datalake(doc_node: Dict[str, Any], flattened_data: list, doc_key: str):
    """
    Sync all extracted assets to the Datalake Knowledge Graph in the memory database.
    Enables unified search (BM25 + Semantic + Graph).
    """
    mem_db_name = os.getenv("MEMORY_ARANGO_DB", "memory")
    try:
        mem_adb = get_arango_client(db_name_alt=mem_db_name)
    except Exception as e:
        logger.warning(f"Could not connect to memory database '{mem_db_name}': {e}")
        return

    # Ensure collections and views
    ensure_datalake_collections(mem_adb)
    ensure_unified_memory_view(mem_adb)

    # 1. Sync Document (with S00 profile metadata for structured queries)
    doc_id = doc_node["_key"]
    profile = doc_node.get("profile", {})
    mem_doc = {
        "_key": doc_id,
        "source": doc_node.get("filename", "unknown"),
        "path": doc_node.get("path"),
        "full_text": "",  # Aggregated later if needed
        "entities": [],
        "source_meta": {
            "title": doc_node.get("filename"),
            "hash": doc_key,
            "ingested_at": doc_node.get("ingested_at")
        },
        "content_type": "canon",
        # S00 profile metadata — enables structured queries like
        # "find PDFs with >10 tables about aerospace tolerances"
        "page_count": profile.get("page_count", 0),
        "domain": profile.get("domain", "unknown"),
        "file_size_mb": profile.get("file_size_mb", 0),
        "table_count": profile.get("table_count", 0),
        "table_pages": profile.get("table_pages", 0),
        "has_tables": profile.get("has_tables", False),
        "has_figures": profile.get("has_figures", False),
        "image_pages": profile.get("image_pages", 0),
        "has_formulas": profile.get("has_formulas", False),
        "has_requirements": profile.get("has_requirements", False),
        "section_estimate": profile.get("section_estimate", 0),
        "layout_columns": profile.get("layout_columns", 1),
        "detected_preset": profile.get("detected_preset", ""),
    }

    # Document lineage — enables cross-version diffing in the graph
    lineage = _extract_lineage(doc_node.get("filename", ""), profile)
    mem_doc["document_family"] = lineage["document_family"]
    mem_doc["revision"] = lineage["revision"]
    mem_doc["revision_date"] = lineage["revision_date"]

    mem_adb.collection("datalake_docs").insert(mem_doc, overwrite=True)

    # 2. Sync Assets as Chunks
    chunks = []
    logger.info(f"Generating embeddings for {len(flattened_data)} assets...")

    # Batch embeddings
    texts_to_embed = [item["text_content"] for item in flattened_data]
    # Filter out empty texts to avoid service errors, but preserve index alignment
    valid_indices = [i for i, t in enumerate(texts_to_embed) if t and t.strip()]
    valid_texts = [texts_to_embed[i] for i in valid_indices]

    vectors = []
    if valid_texts:
        vectors = get_embeddings(valid_texts)
        if len(vectors) != len(valid_texts):
            logger.warning(f"Embedding count mismatch: got {len(vectors)} for {len(valid_texts)} texts")

    # Map original flattened_data index → embedding vector
    vector_map = {}
    for j, orig_idx in enumerate(valid_indices):
        if j < len(vectors):
            vector_map[orig_idx] = vectors[j]

    # Extract taxonomy tags per chunk (keyword-fast mode, ~10ms each)
    taxonomy_input = {}
    for i, item in enumerate(flattened_data):
        chunk_key = hashlib.md5(f"{doc_key}_{item['_key']}_datalake".encode()).hexdigest()
        text = item.get("text_content", "")
        if text and text.strip():
            taxonomy_input[chunk_key] = text
    taxonomy_tags = get_taxonomy_tags(taxonomy_input)
    if taxonomy_tags:
        logger.info(f"Extracted taxonomy tags for {len(taxonomy_tags)}/{len(flattened_data)} chunks")

    for i, item in enumerate(flattened_data):
        chunk_key = hashlib.md5(f"{doc_key}_{item['_key']}_datalake".encode()).hexdigest()
        tags = taxonomy_tags.get(chunk_key, {})

        chunk_node = {
            "_key": chunk_key,
            "doc_id": doc_id,
            "text": item["text_content"],
            "embedding": vector_map.get(i, [0.0] * 384),
            "asset_type": item["object_type"],
            "source": mem_doc["source"],
            "source_meta": {
                **item.get("data", {}),
                "page": item.get("page_num", 0),
                "section_id": item.get("section_id"),
                "section_title": item.get("section_title", ""),
            },
            "content_type": "canon",
            "bridge_tags": tags.get("bridge_tags", []),
            "taxonomy": tags.get("collection_tags", {}),
        }
        chunks.append(chunk_node)

    if chunks:
        logger.info(f"Syncing {len(chunks)} assets to 'datalake_chunks'...")
        mem_adb.collection("datalake_chunks").import_bulk(chunks, on_duplicate="replace")

        # 3. Create Edges
        edges = []
        for chunk in chunks:
            # Document -> Chunk
            edges.append({
                "_from": f"datalake_docs/{doc_id}",
                "_to": f"datalake_chunks/{chunk['_key']}",
                "type": "has_asset",
                "asset_type": chunk["asset_type"]
            })

        if edges:
            mem_adb.collection("datalake_edges").import_bulk(edges, on_duplicate="replace")

    # 4. Ingest Sparta README as Control Text (Special Case — stays in sparta_chunks)
    ensure_sparta_collections(mem_adb)
    sync_sparta_readme(mem_adb, doc_id)

    logger.success(f"Datalake Knowledge Graph Sync Complete: {len(chunks)} assets in '{mem_db_name}'")


def sync_to_codebase(pipeline_dir: Path):
    """Sync the extractor codebase itself as a data source."""
    mem_db_name = os.getenv("MEMORY_ARANGO_DB", "memory")
    try:
        mem_adb = get_arango_client(db_name_alt=mem_db_name)
    except Exception:
        return

    # Use the absolute root defined at module level if available, otherwise detect
    extractor_root = Path(os.getenv("EXTRACTOR_ROOT", str(pipeline_dir.parents[2])))
    if not (extractor_root / "src").exists():
        logger.warning(f"Codebase sync: src not found in {extractor_root}")
        return

    logger.info(f"Syncing codebase from {extractor_root}")
    
    # Filter files and read safely
    code_files = []
    for f in extractor_root.rglob("*.py"):
        # Skip common non-source dirs
        if any(p in f.parts for p in [".venv", "venv", "__pycache__", "build", "dist"]):
            continue
        code_files.append(f)
    
    doc_id = "extractor_codebase"
    mem_doc = {
        "_key": doc_id,
        "source": "extractor-codebase",
        "path": str(extractor_root),
        "content_type": "code"
    }
    chunks = []
    # Index up to 100 source files for broad context
    code_files_to_sync = code_files[:100]
    
    # Pre-collect texts to embed in batch
    texts_to_embed = []
    file_metadata = []
    
    for f in code_files_to_sync:
        try:
            path_rel = f.relative_to(extractor_root)
            if f.stat().st_size > 1_000_000: continue
            
            content = f.read_text(encoding="utf-8")
            if not content.strip(): continue
            
            texts_to_embed.append(content[:1000])
            file_metadata.append((path_rel, content))
        except Exception:
            continue
            
    if not texts_to_embed:
        return

    logger.info(f"Batch embedding {len(texts_to_embed)} codebase files...")
    vectors = get_embeddings(texts_to_embed)
    
    for i, (path_rel, content) in enumerate(file_metadata):
        chunk_key = hashlib.md5(f"code_{path_rel}".encode()).hexdigest()
        
        chunks.append({
            "_key": chunk_key,
            "doc_id": doc_id,
            "text": f"File: {path_rel}\n\n{content[:5000]}",
            "embedding": vectors[i],
            "asset_type": "SourceCode",
            "source": str(path_rel),
            "content_type": "code"
        })
    
    if chunks:
        logger.info(f"Syncing {len(chunks)} codebase files to memory.")
        mem_adb.collection("codebase_chunks").import_bulk(chunks, on_duplicate="replace")


def sync_sparta_readme(mem_adb, doc_id: str):
    """Ingest Sparta project README as a control text chunk."""
    # Find sparta README relative to extractor or via env
    sparta_root = Path(os.getenv("SPARTA_ROOT", str(Path(__file__).parents[4] / "sparta")))
    readme_path = sparta_root / "README.md"
    
    if not readme_path.exists():
        logger.warning(f"Sparta README not found at {readme_path}")
        return

    try:
        content = readme_path.read_text(encoding="utf-8")
        chunk_key = "sparta_readme_control"
        vector = get_embeddings([content])[0]
        
        readme_chunk = {
            "_key": chunk_key,
            "doc_id": doc_id,
            "text": content,
            "embedding": vector,
            "asset_type": "ControlText",
            "source": "sparta/README.md",
            "content_type": "control"
        }
        mem_adb.collection("sparta_chunks").insert(readme_chunk, overwrite=True)
        
        mem_adb.collection("sparta_edges").insert({
            "_from": f"datalake_docs/{doc_id}",
            "_to": f"sparta_chunks/{chunk_key}",
            "type": "has_control_text"
        }, overwrite=True)
        logger.info("Ingested Sparta README as Control Text.")
    except Exception as e:
        logger.warning(f"Could not ingest Sparta README: {e}")


def ensure_collections(db):
    # Vertices
    for col in ["documents", "sections", "requirements", "tables", "figures", "equations"]:
        if not db.has_collection(col):
            db.create_collection(col)

    # Edges
    for edge in ["has_section", "has_requirement", "has_table", "has_figure", "has_equation"]:
        if not db.has_collection(edge):
            db.create_collection(edge, edge=True)


def build_flattened_data(repo, pipeline_dir: Path) -> list:
    """Build flattened data from ContentRepository for JSON export and downstream skills (QRA, etc.)."""
    flattened = []

    doc_name = pipeline_dir.name
    doc_hash = hashlib.md5(doc_name.encode()).hexdigest()
    doc_key = f"doc_{doc_hash}"

    # Build section_id → section_title lookup for non-text elements
    section_title_map = {s.get("id", ""): s.get("title", "") for s in repo.sections}

    # Get sections with aggregated block text and bounding box envelope
    # Group blocks by section_id for text aggregation (replaces STRING_AGG)
    from collections import defaultdict
    blocks_by_section = defaultdict(list)
    for b in repo.blocks:
        sid = b.get("section_id")
        if sid:
            blocks_by_section[sid].append(b)

    for sec in repo.sections:
        s_id = sec.get("id", "")
        title = sec.get("title", "")
        p_start = sec.get("page_start", 0)
        p_id = sec.get("parent_id")

        sec_blocks = sorted(
            blocks_by_section.get(s_id, []),
            key=lambda b: (b.get("page", 0), b.get("y0", 0)),
        )
        content = " ".join(b.get("text", "") for b in sec_blocks if b.get("text"))

        # Compute bounding box envelope
        min_x0 = min((b.get("x0", 0) for b in sec_blocks if b.get("x0") is not None), default=None)
        min_y0 = min((b.get("y0", 0) for b in sec_blocks if b.get("y0") is not None), default=None)
        max_x1 = max((b.get("x1", 0) for b in sec_blocks if b.get("x1") is not None), default=None)
        max_y1 = max((b.get("y1", 0) for b in sec_blocks if b.get("y1") is not None), default=None)
        sec_bbox = [min_x0, min_y0, max_x1, max_y1] if min_x0 is not None else None

        sec_key = hashlib.md5(f"{doc_key}_{s_id}".encode()).hexdigest()
        entry = {
            "_key": sec_key,
            "source_pdf": str(pipeline_dir),
            "object_type": "Text",
            "text_content": content or "",
            "section_id": s_id,
            "section_title": title or "",
            "section_level": 0,
            "page_num": p_start or 0,
            "data": {"text": content or "", "bbox": sec_bbox},
        }
        flattened.append(entry)

    # Get tables
    for tbl in repo.tables:
        t_id = tbl.get("id", "")
        section_id = tbl.get("section_id", "")
        tbl_key = hashlib.md5(f"{doc_key}_table_{t_id}".encode()).hexdigest()
        title = tbl.get("llm_title") or tbl.get("llm_description") or "Untitled"
        html_data = tbl.get("html_data", "")
        x0, y0, x1, y1 = tbl.get("x0"), tbl.get("y0"), tbl.get("x1"), tbl.get("y1")

        entry = {
            "_key": tbl_key,
            "source_pdf": str(pipeline_dir),
            "object_type": "Table",
            "text_content": f"Table: {title}\n{html_data or ''}",
            "section_id": section_id,
            "section_title": section_title_map.get(section_id, ""),
            "page_num": tbl.get("page", 0),
            "data": {
                "table_id": t_id,
                "caption": title,
                "html": html_data,
                "image_path": tbl.get("image_path"),
                "bbox": [x0, y0, x1, y1] if x0 is not None else None,
            },
        }
        flattened.append(entry)

    # Get figures
    for fig in repo.figures:
        f_id = fig.get("id", "")
        section_id = fig.get("section_id", "")
        fig_key = hashlib.md5(f"{doc_key}_figure_{f_id}".encode()).hexdigest()
        title = fig.get("llm_title") or fig.get("llm_description") or "Untitled"
        x0, y0, x1, y1 = fig.get("x0"), fig.get("y0"), fig.get("x1"), fig.get("y1")

        entry = {
            "_key": fig_key,
            "source_pdf": str(pipeline_dir),
            "object_type": "Figure",
            "text_content": f"Figure: {title}",
            "section_id": section_id,
            "section_title": section_title_map.get(section_id, ""),
            "page_num": fig.get("page", 0),
            "data": {
                "figure_id": f_id,
                "caption": title,
                "image_path": fig.get("image_path"),
                "bbox": [x0, y0, x1, y1] if x0 is not None else None,
            },
        }
        flattened.append(entry)

    # Get requirements
    for req in repo.requirements:
        r_id = req.get("req_id", req.get("id", ""))
        s_id = req.get("section_id", "")
        text = req.get("text", "")
        r_type = req.get("type", "")
        conf = req.get("confidence")
        citation = req.get("citation_snippet", "")
        page = req.get("page", 0)
        meta_json = req.get("metadata_json")

        req_bbox = None
        if meta_json:
            try:
                meta = json.loads(meta_json) if isinstance(meta_json, str) else meta_json
                req_bbox = meta.get("bbox")
            except (json.JSONDecodeError, TypeError):
                pass

        entry = {
            "_key": r_id,
            "source_pdf": str(pipeline_dir),
            "object_type": "Requirement",
            "text_content": text or "",
            "section_id": s_id,
            "section_title": section_title_map.get(s_id, ""),
            "page_num": page or 0,
            "data": {
                "req_id": r_id,
                "type": r_type,
                "confidence": conf,
                "citation": citation,
                "bbox": req_bbox,
            },
        }
        flattened.append(entry)

    # Get equations (from blocks where is_equation=True)
    for b in repo.blocks:
        if not b.get("is_equation"):
            continue
        b_id = b.get("id", "")
        s_id = b.get("section_id", "")
        latex = b.get("latex_content", "")
        x0, y0, x1, y1 = b.get("x0"), b.get("y0"), b.get("x1"), b.get("y1")
        eq_key = hashlib.md5(f"{doc_key}_eq_{b_id}".encode()).hexdigest()

        entry = {
            "_key": eq_key,
            "source_pdf": str(pipeline_dir),
            "object_type": "Equation",
            "text_content": latex or "",
            "section_id": s_id,
            "section_title": section_title_map.get(s_id, ""),
            "page_num": b.get("page", 0),
            "data": {
                "block_id": b_id,
                "latex": latex,
                "bbox": [x0, y0, x1, y1] if x0 is not None else None,
            },
        }
        flattened.append(entry)

    return flattened


def run(
    input_path: Path,
    output_dir: Path = None,
    preset_config: Optional[Dict[str, Any]] = None,
):
    """Stage 10: Export to JSON (always) and ArangoDB (optional).

    This stage ALWAYS produces 10_flattened_data.json for downstream composability
    with skills like QRA. ArangoDB sync is optional based on credentials.
    """
    pipeline_dir = input_path.parent.parent if input_path.is_file() else input_path

    # Find assembled content
    data_path = pipeline_dir / "07_assembled" / "assembled_content.json"
    if not data_path.exists():
        logger.error(f"assembled_content.json not found at {data_path}. Cannot export.")
        return

    # Setup output directory
    if output_dir is None:
        output_dir = pipeline_dir / STEP_NAME
    output_dir = Path(output_dir)
    json_output_dir = output_dir / "json_output"
    json_output_dir.mkdir(parents=True, exist_ok=True)

    # 1. ALWAYS build and write flattened JSON (for QRA and other downstream skills)
    from extractor.pipeline.utils.content_query import ContentRepository
    repo = ContentRepository(data_path)

    flattened = build_flattened_data(repo, pipeline_dir)

    json_path = json_output_dir / "10_flattened_data.json"
    json_path.write_text(json.dumps(flattened, indent=2, default=str))
    logger.info(f"Wrote {len(flattened)} entries to {json_path}")

    # 2. OPTIONALLY sync to ArangoDB if credentials available
    # Support both naming conventions: ARANGO_HOST/ARANGO_URL, ARANGO_PASSWORD/ARANGO_PASS
    arango_available = (
        os.getenv("ARANGO_HOST") or os.getenv("ARANGO_URL")
        or os.getenv("ARANGO_PASSWORD") or os.getenv("ARANGO_PASS")
    )

    if not arango_available:
        logger.info("ArangoDB credentials not set. JSON exported, skipping graph sync.")
        return json_path

    try:
        logger.info(f"Connecting to ArangoDB at {os.getenv('ARANGO_HOST', 'localhost')}...")
        adb = get_arango_client()
        ensure_collections(adb)
    except Exception as e:
        logger.warning(f"Failed to connect to ArangoDB: {e}. JSON was still exported.")
        return json_path

    from collections import defaultdict

    doc_name = pipeline_dir.name
    doc_hash = hashlib.md5(doc_name.encode()).hexdigest()
    doc_key = f"doc_{doc_hash}"

    # Upsert document
    doc_meta = {
        "_key": doc_key,
        "filename": doc_name,
        "path": str(pipeline_dir),
    }
    adb.collection("documents").insert(doc_meta, overwrite=True)
    logger.info(f"Upserted Document: {doc_name}")

    # Build blocks-by-section for content aggregation
    blocks_by_section = defaultdict(list)
    for b in repo.blocks:
        sid = b.get("section_id")
        if sid:
            blocks_by_section[sid].append(b)

    # Sync sections
    if repo.sections:
        logger.info(f"Syncing {len(repo.sections)} sections (with content) to ArangoDB...")

        for sec in repo.sections:
            s_id = sec.get("id", "")
            title = sec.get("title", "")
            p_start = sec.get("page_start", 0)
            p_id = sec.get("parent_id")

            sec_blocks = sorted(
                blocks_by_section.get(s_id, []),
                key=lambda b: (b.get("page", 0), b.get("y0", 0)),
            )
            content = " ".join(b.get("text", "") for b in sec_blocks if b.get("text"))

            sec_key = hashlib.md5(f"{doc_key}_{s_id}".encode()).hexdigest()

            sec_node = {
                "_key": sec_key,
                "original_id": s_id,
                "title": title,
                "page_start": p_start,
                "content": content,
            }
            adb.collection("sections").insert(sec_node, overwrite=True)

            adb.collection("has_section").insert(
                {
                    "_from": f"documents/{doc_key}",
                    "_to": f"sections/{sec_key}",
                    "type": "contains",
                },
                overwrite=True,
            )

            if p_id:
                parent_key = hashlib.md5(f"{doc_key}_{p_id}".encode()).hexdigest()
                adb.collection("has_section").insert(
                    {
                        "_from": f"sections/{parent_key}",
                        "_to": f"sections/{sec_key}",
                        "type": "sub_section",
                    },
                    overwrite=True,
                )

    # Sync tables
    for tbl in repo.tables:
        t_id = tbl.get("id", "")
        s_id = tbl.get("section_id", "")
        tbl_key = hashlib.md5(f"{doc_key}_table_{t_id}".encode()).hexdigest()
        if s_id:
            sec_key = hashlib.md5(f"{doc_key}_{s_id}".encode()).hexdigest()
            adb.collection("has_table").insert(
                {"_from": f"sections/{sec_key}", "_to": f"tables/{tbl_key}"},
                overwrite=True,
            )

    # Sync figures
    for fig in repo.figures:
        f_id = fig.get("id", "")
        s_id = fig.get("section_id", "")
        fig_key = hashlib.md5(f"{doc_key}_figure_{f_id}".encode()).hexdigest()
        if s_id:
            sec_key = hashlib.md5(f"{doc_key}_{s_id}".encode()).hexdigest()
            adb.collection("has_figure").insert(
                {"_from": f"sections/{sec_key}", "_to": f"figures/{fig_key}"},
                overwrite=True,
            )

    # Sync requirements
    if repo.requirements:
        logger.info(f"Syncing {len(repo.requirements)} requirements to ArangoDB...")
        for req in repo.requirements:
            r_id = req.get("req_id", req.get("id", ""))
            s_id = req.get("section_id", "")
            conf = req.get("confidence")

            req_node = {
                "_key": r_id,
                "text": req.get("text", ""),
                "type": req.get("type", ""),
                "confidence": conf,
                "citation": req.get("citation_snippet", ""),
                "source_type": "table" if req.get("is_table_row") else "text",
            }
            adb.collection("requirements").insert(req_node, overwrite=True)

            if s_id:
                sec_key = hashlib.md5(f"{doc_key}_{s_id}".encode()).hexdigest()
                adb.collection("has_requirement").insert(
                    {
                        "_from": f"sections/{sec_key}",
                        "_to": f"requirements/{r_id}",
                        "confidence": conf,
                    },
                    overwrite=True,
                )

    # Sync Equations
    eq_blocks = [b for b in repo.blocks if b.get("is_equation")]
    if eq_blocks:
        logger.info(f"Syncing {len(eq_blocks)} equations to ArangoDB...")
        for b in eq_blocks:
            b_id = b.get("id", "")
            s_id = b.get("section_id", "")
            latex = b.get("latex_content", "")
            eq_key = hashlib.md5(f"{doc_key}_eq_{b_id}".encode()).hexdigest()
            eq_node = {"_key": eq_key, "latex": latex, "page": b.get("page", 0)}
            adb.collection("equations").insert(eq_node, overwrite=True)

            if s_id:
                sec_key = hashlib.md5(f"{doc_key}_{s_id}".encode()).hexdigest()
                adb.collection("has_equation").insert(
                    {"_from": f"sections/{sec_key}", "_to": f"equations/{eq_key}"},
                    overwrite=True,
                )

    logger.info("Stage 10 Graph Sync Complete.")

    # Step 4: Logic for Memory Skill Compatibility (Sparta & Codebase)
    if os.getenv("SYNC_TO_MEMORY", "1") == "1":
         # Enrich doc_meta with S00 profile metadata for structured queries
         # (e.g., "find PDFs with >10 tables about X")
         profile_path = pipeline_dir / "00_profile_detector" / "profile.json"
         if profile_path.exists():
             try:
                 s00_profile = json.loads(profile_path.read_text())
                 elements = s00_profile.get("elements", {})
                 doc_meta["profile"] = {
                     "page_count": s00_profile.get("page_count", 0),
                     "domain": s00_profile.get("domain", "unknown"),
                     "file_size_mb": s00_profile.get("file_size_mb", 0),
                     "table_count": elements.get("estimated_table_count", 0),
                     "table_pages": elements.get("table_pages", 0),
                     "has_tables": bool(elements.get("tables", False)),
                     "has_figures": bool(elements.get("figures", False)),
                     "image_pages": elements.get("image_pages", 0),
                     "has_formulas": bool(elements.get("formulas", False)),
                     "has_requirements": bool(elements.get("requirements", False)),
                     "section_estimate": s00_profile.get("hierarchy", {}).get("estimated_sections", 0),
                     "layout_columns": s00_profile.get("layout", {}).get("columns", 1),
                     "detected_preset": s00_profile.get("detected_preset", ""),
                 }
                 # Overlay any lineage fields S00 may have detected
                 for lk in ("document_family", "revision", "revision_date"):
                     val = s00_profile.get(lk)
                     if val:
                         doc_meta["profile"][lk] = val
                 logger.info(f"Enriched doc_meta with S00 profile: {doc_meta['profile'].get('page_count')} pages, "
                             f"{doc_meta['profile'].get('table_count')} tables, domain={doc_meta['profile'].get('domain')}")
             except Exception as e:
                 logger.warning(f"Failed to load S00 profile from {profile_path}: {e}")

         sync_to_datalake(doc_meta, flattened, doc_key)
         sync_to_codebase(pipeline_dir)

    return json_path


if __name__ == "__main__":
    import sys

    # Keep simple sanity check if needed
    if len(sys.argv) > 1 and sys.argv[1] == "sanity":
        sys.exit(sanity())

    # Deprecation
    print("❌ DIRECT EXECUTION DEPRECATED", file=sys.stderr)
    print("Please use the pipeline orchestrator:", file=sys.stderr)
    print("  python -m extractor.pipeline --pdf <PDF> --out <DIR>", file=sys.stderr)
    sys.exit(1)
