import duckdb
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

class ContentRepository:
    """
    Data Access Object for the Pipeline DuckDB.
    Decouples Extract/Load logic from Python Scripts.
    """
    def __init__(self, db_path: Path):
        self.db_path = db_path
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")
            
    def get_proofs(self) -> Dict[str, Dict]:
        """Fetch Lean4 proofs map."""
        con = duckdb.connect(str(self.db_path), read_only=True)
        proofs_map = {}
        try:
            has_proofs = con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'lean4_proofs'").fetchone()
            if has_proofs:
                rows = con.execute("""
                    SELECT id, theorem_strategy, lean4_code, compilation_status, proof_result 
                    FROM lean4_proofs
                """).fetchall()
                for r in rows:
                    proofs_map[r[0]] = {
                        "strategy": r[1],
                        "code": r[2],
                        "status": r[3],
                        "result": r[4]
                    }
        except Exception as e:
            print(f"Warning: Could not load proofs: {e}")
        finally:
            con.close()
        return proofs_map

    def get_sections(self) -> List[Tuple]:
        """Fetch all sections ordered by page."""
        con = duckdb.connect(str(self.db_path), read_only=True)
        try:
            return con.execute("""
                SELECT id, title, page_start, llm_summary 
                FROM sections 
                ORDER BY page_start, id
            """).fetchall()
        finally:
            con.close()

    def get_section_content(self, section_id: str) -> List[Tuple]:
        """
        Fetch merged content for a specific section.
        Union of Text, Tables, Figures, and Requirements.
        """
        query = """
            SELECT 
                mc.type,
                CASE 
                    WHEN mc.type = 'requirement' THEN (SELECT text FROM requirements WHERE id = mc.asset_id)
                    WHEN mc.type = 'table' THEN (SELECT csv_data FROM tables WHERE id = mc.asset_id)
                    WHEN mc.type = 'figure' THEN (SELECT image_path FROM figures WHERE id = mc.asset_id)
                    ELSE mc.content 
                END as content,
                mc.sort_order,
                CASE 
                    WHEN mc.type = 'requirement' THEN (SELECT json_object('req_id', req_id, 'citation', citation_snippet, 'type', type, 'is_conditional', is_conditional) FROM requirements WHERE id = mc.asset_id)
                    WHEN mc.type = 'table' THEN (SELECT json_object('title', llm_title, 'desc', llm_description) FROM tables WHERE id = mc.asset_id)
                    WHEN mc.type = 'figure' THEN (SELECT json_object('title', llm_title, 'desc', llm_description) FROM figures WHERE id = mc.asset_id)
                    ELSE NULL
                END as meta_json,
                mc.asset_id
            FROM merged_content mc
            WHERE mc.section_id = ?
            ORDER BY mc.sort_order
        """
        con = duckdb.connect(str(self.db_path), read_only=True)
        try:
            return con.execute(query, [section_id]).fetchall()
        finally:
            con.close()
