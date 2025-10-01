#!/usr/bin/env python3
"""
ReqIF Export (v0)

Purpose
- Minimal, read-only ReqIF exporter for Stage 10 flattened JSON.
- Generates a small ReqIF XML (.reqif) with a Specification and one SpecObject per requirement-like object.

Notes
- v0 focuses on traceability payload: id, text_content, section breadcrumb, page/bbox evidence.
- IDs are derived from doc_id + object_index_in_doc for stability.
"""
from __future__ import annotations

import uuid
import json
from pathlib import Path
from typing import Dict, Any, List
import xml.etree.ElementTree as ET


def _reqif_root() -> ET.Element:
    root = ET.Element("REQ-IF")
    # Basic header
    header = ET.SubElement(root, "THE-HEADER")
    ET.SubElement(header, "REQ-IF-HEADER")
    # Content container
    ET.SubElement(root, "CORE-CONTENT")
    return root


def _add_spec_types(content: ET.Element) -> None:
    dtd = ET.SubElement(content, "DATATYPE-DEFINITIONS")
    dt_string = ET.SubElement(dtd, "DATATYPE-DEFINITION-STRING")
    dt_string.set("IDENTIFIER", "dt-string")
    ET.SubElement(dt_string, "LONG-NAME").text = "String"

    sotc = ET.SubElement(content, "SPEC-OBJECT-TYPES")
    sot = ET.SubElement(sotc, "SPEC-OBJECT-TYPE")
    sot.set("IDENTIFIER", "sot-requirement")
    ET.SubElement(sot, "LONG-NAME").text = "Requirement"
    attrs = ET.SubElement(sot, "SPEC-ATTRIBUTES")
    a_text = ET.SubElement(attrs, "ATTRIBUTE-DEFINITION-STRING")
    a_text.set("IDENTIFIER", "attr-text")
    ET.SubElement(a_text, "LONG-NAME").text = "Text"
    t = ET.SubElement(a_text, "TYPE")
    ET.SubElement(t, "DATATYPE-DEFINITION-STRING-REF").text = "dt-string"
    ET.SubElement(attrs, "ATTRIBUTE-DEFINITION-XHTML").set("IDENTIFIER", "attr-rtm")


def _add_spec_objects(content: ET.Element, items: List[Dict[str, Any]]) -> int:
    spec_objects = ET.SubElement(content, "SPEC-OBJECTS")
    count = 0
    for obj in items:
        if not isinstance(obj, dict):
            continue
        text = obj.get("text_content") or ""
        if not text:
            continue
        # Heuristic: treat any non-empty text object as a requirement candidate
        so = ET.SubElement(spec_objects, "SPEC-OBJECT")
        so_id = f"{obj.get('doc_id','doc')}:{obj.get('object_index_in_doc',0)}"
        so.set("IDENTIFIER", so_id)
        so.set("LAST-CHANGE", "2025-09-18T00:00:00Z")
        # Type reference
        typeref = ET.SubElement(so, "TYPE")
        ET.SubElement(typeref, "SPEC-OBJECT-TYPE-REF").text = "sot-requirement"
        values = ET.SubElement(so, "VALUES")
        # Text attribute
        tv = ET.SubElement(values, "ATTRIBUTE-VALUE-STRING")
        ET.SubElement(tv, "THE-VALUE").text = str(text)
        # Minimal RTM dump
        rtm = obj.get("rtm") or {}
        rtm_str = json.dumps(
            {
                "section_id": rtm.get("section_id"),
                "breadcrumb": rtm.get("breadcrumb"),
                "evidence": rtm.get("evidence"),
                "lean4_status": rtm.get("lean4_status"),
            },
            ensure_ascii=False,
        )
        rv = ET.SubElement(values, "ATTRIBUTE-VALUE-XHTML")
        ET.SubElement(rv, "THE-VALUE").text = rtm_str
        count += 1
    return count


def export_reqif(stage10_json: Path, out_file: Path) -> Dict[str, Any]:
    data = json.loads(stage10_json.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Stage 10 JSON must be a list of objects")

    root = _reqif_root()
    content = root.find("CORE-CONTENT")
    if content is None:
        raise RuntimeError("REQ-IF content missing")
    # Required child container in REQ-IF 1.0 format
    content = ET.SubElement(content, "REQ-IF-CONTENT")
    _add_spec_types(content)

    spec_id = f"spec-{uuid.uuid4()}"
    specs = ET.SubElement(content, "SPECIFICATIONS")
    spec = ET.SubElement(specs, "SPECIFICATION")
    spec.set("IDENTIFIER", spec_id)
    spec.set("LAST-CHANGE", "2025-09-18T00:00:00Z")
    ET.SubElement(spec, "LONG-NAME").text = "Extractor Requirements"

    # SpecObjects
    count = _add_spec_objects(content, data)

    tree = ET.ElementTree(root)
    # Ensure parent directory exists
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_file, encoding="utf-8", xml_declaration=True)
    return {"ok": True, "count": count, "path": str(out_file)}


if __name__ == "__main__":
    import typer

    app = typer.Typer(add_completion=False)

    @app.command()
    def main(stage10: Path, out: Path = Path("scripts/artifacts/export.reqif")):
        res = export_reqif(stage10, out)
        print(json.dumps(res, indent=2))

    app()
