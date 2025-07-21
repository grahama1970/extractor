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

from src.generate_schema_for_llm.shared.image_processing_utils import process_image_input

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
        content = message.get('content')
        if (
            isinstance(content, list) and 
            any(item.get("type") == "image_url" for item in content)
        ):
            return True
    return False



def process_messages_for_content(messages: List[Dict[str, Any]], image_directory: str, max_size_kb: int = 500) -> List[Dict[str, Any]]:
    """
    Processes messages to extract text and image content in a structured format.

    Args:
        messages (List[Dict[str, Any]]): List of messages containing text or image inputs.
        image_directory (str): Directory to store compressed images.
        max_size_kb (int): Maximum size for compressed images in KB.

    Returns:
        List[Dict[str, Any]]: Structured content list including text, Base64-encoded images, or external URLs.
    """
    # Early return if no images are found
    if not any("image" in msg for msg in messages):
        return messages
    
    if not messages:
        logger.warning("Received empty messages list. Returning an empty content list.")
        return []

    content_list = []
    for msg in messages:
        if "content" in msg and isinstance(msg["content"], str):  # Handle text content
            content_list.append({"type": "text", "text": msg["content"]})
        elif "image" in msg:  # Handle image content
            try:
                processed_image = process_image_input(msg["image"], image_directory, max_size_kb=max_size_kb)
                content_list.append(processed_image)
            except ValueError as e:
                logger.exception(f"Skipping unsupported image input: {msg['image']} - {e}")
        else:
            logger.warning(f"Unsupported message type detected: {msg}. Skipping.")
    return content_list


def format_multimodal_messages(messages: List[Dict[str, Any]], image_directory: str, max_size_kb: int = 500) -> List[Dict[str, Any]]:
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
                        image_url = item["image_url"]["url"]
                        processed_image = process_image_input(image_url, image_directory, max_size_kb)
                        processed_content.append(processed_image)
                    except ValueError as e:
                        logger.error(f"Error processing image: {image_url} - {e}")
                        continue
            processed_messages.append({"role": message.get("role", "user"), "content": processed_content})
        else:
            logger.warning(f"Unsupported message format detected: {message}. Skipping.")
    return processed_messages





###
# Main Function for Multimodal Processing
###
def prepare_multimodal_messages(
    messages: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Handles multimodal message processing.

    Args:
        messages (List[Dict[str, Any]]): Input messages.
        config (Dict[str, Any]): Configuration dictionary.

    Returns:
        List[Dict[str, Any]]: Processed messages or original messages if processing fails.
    """
    if not messages:
        logger.warning("Empty messages list received. Skipping multimodal processing.")
        return messages

    image_directory = config["directories"]["images"]
    max_image_size_kb = config["llm_config"].get("max_image_size_kb", 500)

    logger.debug("Checking for multimodal content in messages...")
    if is_multimodal(messages):
        logger.info("Multimodal content detected. Processing messages...")
        try:
            processed_messages = format_multimodal_messages(
                messages, image_directory, max_image_size_kb
            )
            logger.info("Multimodal processing completed successfully.")
            return processed_messages
        except Exception as e:
            logger.exception(f"Error during multimodal processing: {e}")
            logger.debug("Falling back to raw messages.")
            return messages
    logger.info("No multimodal content detected. Returning original messages.")
    return messages