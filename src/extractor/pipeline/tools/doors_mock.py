#!/usr/bin/env python3
"""Mock DOORS Next OSLC RM V2 server for integration testing.

Serves OSLC-shaped JSON responses from local ReqIF files, allowing
tests and pipeline code to exercise DOORS integration paths without
a live IBM ELM instance.

Usage:
    # Programmatic
    mock = MockDOORSNext(reqif_dir=Path("tests/fixtures/reqif"))
    results = mock.query_requirements(project="sample", where="dcterms:title=*safety*")

    # As HTTP server (for integration tests)
    mock.serve(port=9443)  # Responds to OSLC RM V2 queries

OSLC RM V2 vocabulary reference:
    oslc_rm:Requirement       — a requirement resource
    dcterms:identifier        — stable ID
    dcterms:title             — short name / heading
    dcterms:description       — body text
    oslc_rm:TrackedBy         — traceability link (source tracks target)
    oslc_rm:Satisfies         — satisfaction link
    oslc_rm:ValidatedBy       — validation link
"""
from __future__ import annotations

import fnmatch
import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from loguru import logger

# Optional reqif library — fall back to raw XML parsing if unavailable
try:
    from reqif.parser import ReqIFParser

    REQIF_AVAILABLE = True
except ImportError:
    REQIF_AVAILABLE = False

# ---------------------------------------------------------------------------
# OSLC namespace constants
# ---------------------------------------------------------------------------
OSLC_RM_NS = "http://open-services.net/ns/rm#"
DCTERMS_NS = "http://purl.org/dc/terms/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

# Map relation type name substrings to OSLC RM link types
_RELATION_TYPE_MAP = {
    "trace": "oslc_rm:TrackedBy",
    "track": "oslc_rm:TrackedBy",
    "satisf": "oslc_rm:Satisfies",
    "satis": "oslc_rm:Satisfies",
    "valid": "oslc_rm:ValidatedBy",
    "verif": "oslc_rm:ValidatedBy",
    "derive": "oslc_rm:DerivedFrom",
    "refine": "oslc_rm:Refines",
    "implement": "oslc_rm:ImplementedBy",
    "decompos": "oslc_rm:DecomposedBy",
    "elaborat": "oslc_rm:ElaboratedBy",
}


