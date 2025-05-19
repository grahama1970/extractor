import os
import pytest
import json
from unittest.mock import patch, MagicMock
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables from .env files
load_dotenv()

from marker.services.litellm import LiteLLMService
from marker.schema.blocks.base import Block
from marker.schema.blocks.text import Text
from marker.schema.text.span import Span
from marker.schema.text.line import Line
from pydantic import BaseModel


class TestSchema(BaseModel):
    text: str


@pytest.fixture
def mock_image():
    return MagicMock()


@pytest.fixture
def mock_block():
    block = MagicMock(spec=Block)
    block.update_metadata = MagicMock()
    return block


@pytest.fixture
def litellm_service():
    return LiteLLMService(
        config={
            "litellm_api_key": "test_key",
            "litellm_model": "openai/gpt-4o-mini",
        }
    )


def test_init():
    service = LiteLLMService(
        config={
            "litellm_api_key": "test_key",
            "litellm_model": "openai/gpt-4o-mini",
        }
    )
    assert service.litellm_api_key == "test_key"
    assert service.litellm_model == "openai/gpt-4o-mini"


def test_vertex_model_format():
    service = LiteLLMService(
        config={
            "litellm_api_key": "test_key",
            "litellm_model": "vertex/gemini-pro-vision",
        }
    )
    assert service.litellm_model == "vertex/gemini-pro-vision"


@patch("litellm.completion")
def test_call(mock_completion, litellm_service, mock_image, mock_block):
    # Setup the mock completion response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"text": "mock response"}'
    mock_response.usage.total_tokens = 100
    mock_completion.return_value = mock_response

    # Setup image preparation mock
    litellm_service.prepare_images = MagicMock(return_value=[{"type": "image_url", "image_url": {"url": "data:image/webp;base64,testbase64"}}])

    # Call the service
    result = litellm_service(
        prompt="Test prompt",
        image=mock_image,
        block=mock_block,
        response_schema=TestSchema,
    )

    # Verify the result
    assert result == {"text": "mock response"}
    mock_block.update_metadata.assert_called_once_with(llm_tokens_used=100, llm_request_count=1)

    # Verify litellm.completion was called with the correct arguments
    mock_completion.assert_called_once()
    args, kwargs = mock_completion.call_args
    assert kwargs["model"] == "openai/gpt-4o-mini"
    assert kwargs["api_key"] == "test_key"
    assert kwargs["timeout"] == 30  # Default timeout
    assert kwargs["messages"][0]["role"] == "user"
    assert kwargs["response_format"]["type"] == "json_object"
    assert "schema" in kwargs["response_format"]
    assert kwargs["extra_headers"] == {
        "X-Title": "Marker",
        "HTTP-Referer": "https://github.com/VikParuchuri/marker",
    }


def functional_test_litellm_service():
    """
    Functional test for LiteLLM service using real data without mocking core functionality.

    This function tests the LiteLLM service with a real text block and image.
    It verifies that:
    1. The service can be instantiated correctly
    2. The image preparation works as expected
    3. A real call can be made to the LiteLLM service if API key is provided

    NOTE: This test is skipped by default as it requires an API key. To run it,
    set the OPENAI_API_KEY environment variable.
    """
    # Track validation failures
    validation_failures = []
    total_tests = 0

    # Test 1: Test service initialization
    total_tests += 1
    try:
        # Get API key from environment variable
        api_key = os.environ.get("OPENAI_API_KEY", "dummy_key_for_testing")

        # Create service
        service = LiteLLMService(
            config={
                "litellm_api_key": api_key,
                "litellm_model": "openai/gpt-4o-mini",
            }
        )

        assert service.litellm_api_key == api_key
        assert service.litellm_model == "openai/gpt-4o-mini"
        print("✓ Service initialization test passed")
    except Exception as e:
        validation_failures.append(f"Service initialization test failed: {e}")
        print(f"✗ Service initialization test failed: {e}")

    # Test 2: Test image preparation
    total_tests += 1
    try:
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')

        # Test image preparation
        result = service.prepare_images(img)

        # Validate result
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "image_url"
        assert "image_url" in result[0]
        assert "url" in result[0]["image_url"]
        assert result[0]["image_url"]["url"].startswith("data:image/webp;base64,")
        print("✓ Image preparation test passed")
    except Exception as e:
        validation_failures.append(f"Image preparation test failed: {e}")
        print(f"✗ Image preparation test failed: {e}")

    # Test 3: Create a real text block
    total_tests += 1
    try:
        # Create a real text block
        spans = [Span(text="This is a test span")]
        line = Line(spans=spans)
        text_block = Text(lines=[line], id="/test/Text/1", polygon=[[0, 0], [100, 0], [100, 100], [0, 100]])

        # Just verify that we can create the block
        assert text_block.id == "/test/Text/1"
        assert len(text_block.lines) == 1
        assert text_block.lines[0].spans[0].text == "This is a test span"
        print("✓ Text block creation test passed")
    except Exception as e:
        validation_failures.append(f"Text block creation test failed: {e}")
        print(f"✗ Text block creation test failed: {e}")

    # Test 4: Test actual API call (only if API key is available and not a dummy key)
    if api_key != "dummy_key_for_testing":
        total_tests += 1
        try:
            class SimpleTestSchema(BaseModel):
                description: str

            # Make a real API call
            result = service(
                prompt="Describe this test image in one sentence.",
                image=img,
                block=text_block,
                response_schema=SimpleTestSchema,
            )

            # Verify the result
            assert isinstance(result, dict)
            assert "description" in result
            assert isinstance(result["description"], str)
            assert len(result["description"]) > 0
            print(f"✓ Actual API call test passed. Result: {result}")
        except Exception as e:
            validation_failures.append(f"Actual API call test failed: {e}")
            print(f"✗ Actual API call test failed: {e}")
    else:
        print("ℹ Skipping actual API call test (no API key provided)")

    # Final validation results
    if validation_failures:
        print(f"\n❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed:")
        for failure in validation_failures:
            print(f"  - {failure}")
        return False
    else:
        print(f"\n✅ VALIDATION PASSED - All {total_tests} tests passed")
        return True


if __name__ == "__main__":
    # Run the functional test directly if this file is executed
    functional_test_litellm_service()