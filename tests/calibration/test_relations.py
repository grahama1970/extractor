"""Tests for relation annotation module."""

from unittest.mock import MagicMock, patch


from extractor.pipeline.calibration.relations import (
    AnnotatedRelation,
    RelationDetector,
    RelationHandler,
    RelationProposal,
    RelationType,
    format_relation_summary,
    parse_relation_response,
)


class TestRelationType:
    """Tests for RelationType enum."""

    def test_relation_types_exist(self):
        """Test all expected relation types exist."""
        assert RelationType.PARENT_CHILD.value == "parent_child"
        assert RelationType.CAPTION_OF.value == "caption_of"
        assert RelationType.REFERENCES.value == "references"
        assert RelationType.CONTINUES.value == "continues"
        assert RelationType.RELATED.value == "related"


class TestRelationProposal:
    """Tests for RelationProposal dataclass."""

    def test_format_question_parent_child(self):
        """Test formatting parent-child relation question."""
        proposal = RelationProposal(
            relation_type=RelationType.PARENT_CHILD,
            source_element={"element_type": "header", "text": "3. Methods"},
            target_element={"element_type": "header", "text": "3.1 Data Collection"},
            confidence=0.9,
            reasoning="Section numbering indicates hierarchy",
        )

        question = proposal.format_question()
        assert "child of" in question.lower()
        assert "3.1 Data Collection" in question
        assert "3. Methods" in question
        assert "(yes/no/skip)" in question

    def test_format_question_caption_of(self):
        """Test formatting caption-of relation question."""
        proposal = RelationProposal(
            relation_type=RelationType.CAPTION_OF,
            source_element={"element_type": "text", "text": "Figure 1: Architecture diagram"},
            target_element={"element_type": "figure", "page_num": 5},
            confidence=0.85,
            reasoning="Text starts with 'Figure 1'",
        )

        question = proposal.format_question()
        assert "caption" in question.lower()
        assert "Figure 1" in question

    def test_describe_element_with_text(self):
        """Test element description with text."""
        proposal = RelationProposal(
            relation_type=RelationType.PARENT_CHILD,
            source_element={"element_type": "header", "text": "Introduction"},
            target_element={"element_type": "header", "text": "Background"},
            confidence=0.8,
            reasoning="Test",
        )

        desc = proposal._describe_element({"element_type": "header", "text": "Introduction"})
        assert "header" in desc.lower()
        assert "Introduction" in desc

    def test_describe_element_without_text(self):
        """Test element description without text."""
        proposal = RelationProposal(
            relation_type=RelationType.CAPTION_OF,
            source_element={},
            target_element={"element_type": "figure", "page_num": 3},
            confidence=0.8,
            reasoning="Test",
        )

        desc = proposal._describe_element({"element_type": "figure", "page_num": 3})
        assert "figure" in desc.lower()
        assert "page 3" in desc.lower()


