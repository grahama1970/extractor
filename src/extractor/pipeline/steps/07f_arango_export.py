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


def main(reflow_json: Path, stage03_json: Path, doc_id: str, dry_run: bool = False):
    reflow = json.loads(reflow_json.read_text())
    s03 = json.loads(stage03_json.read_text())

    pdf_objects = _extract_pdf_objects(s03, doc_id)
    sections_payload, blocks_payload, section_edges, block_edges = _extract_reflow(reflow, pdf_objects, doc_id)

    client = ArangoClient(
        url=os.getenv("ARANGO_URL", "http://localhost:8529"),
        db=os.getenv("ARANGO_DB", "extractor"),
        user=os.getenv("ARANGO_USER", ""),
        password=os.getenv("ARANGO_PASSWORD", ""),
    )
    if dry_run:
        logger.info(f"[DRY RUN] Would upsert pdf_objects={len(pdf_objects)}, sections={len(sections_payload)}, blocks={len(blocks_payload)}")
        return
    client.ensure_collections()
    client.upsert_batch("pdf_objects", pdf_objects)
    client.upsert_batch("sections", sections_payload)
    client.upsert_batch("blocks", blocks_payload)
    client.upsert_edges("section_to_pdf_object", section_edges)
    client.upsert_edges("block_to_pdf_object", block_edges)
    logger.success("Arango export complete")


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
        if os.getenv("ARANGO_IGNORE_ERRORS", "0") in ("1", "true", "yes"):
            logger.error(msg)
            return
        raise RuntimeError(msg)


if __name__ == "__main__":
    import typer
    t = typer.Typer()
    @t.command()
    def run(reflow: Path = typer.Option(..., "--reflow"), stage03: Path = typer.Option(..., "--stage03"), doc_id: str = typer.Option(..., "--doc-id"), dry_run: bool = typer.Option(False, "--dry-run")):
        main(reflow, stage03, doc_id, dry_run=dry_run)
    t()
