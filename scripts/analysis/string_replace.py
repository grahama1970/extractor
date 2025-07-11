"""
Module: string_replace.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Fast, optimized string replacement script.

This script performs efficient string replacement on files or streams.
It can process files in-place or create new output files.
"""

import argparse
import os
import re
import sys
import mmap
from typing import Optional, Union, List, Tuple
from pathlib import Path


def replace_in_memory(content: str, old_str: str, new_str: str, count: int = -1, 
                     regex: bool = False) -> str:
    """
    Replace occurrences of old_str with new_str in content.
    
    Args:
        content: The input text content
        old_str: The string to replace
        new_str: The replacement string
        count: Maximum number of replacements (-1 for all)
        regex: Whether to treat old_str as a regular expression
        
    Returns:
        Updated content with replacements
    """
    if regex:
        # Use regex replacement
        pattern = re.compile(old_str, re.MULTILINE)
        if count >= 0:
            return pattern.sub(new_str, content, count=count)
        else:
            return pattern.sub(new_str, content)
    else:
        # Use string replacement (faster for literal strings)
        return content.replace(old_str, new_str, count if count >= 0 else -1)


def replace_in_file(input_file: Union[str, Path], old_str: str, new_str: str, 
                   output_file: Optional[Union[str, Path]] = None, 
                   count: int = -1, regex: bool = False) -> Tuple[int, int]:
    """
    Replace occurrences of old_str with new_str in a file.
    
    Args:
        input_file: Path to the input file
        old_str: The string to replace
        new_str: The replacement string
        output_file: Path to the output file (None for in-place)
        count: Maximum number of replacements (-1 for all)
        regex: Whether to treat old_str as a regular expression
        
    Returns:
        Tuple of (number of replacements, number of lines affected)
    """
    input_file = Path(input_file)
    
    # If no output file specified, we're doing in-place replacement
    in_place = output_file is None
    
    if in_place:
        output_file = input_file.with_suffix('.tmp')
    else:
        output_file = Path(output_file)
        
    # Check if we can use mmap for large files (only for non-regex replacements)
    use_mmap = not regex and input_file.stat().st_size > 1024 * 1024 and old_str in new_str
    replacements = 0
    lines_affected = 0
    
    if use_mmap and in_place:
        # Memory-mapped approach for large files and in-place editing
        with open(input_file, 'r+b') as f:
            mm = mmap.mmap(f.fileno(), 0)
            content = mm.read().decode('utf-8')
            
            # Count original occurrences
            original_count = content.count(old_str)
            if original_count == 0:
                mm.close()
                return 0, 0
                
            # Perform replacement
            new_content = replace_in_memory(content, old_str, new_str, count, regex)
            if new_content == content:
                mm.close()
                return 0, 0
                
            # Count lines affected
            old_lines = content.splitlines()
            new_lines = new_content.splitlines()
            for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
                if old_line != new_line:
                    lines_affected += 1
            
            # Count actual replacements
            if count < 0:
                replacements = original_count - new_content.count(old_str)
            else:
                replacements = min(count, original_count)
            
            # Write back to the file
            mm.resize(len(new_content.encode('utf-8')))
            mm.seek(0)
            mm.write(new_content.encode('utf-8'))
            mm.flush()
            mm.close()
    else:
        # Standard approach for smaller files or when using regex
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with latin-1 encoding if UTF-8 fails
            with open(input_file, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Count original occurrences
        if regex:
            pattern = re.compile(old_str, re.MULTILINE)
            original_count = len(pattern.findall(content))
        else:
            original_count = content.count(old_str)
            
        if original_count == 0:
            return 0, 0
        
        # Perform replacement
        new_content = replace_in_memory(content, old_str, new_str, count, regex)
        if new_content == content:
            return 0, 0
            
        # Count lines affected
        old_lines = content.splitlines()
        new_lines = new_content.splitlines()
        for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
            if old_line != new_line:
                lines_affected += 1
        
        # Count actual replacements
        if regex:
            if count < 0:
                replacements = original_count - len(pattern.findall(new_content))
            else:
                replacements = min(count, original_count)
        else:
            if count < 0:
                replacements = original_count - new_content.count(old_str)
            else:
                replacements = min(count, original_count)
        
        # Write to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
    
    # Handle in-place replacement
    if in_place:
        output_file.replace(input_file)
    
    return replacements, lines_affected


def process_stream(old_str: str, new_str: str, count: int = -1, regex: bool = False) -> None:
    """
    Process stdin stream and replace strings.
    
    Args:
        old_str: The string to replace
        new_str: The replacement string
        count: Maximum number of replacements (-1 for all)
        regex: Whether to treat old_str as a regular expression
    """
    content = sys.stdin.read()
    new_content = replace_in_memory(content, old_str, new_str, count, regex)
    sys.stdout.write(new_content)


def process_files(files: List[Union[str, Path]], old_str: str, new_str: str, 
                 output_dir: Optional[Union[str, Path]] = None, 
                 in_place: bool = False, recursive: bool = False,
                 count: int = -1, regex: bool = False) -> None:
    """
    Process multiple files for string replacement.
    
    Args:
        files: List of files or directories to process
        old_str: The string to replace
        new_str: The replacement string
        output_dir: Output directory for processed files
        in_place: Whether to modify files in-place
        recursive: Whether to recursively process directories
        count: Maximum number of replacements (-1 for all)
        regex: Whether to treat old_str as a regular expression
    """
    total_replacements = 0
    total_files = 0
    total_affected = 0
    
    # Validate output directory
    if output_dir:
        output_dir = Path(output_dir)
        if not output_dir.exists():
            output_dir.mkdir(parents=True)
            
    # Expand file list if recursive
    expanded_files = []
    for file in files:
        path = Path(file)
        if path.is_dir():
            if recursive:
                expanded_files.extend(
                    [f for f in path.glob('**/*') if f.is_file()]
                )
            else:
                expanded_files.extend(
                    [f for f in path.glob('*') if f.is_file()]
                )
        else:
            expanded_files.append(path)
    
    # Process each file
    for file in expanded_files:
        output_file = None
        if not in_place and output_dir:
            # Preserve directory structure in output
            rel_path = file.relative_to(file.parent)
            output_file = output_dir / rel_path
            # Create parent directories
            output_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            replacements, lines_affected = replace_in_file(
                file, old_str, new_str, output_file, count, regex
            )
            
            if replacements > 0:
                total_files += 1
                total_replacements += replacements
                total_affected += lines_affected
                print(f"Modified {file}: {replacements} replacements in {lines_affected} lines")
        except Exception as e:
            print(f"Error processing {file}: {e}", file=sys.stderr)
    
    print(f"\nSummary: {total_replacements} replacements in {total_affected} lines across {total_files} files")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Fast string replacement in files or streams",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Replace in a single file
  python string_replace.py "old_string" "new_string" file.txt
  
  # Replace in multiple files
  python string_replace.py "old_string" "new_string" file1.txt file2.txt
  
  # Replace in-place
  python string_replace.py --in-place "old_string" "new_string" file.txt
  
  # Use regex
  python string_replace.py --regex "pattern.*" "replacement" file.txt
  
  # Process stdin/stdout
  cat file.txt | python string_replace.py "old_string" "new_string" > output.txt
  
  # Recursively process directories
  python string_replace.py --recursive "old_string" "new_string" directory/
        """
    )
    
    parser.add_argument("old_string", help="String to be replaced")
    parser.add_argument("new_string", help="Replacement string")
    parser.add_argument("files", nargs="*", help="Files or directories to process")
    parser.add_argument("--in-place", "-i", action="store_true", 
                        help="Modify files in-place")
    parser.add_argument("--output-dir", "-o", 
                        help="Output directory for processed files")
    parser.add_argument("--recursive", "-r", action="store_true", 
                        help="Recursively process directories")
    parser.add_argument("--count", "-n", type=int, default=-1, 
                        help="Maximum number of replacements per file")
    parser.add_argument("--regex", action="store_true", 
                        help="Treat the search string as a regular expression")
    
    args = parser.parse_args()
    
    # Process stdin/stdout if no files provided
    if not args.files:
        process_stream(args.old_string, args.new_string, args.count, args.regex)
        return
    
    # Process files
    process_files(
        args.files, 
        args.old_string, 
        args.new_string, 
        args.output_dir, 
        args.in_place,
        args.recursive,
        args.count,
        args.regex
    )


if __name__ == "__main__":
    main()