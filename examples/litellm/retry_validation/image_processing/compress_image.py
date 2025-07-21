"""
Module: compress_image.py

External Dependencies:
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from loguru import logger
import os
from PIL import Image

def compress_image(image_path: str, image_directory: str, max_size_kb: int, max_attempts: int = 5, resize_step: int = 10) -> str:
    """
    Compress and resize an image file to be under the size threshold.

    Args:
        image_path (str): Path to the original image file.
        image_directory (str): Directory to store compressed images.
        max_size_kb (int): Maximum size allowed for the compressed image in KB.
        max_attempts (int): Maximum number of compression attempts.
        resize_step (int): Percentage step to reduce image dimensions during resizing.

    Returns:
        str: Path to the compressed image file, or the original image if compression failed.
    """
    os.makedirs(image_directory, exist_ok=True)  # Ensure directory exists
    original_file_name = os.path.basename(image_path)
    compressed_file_path = os.path.join(image_directory, f"{os.path.splitext(original_file_name)[0]}_compressed.jpg")

    # If compressed file already exists, return its path
    if os.path.exists(compressed_file_path):
        return compressed_file_path

    try:
        img = Image.open(image_path)
        img_format = img.format or "JPEG"  # Default to JPEG if format is unknown
        quality = 90  # Initial compression quality
        width, height = img.size  # Original dimensions

        for attempt in range(max_attempts):
            # Save the image with current quality and dimensions
            img.save(compressed_file_path, format=img_format, quality=quality, optimize=True)
            compressed_size_kb = os.path.getsize(compressed_file_path) / 1024

            if compressed_size_kb <= max_size_kb:
                return compressed_file_path

            # If compression alone doesn't work, reduce dimensions
            if attempt < max_attempts - 1:  # Avoid resizing on the last attempt
                width = int(width * (1 - resize_step / 100))
                height = int(height * (1 - resize_step / 100))
                img = img.resize((width, height), Image.LANCZOS)
                logger.info(f"Resizing image to {width}x{height} for attempt {attempt + 1}.")

            quality = max(10, quality - 10)  # Reduce quality for further compression

        logger.warning(f"Could not compress {image_path} under {max_size_kb}KB after {max_attempts} attempts.")
        return image_path
    except Exception as e:
        logger.exception(f"Error compressing image {image_path}: {e}")
        return image_path