#!/usr/bin/env python3
"""
Unit tests for numeric integrity auditor.
"""

import pytest
from extractor.pipeline.utils.numeric_auditor import (
    extract_numeric_literals,
    audit_section_reflow,
    format_audit_report,
)


def test_extract_numeric_literals_integers():
    """Test extraction of integer literals."""
    text = "The values are 42 and 1000 and 7."
    nums = extract_numeric_literals(text)
    
    assert "42" in nums
    assert "1000" in nums
    assert "7" in nums


def test_extract_numeric_literals_decimals():
    """Test extraction of decimal literals."""
    text = "Pi is approximately 3.14 and e is 2.718."
    nums = extract_numeric_literals(text)
    
    assert "3.14" in nums
    assert "2.718" in nums


def test_extract_numeric_literals_with_units():
    """Test extraction of numerics with units."""
    text = "The voltage is 3.3V and current is 2.5A. Max temp: 125°C."
    nums = extract_numeric_literals(text)
    
    assert any("3.3" in n for n in nums)  # May be "3.3" or "3.3V"
    assert any("2.5" in n for n in nums)
    assert any("125" in n for n in nums)


def test_extract_numeric_literals_scientific():
    """Test extraction of scientific notation."""
    text = "Very small: 1.5e-6 and very large: 2.3E+10."
    nums = extract_numeric_literals(text)
    
    assert any("1.5e-6" in n.lower() for n in nums)
    assert any("2.3e+10" in n.lower() for n in nums)


def test_extract_numeric_literals_negative():
    """Test extraction of negative numbers."""
    text = "Temperature dropped to -10 degrees, offset is -3.5."
    nums = extract_numeric_literals(text)
    
    assert "-10" in nums
    assert "-3.5" in nums


def test_extract_numeric_literals_max_samples():
    """Test max_samples parameter limits results."""
    text = "Numbers: 1 2 3 4 5 6 7 8 9 10."
    nums = extract_numeric_literals(text, max_samples=3)
    
    assert len(nums) == 3


def test_audit_perfect_preservation():
    """Test audit with perfect numeric preservation."""
    original = "The voltage is 3.3V and current is 2.5A. Max temp: 125°C."
    reflow = "Voltage: 3.3V, Current: 2.5A. Maximum temperature: 125C."
    
    audit = audit_section_reflow(original, reflow)
    
    # Should have high recall and precision
    assert audit["recall"] >= 0.9
    assert audit["precision"] >= 0.9
    assert audit["confidence_factor"] >= 0.9
    assert len(audit["missing_samples"]) <= 1  # May differ in unit representation


def test_audit_with_missing_numerics():
    """Test audit when some numerics are missing in reflow."""
    original = "Values: 10, 20, 30, 40, 50"
    reflow = "Values: 10, 20, 30"  # Missing 40 and 50
    
    audit = audit_section_reflow(original, reflow)
    
    assert audit["original_count"] == 5
    assert audit["reflow_count"] == 3
    assert audit["matched_count"] == 3
    assert audit["recall"] == 0.6  # 3/5
    assert audit["precision"] == 1.0  # 3/3
    assert len(audit["missing_samples"]) == 2


def test_audit_with_extra_numerics():
    """Test audit when reflow adds extra numerics."""
    original = "Values: 10, 20, 30"
    reflow = "Values: 10, 20, 30, 40, 50"  # Added 40 and 50
    
    audit = audit_section_reflow(original, reflow)
    
    assert audit["original_count"] == 3
    assert audit["reflow_count"] == 5
    assert audit["matched_count"] == 3
    assert audit["recall"] == 1.0  # 3/3
    assert audit["precision"] == 0.6  # 3/5
    assert len(audit["extra_samples"]) == 2


def test_audit_complete_loss():
    """Test audit when all numerics are lost."""
    original = "The values are 10 and 20."
    reflow = "The values are missing."
    
    audit = audit_section_reflow(original, reflow)
    
    assert audit["original_count"] == 2
    assert audit["reflow_count"] == 0
    assert audit["matched_count"] == 0
    assert audit["recall"] == 0.0
    assert audit["precision"] == 1.0  # No false positives
    assert audit["confidence_factor"] == 0.0


