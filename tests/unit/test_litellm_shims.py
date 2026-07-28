

def test_litellm_response_utils_reexports_extract_content():
    """Assert `litellm_response_utils` re-exports `extract_content`."""
    import extractor.pipeline.utils.response_utils as ru
    import extractor.pipeline.utils.litellm_response_utils as lru

    assert hasattr(lru, "extract_content")
    # Re-export should point to the same function object
    assert lru.extract_content is ru.extract_content


def test_litellm_image_utils_reexports_helpers():
    """Verify re-export of image helper functions."""
    import extractor.pipeline.utils.image_helpers as ih
    import extractor.pipeline.utils.litellm_image_utils as lih

    for name in ("compress_image_cached", "fetch_remote_image_cached", "extract_images"):
        assert hasattr(lih, name)
        assert getattr(lih, name) is getattr(ih, name)
