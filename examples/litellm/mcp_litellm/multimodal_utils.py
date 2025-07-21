"""
Module: multimodal_utils.py
Description: Utility functions and helper methods

External Dependencies:
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import List, Dict, Any
from loguru import logger


###
# Helper Functions
###
def is_multimodal(messages: List[Dict[str, Any]]) -> bool:
    """
    Determine if the messages list contains multimodal content (e.g., images).

    Args:
        messages (List[Dict[str, Any]]): List of message dictionaries.

    Returns:
        bool: True if any message contains multimodal content, False otherwise.
    """
    for message in messages:
        content = message.get("content")
        if isinstance(content, list) and any(
            item.get("type") == "image_url" for item in content
        ):
            return True
    return False


def format_multimodal_messages(
    messages: List[Dict[str, Any]], image_directory: str, max_size_kb: int = 500
) -> List[Dict[str, Any]]:
    """
    Processes a messages list to extract and format content for LLM input.

    Args:
        messages (List[Dict[str, Any]]): List of messages, each containing multimodal content.
        image_directory (str): Directory to store compressed images.
        max_size_kb (int): Maximum size for compressed images in KB.

    Returns:
        List[Dict[str, Any]]: Processed list of content dictionaries.
    """
    if not messages:
        logger.warning("Received empty messages list. Returning an empty content list.")
        return []

    processed_messages = []
    for message in messages:
        if "content" in message and isinstance(message["content"], list):
            processed_content = []
            for item in message["content"]:
                if item.get("type") == "text":
                    processed_content.append({"type": "text", "text": item["text"]})
                elif item.get("type") == "image_url":
                    try:
                        # Extract the URL directly from the nested structure
                        image_url = item["image_url"]["url"]
                        # Format it correctly for the API
                        processed_content.append(
                            {"type": "image_url", "url": image_url}
                        )
                    except ValueError as e:
                        logger.error(f"Error processing image: {image_url} - {e}")
                        continue
            processed_messages.append(
                {"role": message.get("role", "user"), "content": processed_content}
            )
        else:
            # If not multimodal content, pass through unchanged
            processed_messages.append(message)
    return processed_messages
