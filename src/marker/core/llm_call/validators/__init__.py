"""Built-in validators for common use cases.

This package contains various validators for different types of content:
- Base validators (field presence, length, format, etc.)
- Table validators (structure, consistency)
- Image validators (descriptions, alt text)
- Math validators (LaTeX syntax, consistency)
- Code validators (syntax, language, completeness)
- Citation validators (fuzzy matching, format, relevance)
- General validators (content quality, tone, JSON structure)
"""

# Import base validators
from marker.core.llm_call.validators.base import (
    FieldPresenceValidator,
    LengthValidator,
    FormatValidator,
    TypeValidator,
    RangeValidator,
)

# Import specialized validators
from marker.core.llm_call.validators.table import (
    TableStructureValidator,
    TableConsistencyValidator,
)

from marker.core.llm_call.validators.image import (
    ImageDescriptionValidator,
    AltTextValidator,
)

from marker.core.llm_call.validators.math import (
    LaTeXSyntaxValidator,
    MathConsistencyValidator,
)

from marker.core.llm_call.validators.code import (
    PythonSyntaxValidator,
    CodeLanguageValidator,
    CodeCompletenessValidator,
)

from marker.core.llm_call.validators.citation import (
    CitationMatchValidator,
    CitationFormatValidator,
    CitationRelevanceValidator,
)

from marker.core.llm_call.validators.general import (
    ContentQualityValidator,
    ToneConsistencyValidator,
    JSONStructureValidator,
)

from marker.core.llm_call.validators.value import (
    ValueInListValidator,
)

__all__ = [
    # Base validators
    "FieldPresenceValidator",
    "LengthValidator",
    "FormatValidator",
    "TypeValidator",
    "RangeValidator",
    # Table validators
    "TableStructureValidator",
    "TableConsistencyValidator",
    # Image validators
    "ImageDescriptionValidator",
    "AltTextValidator",
    # Math validators
    "LaTeXSyntaxValidator",
    "MathConsistencyValidator",
    # Code validators
    "PythonSyntaxValidator",
    "CodeLanguageValidator",
    "CodeCompletenessValidator",
    # Citation validators
    "CitationMatchValidator",
    "CitationFormatValidator",
    "CitationRelevanceValidator",
    # General validators
    "ContentQualityValidator",
    "ToneConsistencyValidator",
    "JSONStructureValidator",
    # Value validators
    "ValueInListValidator",
]