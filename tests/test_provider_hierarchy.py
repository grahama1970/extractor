from pathlib import Path

from extractor.core.providers.markdown import MarkdownProvider
from extractor.core.providers.html import HTMLProvider


def test_markdown_provider_has_hierarchy(tmp_path: Path):
    """Validate the hierarchy of blocks in a Markdown document."""
    md_file = tmp_path / "sample.md"
    md_file.write_text("# Title\nParagraph text")

    provider = MarkdownProvider()
    doc = provider.extract_document(md_file)

    assert doc.hierarchy is not None
    # All blocks should have a parent after normalization
    assert all(getattr(b, "parent_id", None) is not None for b in doc.blocks)


def test_html_provider_hierarchy_fallback(tmp_path: Path):
    """Verify HTMLProvider extracts document hierarchy from simple HTML."""
    html_file = tmp_path / "sample.html"
    html_file.write_text("<html><body><p>hello</p></body></html>")

    provider = HTMLProvider()
    doc = provider.extract_document(html_file)

    assert doc.hierarchy is not None
    assert all(getattr(b, "parent_id", None) is not None for b in doc.blocks)
