#!/usr/bin/env python3
from __future__ import annotations

"""
07f: Arango export scaffolding for Stage 07 outputs and Stage 03 pdf_objects.

Collections (expected):
  - sections
  - blocks
  - pdf_objects
  - section_to_pdf_object (edge)
  - block_to_pdf_object (edge)

Environment variables:
  ARANGO_URL, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD
  DOC_ID (document identifier, required)
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

try:
    import requests
except Exception as e:
    raise SystemExit("pip install requests required for 07f_arango_export")


def main(
    reflow_json: Path,
    stage03_json: Path,
    doc_id: str,
    dry_run: bool = False,
    cross_refs_json: Path | None = None,
    requirements_json: Path | None = None,
    entities_json: Path | None = None,
    equations_json: Path | None = None,
    deltas_json: Path | None = None,
):
    reflow = json.loads(reflow_json.read_text())
    s03 = json.loads(stage03_json.read_text())

    pdf_objects = _extract_pdf_objects(s03, doc_id)
    sections_payload, blocks_payload, section_edges, block_edges = _extract_reflow(reflow, pdf_objects, doc_id)
    try:
        logger.info(
            "07f:start doc_id=%s strict=%s pdf_objects=%d sections=%d blocks=%d edges(section=%d,block=%d)",
            doc_id,
            os.getenv("STRICT_KEY_NAMESPACE", "0"),
            len(pdf_objects),
            len(sections_payload),
            len(blocks_payload),
            len(section_edges),
            len(block_edges),
        )
    except Exception:
        pass

    client = ArangoClient(
        url=os.getenv("ARANGO_URL", "http://localhost:8529"),
        db=os.getenv("ARANGO_DB", "extractor"),
        user=os.getenv("ARANGO_USER", ""),
        password=os.getenv("ARANGO_PASSWORD", ""),
    )
    extra_nodes, extra_edges = _load_semantic_layers(
        doc_id=doc_id,
        cross_refs_json=cross_refs_json,
        requirements_json=requirements_json,
        entities_json=entities_json,
        equations_json=equations_json,
        deltas_json=deltas_json,
    )
    if dry_run:
        logger.info(f"[DRY RUN] Would upsert pdf_objects={len(pdf_objects)}, sections={len(sections_payload)}, blocks={len(blocks_payload)}")
        logger.info(f"[DRY RUN] semantic nodes={sum(len(v) for v in (extra_nodes or {}).values())}, edges={sum(len(v) for v in (extra_edges or {}).values())}")
        return
    client.ensure_collections()
    # Optional strict namespacing checks (dev only)
    if os.getenv("STRICT_KEY_NAMESPACE", "0").lower() in ("1","true","yes"):
        prefix_map = {
            "pdf_objects": f"obj::{doc_id}::",
            "sections": f"sec::{doc_id}::",
            "blocks": f"blk::{doc_id}::",
            "requirements": f"req::{doc_id}::",
            "entities": f"ent::{doc_id}::",
            "equations": f"eq::{doc_id}::",
            "variables": f"var::{doc_id}::",
            "deltas": f"delta::{doc_id}::",
        }
        def _check(col: str, docs: list[dict]):
            pre = prefix_map.get(col)
            if not pre:
                return
            for d in docs:
                k = d.get("_key", "")
                if not isinstance(k, str) or not k.startswith(pre):
                    raise SystemExit(f"STRICT_KEY_NAMESPACE: {_key} invalid for {col}; expected prefix '{pre}'")
        _check("pdf_objects", pdf_objects)
        _check("sections", sections_payload)
        _check("blocks", blocks_payload)
        for col, docs in (extra_nodes or {}).items():
            _check(col, docs)
    client.upsert_batch("pdf_objects", pdf_objects)
    client.upsert_batch("sections", sections_payload)
    client.upsert_batch("blocks", blocks_payload)
    client.upsert_edges("section_to_pdf_object", section_edges)
    client.upsert_edges("block_to_pdf_object", block_edges)
    # Semantic layer
    for col, docs in (extra_nodes or {}).items():
        client.upsert_batch(col, docs)
    # Strict validation for edge collections and namespaces (dev safety)
    allowed_edge_cols = {
        "references",
        "block_to_reference_target",
        "block_to_requirement",
        "entity_occurs_in",
        "variable_in_equation",
        "deltas",
        "requirement_deltas",
        "cross_version_links",
    }
    for ecol, edocs in (extra_edges or {}).items():
        if os.getenv("STRICT_KEY_NAMESPACE", "0").lower() in ("1","true","yes"):
            if ecol not in allowed_edge_cols:
                raise SystemExit(f"STRICT_KEY_NAMESPACE: disallowed edge collection '{ecol}'")
            # Enforce that _from/_to have expected collection prefixes
            for e in edocs:
                frm = e.get("_from", "")
                to = e.get("_to", "")
                if not (isinstance(frm, str) and isinstance(to, str) and "/" in frm and "/" in to):
                    raise SystemExit(f"STRICT_KEY_NAMESPACE: malformed edge endpoints for {ecol}: {e}")
                # Ensure each endpoint starts with a whitelisted collection
                from_col = frm.split("/", 1)[0]
                to_col = to.split("/", 1)[0]
                allowed_node_cols = {"sections", "blocks", "requirements", "entities", "variables", "equations"}
                if from_col not in allowed_node_cols or to_col not in allowed_node_cols:
                    raise SystemExit(f"STRICT_KEY_NAMESPACE: edge {ecol} has invalid endpoint collections: {from_col}->{to_col}")
        client.upsert_edges(ecol, edocs)
        if os.getenv("STRICT_KEY_NAMESPACE", "0").lower() in ("1","true","yes"):
            import logging as _logging
            _logging.getLogger(__name__).info(
                "arango_export(strict): validated edge_col=%s count=%d", ecol, len(edocs)
            )
    try:
        total_nodes = sum(len(v) for v in (extra_nodes or {}).values()) + len(pdf_objects) + len(sections_payload) + len(blocks_payload)
        total_edges = len(section_edges) + len(block_edges) + sum(len(v) for v in (extra_edges or {}).values())
        logger.success("07f:exported nodes=%d edges=%d", total_nodes, total_edges)
    except Exception:
        pass
    logger.success("Arango export complete")

def _load_json_safe(p: Path | None):
    if not p or not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def _load_semantic_layers(*, doc_id: str, cross_refs_json: Path | None, requirements_json: Path | None, entities_json: Path | None, equations_json: Path | None, deltas_json: Path | None):
    nodes: Dict[str, list] = {"requirements": [], "entities": [], "equations": [], "variables": [], "deltas": []}
    edges: Dict[str, list] = {"references": [], "block_to_reference_target": [], "block_to_requirement": [], "entity_occurs_in": [], "variable_in_equation": []}
    # Cross-refs
    cref = _load_json_safe(cross_refs_json).get("references", [])
    for r in cref:
        sa = r.get("source_paragraph")
        ta = r.get("target_anchor") or "missing"
        edges["references"].append({"_from": f"blocks/blk::{doc_id}::{sa}", "_to": f"blocks/blk::{doc_id}::{ta}", "label": r.get("label"), "kind": r.get("kind")})
    # Requirements
    reqs = _load_json_safe(requirements_json).get("requirements", [])
    for rq in reqs:
        if rq.get("final_label") == "requirement":
            key = rq.get("requirement_id")
            nodes["requirements"].append({"_key": f"req::{doc_id}::{key}", "doc_id": doc_id, "requirement_id": key, "text": rq.get("text"), "section_id": rq.get("section_id"), "hash": rq.get("hash")})
            edges["block_to_requirement"].append({"_from": f"blocks/blk::{doc_id}::{rq.get('anchor_id')}", "_to": f"requirements/req::{doc_id}::{key}"})
    # Entities
    ents = _load_json_safe(entities_json).get("entities", [])
    for e in ents:
        ek = e.get("entity_id", "ent::x::000").split("::")[-1]
        nodes["entities"].append({"_key": f"ent::{doc_id}::{ek}", "doc_id": doc_id, "name": e.get("name"), "category": e.get("category")})
        for occ in e.get("occurrences", []):
            edges["entity_occurs_in"].append({"_from": f"entities/ent::{doc_id}::{ek}", "_to": f"blocks/blk::{doc_id}::{occ.get('anchor_id')}", "span": occ.get("span")})
    # Equations & variables
    eq_pack = _load_json_safe(equations_json)
    for eq in eq_pack.get("equations", []):
        ek = eq.get("equation_id", "eq::x").split("::")[-1]
        nodes["equations"].append({"_key": f"eq::{doc_id}::{ek}", "doc_id": doc_id, "text": eq.get("text"), "section_id": eq.get("section_id")})
    for var in eq_pack.get("variables", []):
        vk = var.get("variable_id", "var::x").split("::")[-1]
        nodes["variables"].append({"_key": f"var::{doc_id}::{vk}", "doc_id": doc_id, "symbol": var.get("symbol")})
        for eqid in var.get("equations", []):
            edges["variable_in_equation"].append({"_from": f"variables/var::{doc_id}::{vk}", "_to": f"equations/eq::{doc_id}::{eqid.split('::')[-1]}"})
    # Deltas
    dels = _load_json_safe(deltas_json).get("deltas", [])
    for d in dels:
        nodes["deltas"].append({"_key": f"delta::{doc_id}::{d.get('anchor_id')}-{d.get('change_type')}", "anchor_id": d.get("anchor_id"), "change_type": d.get("change_type"), "doc_id": doc_id})
    nodes = {k: v for k, v in nodes.items() if v}
    edges = {k: v for k, v in edges.items() if v}
    return nodes, edges


def _extract_pdf_objects(s03: dict, doc_id: str) -> List[Dict[str, Any]]:
    out = []
    for b in s03.get("blocks", []):
        lv = b.get("llm_verification", {})
        res = lv.get("result") if isinstance(lv, dict) else {}
        is_header = bool(res.get("is_header", True)) if isinstance(res, dict) else True
        oid = b.get("object_id") or f"hdr_p{b.get('page_idx')}_b?"
        key = f"obj::{doc_id}::{oid}"
        out.append({
            "_key": key,
            "doc_id": doc_id,
            "object_type": "header_candidate",
            "page_idx": b.get("page_idx"),
            "bbox": b.get("bbox"),
            "is_header": is_header,
            "reasoning": res.get("reasoning") if isinstance(res, dict) else None,
            "normalized_header_text": b.get("normalized_header_text"),
        })
    return out


def _extract_reflow(reflow: dict, pdf_objects: List[dict], doc_id: str):
    pdf_object_keys = {o["_key"] for o in pdf_objects}
    sections_payload = []
    blocks_payload = []
    section_edges = []
    block_edges = []
    for s in reflow.get("reflowed_sections", []) or reflow.get("sections", []):
        sid = s.get("id") or s.get("section_id")
        skey = f"sec::{doc_id}::{sid}"
        prov = s.get("provenance", {})
        sections_payload.append({
            "_key": skey,
            "doc_id": doc_id,
            "title": s.get("reflowed_json", {}).get("title") or s.get("title"),
            "content_hash": prov.get("content_hash"),
            "annotation_hash": prov.get("stage03_annotation_hash"),
            "needs_layout_image": prov.get("needs_layout_image"),
        })
        for oid in prov.get("prompt_source_objects", []) or []:
            okey = f"obj::{doc_id}::{oid}"
            if okey in pdf_object_keys:
                section_edges.append({"_from": f"sections/{skey}", "_to": f"pdf_objects/{okey}"})
        for bi, block in enumerate(s.get("reflowed_json", {}).get("blocks", [])):
            bkey = f"blk::{doc_id}::{sid}::{bi}"
            rec = {
                "_key": bkey,
                "doc_id": doc_id,
                "section_id": sid,
                "block_type": block.get("type"),
                "normalized_label": block.get("normalized_label"),
            }
            if block.get("type") == "table":
                rec["columns"] = block.get("columns")
                rec["rows"] = block.get("rows")
            if block.get("type") == "figure":
                rec["caption"] = block.get("caption")
            blocks_payload.append(rec)
    return sections_payload, blocks_payload, section_edges, block_edges


class ArangoClient:
    def __init__(self, url: str, db: str, user: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.session = requests.Session()
        if user:
            self.session.auth = (user, password)

    def _col_url(self, col: str) -> str:
        return f"{self.url}/_db/{self.db}/_api/document/{col}"

    def _edge_url(self, col: str) -> str:
        return f"{self.url}/_db/{self.db}/_api/document/{col}"

    def ensure_collections(self):
        required = [
            ("pdf_objects", False),
            ("sections", False),
            ("blocks", False),
            ("section_to_pdf_object", True),
            ("block_to_pdf_object", True),
        ]
        for name, is_edge in required:
            self._ensure_collection(name, is_edge)

    def _ensure_collection(self, name: str, is_edge: bool):
        meta_url = f"{self.url}/_db/{self.db}/_api/collection/{name}"
        r = self.session.get(meta_url)
        if r.status_code == 200:
            return
        payload = {"name": name}
        if is_edge:
            payload["type"] = 3
        cr = self.session.post(f"{self.url}/_db/{self.db}/_api/collection", json=payload)
        if not cr.ok:
            raise RuntimeError(f"Failed to create collection {name}: {cr.text}")

    def upsert_batch(self, col: str, docs: List[Dict[str, Any]], chunk: int = 100):
        for i in range(0, len(docs), chunk):
            batch = docs[i:i+chunk]
            if not batch:
                continue
            self._post_with_retry(self._col_url(col), batch, col)

    def upsert_edges(self, col: str, edges: List[Dict[str, Any]], chunk: int = 200):
        for i in range(0, len(edges), chunk):
            batch = edges[i:i+chunk]
            if not batch:
                continue
            self._post_with_retry(self._edge_url(col), batch, col)

    def _post_with_retry(self, url: str, payload: Any, col: str, attempt: int = 0):
        params = {"overwrite": "true"}
        r = self.session.post(url, json=payload, params=params, timeout=30)
        if r.ok:
            return
        if attempt == 0:
            logger.warning(f"Retrying {col} due to {r.status_code}: {r.text[:140]}")
            return self._post_with_retry(url, payload, col, attempt=1)
        msg = f"Upsert failed for {col}: {r.status_code} {r.text[:200]}"
        fail_open = os.getenv("ARANGO_FAIL_OPEN", "0").lower() in ("1", "true", "yes")
        ignore_all = os.getenv("ARANGO_IGNORE_ERRORS", "0").lower() in ("1", "true", "yes")
        if ignore_all or fail_open:
            logger.error(msg)
            return
        raise RuntimeError(msg)


if __name__ == "__main__":
    import typer
    t = typer.Typer()
    @t.command()
    def run(
        reflow: Path = typer.Option(..., "--reflow"),
        stage03: Path = typer.Option(..., "--stage03"),
        doc_id: str = typer.Option(..., "--doc-id"),
        dry_run: bool = typer.Option(False, "--dry-run"),
        refs: Path = typer.Option(None, "--refs"),
        requirements: Path = typer.Option(None, "--requirements"),
        entities: Path = typer.Option(None, "--entities"),
        equations: Path = typer.Option(None, "--equations"),
        deltas: Path = typer.Option(None, "--deltas"),
    ):
        main(reflow, stage03, doc_id, dry_run=dry_run, cross_refs_json=refs, requirements_json=requirements, entities_json=entities, equations_json=equations, deltas_json=deltas)
    t()