class TestRelationDetector:
    """Tests for RelationDetector class."""

    def test_propose_header_hierarchy(self):
        """Test detecting header parent-child relationships."""
        detector = RelationDetector()
        elements = [
            {"element_type": "header", "text": "1. Introduction", "page_num": 1, "element_idx": 0},
            {"element_type": "header", "text": "1.1 Background", "page_num": 1, "element_idx": 1},
            {"element_type": "header", "text": "1.2 Motivation", "page_num": 1, "element_idx": 2},
            {"element_type": "header", "text": "2. Methods", "page_num": 2, "element_idx": 3},
        ]

        proposals = detector.propose_relations(elements)

        # Should propose 1.1 as child of 1, and 1.2 as child of 1
        parent_child_proposals = [
            p for p in proposals if p.relation_type == RelationType.PARENT_CHILD
        ]
        assert len(parent_child_proposals) >= 2

    def test_propose_header_hierarchy_deep(self):
        """Test detecting deep header hierarchy."""
        detector = RelationDetector()
        elements = [
            {"element_type": "header", "text": "3. Methods", "page_num": 1, "element_idx": 0},
            {"element_type": "header", "text": "3.2 Analysis", "page_num": 1, "element_idx": 1},
            {
                "element_type": "header",
                "text": "3.2.1 Statistical Tests",
                "page_num": 2,
                "element_idx": 2,
            },
        ]

        proposals = detector.propose_relations(elements)

        # Should propose 3.2.1 as child of 3.2
        found = False
        for p in proposals:
            if p.relation_type == RelationType.PARENT_CHILD:
                if "3.2.1" in str(p.target_element) and "3.2" in str(p.source_element):
                    found = True
                    break
        assert found

    def test_propose_caption_relations(self):
        """Test detecting caption-figure relationships."""
        detector = RelationDetector()
        # Caption below figure (caption y > figure bottom)
        elements = [
            {
                "element_type": "figure",
                "text": "",
                "page_num": 1,
                "element_idx": 0,
                "bbox": [72, 200, 540, 380],
            },
            {
                "element_type": "text",
                "text": "Figure 1: System architecture",
                "page_num": 1,
                "element_idx": 1,
                "bbox": [72, 390, 540, 410],  # Just below the figure
            },
        ]

        proposals = detector.propose_relations(elements)

        caption_proposals = [p for p in proposals if p.relation_type == RelationType.CAPTION_OF]
        # Caption detection looks for text starting with "Figure X" near a figure
        assert len(caption_proposals) >= 1

    def test_max_proposals_limit(self):
        """Test that max_proposals is respected."""
        detector = RelationDetector()
        elements = [
            {"element_type": "header", "text": f"{i}. Section {i}", "page_num": 1, "element_idx": i}
            for i in range(1, 20)
        ]

        proposals = detector.propose_relations(elements, max_proposals=5)
        assert len(proposals) <= 5


class TestParseRelationResponse:
    """Tests for parse_relation_response function."""

    def test_parse_yes(self):
        """Test parsing affirmative responses."""
        assert parse_relation_response("yes")[0] == "yes"
        assert parse_relation_response("y")[0] == "yes"
        assert parse_relation_response("Yes")[0] == "yes"
        assert parse_relation_response("correct")[0] == "yes"
        assert parse_relation_response("that's right")[0] == "yes"
        assert parse_relation_response("looks good")[0] == "yes"

    def test_parse_no(self):
        """Test parsing negative responses."""
        assert parse_relation_response("no")[0] == "no"
        assert parse_relation_response("n")[0] == "no"
        assert parse_relation_response("No")[0] == "no"
        assert parse_relation_response("wrong")[0] == "no"
        assert parse_relation_response("incorrect")[0] == "no"

    def test_parse_skip(self):
        """Test parsing skip responses."""
        assert parse_relation_response("skip")[0] == "skip"
        assert parse_relation_response("pass")[0] == "skip"
        assert parse_relation_response("unsure")[0] == "skip"
        assert parse_relation_response("not sure")[0] == "skip"

    def test_parse_with_note(self):
        """Test parsing responses with notes."""
        verdict, note = parse_relation_response("yes, they are definitely related")
        assert verdict == "yes"
        assert note == "they are definitely related"

        verdict, note = parse_relation_response("no, different sections")
        assert verdict == "no"
        assert note == "different sections"

    def test_parse_unclear(self):
        """Test parsing unclear responses defaults to skip."""
        verdict, note = parse_relation_response("I think so maybe")
        assert verdict == "skip"
        assert "Unclear" in note


class TestAnnotatedRelation:
    """Tests for AnnotatedRelation dataclass."""

    def test_create_relation(self):
        """Test creating an annotated relation."""
        relation = AnnotatedRelation(
            relation_type=RelationType.PARENT_CHILD,
            source_id="elem_001",
            target_id="elem_002",
            confirmed_by="human",
            note="Clear hierarchy",
        )

        assert relation.relation_type == RelationType.PARENT_CHILD
        assert relation.source_id == "elem_001"
        assert relation.target_id == "elem_002"
        assert relation.confirmed_by == "human"
        assert relation.confidence == 1.0


