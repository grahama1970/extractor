"""Citation validators using fuzzy matching for LLM validation."""

from typing import Any, Dict, List, Optional
from rapidfuzz import fuzz, process

from marker.core.llm_call.core.base import ValidationResult
from marker.core.llm_call.core.strategies import validator


@validator("citation_match")
class CitationMatchValidator:
    """Validates citations against reference texts using fuzzy matching."""
    
    def __init__(self, min_score: float = 80.0):
        """Initialize citation validator.
        
        Args:
            min_score: Minimum fuzzy match score to consider a citation valid
        """
        self.min_score = min_score
    
    @property
    def name(self) -> str:
        return f"citation_match(min_score={self.min_score})"
    
    @property
    def description(self) -> str:
        return "Validates citations against reference material using fuzzy matching"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate that citations match reference material."""
        # Extract citations from response
        citations = []
        if hasattr(response, 'citations'):
            citations = response.citations
        elif isinstance(response, dict) and 'citations' in response:
            citations = response['citations']
        
        if not citations:
            return ValidationResult(
                valid=False,
                error="Response contains no citations",
                suggestions=["Include citations for factual claims"]
            )
        
        # Get reference texts from context
        references = context.get("references", [])
        if not references:
            return ValidationResult(
                valid=True,
                debug_info={"warning": "No reference texts provided for comparison"}
            )
        
        unmatched_citations = []
        matched_citations = []
        
        for i, citation in enumerate(citations):
            # Convert citation to string if it's an object
            citation_text = str(citation) if not isinstance(citation, str) else citation
            
            # Use RapidFuzz to find best match in references
            best_match = process.extractOne(
                citation_text,
                references,
                scorer=fuzz.partial_ratio,
                score_cutoff=self.min_score
            )
            
            if not best_match:
                # Try token sort ratio for better matching of reordered text
                best_match = process.extractOne(
                    citation_text,
                    references,
                    scorer=fuzz.token_sort_ratio,
                    score_cutoff=self.min_score
                )
            
            if not best_match:
                unmatched_citations.append({
                    "index": i,
                    "text": citation_text[:100] + "..." if len(citation_text) > 100 else citation_text,
                    "best_score": 0
                })
            else:
                matched_citations.append({
                    "index": i,
                    "text": citation_text[:100] + "..." if len(citation_text) > 100 else citation_text,
                    "match": best_match[0][:100] + "..." if len(best_match[0]) > 100 else best_match[0],
                    "score": best_match[1]
                })
        
        if unmatched_citations:
            return ValidationResult(
                valid=False,
                error=f"Found {len(unmatched_citations)} citations that don't match references",
                debug_info={
                    "unmatched": unmatched_citations,
                    "matched": matched_citations
                },
                suggestions=[
                    "Check citation accuracy",
                    "Ensure citations are from provided reference material",
                    "Fix citation formatting",
                    f"Use references with similarity score above {self.min_score}%"
                ]
            )
        
        return ValidationResult(
            valid=True,
            debug_info={
                "matched_citations": len(matched_citations),
                "citations": matched_citations
            }
        )


@validator("citation_format")
class CitationFormatValidator:
    """Validates citation formatting and structure."""
    
    def __init__(self, 
                 format_style: str = "apa",
                 require_year: bool = True,
                 require_author: bool = True):
        """Initialize citation format validator.
        
        Args:
            format_style: Citation format style (apa, mla, chicago)
            require_year: Whether citations must include year
            require_author: Whether citations must include author
        """
        self.format_style = format_style.lower()
        self.require_year = require_year
        self.require_author = require_author
    
    @property
    def name(self) -> str:
        return f"citation_format(style={self.format_style})"
    
    @property
    def description(self) -> str:
        return f"Validates {self.format_style.upper()} citation formatting"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate citation formatting."""
        # Extract citations from response
        citations = []
        if hasattr(response, 'citations'):
            citations = response.citations
        elif isinstance(response, dict) and 'citations' in response:
            citations = response['citations']
        
        if not citations:
            return ValidationResult(
                valid=False,
                error="No citations found in response"
            )
        
        errors = []
        suggestions = []
        invalid_citations = []
        
        for i, citation in enumerate(citations):
            citation_text = str(citation) if not isinstance(citation, str) else citation
            citation_errors = []
            
            if self.format_style == "apa":
                # Basic APA format checking
                # Pattern: Author, A. A. (Year). Title. Publisher.
                if self.require_author and not any(c.isupper() for c in citation_text[:20]):
                    citation_errors.append("Missing capitalized author name")
                
                if self.require_year:
                    import re
                    year_pattern = r'\((\d{4})\)'
                    if not re.search(year_pattern, citation_text):
                        citation_errors.append("Missing year in parentheses")
                
                if not citation_text.endswith('.'):
                    citation_errors.append("Citation should end with a period")
            
            elif self.format_style == "mla":
                # Basic MLA format checking
                # Pattern: Author. "Title." Publisher, Year.
                if self.require_author and not any(c.isupper() for c in citation_text[:20]):
                    citation_errors.append("Missing capitalized author name")
                
                if '"' not in citation_text:
                    citation_errors.append("Title should be in quotes")
            
            if citation_errors:
                invalid_citations.append({
                    "index": i,
                    "text": citation_text[:100] + "..." if len(citation_text) > 100 else citation_text,
                    "errors": citation_errors
                })
                errors.extend(citation_errors)
        
        if errors:
            suggestions.append(f"Follow {self.format_style.upper()} citation format")
            if self.require_author:
                suggestions.append("Include author names")
            if self.require_year:
                suggestions.append("Include publication year")
            
            return ValidationResult(
                valid=False,
                error=f"Invalid {self.format_style.upper()} format in {len(invalid_citations)} citations",
                debug_info={"invalid_citations": invalid_citations},
                suggestions=suggestions
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"citation_count": len(citations)}
        )


