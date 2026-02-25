"""ArangoDB schema for calibration collections.

Defines the collections used for iterative preset calibration:
- calibration_sessions: Track calibration session state and progress
- calibration_examples: Individual human-reviewed examples
- learned_patterns: Patterns learned from human feedback
- calibration_confirms: Edge collection linking examples to patterns
"""

import os
from dataclasses import dataclass
from typing import Any

from arango import ArangoClient
from arango.database import StandardDatabase
from dotenv import find_dotenv, load_dotenv

# Load environment variables
load_dotenv(find_dotenv(usecwd=True), override=False)

# Collection names
COLLECTION_SESSIONS = "calibration_sessions"
COLLECTION_EXAMPLES = "calibration_examples"
COLLECTION_PATTERNS = "learned_patterns"
EDGE_CONFIRMS = "calibration_confirms"


@dataclass
class ArangoConfig:
    """ArangoDB connection configuration."""

    host: str = "localhost"
    port: int = 8529
    username: str = "root"
    password: str = ""
    database: str = "extractor_calibration"

    @classmethod
    def from_env(cls) -> "ArangoConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("ARANGO_HOST", "localhost"),
            port=int(os.getenv("ARANGO_PORT", "8529")),
            username=os.getenv("ARANGO_USER", os.getenv("ARANGO_USERNAME", "root")),
            password=os.getenv("ARANGO_PASS", os.getenv("ARANGO_PASSWORD", "")),
            database=os.getenv("ARANGO_DB", "extractor_calibration"),
        )


