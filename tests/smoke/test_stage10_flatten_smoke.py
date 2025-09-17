def test_flatten_document_minimal():
    # dynamic import due to filename starting with digits
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "stage10", "src/extractor/pipeline/steps/10_arangodb_exporter.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    flatten = getattr(mod, "flatten_document_to_pdf_objects")

    pipeline_data = {
        "reflowed_sections": [
            {
                "id": "s1",
                "title": "Intro",
                "level": 1,
                "page_start": 0,
                "bbox": [0, 0, 100, 50],
                "reflow_status": "success",
                "reflowed_text": "Hello world",
                "tables": [
                    {"title": "INFERRED: T1", "headers": ["A"], "page_index": 0, "bbox": [0, 60, 200, 120]}
                ],
                "figures": [
                    {"title": "F1", "ai_description": "desc", "page": 0, "bbox": [0, 130, 100, 200]}
                ],
            }
        ]
    }
    summaries = {
        "summaries": [
            {
                "section_id": "s1",
                "success": True,
                "summary_data": {"summary": "hi", "key_concepts": []},
            }
        ]
    }

    objs = flatten(pipeline_data, summaries)
    assert isinstance(objs, list) and len(objs) >= 3
    # Ensure ordering key and basic fields exist
    assert all("object_index_in_doc" in o for o in objs)
    assert any(o["object_type"] == "Text" for o in objs)
    assert any(o["object_type"] == "Table" for o in objs)
    assert any(o["object_type"] == "Figure" for o in objs)
