from extractor.pipeline.utils.label_normalization import (
    normalize_table_label,
    normalize_figure_label,
)


def test_normalize_table_label_basic():
    assert normalize_table_label("Table 4-1. Pipeline Stages") == "table/4-1"
    assert normalize_table_label("table 4.2a:") == "table/4-2a"
    assert normalize_table_label("TABLE 10–3") == "table/10-3"
    assert normalize_table_label("Figure 1-1") is None


def test_normalize_figure_label_basic():
    assert normalize_figure_label("Figure 3.2b Schematic") == "figure/3-2b"
    assert normalize_figure_label("fig 7-1") == "figure/7-1"
    assert normalize_figure_label("Table 1-1") is None

