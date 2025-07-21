"""
Module: glossary_search.py

External Dependencies:
- loguru: https://loguru.readthedocs.io/
- arango: https://docs.python-arango.com/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import sys
import re
import json
import os
from typing import Dict, List, Any, Set, Optional, Tuple
from loguru import logger
from colorama import init, Fore, Style
from tabulate import tabulate
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from arango.database import StandardDatabase
from arango.collection import StandardCollection
from arango.exceptions import CollectionCreateError, DocumentInsertError

# Import display and log utilities for proper content formatting
from complexity.arangodb.log_utils import truncate_large_value
from complexity.arangodb.display_utils import print_search_results


class GlossaryService:
    """Service for managing glossary terms in ArangoDB."""
    
    def __init__(self, db: StandardDatabase, collection_name: str = "glossary"):
        """
        Initialize the glossary service.
        
        Args:
            db: ArangoDB database connection
            collection_name: Name of the glossary collection
        """
        init()  # Initialize colorama for colored console output
        self.db = db
        self.collection_name = collection_name
        self.collection = None
        self._terms_cache = {}  # Cache of terms for faster lookups
        self._terms_by_length = []  # Terms sorted by length (descending)
        try:
            self.console = Console(force=None)  # Auto-detect terminal capabilities
        except Exception as e:
            logger.warning(f"Rich console initialization failed: {e}. Falling back to plain output.")
            self.console = None
    
    def initialize_collection(self, truncate: bool = False) -> StandardCollection:
        """
        Initialize the glossary collection in ArangoDB.
        Creates the collection if it doesn't exist.'
        
        Args:
            truncate: If True, truncate the collection if it exists (useful for testing)
        
        Returns:
            ArangoDB collection object
        """
        collection_exists = any(c['name'] == self.collection_name for c in self.db.collections())
        
        if collection_exists:
            self.collection = self.db.collection(self.collection_name)
            logger.info(f"Using existing glossary collection: {self.collection_name}")
            
            if truncate:
                try:
                    self.collection.truncate()
                    logger.info(f"Truncated glossary collection: {self.collection_name}")
                except Exception as e:
                    logger.error(f"Error truncating collection: {e}")
                    raise
        else:
            try:
                self.collection = self.db.create_collection(self.collection_name)
                logger.info(f"Created glossary collection: {self.collection_name}")
                
                self.collection.add_hash_index(["term"], unique=True)
                logger.info("Created index on term field")
            except CollectionCreateError as e:
                logger.error(f"Error creating glossary collection: {e}")
                raise
        
        self._refresh_cache()
        
        return self.collection
    
    def add_term(self, term: str, definition: str) -> bool:
        """
        Add a term to the glossary collection.
        
        Args:
            term: The glossary term to add
            definition: The definition of the term
            
        Returns:
            True if added successfully, False otherwise
        """
        if not self.collection:
            try:
                self.initialize_collection()
            except Exception as e:
                logger.error(f"Failed to initialize collection: {e}")
                return False
        
        try:
            doc = {
                "term": term,
                "term_lower": term.lower(),
                "definition": definition,
                "length": len(term)
            }
            
            aql = f"""
            FOR doc IN {self.collection_name}
            FILTER doc.term_lower == @term_lower
            RETURN doc
            """
            
            cursor = self.db.aql.execute(
                aql,
                bind_vars={
                    "term_lower": term.lower()
                }
            )
            
            existing_term = next(cursor, None)
            
            if existing_term:
                if existing_term["definition"] != definition:
                    self.collection.update(
                        existing_term["_key"],
                        {"definition": definition}
                    )
                    logger.info(f"Updated term: {term}")
                    
                    self._terms_cache[term.lower()] = {
                        "term": term,
                        "definition": definition
                    }
                    self._rebuild_sorted_terms()
                    
                    return True
                else:
                    return True
            else:
                self.collection.insert(doc)
                logger.info(f"Added term: {term}")
                
                self._terms_cache[term.lower()] = {
                    "term": term,
                    "definition": definition
                }
                self._rebuild_sorted_terms()
                
                return True
        except Exception as e:
            logger.error(f"Error adding term '{term}': {e}")
            return False
    
    def add_terms(self, terms_dict: Dict[str, str]) -> int:
        """
        Add multiple terms to the glossary collection using individual inserts.
        
        Args:
            terms_dict: Dictionary mapping terms to definitions
            
        Returns:
            Number of terms added successfully
        """
        if not terms_dict:
            return 0
            
        count = 0
        for term, definition in terms_dict.items():
            if self.add_term(term, definition):
                count += 1
        
        return count
    
    def add_terms_bulk(self, terms_dict: Dict[str, str]) -> int:
        """
        Add multiple terms to the glossary collection using bulk insert.
        
        Args:
            terms_dict: Dictionary mapping terms to definitions
            
        Returns:
            Number of terms added or updated successfully
        """
        if not terms_dict:
            return 0
            
        if not self.collection:
            try:
                self.initialize_collection()
            except Exception as e:
                logger.error(f"Failed to initialize collection: {e}")
                return 0
        
        try:
            documents = [
                {
                    "term": term,
                    "term_lower": term.lower(),
                    "definition": definition,
                    "length": len(term)
                }
                for term, definition in terms_dict.items()
            ]
            
            result = self.collection.insert_many(
                documents,
                overwrite_mode="update",
                return_new=True,
                return_old=True
            )
            
            for doc in result:
                if "new" in doc:
                    term_lower = doc["new"]["term_lower"]
                    self._terms_cache[term_lower] = {
                        "term": doc["new"]["term"],
                        "definition": doc["new"]["definition"]
                    }
                elif "old" in doc:
                    term_lower = doc["old"]["term_lower"]
                    self._terms_cache[term_lower] = {
                        "term": doc["old"]["term"],
                        "definition": doc["old"]["definition"]
                    }
            
            self._rebuild_sorted_terms()
            
            logger.info(f"Bulk inserted/updated {len(result)} terms")
            return len(result)
            
        except DocumentInsertError as e:
            logger.error(f"Error during bulk insert: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error during bulk insert: {e}")
            return 0
    
    def add_default_terms(self) -> int:
        """
        Add default color-related glossary terms to the collection.
        
        Returns:
            Number of terms added
        """
        DEFAULT_GLOSSARY = {
            "primary color": "One of the three colors (red, blue, yellow) that cannot be created by mixing other colors",
            "secondary color": "A color made by mixing two primary colors",
            "tertiary color": "A color made by mixing a primary color with a secondary color",
            "cool color": "Colors that evoke a sense of calm such as blue, green, and purple",
            "warm color": "Colors that evoke a sense of warmth such as red, orange, and yellow",
            "RGB": "Color model that uses red, green, and blue light to create colors on electronic displays",
            "hue": "The pure color attribute; what we normally think of as 'color'",
            "saturation": "The intensity or purity of a color",
            "value": "The lightness or darkness of a color",
            "azure": "A bright, cyan-blue color named after the blue mineral azurite",
            "ruby": "A deep red color named after the ruby gemstone",
            "color": "The visual perceptual property corresponding to the categories called red, green, blue, etc.",
            "hexadecimal color": "A color expressed as a six-digit combination of numbers and letters, used in HTML and CSS"
        }
        
        return self.add_terms_bulk(DEFAULT_GLOSSARY)
    
    def get_all_terms(self, output: str = "table") -> Any:
        """
        Get all terms from the glossary collection, formatted as a table or JSON.
        
        Args:
            output: Output format, either "table" (default) or "json"
        
        Returns:
            If output="table", prints a formatted table and returns None.
            If output="json", returns a JSON string of terms and definitions.
        """
        if not self.collection:
            try:
                self.initialize_collection()
            except Exception as e:
                logger.error(f"Failed to initialize collection: {e}")
                return [] if output == "json" else None
        
        try:
            aql = """
            FOR doc IN @@collection
            SORT doc.term_lower
            RETURN {
                "term": doc.term,
                "definition": doc.definition
            }
            """
            
            cursor = self.db.aql.execute(
                aql,
                bind_vars={
                    "@collection": self.collection_name
                }
            )
            
            terms = [doc for doc in cursor]
            
            if output == "json":
                return json.dumps(terms, indent=2)
            
            if not terms:
                if self.console:
                    self.console.print("[yellow]No terms found in the glossary.[/yellow]")
                else:
                    print(f"{Fore.YELLOW}No terms found in the glossary.{Style.RESET_ALL}")
                return None
            
            # Format the terms list as results for the display utility
            formatted_results = {
                "results": [{"doc": term, "score": 1.0} for term in terms],
                "total": len(terms),
                "query": "All glossary terms",
                "time": 0.0,
                "format": "table",
                "search_engine": "glossary"
            }
            
            # Use the unified display utility with glossary-specific settings
            print_search_results(
                formatted_results, 
                title_field="Definition",
                id_field="term",
                score_field="score",
                score_name="Relevance",
                table_title="Glossary Terms"
            )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting all terms: {e}")
            return [] if output == "json" else None
    
    def find_terms_in_text(self, text: str, output: str = "table", max_width: int = 120) -> Any:
        """
        Find glossary terms in the provided text.
        Returns terms and definitions as a table or JSON based on output parameter.
        
        Args:
            text: The text to search for glossary terms
            output: Output format, either "table" (prints table, returns None) or
                    "json" (returns JSON string)
            max_width: Maximum width for definition field in characters (used for table format)
            
        Returns:
            If output="table", prints a formatted table and returns None.
            If output="json", returns a JSON string of matched terms and definitions.
        """
        if not text:
            if output == "json":
                return json.dumps([], indent=2)
            if self.console:
                self.console.print("[yellow]No text provided.[/yellow]")
            else:
                print(f"{Fore.YELLOW}No text provided.{Style.RESET_ALL}")
            return None
            
        if not self._terms_cache:
            self._refresh_cache()
            
        if not self._terms_cache:
            if output == "json":
                return json.dumps([], indent=2)
            if self.console:
                self.console.print("[yellow]No terms available in glossary.[/yellow]")
            else:
                print(f"{Fore.YELLOW}No terms available in glossary.{Style.RESET_ALL}")
            return None
        
        try:
            # Truncate large text input for matching to avoid memory issues
            safe_text = truncate_large_value(text, max_str_len=5000)
            text_lower = safe_text.lower() if isinstance(safe_text, str) else str(safe_text).lower()
            matched_terms = []
            matched_positions = set()
            
            for term_lower, term_info in self._terms_by_length:
                pattern = r'\b' + re.escape(term_lower) + r'\b'
                for match in re.finditer(pattern, text_lower):
                    start, end = match.span()
                    overlap = False
                    for pos in range(start, end):
                        if pos in matched_positions:
                            overlap = True
                            break
                    
                    if not overlap:
                        matched_terms.append({
                            "term": term_info["term"],
                            "definition": term_info["definition"]
                        })
                        for pos in range(start, end):
                            matched_positions.add(pos)
            
            matched_terms.sort(key=lambda x: x["term"].lower())
            
            if output == "json":
                return json.dumps(matched_terms, indent=2)
            
            if not matched_terms:
                if self.console:
                    self.console.print("[yellow]No glossary terms found in text.[/yellow]")
                else:
                    print(f"{Fore.YELLOW}No glossary terms found in text.{Style.RESET_ALL}")
                return None
            
            # Format the matched terms for the display utility
            # Use a special display format for term matches
            print(f"{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}")
            print(f"Found {Fore.GREEN}{len(matched_terms)}{Style.RESET_ALL} matched terms")
            # Truncate text preview if too long
            text_preview = truncate_large_value(text, max_str_len=50)
            print(f"Text: '{Fore.YELLOW}{text_preview}{Style.RESET_ALL}'")
            print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
            
            # Format results for display utility
            formatted_results = {
                "results": [{"doc": term, "similarity_score": 1.0} for term in matched_terms],
                "total": len(matched_terms),
                "query": f"Terms in text: '{text_preview}'",
                "time": 0.0,
                "format": "table",
                "search_engine": "glossary-matcher"
            }
            
            # Use the unified display utility with glossary-specific settings
            print_search_results(
                formatted_results, 
                title_field="Definition",
                id_field="term",
                score_field="similarity_score",
                score_name="Match",
                table_title="Matched Terms"
            )
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding terms in text: {e}")
            if output == "json":
                return json.dumps([], indent=2)
            return None
    
    def highlight_terms(self, text: str) -> str:
        """
        Highlight glossary terms in the provided text.
        
        Args:
            text: The text to process
            
        Returns:
            Text with glossary terms highlighted with asterisks
        """
        if not text:
            return text
            
        # Ensure input text isn't too large by truncating if needed
        safe_text = truncate_large_value(text, max_str_len=10000)
        if not isinstance(safe_text, str):
            return str(safe_text)
            
        matched_terms = json.loads(self.find_terms_in_text(safe_text, output="json"))
        
        if not matched_terms:
            return safe_text
        
        pattern_parts = []
        for term_info in matched_terms:
            term = term_info["term"]
            pattern_parts.append(r'\b' + re.escape(term) + r'\b')
        
        pattern = '|'.join(pattern_parts)
        
        highlighted_text = re.sub(
            pattern,
            r'**\g<0>**',
            safe_text,
            flags=re.IGNORECASE
        )
        
        return highlighted_text
    
    def _refresh_cache(self):
        """Refresh the in-memory cache of terms."""
        if not self.collection:
            return
            
        try:
            self._terms_cache = {}
            
            aql = """
            FOR doc IN @@collection
            RETURN {
                "term_lower": doc.term_lower,
                "term": doc.term,
                "definition": doc.definition,
                "length": doc.length
            }
            """
            
            cursor = self.db.aql.execute(
                aql,
                bind_vars={
                    "@collection": self.collection_name
                }
            )
            
            for doc in cursor:
                self._terms_cache[doc["term_lower"]] = {
                    "term": doc["term"],
                    "definition": doc["definition"]
                }
            
            self._rebuild_sorted_terms()
            
            logger.info(f"Refreshed cache with {len(self._terms_cache)} terms")
        except Exception as e:
            logger.error(f"Error refreshing cache: {e}")
    
    def _rebuild_sorted_terms(self):
        """Rebuild the sorted list of terms by length (descending)."""
        self._terms_by_length = sorted(
            self._terms_cache.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )


# Example usage
if __name__ == "__main__":
    from complexity.arangodb.arango_setup import connect_arango, ensure_database
    
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:HH:mm:ss} | {level:<7} | {message}"
    )
    
    try:
        client = connect_arango()
        db = ensure_database(client)
        
        glossary_service = GlossaryService(db)
        glossary_service.initialize_collection(truncate=True)
        
        added_count = glossary_service.add_default_terms()
        print(f"Added {added_count} default terms to glossary")
        
        sample_text = (
            "What is the relationship between primary color and secondary color?\n"
            "Also, how does the RGB color model work?"
        )
        
        print("\nTable output for matched terms:")
        glossary_service.find_terms_in_text(sample_text, output="table")
        
        print("\nJSON output for matched terms:")
        json_output = glossary_service.find_terms_in_text(sample_text, output="json")
        print(json_output)
        
        highlighted = glossary_service.highlight_terms(sample_text)
        print(f"\nHighlighted text:\n{highlighted}")
        
        print("\nNote: If the table lacks rich formatting (e.g., no panel border), ensure your terminal supports Unicode and ANSI colors.")
        
    except Exception as e:
        logger.error(f"Error in example: {e}")