def _strip_xhtml(text: Optional[str]) -> str:
    """Strip XHTML/XML tags from a string, returning plain text."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _infer_link_type(relation_type_ref: str, long_name: str) -> str:
    """Map a ReqIF relation-type name to an OSLC RM link predicate."""
    combined = (relation_type_ref + " " + long_name).lower()
    for substring, oslc_type in _RELATION_TYPE_MAP.items():
        if substring in combined:
            return oslc_type
    return "oslc_rm:TrackedBy"  # safe default


# ---------------------------------------------------------------------------
# ReqIF → internal model
# ---------------------------------------------------------------------------

class _ReqIFProject:
    """Internal representation of one parsed ReqIF file (= one OSLC 'project')."""

    __slots__ = ("name", "requirements", "relations", "hierarchy", "metadata")

    def __init__(self, name: str):
        self.name = name
        self.requirements: List[Dict[str, Any]] = []
        self.relations: List[Dict[str, Any]] = []
        self.hierarchy: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}


def _parse_with_reqif_lib(filepath: Path) -> _ReqIFProject:
    """Parse a .reqif file using the strictdoc reqif library."""
    bundle = ReqIFParser.parse(str(filepath))
    project = _ReqIFProject(name=filepath.stem)

    content = getattr(bundle, "core_content", None)
    req_if_content = getattr(content, "req_if_content", None) if content else None
    if req_if_content is None:
        return project

    # --- Header metadata ---
    header = getattr(bundle, "the_header", None)
    if header:
        project.metadata["title"] = getattr(header, "title", None) or filepath.stem
        project.metadata["source_tool"] = getattr(header, "source_tool_id", None) or ""
        project.metadata["creation_time"] = str(getattr(header, "creation_time", "") or "")

    # --- SPEC-OBJECTS → requirements ---
    spec_objects = getattr(req_if_content, "spec_objects", None) or []
    for spec_obj in spec_objects:
        identifier = getattr(spec_obj, "identifier", "") or ""
        long_name = getattr(spec_obj, "long_name", "") or ""
        description = getattr(spec_obj, "description", "") or ""
        spec_type = getattr(spec_obj, "spec_object_type", "") or ""

        # Collect attribute texts
        attr_texts: List[str] = []
        attributes = getattr(spec_obj, "attributes", None) or []
        for attr in attributes:
            xhtml_val = getattr(attr, "value_stripped_xhtml", None)
            raw_val = getattr(attr, "value", None)
            if xhtml_val:
                attr_texts.append(_strip_xhtml(xhtml_val))
            elif raw_val is not None:
                attr_texts.append(_strip_xhtml(str(raw_val)))

        body_parts = [p for p in [long_name, description, *attr_texts] if p]
        body = "\n".join(body_parts).strip() or f"[SPEC-OBJECT {identifier}]"

        project.requirements.append({
            "identifier": identifier,
            "title": long_name or identifier,
            "description": body,
            "spec_type": spec_type,
            "last_change": getattr(spec_obj, "last_change", "") or "",
        })

    # --- SPEC-RELATIONS → traceability links ---
    spec_relations = getattr(req_if_content, "spec_relations", None) or []
    for rel in spec_relations:
        source = getattr(rel, "source", "") or ""
        target = getattr(rel, "target", "") or ""
        if not (source and target):
            continue
        project.relations.append({
            "identifier": getattr(rel, "identifier", "") or "",
            "source": source,
            "target": target,
            "relation_type_ref": getattr(rel, "relation_type_ref", "") or "",
            "long_name": getattr(rel, "long_name", "") or "",
        })

    # --- SPEC-HIERARCHY → module structure ---
    specifications = getattr(req_if_content, "specifications", None) or []
    for spec in specifications:
        spec_node = {
            "identifier": getattr(spec, "identifier", "") or "",
            "title": getattr(spec, "long_name", "") or filepath.stem,
            "children": [],
        }
        for child in (getattr(spec, "children", None) or []):
            _walk_hierarchy_lib(child, spec_node["children"])
        project.hierarchy.append(spec_node)

    return project


def _walk_hierarchy_lib(hier: Any, parent_children: List[Dict[str, Any]]) -> None:
    """Recursively walk SPEC-HIERARCHY from the reqif library."""
    node = {
        "identifier": getattr(hier, "identifier", "") or "",
        "title": getattr(hier, "long_name", "") or "",
        "spec_object_ref": getattr(hier, "spec_object", "") or "",
        "children": [],
    }
    for child in (getattr(hier, "children", None) or []):
        _walk_hierarchy_lib(child, node["children"])
    parent_children.append(node)


def _parse_with_xml(filepath: Path) -> _ReqIFProject:
    """Fallback XML parser when the reqif library is not available."""
    project = _ReqIFProject(name=filepath.stem)
    tree = ET.parse(str(filepath))
    root = tree.getroot()

    # Strip namespace prefixes for easier querying
    ns_re = re.compile(r"\{[^}]+\}")

    def _tag(elem: ET.Element) -> str:
        return ns_re.sub("", elem.tag)

    def _find_all_recursive(elem: ET.Element, tag: str) -> List[ET.Element]:
        """Find all descendants matching a tag name (namespace-stripped)."""
        results: List[ET.Element] = []
        for child in elem.iter():
            if _tag(child) == tag:
                results.append(child)
        return results

    # --- SPEC-OBJECTS ---
    for so in _find_all_recursive(root, "SPEC-OBJECT"):
        identifier = so.get("IDENTIFIER", "")
        long_name_el = so.find("LONG-NAME") if so.find("LONG-NAME") is not None else None
        long_name = ""
        # Try child LONG-NAME element first, then attribute
        for child in so:
            if _tag(child) == "LONG-NAME":
                long_name = (child.text or "").strip()
                break

        # Extract text from VALUES
        description_parts: List[str] = []
        for val_el in so.iter():
            if _tag(val_el) == "THE-VALUE":
                val_text = (val_el.text or "").strip()
                if val_text:
                    description_parts.append(val_text)

        body = "\n".join(description_parts).strip()
        if long_name:
            body = long_name + ("\n" + body if body else "")
        if not body:
            body = f"[SPEC-OBJECT {identifier}]"

        project.requirements.append({
            "identifier": identifier,
            "title": long_name or identifier,
            "description": body,
            "spec_type": "",
            "last_change": so.get("LAST-CHANGE", ""),
        })

    # --- SPEC-RELATIONS ---
    for sr in _find_all_recursive(root, "SPEC-RELATION"):
        source = ""
        target = ""
        for child in sr.iter():
            tag = _tag(child)
            if tag == "SPEC-OBJECT-REF":
                text = (child.text or "").strip()
                if not source:
                    source = text
                else:
                    target = text
        if source and target:
            project.relations.append({
                "identifier": sr.get("IDENTIFIER", ""),
                "source": source,
                "target": target,
                "relation_type_ref": "",
                "long_name": "",
            })

    # --- SPEC-HIERARCHY ---
    for spec_el in _find_all_recursive(root, "SPECIFICATION"):
        spec_id = spec_el.get("IDENTIFIER", "")
        spec_title = ""
        for child in spec_el:
            if _tag(child) == "LONG-NAME":
                spec_title = (child.text or "").strip()
                break
        spec_node: Dict[str, Any] = {
            "identifier": spec_id,
            "title": spec_title or filepath.stem,
            "children": [],
        }
        for child in spec_el:
            if _tag(child) == "CHILDREN":
                _walk_hierarchy_xml(child, spec_node["children"], _tag)
        project.hierarchy.append(spec_node)

    return project


def _walk_hierarchy_xml(
    parent: ET.Element,
    children_list: List[Dict[str, Any]],
    tag_fn: Any,
) -> None:
    """Recursively walk SPEC-HIERARCHY XML elements."""
    for child in parent:
        if tag_fn(child) != "SPEC-HIERARCHY":
            continue
        node: Dict[str, Any] = {
            "identifier": child.get("IDENTIFIER", ""),
            "title": "",
            "spec_object_ref": "",
            "children": [],
        }
        for sub in child:
            t = tag_fn(sub)
            if t == "LONG-NAME":
                node["title"] = (sub.text or "").strip()
            elif t == "OBJECT":
                for ref in sub:
                    if tag_fn(ref) == "SPEC-OBJECT-REF":
                        node["spec_object_ref"] = (ref.text or "").strip()
            elif t == "CHILDREN":
                _walk_hierarchy_xml(sub, node["children"], tag_fn)
        children_list.append(node)


def _parse_reqif(filepath: Path) -> _ReqIFProject:
    """Parse a single .reqif file, preferring the reqif library.

    Falls back to raw XML parsing if the library is unavailable or
    returns an empty bundle (core_content is None — common with
    simplified ReqIF files from our own exporters).
    """
    if REQIF_AVAILABLE:
        try:
            project = _parse_with_reqif_lib(filepath)
            if project.requirements or project.hierarchy:
                return project
            # Library parsed OK but found nothing — try XML fallback
            logger.debug(
                "reqif library returned empty for {}; trying XML fallback",
                filepath.name,
            )
        except Exception as exc:
            logger.warning("reqif library failed on {}: {}; falling back to XML", filepath.name, exc)
    return _parse_with_xml(filepath)


# ---------------------------------------------------------------------------
# OSLC RM V2 response builders
# ---------------------------------------------------------------------------

def _requirement_to_oslc(
    req: Dict[str, Any],
    project_name: str,
    base_url: str = "http://localhost:9443",
) -> Dict[str, Any]:
    """Convert an internal requirement dict to an OSLC RM V2 resource."""
    rid = req["identifier"]
    return {
        "@type": "oslc_rm:Requirement",
        "@id": f"{base_url}/oslc/rm/resources/{project_name}/{rid}",
        "rdf:type": f"{OSLC_RM_NS}Requirement",
        "dcterms:identifier": rid,
        "dcterms:title": req["title"],
        "dcterms:description": req["description"],
        "dcterms:modified": req.get("last_change", ""),
        "oslc_rm:specObjectType": req.get("spec_type", ""),
    }


def _relation_to_oslc(
    rel: Dict[str, Any],
    project_name: str,
    base_url: str = "http://localhost:9443",
) -> Dict[str, Any]:
    """Convert an internal relation dict to an OSLC RM V2 link."""
    link_type = _infer_link_type(rel["relation_type_ref"], rel["long_name"])
    return {
        "@type": link_type,
        "dcterms:identifier": rel["identifier"],
        "oslc_rm:source": f"{base_url}/oslc/rm/resources/{project_name}/{rel['source']}",
        "oslc_rm:target": f"{base_url}/oslc/rm/resources/{project_name}/{rel['target']}",
        "dcterms:title": rel["long_name"] or link_type,
        "oslc_rm:relationType": rel["relation_type_ref"],
    }


def _hierarchy_to_oslc(
    node: Dict[str, Any],
    project_name: str,
    base_url: str = "http://localhost:9443",
    depth: int = 0,
) -> Dict[str, Any]:
    """Convert a hierarchy node to OSLC-shaped structure."""
    result: Dict[str, Any] = {
        "dcterms:identifier": node.get("identifier", ""),
        "dcterms:title": node.get("title", ""),
        "oslc_rm:depth": depth,
    }
    spec_ref = node.get("spec_object_ref", "")
    if spec_ref:
        result["oslc_rm:requirementRef"] = (
            f"{base_url}/oslc/rm/resources/{project_name}/{spec_ref}"
        )
    children = node.get("children", [])
    if children:
        result["oslc_rm:children"] = [
            _hierarchy_to_oslc(c, project_name, base_url, depth + 1)
            for c in children
        ]
    return result


# ---------------------------------------------------------------------------
# Main mock class
# ---------------------------------------------------------------------------

class MockDOORSNext:
    """Mock DOORS Next OSLC RM V2 server backed by local ReqIF files.

    Each .reqif file in ``reqif_dir`` becomes a separate "project".
    The project name is derived from the file stem.

    Parameters
    ----------
    reqif_dir : Path
        Directory containing .reqif files. Each file = one project.
    base_url : str
        Base URL used in generated ``@id`` URIs. Only affects the shape
        of the responses, not actual network behaviour.
    """

    def __init__(
        self,
        reqif_dir: Path,
        base_url: str = "http://localhost:9443",
    ):
        self.reqif_dir = Path(reqif_dir)
        self.base_url = base_url.rstrip("/")
        self._projects: Dict[str, _ReqIFProject] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Scan reqif_dir and parse all .reqif files."""
        if not self.reqif_dir.is_dir():
            logger.warning("ReqIF directory does not exist: {}", self.reqif_dir)
            return

        for reqif_path in sorted(self.reqif_dir.glob("*.reqif")):
            try:
                project = _parse_reqif(reqif_path)
                self._projects[project.name] = project
                logger.info(
                    "Loaded project '{}': {} requirements, {} relations",
                    project.name,
                    len(project.requirements),
                    len(project.relations),
                )
            except Exception as exc:
                logger.error("Failed to load {}: {}", reqif_path.name, exc)

    @property
    def project_names(self) -> List[str]:
        """List available project names."""
        return sorted(self._projects.keys())

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def query_requirements(
        self,
        project: str,
        where: Optional[str] = None,
        select: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query requirements from a project, returning an OSLC result set.

        Parameters
        ----------
        project : str
            Project name (ReqIF file stem).
        where : str, optional
            Simple filter in ``field=pattern`` form. Supports ``*`` glob
            patterns. Supported fields: ``dcterms:title``,
            ``dcterms:description``, ``dcterms:identifier``.
        select : str, optional
            Comma-separated list of fields to include. If None, all fields
            are returned.

        Returns
        -------
        dict
            OSLC-shaped response with ``oslc:results``, ``oslc:totalCount``,
            and ``oslc:responseInfo``.
        """
        proj = self._projects.get(project)
        if proj is None:
            return self._error_response(f"Project '{project}' not found", 404)

        resources = [
            _requirement_to_oslc(r, project, self.base_url)
            for r in proj.requirements
        ]

        # Apply where filter
        if where:
            resources = self._apply_where(resources, where)

        # Apply select projection
        if select:
            resources = self._apply_select(resources, select)

        return {
            "oslc:responseInfo": {
                "@type": "oslc:ResponseInfo",
                "dcterms:title": f"Requirements for project '{project}'",
                "oslc:totalCount": len(resources),
            },
            "oslc:results": resources,
        }

    def get_requirement(
        self,
        project: str,
        identifier: str,
    ) -> Dict[str, Any]:
        """Get a single requirement by identifier.

        Returns
        -------
        dict
            OSLC RM V2 requirement resource, or error response.
        """
        proj = self._projects.get(project)
        if proj is None:
            return self._error_response(f"Project '{project}' not found", 404)

        for req in proj.requirements:
            if req["identifier"] == identifier:
                return _requirement_to_oslc(req, project, self.base_url)

        return self._error_response(
            f"Requirement '{identifier}' not found in project '{project}'", 404
        )

    def get_module_structure(
        self,
        project: str,
    ) -> Dict[str, Any]:
        """Get the module/specification hierarchy for a project.

        Returns
        -------
        dict
            OSLC-shaped module structure derived from SPEC-HIERARCHY.
        """
        proj = self._projects.get(project)
        if proj is None:
            return self._error_response(f"Project '{project}' not found", 404)

        modules = [
            _hierarchy_to_oslc(h, project, self.base_url) for h in proj.hierarchy
        ]

        return {
            "oslc:responseInfo": {
                "@type": "oslc:ResponseInfo",
                "dcterms:title": f"Module structure for project '{project}'",
                "oslc:totalCount": len(modules),
            },
            "oslc:results": modules,
        }

    def get_traceability_links(
        self,
        project: str,
        requirement_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get traceability links (SPEC-RELATIONS) for a project.

        Parameters
        ----------
        project : str
            Project name.
        requirement_id : str, optional
            If provided, filter to links involving this requirement
            (as source or target).

        Returns
        -------
        dict
            OSLC-shaped link collection.
        """
        proj = self._projects.get(project)
        if proj is None:
            return self._error_response(f"Project '{project}' not found", 404)

        links = [
            _relation_to_oslc(r, project, self.base_url) for r in proj.relations
        ]

        if requirement_id:
            links = [
                lnk for lnk in links
                if requirement_id in lnk.get("oslc_rm:source", "")
                or requirement_id in lnk.get("oslc_rm:target", "")
            ]

        return {
            "oslc:responseInfo": {
                "@type": "oslc:ResponseInfo",
                "dcterms:title": f"Traceability links for project '{project}'",
                "oslc:totalCount": len(links),
            },
            "oslc:results": links,
        }

    # ------------------------------------------------------------------
    # Filtering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_where(
        resources: List[Dict[str, Any]], where: str
    ) -> List[Dict[str, Any]]:
        """Apply a simple ``field=pattern`` filter.

        Pattern supports ``*`` wildcards (translated to fnmatch).
        Multiple conditions can be separated by ``and`` (case-insensitive).
        """
        conditions = re.split(r"\s+and\s+", where, flags=re.IGNORECASE)
        filtered = resources

        for condition in conditions:
            condition = condition.strip()
            if "=" not in condition:
                continue
            field, pattern = condition.split("=", 1)
            field = field.strip()
            pattern = pattern.strip()

            filtered = [
                r for r in filtered
                if fnmatch.fnmatch(
                    str(r.get(field, "")).lower(),
                    pattern.lower(),
                )
            ]

        return filtered

    @staticmethod
    def _apply_select(
        resources: List[Dict[str, Any]], select: str
    ) -> List[Dict[str, Any]]:
        """Project resources to only include selected fields."""
        fields = {f.strip() for f in select.split(",")}
        # Always keep @type and @id
        fields.update({"@type", "@id"})
        return [{k: v for k, v in r.items() if k in fields} for r in resources]

    @staticmethod
    def _error_response(message: str, status: int = 400) -> Dict[str, Any]:
        return {
            "oslc:error": {
                "oslc:statusCode": status,
                "oslc:message": message,
            }
        }

    # ------------------------------------------------------------------
    # HTTP server
    # ------------------------------------------------------------------

    def serve(self, port: int = 9443) -> None:
        """Start a simple HTTP server that responds to OSLC RM V2 queries.

        Routes:
            GET /oslc/rm/projects
                → list of project names
            GET /oslc/rm/resources/{project}?oslc.where=...&oslc.select=...
                → query requirements
            GET /oslc/rm/resources/{project}/{identifier}
                → single requirement
            GET /oslc/rm/modules/{project}
                → module structure
            GET /oslc/rm/links/{project}?requirement_id=...
                → traceability links
        """
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/")
                qs = parse_qs(parsed.query)

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()

                result: Dict[str, Any]

                if path == "/oslc/rm/projects":
                    result = {"projects": mock.project_names}

                elif path.startswith("/oslc/rm/resources/"):
                    parts = path.replace("/oslc/rm/resources/", "").split("/", 1)
                    project_name = parts[0]
                    if len(parts) == 2:
                        result = mock.get_requirement(project_name, parts[1])
                    else:
                        where = qs.get("oslc.where", [None])[0]
                        select = qs.get("oslc.select", [None])[0]
                        result = mock.query_requirements(
                            project_name, where=where, select=select
                        )

                elif path.startswith("/oslc/rm/modules/"):
                    project_name = path.replace("/oslc/rm/modules/", "")
                    result = mock.get_module_structure(project_name)

                elif path.startswith("/oslc/rm/links/"):
                    project_name = path.replace("/oslc/rm/links/", "")
                    req_id = qs.get("requirement_id", [None])[0]
                    result = mock.get_traceability_links(
                        project_name, requirement_id=req_id
                    )

                else:
                    result = mock._error_response(f"Unknown path: {path}", 404)

                self.wfile.write(json.dumps(result, indent=2).encode("utf-8"))

            def log_message(self, format: str, *args: Any) -> None:
                logger.debug(format, *args)

        server = HTTPServer(("0.0.0.0", port), Handler)
        logger.info("MockDOORSNext serving on port {} with {} projects", port, len(self._projects))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down MockDOORSNext server")
            server.server_close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python doors_mock.py <reqif_dir> [--port PORT]")
        print("       python doors_mock.py <reqif_dir> --query <project> [--where FILTER]")
        sys.exit(1)

    reqif_dir = Path(sys.argv[1])
    mock = MockDOORSNext(reqif_dir=reqif_dir)

    if "--query" in sys.argv:
        idx = sys.argv.index("--query")
        project_name = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        where_filter = None
        if "--where" in sys.argv:
            wi = sys.argv.index("--where")
            where_filter = sys.argv[wi + 1] if wi + 1 < len(sys.argv) else None
        result = mock.query_requirements(project_name, where=where_filter)
        print(json.dumps(result, indent=2))
    else:
        port = 9443
        if "--port" in sys.argv:
            pi = sys.argv.index("--port")
            port = int(sys.argv[pi + 1])
        mock.serve(port=port)
