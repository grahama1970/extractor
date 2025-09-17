from enum import auto, Enum


class BlockTypes(str, Enum):
    Line = auto()
    Span = auto()
    Char = auto()
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


# Define ProcessorType here alongside BlockTypes
class ProcessorType(Enum):
    """Defines the types of processors available in the pipeline."""

    ANNOTATION_LEARNING = "annotation_learning"
    MARKER_EXTRACTION = "marker_extraction"
    TEXT_CLEANING = "text_cleaning"
    BLOCK_MERGING = "block_merging"
    SECTION_HEADER_DETECTION = "section_header_detection"
    BLOCK_VERIFICATION = "block_verification"
    HIERARCHY_BUILDER = "hierarchy_builder"
    OUTPUT_RENDERER = "output_renderer"
    FONT_STYLE = "font_style"
    SUSPICIOUS_BLOCK = "suspicious_block"
    SUSPICIOUS_HEADER = "suspicious_header"