def test_audit_empty_original():
    """Test audit when original has no numerics."""
    original = "No numbers here at all."
    reflow = "Still no numbers."
    
    audit = audit_section_reflow(original, reflow)
    
    assert audit["original_count"] == 0
    assert audit["recall"] == 1.0  # Perfect preservation of nothing
    assert audit["confidence_factor"] == 1.0


def test_audit_empty_reflow():
    """Test audit when reflow is empty."""
    original = "Values: 10, 20, 30"
    reflow = ""
    
    audit = audit_section_reflow(original, reflow)
    
    assert audit["original_count"] == 3
    assert audit["reflow_count"] == 0
    assert audit["recall"] == 0.0


def test_audit_case_insensitive():
    """Test that matching is case-insensitive."""
    original = "Value: 3.3V"
    reflow = "Value: 3.3v"  # Lowercase 'v'
    
    audit = audit_section_reflow(original, reflow)
    
    # Should match despite case difference
    assert audit["matched_count"] >= 1
    assert audit["recall"] >= 0.9


def test_audit_confidence_factor_geometric_mean():
    """Test confidence factor is geometric mean of recall and precision."""
    original = "Values: 10, 20, 30, 40"
    reflow = "Values: 10, 20, 50"  # 2 matched, 2 missing, 1 extra
    
    audit = audit_section_reflow(original, reflow)
    
    # Recall: 2/4 = 0.5
    # Precision: 2/3 ≈ 0.667
    # Geometric mean: sqrt(0.5 * 0.667) ≈ 0.577
    
    assert abs(audit["recall"] - 0.5) < 0.01
    assert abs(audit["precision"] - 0.6667) < 0.01
    expected_conf = (0.5 * 0.6667) ** 0.5
    assert abs(audit["confidence_factor"] - expected_conf) < 0.01


def test_format_audit_report_full():
    """Test formatting audit report with missing and extra samples."""
    original = "Values: 10, 20, 30"
    reflow = "Values: 10, 40"
    
    audit = audit_section_reflow(original, reflow, max_samples=10)
    report = format_audit_report(audit)
    
    assert "Numeric Content Audit:" in report
    assert "Original numerics:" in report
    assert "Reflow numerics:" in report
    assert "Recall:" in report
    assert "Precision:" in report
    assert "Missing numerics" in report
    assert "Extra numerics" in report


def test_format_audit_report_perfect():
    """Test formatting report with perfect preservation."""
    original = "Value: 42"
    reflow = "Value: 42"
    
    audit = audit_section_reflow(original, reflow)
    report = format_audit_report(audit)
    
    assert "100%" in report or "1.00" in report  # Perfect recall/precision
    assert "Missing numerics" not in report  # No missing section if empty


def test_audit_with_complex_units():
    """Test audit with complex unit combinations."""
    original = "Frequency: 100MHz, Capacitance: 10µF, Resistance: 1kΩ"
    reflow = "Freq: 100MHz, Cap: 10µF, Res: 1kΩ"
    
    audit = audit_section_reflow(original, reflow)
    
    # Should match all three values
    assert audit["matched_count"] >= 3
    assert audit["recall"] >= 0.9
    assert audit["precision"] >= 0.9


def test_audit_max_samples_limits_output():
    """Test that max_samples limits diagnostic samples."""
    original = "Values: " + ", ".join(str(i) for i in range(1, 21))
    reflow = "Values: 1, 2, 3"  # Only first 3
    
    audit = audit_section_reflow(original, reflow, max_samples=3)
    
    # Should have many missing, but only 3 samples
    assert len(audit["missing_samples"]) <= 3
    assert audit["original_count"] > 10


def test_extract_numeric_literals_empty():
    """Test extraction from empty text."""
    nums = extract_numeric_literals("")
    assert nums == []


def test_extract_numeric_literals_no_numerics():
    """Test extraction from text with no numerics."""
    text = "This text has no numbers at all."
    nums = extract_numeric_literals(text)
    assert nums == []
