"""
Module: __init__.py
Description: Package initialization and exports

External Dependencies:
- enum: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from enum import auto, Enum


class BlockTypes(str, Enum):
    Line = auto()
    Span = auto()
    FigureGroup = auto()
    TableGroup = auto()
    ListGroup = auto()
    PictureGroup = auto()
    Page = auto()
    Caption = auto()
    Code = auto()
    Figure = auto()
    Footnote = auto()
    Form = auto()
    Equation = auto()
    Handwriting = auto()
    TextInlineMath = auto()
    ListItem = auto()
    PageFooter = auto()
    PageHeader = auto()
    Picture = auto()
    SectionHeader = auto()
    Table = auto()
    Text = auto()
    TableOfContents = auto()
    Document = auto()
    ComplexRegion = auto()
    TableCell = auto()
    Reference = auto()

    def __str__(self):
        return self.name
