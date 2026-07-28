"""
Content Repository — JSON-backed data access for pipeline artifacts.

Replaces the former DuckDB-backed ContentRepository. Loads assembled_content.json
produced by s07_json_assembler and provides the same interface downstream stages expect.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ContentRepository:
    """
    Data Access Object for pipeline assembled content.
    Loads assembled_content.json and provides query methods for downstream stages.
    """

    def __init__(self, json_path: Path):
        """
        Initialize from assembled_content.json path.

        Also accepts a pipeline_dir (auto-discovers the JSON file).
        """
        json_path = Path(json_path)

        # Auto-discover: if given a directory, look for the JSON file
        if json_path.is_dir():
            candidate = json_path / "07_assembled" / "assembled_content.json"
            if candidate.exists():
                json_path = candidate
            else:
                raise FileNotFoundError(
                    f"assembled_content.json not found at {candidate}"
                )

        if not json_path.exists():
            raise FileNotFoundError(f"Assembled content not found at {json_path}")

        self.json_path = json_path
        self._data = json.loads(json_path.read_text())

    # -- raw accessors for direct consumption by migrated stages --

    @property
    def sections(self) -> List[Dict]:
        """Return the sections list, defaulting to empty."""
        return self._data.get("sections", [])

    @property
    def blocks(self) -> List[Dict]:
        """Return blocks, defaulting to an empty list."""
        return self._data.get("blocks", [])

    @property
    def tables(self) -> List[Dict]:
        """Return stored tables, defaulting to an empty list."""
        return self._data.get("tables", [])

    @property
    def figures(self) -> List[Dict]:
        """Return a list of figures from the data dictionary."""
        return self._data.get("figures", [])

    @property
    def merged_content(self) -> List[Dict]:
        """Return merged content from data as a list of dictionaries."""
        return self._data.get("merged_content", [])

    @property
    def requirements(self) -> List[Dict]:
        """Return a list of requirements from the data dictionary."""
        return self._data.get("requirements", [])

    @property
    def annotations(self) -> List[Dict]:
        """Return a list of annotations from the data dictionary."""
        return self._data.get("annotations", [])

    @property
    def toc_entries(self) -> List[Dict]:
        """Return TOC entries, defaulting to an empty list."""
        return self._data.get("toc_entries", [])

    @property
    def document_metadata(self) -> Optional[Dict]:
        """Return document metadata from internal data dictionary."""
        return self._data.get("document_metadata")

    @property
    def lean4_proofs(self) -> List[Dict]:
        """Return Lean 4 proofs, or an empty list if not found."""
        return self._data.get("lean4_proofs", [])

    @property
    def metadata(self) -> Dict:
        """Return metadata from the internal data dictionary."""
        return self._data.get("metadata", {})

    # -- lookup helpers --

    def _build_lookup(self, collection: str, key_field: str = "id") -> Dict[str, Dict]:
        """Build a {id: record} lookup dict for a collection."""
        return {item[key_field]: item for item in self._data.get(collection, []) if key_field in item}

    # -- legacy interface (tuple-based, used by s10_markdown_exporter / s11) --

    def get_proofs(self) -> Dict[str, Dict]:
        """Fetch Lean4 proofs map: {requirement_id: {strategy, code, status, result}}."""
        proofs_map = {}
        for p in self.lean4_proofs:
            proofs_map[p.get("requirement_id", p.get("id", ""))] = {
                "strategy": p.get("theorem_strategy"),
                "code": p.get("lean4_code"),
                "status": p.get("compilation_status"),
                "result": p.get("proof_result"),
            }
        return proofs_map

    def get_sections(self) -> List[Tuple]:
        """Fetch all sections ordered by page: [(id, title, page_start, llm_summary), ...]."""
        sorted_sections = sorted(
            self.sections,
            key=lambda s: (s.get("page_start") or 0, s.get("id", "")),
        )
        return [
            (s["id"], s.get("title"), s.get("page_start"), s.get("llm_summary"))
            for s in sorted_sections
        ]

    def get_section_content(self, section_id: str) -> List[Tuple]:
        """
        Fetch merged content for a section with asset metadata.

        Returns: [(type, content, sort_order, meta_json, asset_id), ...]
        Matches the old DuckDB query output format.
        """
        # Build lookup dicts for asset metadata
        req_lookup = self._build_lookup("requirements")
        tbl_lookup = self._build_lookup("tables")
        fig_lookup = self._build_lookup("figures")

        rows = []
        for mc in self.merged_content:
            if mc.get("section_id") != section_id:
                continue

            mc_type = mc.get("type", "text")
            asset_id = mc.get("asset_id")
            content = mc.get("content")
            meta_json = None

            if mc_type == "requirement" and asset_id and asset_id in req_lookup:
                req = req_lookup[asset_id]
                content = req.get("text", content)
                meta_json = json.dumps({
                    "req_id": req.get("req_id"),
                    "citation": req.get("citation_snippet"),
                    "type": req.get("type"),
                    "is_conditional": req.get("is_conditional"),
                })
            elif mc_type == "table" and asset_id and asset_id in tbl_lookup:
                tbl = tbl_lookup[asset_id]
                content = tbl.get("csv_data", content)
                meta_json = json.dumps({
                    "title": tbl.get("llm_title"),
                    "desc": tbl.get("llm_description"),
                })
            elif mc_type == "figure" and asset_id and asset_id in fig_lookup:
                fig = fig_lookup[asset_id]
                content = fig.get("image_path", content)
                meta_json = json.dumps({
                    "title": fig.get("llm_title"),
                    "desc": fig.get("llm_description"),
                })

            rows.append((
                mc_type,
                content,
                mc.get("sort_order", 0),
                meta_json,
                asset_id,
            ))

        rows.sort(key=lambda r: r[2])
        return rows

    # -- mutation methods (used by S08 requirements, S09 summaries) --

    def add_requirements(self, new_requirements: List[Dict]):
        """Append requirements and their merged_content entries, then save."""
        if "requirements" not in self._data:
            self._data["requirements"] = []
        self._data["requirements"].extend(new_requirements)

    def add_merged_content(self, new_entries: List[Dict]):
        """Append merged_content entries."""
        if "merged_content" not in self._data:
            self._data["merged_content"] = []
        self._data["merged_content"].extend(new_entries)

    def update_section(self, section_id: str, **kwargs):
        """Update fields on a section by ID."""
        for s in self._data.get("sections", []):
            if s.get("id") == section_id:
                s.update(kwargs)
                return True
        return False

    def set_document_metadata(self, metadata: Dict):
        """Set or update document_metadata."""
        self._data["document_metadata"] = metadata

    def add_lean4_proofs(self, proofs: List[Dict]):
        """Append lean4 proof records."""
        if "lean4_proofs" not in self._data:
            self._data["lean4_proofs"] = []
        self._data["lean4_proofs"].extend(proofs)

    def save(self):
        """Write current state back to assembled_content.json."""
        self.json_path.write_text(json.dumps(self._data, indent=2, default=str))

    # -- convenience queries --

    def get_clean_blocks(self, section_id: Optional[str] = None) -> List[Dict]:
        """
        Return blocks not overlapped >50% by tables/figures.
        Equivalent to the old v_clean_blocks DuckDB view.
        """
        def box_overlap(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1):
            """Calculate the area of overlap between two rectangles."""
            return max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(0.0, min(ay1, by1) - max(ay0, by0))

        def box_area(x0, y0, x1, y1):
            """Calculate the area of a rectangle defined by two corners."""
            return (x1 - x0) * (y1 - y0)

        clean = []
        for b in self.blocks:
            if section_id and b.get("section_id") != section_id:
                continue
            bx0 = b.get("x0") or 0
            by0 = b.get("y0") or 0
            bx1 = b.get("x1") or 0
            by1 = b.get("y1") or 0
            b_area = box_area(bx0, by0, bx1, by1)
            if b_area <= 0:
                clean.append(b)
                continue

            suppressed = False
            for t in self.tables:
                if b.get("page") != t.get("page"):
                    continue
                overlap = box_overlap(bx0, by0, bx1, by1,
                                      t.get("x0", 0), t.get("y0", 0),
                                      t.get("x1", 0), t.get("y1", 0))
                if overlap >= 0.5 * b_area:
                    suppressed = True
                    break
            if not suppressed:
                for f in self.figures:
                    if b.get("page") != f.get("page"):
                        continue
                    overlap = box_overlap(bx0, by0, bx1, by1,
                                          f.get("x0", 0), f.get("y0", 0),
                                          f.get("x1", 0), f.get("y1", 0))
                    if overlap >= 0.5 * b_area:
                        suppressed = True
                        break
            if not suppressed:
                clean.append(b)
        return clean

    def get_blocks_for_section(self, section_id: str) -> List[Dict]:
        """Get all blocks for a section."""
        return [b for b in self.blocks if b.get("section_id") == section_id]

    def get_tables_for_section(self, section_id: str) -> List[Dict]:
        """Get all tables for a section."""
        return [t for t in self.tables if t.get("section_id") == section_id]

    def get_figures_for_section(self, section_id: str) -> List[Dict]:
        """Get all figures for a section."""
        return [f for f in self.figures if f.get("section_id") == section_id]

    def get_merged_content_for_section(self, section_id: str) -> List[Dict]:
        """Get merged content for a section, sorted by sort_order."""
        entries = [mc for mc in self.merged_content if mc.get("section_id") == section_id]
        entries.sort(key=lambda mc: mc.get("sort_order", 0))
        return entries

    def get_requirements_for_section(self, section_id: str) -> List[Dict]:
        """Get requirements for a section."""
        return [r for r in self.requirements if r.get("section_id") == section_id]
