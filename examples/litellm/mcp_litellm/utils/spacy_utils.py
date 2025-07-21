"""
Module: spacy_utils.py
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

import spacy
from loguru import logger
from functools import lru_cache
import subprocess
import sys
from pathlib import Path


@lru_cache(maxsize=1)
def get_spacy_model(
    model_name: str = "en_core_web_sm",
    model_url: str = "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0.tar.gz",
):
    """Get cached spaCy model. Download it if not already installed."""
    try:
        # Attempt to load the model
        return spacy.load(model_name)
    except OSError:
        # If the model is not found, download and install it
        logger.info(f"Model '{model_name}' not found. Attempting to install...")
        try:
            # Step 1: Install spaCy using uv
            logger.info("Installing spaCy using uv...")
            subprocess.run(
                [sys.executable, "-m", "uv", "pip", "install", "spacy"], check=True
            )

            # Step 2: Download the model using curl
            logger.info(f"Downloading '{model_name}' model...")
            model_file = Path(model_url.split("/")[-1])  # Extract filename from URL
            subprocess.run(["curl", "-L", "-o", str(model_file), model_url], check=True)

            # Step 3: Install the model using uv
            logger.info(f"Installing '{model_name}' model using uv...")
            subprocess.run(
                [sys.executable, "-m", "uv", "pip", "install", str(model_file)],
                check=True,
            )

            # Clean up the downloaded file
            model_file.unlink()  # Delete the downloaded file
            logger.info("Cleaned up downloaded model file.")

            # Try loading the model again after installation
            logger.info(f"Model '{model_name}' installed successfully.")
            return spacy.load(model_name)

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install '{model_name}': {e}")
            raise


def count_tokens(text: str) -> int:
    """Count tokens in text using cached spaCy model."""
    nlp = get_spacy_model()
    return len(nlp(text))


def truncate_text_by_tokens(text: str, max_tokens: int = 50) -> str:
    """Truncate text to max_tokens while preserving meaning."""
    nlp = get_spacy_model()
    doc = nlp(text)

    if len(doc) <= max_tokens:
        return text

    # Get first and last n/2 tokens
    half_tokens = max_tokens // 2
    start_text = "".join(token.text_with_ws for token in doc[:half_tokens])
    end_text = "".join(token.text_with_ws for token in doc[-half_tokens:])

    return f"{start_text.strip()}... {end_text.strip()}"
