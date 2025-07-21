"""
Module: env_utils.py
Description: Utility functions and helper methods

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from pathlib import Path
import os
from dotenv import load_dotenv


def get_project_root(marker_file=".git"):
    """
    Find the project root directory by looking for a marker file.
    
    Args:
        marker_file (str): File/directory to look for (default: ".git")
        
    Returns:
        Path: Project root directory path
        
    Raises:
        RuntimeError: If marker file not found in parent directories
    """
    current_dir = Path(__file__).resolve().parent
    while current_dir != current_dir.root:
        if (current_dir / marker_file).exists():
            return current_dir
        current_dir = current_dir.parent
    raise RuntimeError(f"Could not find project root. Ensure {marker_file} exists.")


def load_env_file(env_type="backend"):
    """
    Load environment variables from a .env file.
    
    Args:
        env_type (str): Type of environment to load (default: "backend")
        
    Raises:
        FileNotFoundError: If .env file not found in expected locations
    """
    project_dir = get_project_root()
    env_dirs = [project_dir, project_dir / "app/backend"]
    
    for env_dir in env_dirs:
        env_file = env_dir / f".env.{env_type}"
        if env_file.exists():
            load_dotenv(env_file)
            print(f"Loaded environment file: {env_file}")
            return
            
    raise FileNotFoundError(f"Environment file .env.{env_type} not found in any known locations.")


if __name__ == '__main__':
    load_env_file()
    print(os.getenv('OPENAI_API_KEY'))
