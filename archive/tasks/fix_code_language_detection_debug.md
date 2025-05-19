# Fix Code Language Detection Debug Script

## Objective
Update and fix the code_language_detection_debug.py script to work with the current marker project structure and properly demonstrate the tree-sitter language detection capabilities.

## Tasks
- [x] Add tree_sitter_utils to marker.services.utils.__init__.py exports
- [x] Fix the tree-sitter imports in code_language_detection_debug.py
- [x] Improve error handling for the loguru dependency in tree_sitter_utils.py
- [x] Update Document and Page initialization to work with current API
- [x] Fix code block handling to work with current project structure
- [x] Improve error reporting and testing for language detection
- [x] Make the script robust to handling edge cases (like SQL language)
- [x] Ensure all tests pass with the updated code

## Changes Made
1. Updated `marker/services/utils/__init__.py` to properly export tree-sitter utilities
2. Added fallback for the loguru dependency in `tree_sitter_utils.py`
3. Fixed document and page creation to match current API requirements
4. Fixed polygon box requirements for proper block creation
5. Improved test cases to handle unsupported languages like SQL
6. Added better error reporting and debug information
7. Made test logic more resilient to failures

## Results
The script now correctly demonstrates both tree-sitter and heuristic language detection for code blocks in various languages, providing detailed information about detection results and confidence.

All tests are passing, with proper handling of edge cases like unsupported languages.