"""
Module: __init__.py
Description: Package initialization and exports

External Dependencies:
- __future__: [Documentation URL]
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from __future__ import annotations

from extractor.core.schema.blocks.base import Block, BlockId, BlockOutput
from extractor.core.schema.blocks.caption import Caption
from extractor.core.schema.blocks.code import Code
from extractor.core.schema.blocks.figure import Figure
from extractor.core.schema.blocks.footnote import Footnote
from extractor.core.schema.blocks.form import Form
from extractor.core.schema.blocks.equation import Equation
from extractor.core.schema.blocks.handwriting import Handwriting
from extractor.core.schema.blocks.inlinemath import InlineMath
from extractor.core.schema.blocks.listitem import ListItem
from extractor.core.schema.blocks.pagefooter import PageFooter
from extractor.core.schema.blocks.pageheader import PageHeader
from extractor.core.schema.blocks.picture import Picture
from extractor.core.schema.blocks.sectionheader import SectionHeader
from extractor.core.schema.blocks.table import Table
from extractor.core.schema.blocks.text import Text
from extractor.core.schema.blocks.toc import TableOfContents
from extractor.core.schema.blocks.complexregion import ComplexRegion
from extractor.core.schema.blocks.tablecell import TableCell
from extractor.core.schema.blocks.reference import Reference
