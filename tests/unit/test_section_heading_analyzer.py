#!/usr/bin/env python3
"""
Unit tests for section heading anomaly analyzer.
"""

import pytest
from extractor.pipeline.utils.section_heading_analyzer import (
    analyze_section_headings,
    format_anomaly_report,
)


def test_analyze_clean_hierarchy():
    """Test analysis of clean section hierarchy with no anomalies."""
    sections = [
        {"id": "s1", "title": "Introduction", "level": 1},
        {"id": "s2", "title": "Background", "level": 2},
        {"id": "s3", "title": "Methods", "level": 2},
        {"id": "s4", "title": "Results", "level": 1},
    ]
    
    result = analyze_section_headings(sections)
    
    assert result["total_sections"] == 4
    assert result["anomaly_count"] == 0
    assert result["confidence_factor"] == 1.0
    assert len(result["anomalies"]) == 0


def test_analyze_level_jump():
    """Test detection of level jump anomaly."""
    sections = [
        {"id": "s1", "title": "Introduction", "level": 1},
        {"id": "s2", "title": "Deep Subsection", "level": 3},  # Jump from 1 to 3
    ]
    
    result = analyze_section_headings(sections)
    
    assert result["anomaly_count"] == 1
    assert result["anomalies"][0]["type"] == "level_jump"
    assert result["anomalies"][0]["from_level"] == 1
    assert result["anomalies"][0]["to_level"] == 3
    assert result["anomalies"][0]["severity"] == "moderate"
    assert result["confidence_factor"] < 1.0


def test_analyze_multiple_level_jumps():
    """Test multiple level jump anomalies."""
    sections = [
        {"id": "s1", "title": "Root", "level": 1},
        {"id": "s2", "title": "Jump 1", "level": 3},  # Jump 1->3
        {"id": "s3", "title": "Jump 2", "level": 1},
        {"id": "s4", "title": "Jump 3", "level": 4},  # Jump 1->4
    ]
    
    result = analyze_section_headings(sections)
    
    jumps = [a for a in result["anomalies"] if a["type"] == "level_jump"]
    assert len(jumps) == 2
    # Confidence should be lower with multiple jumps
    assert result["confidence_factor"] < 0.95


def test_analyze_wrapper_heading():
    """Test detection of wrapper heading anomaly."""
    sections = [
        {"id": "s1", "title": "REQUIREMENTS (Simulated)", "level": 1},
        {"id": "s2", "title": "Normal Section", "level": 2},
    ]
    
    result = analyze_section_headings(sections)
    
    assert result["anomaly_count"] >= 1
    wrapper_anomalies = [a for a in result["anomalies"] if a["type"] == "wrapper_heading"]
    assert len(wrapper_anomalies) == 1
    assert wrapper_anomalies[0]["title"] == "REQUIREMENTS (Simulated)"
    assert wrapper_anomalies[0]["severity"] == "minor"


def test_analyze_continued_wrapper():
    """Test detection of '- Continued' wrapper pattern."""
    sections = [
        {"id": "s1", "title": "Some Section - Continued", "level": 1},
        {"id": "s2", "title": "Normal Section", "level": 2},
    ]
    
    result = analyze_section_headings(sections)
    
    wrapper_anomalies = [a for a in result["anomalies"] if a["type"] == "wrapper_heading"]
    assert len(wrapper_anomalies) >= 1


def test_analyze_colon_short_heading():
    """Test detection of short colon-ending heading."""
    sections = [
        {"id": "s1", "title": "Introduction", "level": 1},
        {"id": "s2", "title": "Background:", "level": 2},  # Short colon
        {"id": "s3", "title": "Methods", "level": 2},
    ]
    
    result = analyze_section_headings(sections)
    
    colon_anomalies = [a for a in result["anomalies"] if a["type"] == "colon_short"]
    assert len(colon_anomalies) == 1
    assert colon_anomalies[0]["title"] == "Background:"
    assert colon_anomalies[0]["length"] == 11
    assert colon_anomalies[0]["severity"] == "minor"