class TestRelationHandler:
    """Tests for RelationHandler class."""

    @patch("extractor.pipeline.calibration.relations.CalibrationSchema")
    def test_save_relation(self, mock_schema_class):
        """Test saving a relation."""
        mock_schema = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.insert.return_value = {"_key": "rel_001"}
        mock_db.collection.return_value = mock_coll
        mock_db.has_collection.return_value = True
        mock_schema.db = mock_db
        mock_schema_class.return_value = mock_schema

        handler = RelationHandler(mock_schema)
        relation = AnnotatedRelation(
            relation_type=RelationType.CAPTION_OF,
            source_id="text_001",
            target_id="fig_001",
        )

        key = handler.save_relation("session_001", relation)
        assert key == "rel_001"
        mock_coll.insert.assert_called_once()

    @patch("extractor.pipeline.calibration.relations.CalibrationSchema")
    def test_get_session_relations(self, mock_schema_class):
        """Test getting relations for a session."""
        mock_schema = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.find.return_value = [
            {"relation_type": "parent_child", "source_id": "h1", "target_id": "h2"},
            {"relation_type": "caption_of", "source_id": "t1", "target_id": "f1"},
        ]
        mock_db.collection.return_value = mock_coll
        mock_db.has_collection.return_value = True
        mock_schema.db = mock_db
        mock_schema_class.return_value = mock_schema

        handler = RelationHandler(mock_schema)
        relations = handler.get_session_relations("session_001")

        assert len(relations) == 2

    @patch("extractor.pipeline.calibration.relations.CalibrationSchema")
    def test_get_relation_stats(self, mock_schema_class):
        """Test getting relation statistics."""
        mock_schema = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.find.return_value = [
            {"relation_type": "parent_child"},
            {"relation_type": "parent_child"},
            {"relation_type": "caption_of"},
        ]
        mock_db.collection.return_value = mock_coll
        mock_db.has_collection.return_value = True
        mock_schema.db = mock_db
        mock_schema_class.return_value = mock_schema

        handler = RelationHandler(mock_schema)
        stats = handler.get_relation_stats("session_001")

        assert stats["parent_child"] == 2
        assert stats["caption_of"] == 1


class TestFormatRelationSummary:
    """Tests for format_relation_summary function."""

    def test_format_empty(self):
        """Test formatting empty relations list."""
        summary = format_relation_summary([])
        assert "No relations" in summary

    def test_format_with_relations(self):
        """Test formatting relations list."""
        relations = [
            {"relation_type": "parent_child", "source_id": "h1", "target_id": "h2"},
            {"relation_type": "parent_child", "source_id": "h1", "target_id": "h3"},
            {"relation_type": "caption_of", "source_id": "t1", "target_id": "f1"},
        ]

        summary = format_relation_summary(relations)
        assert "Parent Child" in summary
        assert "Caption Of" in summary
        assert "h1" in summary
        assert "→" in summary

    def test_format_truncates_long_lists(self):
        """Test that long lists are truncated."""
        relations = [
            {"relation_type": "parent_child", "source_id": f"h{i}", "target_id": f"h{i+1}"}
            for i in range(10)
        ]

        summary = format_relation_summary(relations)
        assert "and 5 more" in summary


class TestRelationDetectorEdgeCases:
    """Edge case tests for RelationDetector."""

    def test_empty_elements(self):
        """Test with empty elements list."""
        detector = RelationDetector()
        proposals = detector.propose_relations([])
        assert proposals == []

    def test_no_headers(self):
        """Test with no headers (no parent-child possible)."""
        detector = RelationDetector()
        elements = [
            {"element_type": "table", "text": "Data table", "page_num": 1, "element_idx": 0},
            {"element_type": "figure", "text": "", "page_num": 1, "element_idx": 1},
        ]

        proposals = detector.propose_relations(elements)
        # Should have no parent-child proposals
        parent_child = [p for p in proposals if p.relation_type == RelationType.PARENT_CHILD]
        assert len(parent_child) == 0

    def test_headers_without_numbers(self):
        """Test headers without section numbers."""
        detector = RelationDetector()
        elements = [
            {"element_type": "header", "text": "Introduction", "page_num": 1, "element_idx": 0},
            {"element_type": "header", "text": "Background", "page_num": 1, "element_idx": 1},
        ]

        proposals = detector.propose_relations(elements)
        # Should have no parent-child proposals (no numbers)
        parent_child = [p for p in proposals if p.relation_type == RelationType.PARENT_CHILD]
        assert len(parent_child) == 0
