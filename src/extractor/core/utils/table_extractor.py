"""
import re
import json
import csv
import io
from typing import Dict, List, Any, Tuple
Module: table_extractor.py
Description: Functions for table extractor operations
Description: Functions for table extractor operations


def extract_tables_from_markdown(markdown_content: str) -> List[Dict[str, Any]]:
    """
"""
Utilities for extracting table data in CSV/JSON format from markdown files.
    Extract all tables with their CSV/JSON data from a markdown document.
    
    Args:
        markdown_content: The markdown content to extract tables from
        
    Returns:
        List of table data dictionaries with keys:
        - markdown: The markdown table representation
        - csv: The CSV representation (if available)
        - json: The JSON representation (if available)
    """
    # Extract markdown tables
    table_pattern = r'(\|[^\n]+\|\n\|[\s-]+\|\n(?:\|[^\n]+\|\n)+)'
    markdown_tables = re.findall(table_pattern, markdown_content)
    
    # Extract CSV data
    csv_pattern = r'<!-- TABLE_CSV:\n(.*?)\n-->'
    csv_data = re.findall(csv_pattern, markdown_content, re.DOTALL)
    
    # Extract JSON data
    json_pattern = r'<!-- TABLE_JSON:\n(.*?)\n-->'
    json_data = re.findall(json_pattern, markdown_content, re.DOTALL)
    
    # Match tables with their data
    table_count = len(markdown_tables)
    csv_count = len(csv_data)
    json_count = len(json_data)
    
    # Ensure we have the same count of each or handle mismatches
    results = []
    for i in range(table_count):
        table_dict = {
            "markdown": markdown_tables[i],
            "csv": csv_data[i] if i < csv_count else None,
            "json": json_data[i] if i < json_count else None
        }
        
        # Parse JSON if available
        if table_dict["json"]:
            try:
                table_dict["json_parsed"] = json.loads(table_dict["json"])
            except json.JSONDecodeError:
                table_dict["json_parsed"] = None
                
        # Parse CSV if available
        if table_dict["csv"]:
            try:
                reader = csv.reader(io.StringIO(table_dict["csv"]))
                table_dict["csv_parsed"] = list(reader)
            except Exception:
                table_dict["csv_parsed"] = None
                
        results.append(table_dict)
    
    return results


def convert_markdown_table_to_csv(markdown_table: str) -> str:
    """
    Convert a markdown table to CSV format.
    
    Args:
        markdown_table: The markdown table to convert
        
    Returns:
        CSV representation of the table
    """
    lines = markdown_table.strip().split('\n')
    # Remove header separator line (---|---|---)
    if len(lines) > 1 and all(c == '-' or c == '|' or c.isspace() for c in lines[1]):
        lines.pop(1)
    
    # Process each line
    csv_rows = []
    for line in lines:
        # Remove leading/trailing |
        line = line.strip()
        if line.startswith('|'):
            line = line[1:]
        if line.endswith('|'):
            line = line[:-1]
            
        # Split by | and strip whitespace
        cells = [cell.strip() for cell in line.split('|')]
        csv_rows.append(cells)
    
    # Write to CSV
    output = io.StringIO()
    writer = csv.writer(output)
    for row in csv_rows:
        writer.writerow(row)
    
    return output.getvalue()


def convert_markdown_table_to_json(markdown_table: str) -> str:
    """
    Convert a markdown table to JSON format.
    
    Args:
        markdown_table: The markdown table to convert
        
    Returns:
        JSON representation of the table
    """
    lines = markdown_table.strip().split('\n')
    
    # Process header line
    header_line = lines[0]
    header_line = header_line.strip()
    if header_line.startswith('|'):
        header_line = header_line[1:]
    if header_line.endswith('|'):
        header_line = header_line[:-1]
    headers = [header.strip() for header in header_line.split('|')]
    
    # Skip separator line
    data_lines = lines[2:] if len(lines) > 2 else []
    
    # Process data rows
    rows = []
    for line in data_lines:
        line = line.strip()
        if line.startswith('|'):
            line = line[1:]
        if line.endswith('|'):
            line = line[:-1]
        
        cells = [cell.strip() for cell in line.split('|')]
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                row_dict[header] = cells[i]
            else:
                row_dict[header] = ""
        
        rows.append(row_dict)
    
    # Create JSON structure
    json_data = {
        "headers": headers,
        "rows": rows
    }
    
    return json.dumps(json_data, indent=2, ensure_ascii=False)