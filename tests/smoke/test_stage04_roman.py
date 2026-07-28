from extractor.pipeline.steps import s04_section_builder as s04


def test_roman_map_D_is_500():
    """Test Roman numeral to integer conversion."""
    assert s04._roman_to_int("D") == 500
    assert s04._roman_to_int("IV") == 4
    assert s04._roman_to_int("XL") == 40
