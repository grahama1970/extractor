"""Path validation utilities for security."""

from pathlib import Path


def validate_safe_path(user_path: str, base_dir: str = None) -> Path:
    """Validate that a path is safe from traversal attacks.

    Args:
        user_path: The user-provided path
        base_dir: Optional base directory to restrict to

    Returns:
        Resolved safe Path object

    Raises:
        ValueError: If path is unsafe
    """
    # Resolve to absolute path
    path = Path(user_path).resolve()

    # Check for suspicious patterns
    path_str = str(path)
    if ".." in user_path or path_str.count("/") > 20:
        raise ValueError(f"Suspicious path pattern: {user_path}")

    # If base_dir provided, ensure path is within it
    if base_dir:
        base = Path(base_dir).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            raise ValueError(f"Path {user_path} is outside allowed directory {base_dir}")

    return path
