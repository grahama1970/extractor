"""
Module: vector_utils.py
Description: Utility functions and helper methods

External Dependencies:
- numpy: https://numpy.org/doc/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import Dict, Any, List, Union, Optional
import numpy as np


def truncate_vector_for_display(
    vector: Union[List[float], np.ndarray], max_items: int = 3, precision: int = 4
) -> str:
    """
    Truncate a vector/embedding for display purposes, showing only the first few items.

    Args:
        vector: The vector to truncate (list or numpy array)
        max_items: Maximum number of items to show
        precision: Number of decimal places to round to

    Returns:
        A string representation like "[0.1234, 0.5678, ... +508 more]"
    """
    if vector is None:
        return "None"

    if isinstance(vector, np.ndarray):
        vector = vector.tolist()

    if not vector:
        return "[]"

    # Format the first few items
    formatted_items = [f"{x:.{precision}f}" for x in vector[:max_items]]
    remaining = len(vector) - max_items

    if remaining > 0:
        return f"[{', '.join(formatted_items)}, ... +{remaining} more]"
    else:
        return f"[{', '.join(formatted_items)}]"


def format_embedding_for_debug(
    embedding_data: Optional[Dict[str, Any]],
    max_vector_items: int = 3,
    precision: int = 4,
) -> str:
    """
    Format embedding data for debug output, truncating the vector component.

    Args:
        embedding_data: The embedding dictionary containing vector and metadata
        max_vector_items: Maximum number of vector items to show
        precision: Number of decimal places for vector values

    Returns:
        A formatted string suitable for debug output
    """
    if embedding_data is None:
        return "None"

    result = {}

    # Copy all non-vector fields as is
    for key, value in embedding_data.items():
        if key != "embedding":
            result[key] = value

    # Truncate the embedding vector if present
    if "embedding" in embedding_data:
        result["embedding"] = truncate_vector_for_display(
            embedding_data["embedding"], max_items=max_vector_items, precision=precision
        )

    return str(result)


def get_vector_stats(vector: Union[List[float], np.ndarray]) -> Dict[str, float]:
    """
    Get basic statistics about a vector for debugging purposes.

    Args:
        vector: The vector to analyze

    Returns:
        Dictionary with basic statistics (min, max, mean, std)
    """
    if vector is None:
        return {}

    if isinstance(vector, list):
        vector = np.array(vector)

    if len(vector) == 0:
        return {}

    return {
        "min": float(np.min(vector)),
        "max": float(np.max(vector)),
        "mean": float(np.mean(vector)),
        "std": float(np.std(vector)),
        "norm": float(np.linalg.norm(vector)),
    }