def test_analyze_long_colon_not_flagged():
    """Test that long colon-ending headings are NOT flagged."""
    sections = [
        {"id": "s1", "title": "This is a very long section heading that ends with a colon:", "level": 1},
    ]
    
    result = analyze_section_headings(sections, max_colon_length=40)
    
    colon_anomalies = [a for a in result["anomalies"] if a["type"] == "colon_short"]
    assert len(colon_anomalies) == 0


def test_analyze_combined_anomalies():
    """Test section with multiple types of anomalies."""
    sections = [
        {"id": "s1", "title": "Introduction", "level": 1},
        {"id": "s2", "title": "REQUIREMENTS (Simulated)", "level": 1},  # Wrapper
        {"id": "s3", "title": "Details:", "level": 3},  # Level jump + colon
    ]
    
    result = analyze_section_headings(sections)
    
    # Should have at least 3 anomalies (wrapper, jump, colon)
    assert result["anomaly_count"] >= 3
    
    # Confidence should be notably reduced
    assert result["confidence_factor"] < 0.9
    
    # Check severity breakdown
    assert "minor" in result["severity_breakdown"]
    assert "moderate" in result["severity_breakdown"]


def test_analyze_empty_sections():
    """Test analysis with empty section list."""
    result = analyze_section_headings([])
    
    assert result["total_sections"] == 0
    assert result["anomaly_count"] == 0
    assert result["confidence_factor"] == 1.0
    assert result["anomalies"] == []


def test_analyze_single_section():
    """Test analysis with single section (no comparisons possible)."""
    sections = [
        {"id": "s1", "title": "Only Section", "level": 1},
    ]
    
    result = analyze_section_headings(sections)
    
    # No level jumps possible with single section
    assert result["total_sections"] == 1
    # May still flag wrapper or colon anomalies
    assert result["confidence_factor"] >= 0.9


def test_confidence_factor_calculation():
    """Test confidence factor penalty calculation."""
    # Minor anomaly: -0.02
    sections_minor = [
        {"id": "s1", "title": "Test:", "level": 1},  # Colon short (minor)
    ]
    result_minor = analyze_section_headings(sections_minor)
    assert result_minor["confidence_factor"] == 0.98
    
    # Moderate anomaly: -0.05
    sections_moderate = [
        {"id": "s1", "title": "Test", "level": 1},
        {"id": "s2", "title": "Test", "level": 3},  # Level jump (moderate)
    ]
    result_moderate = analyze_section_headings(sections_moderate)
    assert result_moderate["confidence_factor"] == 0.95


def test_confidence_factor_floor():
    """Test that confidence factor has floor of 0.50."""
    # Create many anomalies to exceed floor
    sections = []
    for i in range(20):
        sections.append({"id": f"s{i}", "title": f"Section {i}:", "level": 1 + (i % 2) * 3})
    
    result = analyze_section_headings(sections)
    
    # Should hit floor despite many anomalies
    assert result["confidence_factor"] >= 0.50
    assert result["anomaly_count"] > 10


def test_format_anomaly_report():
    """Test formatting of anomaly report."""
    sections = [
        {"id": "s1", "title": "Test", "level": 1},
        {"id": "s2", "title": "Test", "level": 3},  # Level jump
    ]
    
    result = analyze_section_headings(sections)
    report = format_anomaly_report(result)
    
    assert "Total sections: 2" in report
    assert "Anomalies found:" in report
    assert "Confidence factor:" in report
    assert "level_jump" in report
    assert "Detailed Anomalies:" in report


def test_custom_wrapper_patterns():
    """Test with custom wrapper patterns."""
    sections = [
        {"id": "s1", "title": "Custom Wrapper Pattern", "level": 1},
    ]
    
    custom_patterns = [r"custom wrapper pattern"]
    result = analyze_section_headings(sections, wrapper_patterns=custom_patterns)
    
    wrapper_anomalies = [a for a in result["anomalies"] if a["type"] == "wrapper_heading"]
    assert len(wrapper_anomalies) == 1
    assert wrapper_anomalies[0]["pattern"] == r"custom wrapper pattern"
