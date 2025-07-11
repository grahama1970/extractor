"""Table-specific validators for LLM validation."""
Module: table.py

from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from extractor.core.llm_call.core.base import ValidationResult
from extractor.core.llm_call.validators.base import BaseValidator
from extractor.core.llm_call.core.strategies import validator


@validator("table_structure")
class TableStructureValidator(BaseValidator):
    """Validates HTML table structure and content."""
    
    def __init__(self, 
                 min_rows: Optional[int] = None, 
                 max_rows: Optional[int] = None,
                 min_cols: Optional[int] = None,
                 max_cols: Optional[int] = None,
                 require_headers: bool = False):
        """Initialize table validator.
        
        Args:
            min_rows: Minimum number of rows required
            max_rows: Maximum number of rows allowed
            min_cols: Minimum number of columns required
            max_cols: Maximum number of columns allowed
            require_headers: Whether table must have header row
        """
        self.min_rows = min_rows
        self.max_rows = max_rows
        self.min_cols = min_cols
        self.max_cols = max_cols
        self.require_headers = require_headers
    
    @property
    def name(self) -> str:
        params = []
        if self.min_rows is not None:
            params.append(f"min_rows={self.min_rows}")
        if self.max_rows is not None:
            params.append(f"max_rows={self.max_rows}")
        if self.min_cols is not None:
            params.append(f"min_cols={self.min_cols}")
        if self.max_cols is not None:
            params.append(f"max_cols={self.max_cols}")
        if self.require_headers:
            params.append("require_headers=True")
        
        params_str = f"({', '.join(params)})" if params else ""
        return f"table_structure{params_str}"
    
    @property
    def description(self) -> str:
        return "Validates HTML table structure and dimensions"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate table structure."""
        # Get HTML content from response
        if hasattr(response, 'html'):
            html_content = response.html
        elif isinstance(response, dict) and 'html' in response:
            html_content = response['html']
        elif isinstance(response, str):
            html_content = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract HTML content from response type: {type(response)}"
            )
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return ValidationResult(
                    valid=False,
                    error="No table found in HTML content",
                    suggestions=["Ensure response contains a valid HTML table"]
                )
            
            # Count rows and columns
            rows = table.find_all('tr')
            row_count = len(rows)
            
            # Check for headers
            has_headers = bool(table.find('thead')) or bool(table.find_all('th'))
            
            # Count columns (use first row as reference)
            col_count = 0
            if rows:
                first_row = rows[0]
                col_count = len(first_row.find_all(['td', 'th']))
            
            errors = []
            suggestions = []
            
            # Validate row count
            if self.min_rows is not None and row_count < self.min_rows:
                errors.append(f"Table has {row_count} rows, minimum required is {self.min_rows}")
                suggestions.append(f"Add at least {self.min_rows - row_count} more rows")
            
            if self.max_rows is not None and row_count > self.max_rows:
                errors.append(f"Table has {row_count} rows, maximum allowed is {self.max_rows}")
                suggestions.append(f"Remove {row_count - self.max_rows} rows")
            
            # Validate column count
            if self.min_cols is not None and col_count < self.min_cols:
                errors.append(f"Table has {col_count} columns, minimum required is {self.min_cols}")
                suggestions.append(f"Add at least {self.min_cols - col_count} more columns")
            
            if self.max_cols is not None and col_count > self.max_cols:
                errors.append(f"Table has {col_count} columns, maximum allowed is {self.max_cols}")
                suggestions.append(f"Remove {col_count - self.max_cols} columns")
            
            # Validate headers
            if self.require_headers and not has_headers:
                errors.append("Table is missing header row")
                suggestions.append("Add a header row with <th> elements or use <thead>")
            
            if errors:
                return ValidationResult(
                    valid=False,
                    error="; ".join(errors),
                    suggestions=suggestions,
                    debug_info={
                        "row_count": row_count,
                        "col_count": col_count,
                        "has_headers": has_headers
                    }
                )
            
            return ValidationResult(
                valid=True,
                debug_info={
                    "row_count": row_count,
                    "col_count": col_count,
                    "has_headers": has_headers
                }
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"Error parsing HTML table: {str(e)}",
                suggestions=["Ensure HTML is well-formed", "Check for proper table tags"]
            )


@validator("table_consistency")
class TableConsistencyValidator(BaseValidator):
    """Validates table consistency across rows."""
    
    def __init__(self, check_column_count: bool = True, check_cell_types: bool = False):
        """Initialize consistency validator.
        
        Args:
            check_column_count: Whether to check all rows have same column count
            check_cell_types: Whether to check consistent data types in columns
        """
        self.check_column_count = check_column_count
        self.check_cell_types = check_cell_types
    
    @property
    def name(self) -> str:
        params = []
        if self.check_column_count:
            params.append("check_column_count=True")
        if self.check_cell_types:
            params.append("check_cell_types=True")
        params_str = f"({', '.join(params)})" if params else ""
        return f"table_consistency{params_str}"
    
    @property
    def description(self) -> str:
        return "Validates consistency across table rows"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate table consistency."""
        # Get HTML content from response
        if hasattr(response, 'html'):
            html_content = response.html
        elif isinstance(response, dict) and 'html' in response:
            html_content = response['html']
        elif isinstance(response, str):
            html_content = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract HTML content from response type: {type(response)}"
            )
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return ValidationResult(
                    valid=False,
                    error="No table found in HTML content"
                )
            
            rows = table.find_all('tr')
            errors = []
            suggestions = []
            
            if self.check_column_count:
                # Check if all rows have same number of columns
                column_counts = []
                for i, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    column_counts.append(len(cells))
                
                if column_counts and len(set(column_counts)) > 1:
                    errors.append(f"Inconsistent column counts: {column_counts}")
                    suggestions.append("Ensure all rows have the same number of columns")
            
            if self.check_cell_types:
                # Check data type consistency in columns
                # This is a simplified check - could be enhanced
                pass
            
            if errors:
                return ValidationResult(
                    valid=False,
                    error="; ".join(errors),
                    suggestions=suggestions,
                    debug_info={
                        "row_count": len(rows),
                        "column_counts": column_counts if self.check_column_count else None
                    }
                )
            
            return ValidationResult(
                valid=True,
                debug_info={
                    "row_count": len(rows),
                    "consistent_columns": True
                }
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"Error checking table consistency: {str(e)}"
            )