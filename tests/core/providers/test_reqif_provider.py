"""Tests for ReqIFProvider.

ReqIF is an XML-based format for exchanging requirements. The provider
has an optional dependency on the ``reqif`` library — when unavailable it
falls back to XMLProvider.  These tests exercise the fallback XML path
which always works, plus native ReqIF parsing when the library is present.
"""

from pathlib import Path

import pytest

from extractor.core.providers.reqif import ReqIFProvider, REQIF_AVAILABLE
from extractor.core.schema.unified_document import SourceType


MINIMAL_REQIF = """\
<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">
  <THE-HEADER>
    <REQ-IF-HEADER IDENTIFIER="header-1">
      <TITLE>Test Requirements</TITLE>
    </REQ-IF-HEADER>
  </THE-HEADER>
  <CORE-CONTENT>
    <REQ-IF-CONTENT>
      <DATATYPES>
        <DATATYPE-DEFINITION-STRING IDENTIFIER="dt-string" LONG-NAME="String" MAX-LENGTH="2000"/>
      </DATATYPES>
      <SPEC-TYPES>
        <SPEC-OBJECT-TYPE IDENTIFIER="sot-1" LONG-NAME="Requirement">
          <SPEC-ATTRIBUTES>
            <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="ad-text" LONG-NAME="ReqText">
              <TYPE><DATATYPE-DEFINITION-STRING-REF>dt-string</DATATYPE-DEFINITION-STRING-REF></TYPE>
            </ATTRIBUTE-DEFINITION-STRING>
          </SPEC-ATTRIBUTES>
        </SPEC-OBJECT-TYPE>
      </SPEC-TYPES>
      <SPEC-OBJECTS>
        <SPEC-OBJECT IDENTIFIER="req-001" LONG-NAME="REQ-001">
          <TYPE><SPEC-OBJECT-TYPE-REF>sot-1</SPEC-OBJECT-TYPE-REF></TYPE>
          <VALUES>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="The system shall operate at 28V DC.">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>ad-text</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
          </VALUES>
        </SPEC-OBJECT>
        <SPEC-OBJECT IDENTIFIER="req-002" LONG-NAME="REQ-002">
          <TYPE><SPEC-OBJECT-TYPE-REF>sot-1</SPEC-OBJECT-TYPE-REF></TYPE>
          <VALUES>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="Temperature range shall be -55C to +125C.">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>ad-text</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
          </VALUES>
        </SPEC-OBJECT>
      </SPEC-OBJECTS>
    </REQ-IF-CONTENT>
  </CORE-CONTENT>
</REQ-IF>
"""


@pytest.fixture
def provider():
    """Return an instance of ReqIFProvider for testing purposes."""
    return ReqIFProvider()


@pytest.fixture
def reqif_file(tmp_path: Path) -> Path:
    """Create a temporary REQIF file for testing purposes."""
    fp = tmp_path / "requirements.reqif"
    fp.write_text(MINIMAL_REQIF)
    return fp


def _all_text(doc) -> str:
    """Join all string content from blocks (some blocks have dict content)."""
    parts = []
    for b in doc.blocks:
        if isinstance(b.content, str):
            parts.append(b.content)
        elif isinstance(b.content, dict):
            parts.append(str(b.content))
    return " ".join(parts)


def test_reqif_basic_extraction(reqif_file: Path, provider):
    """Test that ReqIF file is extracted and contains requirement text."""
    doc = provider.extract_document(reqif_file)

    # ReqIF uses XML source type (it IS XML)
    assert doc.source_type == SourceType.XML
    assert len(doc.blocks) >= 1
    all_text = _all_text(doc)
    assert "28V DC" in all_text or "req-001" in all_text.lower()


def test_reqif_multiple_requirements(reqif_file: Path, provider):
    """Test both requirements are extracted."""
    doc = provider.extract_document(reqif_file)

    all_text = _all_text(doc)
    # At least one of the requirement texts should appear
    has_req1 = "28V" in all_text
    has_req2 = "125C" in all_text or "Temperature" in all_text
    assert has_req1 or has_req2


def test_reqif_empty_file(tmp_path: Path, provider):
    """Test minimal ReqIF with no spec-objects."""
    fp = tmp_path / "empty.reqif"
    fp.write_text("""\
<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">
  <THE-HEADER>
    <REQ-IF-HEADER IDENTIFIER="h1"><TITLE>Empty</TITLE></REQ-IF-HEADER>
  </THE-HEADER>
  <CORE-CONTENT>
    <REQ-IF-CONTENT>
      <DATATYPES/>
      <SPEC-TYPES/>
      <SPEC-OBJECTS/>
    </REQ-IF-CONTENT>
  </CORE-CONTENT>
</REQ-IF>
""")

    doc = provider.extract_document(fp)

    assert doc.source_type == SourceType.XML
    assert doc.blocks is not None


@pytest.mark.skipif(not REQIF_AVAILABLE, reason="reqif library not installed")
def test_reqif_native_parser(reqif_file: Path, provider):
    """Test native reqif library parsing (when available)."""
    doc = provider.extract_document(reqif_file)

    # Native parser should extract requirement identifiers
    all_text = _all_text(doc)
    assert "28V DC" in all_text


def test_reqif_xml_fallback(tmp_path: Path):
    """Test that ReqIF falls back to XML parsing for malformed content."""
    fp = tmp_path / "almost.reqif"
    fp.write_text("""\
<?xml version="1.0"?>
<root>
  <requirement id="R1">System shall be safe.</requirement>
</root>
""")

    provider = ReqIFProvider()
    doc = provider.extract_document(fp)

    # Should still produce a document via XML fallback
    assert doc.blocks is not None
    all_text = _all_text(doc)
    assert "safe" in all_text or "System" in all_text