class CalibrationSchema:
    """Manage ArangoDB schema for calibration collections."""

    def __init__(self, config: ArangoConfig | None = None):
        """Initialize schema manager.

        Args:
            config: ArangoDB connection config. Uses env vars if not provided.
        """
        self.config = config or ArangoConfig.from_env()
        self._client: ArangoClient | None = None
        self._db: StandardDatabase | None = None

    @property
    def client(self) -> ArangoClient:
        """Get or create ArangoDB client."""
        if self._client is None:
            self._client = ArangoClient(hosts=f"http://{self.config.host}:{self.config.port}")
        return self._client

    @property
    def db(self) -> StandardDatabase:
        """Get or create database connection."""
        if self._db is None:
            self._ensure_database()
            self._db = self.client.db(
                self.config.database,
                username=self.config.username,
                password=self.config.password,
            )
        return self._db

    def _ensure_database(self) -> None:
        """Ensure the calibration database exists."""
        sys_db = self.client.db(
            "_system",
            username=self.config.username,
            password=self.config.password,
        )
        if not sys_db.has_database(self.config.database):
            sys_db.create_database(self.config.database)

    def create_collections(self) -> dict[str, bool]:
        """Create all calibration collections if they don't exist.

        Returns:
            Dictionary mapping collection names to whether they were created.
        """
        results = {}

        # Create document collections
        for name in [COLLECTION_SESSIONS, COLLECTION_EXAMPLES, COLLECTION_PATTERNS]:
            if not self.db.has_collection(name):
                self.db.create_collection(name)
                results[name] = True
            else:
                results[name] = False

        # Create edge collection
        if not self.db.has_collection(EDGE_CONFIRMS):
            self.db.create_collection(EDGE_CONFIRMS, edge=True)
            results[EDGE_CONFIRMS] = True
        else:
            results[EDGE_CONFIRMS] = False

        return results

    def drop_collections(self) -> dict[str, bool]:
        """Drop all calibration collections.

        WARNING: This deletes all calibration data!

        Returns:
            Dictionary mapping collection names to whether they were dropped.
        """
        results = {}
        for name in [
            COLLECTION_SESSIONS,
            COLLECTION_EXAMPLES,
            COLLECTION_PATTERNS,
            EDGE_CONFIRMS,
        ]:
            if self.db.has_collection(name):
                self.db.delete_collection(name)
                results[name] = True
            else:
                results[name] = False
        return results

    def get_collection(self, name: str) -> Any:
        """Get a collection by name.

        Args:
            name: Collection name (use COLLECTION_* constants).

        Returns:
            ArangoDB collection object.

        Raises:
            ValueError: If collection doesn't exist.
        """
        if not self.db.has_collection(name):
            raise ValueError(f"Collection {name} does not exist")
        return self.db.collection(name)

    @property
    def sessions(self) -> Any:
        """Get the sessions collection."""
        return self.get_collection(COLLECTION_SESSIONS)

    @property
    def examples(self) -> Any:
        """Get the examples collection."""
        return self.get_collection(COLLECTION_EXAMPLES)

    @property
    def patterns(self) -> Any:
        """Get the patterns collection."""
        return self.get_collection(COLLECTION_PATTERNS)

    @property
    def confirms(self) -> Any:
        """Get the confirms edge collection."""
        return self.get_collection(EDGE_CONFIRMS)

    # Session CRUD operations

    def create_session(self, session_data: dict) -> dict:
        """Create a new calibration session.

        Args:
            session_data: Session data matching CalibrationSession model.

        Returns:
            Created document with _key, _id, _rev.
        """
        self.create_collections()
        return self.sessions.insert(session_data)

    def get_session(self, key: str) -> dict | None:
        """Get a session by key.

        Args:
            key: Session key (e.g., "boeing-specs_2026-01-19").

        Returns:
            Session document or None if not found.
        """
        return self.sessions.get(key)

    def update_session(self, key: str, updates: dict) -> dict:
        """Update a session.

        Args:
            key: Session key.
            updates: Fields to update.

        Returns:
            Updated document.
        """
        return self.sessions.update({"_key": key, **updates})

    def list_sessions(self, preset_id: str | None = None) -> list[dict]:
        """List calibration sessions.

        Args:
            preset_id: Optional filter by preset ID.

        Returns:
            List of session documents.
        """
        if preset_id:
            cursor = self.db.aql.execute(
                "FOR s IN @@collection FILTER s.preset_id == @preset_id RETURN s",
                bind_vars={
                    "@collection": COLLECTION_SESSIONS,
                    "preset_id": preset_id,
                },
            )
        else:
            cursor = self.db.aql.execute(
                "FOR s IN @@collection RETURN s",
                bind_vars={"@collection": COLLECTION_SESSIONS},
            )
        return list(cursor)

    def find_session_by_pdf(self, pdf_path: str, status: str | None = "in_progress") -> dict | None:
        """Find an existing session by PDF path.

        Used for auto-resume: when user calls /calibrate on same PDF,
        automatically resume the existing session.

        Args:
            pdf_path: Path to the PDF being calibrated.
            status: Optional filter by status. Default "in_progress".
                    Pass None to find any status.

        Returns:
            Most recent session for this PDF, or None if not found.
        """
        self.create_collections()
        if status:
            cursor = self.db.aql.execute(
                """
                FOR s IN @@collection
                    FILTER s.pdf_path == @pdf_path
                    FILTER s.status == @status
                    SORT s.updated_at DESC
                    LIMIT 1
                    RETURN s
                """,
                bind_vars={
                    "@collection": COLLECTION_SESSIONS,
                    "pdf_path": pdf_path,
                    "status": status,
                },
            )
        else:
            cursor = self.db.aql.execute(
                """
                FOR s IN @@collection
                    FILTER s.pdf_path == @pdf_path
                    SORT s.updated_at DESC
                    LIMIT 1
                    RETURN s
                """,
                bind_vars={
                    "@collection": COLLECTION_SESSIONS,
                    "pdf_path": pdf_path,
                },
            )
        results = list(cursor)
        return results[0] if results else None

    # Example CRUD operations

    def create_example(self, example_data: dict) -> dict:
        """Create a new calibration example.

        Args:
            example_data: Example data matching CalibrationExample model.

        Returns:
            Created document with _key, _id, _rev.
        """
        self.create_collections()
        return self.examples.insert(example_data)

    def get_example(self, key: str) -> dict | None:
        """Get an example by key.

        Args:
            key: Example key (e.g., "boeing-specs_2026-01-19_p5_elem_3").

        Returns:
            Example document or None if not found.
        """
        return self.examples.get(key)

    def list_examples(self, session_key: str | None = None, page: int | None = None) -> list[dict]:
        """List calibration examples.

        Args:
            session_key: Optional filter by session key.
            page: Optional filter by page number.

        Returns:
            List of example documents.
        """
        filters = []
        bind_vars: dict[str, Any] = {"@collection": COLLECTION_EXAMPLES}

        if session_key:
            filters.append("e.session_key == @session_key")
            bind_vars["session_key"] = session_key
        if page is not None:
            filters.append("e.page == @page")
            bind_vars["page"] = page

        filter_clause = f"FILTER {' AND '.join(filters)}" if filters else ""

        cursor = self.db.aql.execute(
            f"FOR e IN @@collection {filter_clause} RETURN e",
            bind_vars=bind_vars,
        )
        return list(cursor)

    # Pattern CRUD operations

    def create_pattern(self, pattern_data: dict) -> dict:
        """Create a new learned pattern.

        Args:
            pattern_data: Pattern data matching LearnedPattern model.

        Returns:
            Created document with _key, _id, _rev.
        """
        self.create_collections()
        return self.patterns.insert(pattern_data)

    def get_pattern(self, key: str) -> dict | None:
        """Get a pattern by key.

        Args:
            key: Pattern key (e.g., "boeing-specs_header_blue_font").

        Returns:
            Pattern document or None if not found.
        """
        return self.patterns.get(key)

    def update_pattern(self, key: str, updates: dict) -> dict:
        """Update a pattern.

        Args:
            key: Pattern key.
            updates: Fields to update.

        Returns:
            Updated document.
        """
        return self.patterns.update({"_key": key, **updates})

    def list_patterns(self, preset_id: str | None = None, active_only: bool = True) -> list[dict]:
        """List learned patterns.

        Args:
            preset_id: Optional filter by preset ID.
            active_only: If True, only return active patterns.

        Returns:
            List of pattern documents.
        """
        filters = []
        bind_vars: dict[str, Any] = {"@collection": COLLECTION_PATTERNS}

        if preset_id:
            filters.append("p.preset_id == @preset_id")
            bind_vars["preset_id"] = preset_id
        if active_only:
            filters.append("p.active == true")

        filter_clause = f"FILTER {' AND '.join(filters)}" if filters else ""

        cursor = self.db.aql.execute(
            f"FOR p IN @@collection {filter_clause} RETURN p",
            bind_vars=bind_vars,
        )
        return list(cursor)

    # Edge (confirms) operations

    def create_confirm_edge(
        self, example_key: str, pattern_key: str, relationship: str = "confirms"
    ) -> dict:
        """Create an edge linking an example to a pattern.

        Args:
            example_key: Key of the example.
            pattern_key: Key of the pattern.
            relationship: Either "confirms" or "contradicts".

        Returns:
            Created edge document.
        """
        self.create_collections()
        return self.confirms.insert(
            {
                "_from": f"{COLLECTION_EXAMPLES}/{example_key}",
                "_to": f"{COLLECTION_PATTERNS}/{pattern_key}",
                "relationship": relationship,
            }
        )

    def get_pattern_examples(self, pattern_key: str) -> list[dict]:
        """Get all examples that confirm a pattern.

        Args:
            pattern_key: Key of the pattern.

        Returns:
            List of example documents linked to the pattern.
        """
        cursor = self.db.aql.execute(
            """
            FOR v, e IN 1..1 INBOUND @pattern @@edge_collection
                RETURN v
            """,
            bind_vars={
                "pattern": f"{COLLECTION_PATTERNS}/{pattern_key}",
                "@edge_collection": EDGE_CONFIRMS,
            },
        )
        return list(cursor)
