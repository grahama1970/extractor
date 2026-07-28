"""
Integration tests for glossary collection — requires ArangoDB.

Skip these tests if ArangoDB is not available.
"""

import hashlib
import os
import pytest

# Skip entire module if ArangoDB is not reachable
pytestmark = pytest.mark.skipif(
    not os.getenv("ARANGO_URL") and not os.getenv("ARANGO_HOST"),
    reason="ArangoDB not configured (set ARANGO_URL)",
)


@pytest.fixture(scope="module")
def mem_db():
    """Connect to memory database for testing."""
    from scripts.glossary.setup import get_memory_db, ensure_glossary_collections, ensure_glossary_search_view
    db = get_memory_db()
    ensure_glossary_collections(db)
    ensure_glossary_search_view(db)
    return db


@pytest.fixture(autouse=True)
def cleanup_test_entries(mem_db):
    """Clean up test entries after each test."""
    yield
    # Remove test entries
    col = mem_db.collection("glossary")
    for term in ["TESTTERM", "TESTTERM2", "TESTTERM3"]:
        key = hashlib.md5(term.lower().encode()).hexdigest()
        try:
            col.delete(key)
        except Exception:
            pass


class TestGlossarySetup:
    """Test ArangoDB collection creation."""

    def test_collections_exist(self, mem_db):
        """Check existence of specified collections in the database."""
        assert mem_db.has_collection("glossary")
        assert mem_db.has_collection("glossary_edges")

    def test_view_exists(self, mem_db):
        """Check if the view 'glossary_search' exists in the database."""
        views = [v.get("name") for v in mem_db.views()]
        assert "glossary_search" in views


class TestGlossaryUpsert:
    """Test upserting glossary entries."""

    def test_insert_new_entry(self, mem_db):
        """Test inserting a new glossary entry."""
        from extractor.pipeline.steps.s10_arangodb_exporter import _upsert_glossary_entry
        col = mem_db.collection("glossary")
        edge_col = mem_db.collection("glossary_edges")

        _upsert_glossary_entry(
            col, edge_col,
            term="TESTTERM",
            definition="A test term for unit testing",
            category="acronym",
            doc_key="test_doc_001",
            doc_name="test.pdf",
            section_id="sec_1",
            section_title="Acronyms",
        )

        key = hashlib.md5("testterm".encode()).hexdigest()
        doc = col.get(key)
        assert doc is not None
        assert doc["term"] == "TESTTERM"
        assert doc["term_lower"] == "testterm"
        assert len(doc["definitions"]) == 1
        assert doc["definitions"][0]["definition"] == "A test term for unit testing"

    def test_upsert_appends_definition(self, mem_db):
        """Verifies glossary entry upsert appends definitions."""
        from extractor.pipeline.steps.s10_arangodb_exporter import _upsert_glossary_entry
        col = mem_db.collection("glossary")
        edge_col = mem_db.collection("glossary_edges")

        # Insert first
        _upsert_glossary_entry(
            col, edge_col,
            term="TESTTERM2", definition="Definition from doc A",
            category="acronym", doc_key="doc_a", doc_name="a.pdf",
            section_id="sec_1", section_title="Glossary",
        )
        # Upsert from different doc
        _upsert_glossary_entry(
            col, edge_col,
            term="TESTTERM2", definition="Definition from doc B",
            category="acronym", doc_key="doc_b", doc_name="b.pdf",
            section_id="sec_2", section_title="Acronyms",
        )

        key = hashlib.md5("testterm2".encode()).hexdigest()
        doc = col.get(key)
        assert len(doc["definitions"]) == 2

    def test_upsert_dedup_same_doc(self, mem_db):
        """Verifies glossary entry deduplication on repeated upsert."""
        from extractor.pipeline.steps.s10_arangodb_exporter import _upsert_glossary_entry
        col = mem_db.collection("glossary")
        edge_col = mem_db.collection("glossary_edges")

        for _ in range(3):
            _upsert_glossary_entry(
                col, edge_col,
                term="TESTTERM3", definition="Same definition",
                category="acronym", doc_key="doc_x", doc_name="x.pdf",
                section_id="sec_1", section_title="Glossary",
            )

        key = hashlib.md5("testterm3".encode()).hexdigest()
        doc = col.get(key)
        assert len(doc["definitions"]) == 1  # No duplicates


class TestGlossaryRecall:
    """Test the recall CLI function."""

    def test_recall_exact(self, mem_db):
        """Test the recall of exact glossary entries in the database."""
        from extractor.pipeline.steps.s10_arangodb_exporter import _upsert_glossary_entry
        col = mem_db.collection("glossary")
        edge_col = mem_db.collection("glossary_edges")

        _upsert_glossary_entry(
            col, edge_col,
            term="TESTTERM", definition="A test term",
            category="acronym", doc_key="doc_recall", doc_name="recall.pdf",
            section_id="sec_1", section_title="Glossary",
        )

        from scripts.glossary.recall import recall_definition
        result = recall_definition("TESTTERM", db=mem_db)
        assert result["found"] is True
        assert result["term"] == "TESTTERM"
        assert len(result["definitions"]) == 1

    def test_recall_not_found(self, mem_db):
        """Test recall_definition when a term is not found."""
        from scripts.glossary.recall import recall_definition
        result = recall_definition("NONEXISTENT_XYZZY_TERM", db=mem_db)
        assert result["found"] is False