@validator("citation_relevance")
class CitationRelevanceValidator:
    """Validates that citations are relevant to the content."""
    
    def __init__(self, 
                 min_relevance_score: float = 70.0,
                 check_context: bool = True):
        """Initialize citation relevance validator.
        
        Args:
            min_relevance_score: Minimum relevance score for fuzzy matching
            check_context: Whether to check citation context
        """
        self.min_relevance_score = min_relevance_score
        self.check_context = check_context
    
    @property
    def name(self) -> str:
        return f"citation_relevance(min_score={self.min_relevance_score})"
    
    @property
    def description(self) -> str:
        return "Validates that citations are relevant to the content"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate citation relevance to content."""
        # Extract content and citations
        content = ""
        citations = []
        
        if hasattr(response, 'content'):
            content = response.content
        elif isinstance(response, dict) and 'content' in response:
            content = response['content']
        
        if hasattr(response, 'citations'):
            citations = response.citations
        elif isinstance(response, dict) and 'citations' in response:
            citations = response['citations']
        
        if not citations:
            return ValidationResult(
                valid=True,
                debug_info={"warning": "No citations to validate"}
            )
        
        if not content:
            return ValidationResult(
                valid=False,
                error="No content provided to check citation relevance"
            )
        
        irrelevant_citations = []
        
        # Extract sentences around citation markers if available
        citation_contexts = context.get("citation_contexts", [])
        
        for i, citation in enumerate(citations):
            citation_text = str(citation) if not isinstance(citation, str) else citation
            
            # Check if citation is referenced in the content
            # Look for common citation markers like [1], (Author, Year), etc.
            is_referenced = False
            
            # Simple check for numeric references
            if f"[{i+1}]" in content or f"({i+1})" in content:
                is_referenced = True
            
            # Check for author name in content
            if not is_referenced:
                # Extract potential author name (first word before comma or parenthesis)
                import re
                author_match = re.match(r'^([A-Z][a-z]+)', citation_text)
                if author_match:
                    author_name = author_match.group(1)
                    if author_name in content:
                        is_referenced = True
            
            # If we have citation contexts, check relevance
            relevance_score = 0
            if self.check_context and i < len(citation_contexts):
                context_text = citation_contexts[i]
                relevance_result = process.extractOne(
                    citation_text,
                    [context_text],
                    scorer=fuzz.token_sort_ratio
                )
                if relevance_result:
                    relevance_score = relevance_result[1]
            
            if not is_referenced or (self.check_context and relevance_score < self.min_relevance_score):
                irrelevant_citations.append({
                    "index": i,
                    "text": citation_text[:100] + "..." if len(citation_text) > 100 else citation_text,
                    "referenced": is_referenced,
                    "relevance_score": relevance_score
                })
        
        if irrelevant_citations:
            return ValidationResult(
                valid=False,
                error=f"Found {len(irrelevant_citations)} citations that may not be relevant",
                debug_info={"irrelevant_citations": irrelevant_citations},
                suggestions=[
                    "Ensure all citations are referenced in the text",
                    "Check that citations support the claims made",
                    "Remove citations that aren't directly relevant"
                ]
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"citation_count": len(citations)}
        )