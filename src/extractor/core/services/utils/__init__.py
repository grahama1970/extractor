"""
Module: __init__.py
Description: Package initialization and exports

External Dependencies:
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

# Utils package for marker services
from extractor.core.services.utils.log_utils import (
    truncate_large_value,
    log_safe_results,
    log_api_request,
    log_api_response,
    log_api_error
)

from extractor.core.services.utils.json_utils import (
    clean_json_string,
    parse_json,
    load_json_file,
    save_json_to_file
)

from extractor.core.services.utils.tree_sitter_utils import (
    get_supported_language,
    extract_code_metadata,
    LANGUAGE_MAPPINGS
)

__all__ = [
    # From log_utils
    'truncate_large_value',
    'log_safe_results',
    'log_api_request',
    'log_api_response',
    'log_api_error',

    # From json_utils
    'clean_json_string',
    'parse_json',
    'load_json_file',
    'save_json_to_file',
    
    # From tree_sitter_utils
    'get_supported_language',
    'extract_code_metadata',
    'LANGUAGE_MAPPINGS'
]