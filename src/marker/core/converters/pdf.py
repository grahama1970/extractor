import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # disables a tokenizers warning

from collections import defaultdict
from typing import Annotated, Any, Dict, List, Optional, Type, Tuple

from marker.core.processors import BaseProcessor
from marker.core.processors.llm.llm_table_merge import LLMTableMergeProcessor
from marker.core.providers.registry import provider_from_filepath
from marker.core.builders.document import DocumentBuilder
from marker.core.builders.layout import LayoutBuilder
from marker.core.builders.llm_layout import LLMLayoutBuilder
from marker.core.builders.line import LineBuilder
from marker.core.builders.ocr import OcrBuilder
from marker.core.builders.structure import StructureBuilder
from marker.core.converters import BaseConverter
from marker.core.processors.blockquote import BlockquoteProcessor
from marker.core.processors.code import CodeProcessor
from marker.core.processors.debug import DebugProcessor
from marker.core.processors.document_toc import DocumentTOCProcessor
from marker.core.processors.equation import EquationProcessor
from marker.core.processors.footnote import FootnoteProcessor
from marker.core.processors.ignoretext import IgnoreTextProcessor
from marker.core.processors.line_numbers import LineNumbersProcessor
from marker.core.processors.list import ListProcessor
from marker.core.processors.llm.llm_complex import LLMComplexRegionProcessor
from marker.core.processors.llm.llm_form import LLMFormProcessor
from marker.core.processors.llm.llm_image_description import LLMImageDescriptionProcessor
from marker.core.processors.llm.llm_table import LLMTableProcessor
from marker.core.processors.llm.llm_inlinemath import LLMInlineMathLinesProcessor
from marker.core.processors.page_header import PageHeaderProcessor
from marker.core.processors.reference import ReferenceProcessor
from marker.core.processors.sectionheader import SectionHeaderProcessor
from marker.core.processors.table import TableProcessor
from marker.core.processors.text import TextProcessor
from marker.core.processors.llm.llm_equation import LLMEquationProcessor
from marker.core.renderers.markdown import MarkdownRenderer
from marker.core.schema import BlockTypes
from marker.core.schema.blocks import Block
from marker.core.schema.registry import register_block_class
from marker.core.util import strings_to_classes
from marker.core.processors.llm.llm_handwriting import LLMHandwritingProcessor
from marker.core.processors.order import OrderProcessor
from marker.core.services.litellm import LiteLLMService
from marker.core.processors.line_merge import LineMergeProcessor
from marker.core.processors.llm.llm_mathblock import LLMMathBlockProcessor
try:
    from marker.core.processors.enhanced_camelot import EnhancedTableProcessor
    ENHANCED_CAMELOT_AVAILABLE = True
except ImportError:
    ENHANCED_CAMELOT_AVAILABLE = False


class PdfConverter(BaseConverter):
    """
    A converter for processing and rendering PDF files into Markdown, JSON, HTML and other formats.
    """
    override_map: Annotated[
        Dict[BlockTypes, Type[Block]],
        "A mapping to override the default block classes for specific block types.",
        "The keys are `BlockTypes` enum values, representing the types of blocks,",
        "and the values are corresponding `Block` class implementations to use",
        "instead of the defaults."
    ] = defaultdict()
    use_llm: Annotated[
        bool,
        "Enable higher quality processing with LLMs.",
    ] = False
    default_processors: Tuple[BaseProcessor, ...] = (
        OrderProcessor,
        LineMergeProcessor,
        BlockquoteProcessor,
        CodeProcessor,
        DocumentTOCProcessor,
        EquationProcessor,
        FootnoteProcessor,
        IgnoreTextProcessor,
        LineNumbersProcessor,
        ListProcessor,
        PageHeaderProcessor,
        SectionHeaderProcessor,
        # Use EnhancedTableProcessor if available, otherwise fallback to TableProcessor
        *(
            [EnhancedTableProcessor] 
            if ENHANCED_CAMELOT_AVAILABLE 
            else [TableProcessor]
        ),
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        TextProcessor,
        LLMInlineMathLinesProcessor,
        LLMComplexRegionProcessor,
        LLMImageDescriptionProcessor,
        LLMEquationProcessor,
        LLMHandwritingProcessor,
        LLMMathBlockProcessor,
        ReferenceProcessor,
        DebugProcessor,
    )

    def __init__(
        self,
        artifact_dict: Dict[str, Any],
        processor_list: Optional[List[str]] = None,
        renderer: str | None = None,
        llm_service: str | None = None,
        config=None
    ):
        super().__init__(config)

        if config is None:
            config = {}

        for block_type, override_block_type in self.override_map.items():
            register_block_class(block_type, override_block_type)

        if processor_list:
            if isinstance(processor_list, str) and processor_list.startswith("default+"):
                # Use default processors and append the additional ones
                additional_processor = processor_list.replace("default+", "")
                processor_list = list(self.default_processors) + strings_to_classes([additional_processor])
            else:
                processor_list = strings_to_classes(processor_list)
        else:
            processor_list = self.default_processors

        if renderer:
            renderer = strings_to_classes([renderer])[0]
        else:
            renderer = MarkdownRenderer

        if llm_service:
            llm_service_cls = strings_to_classes([llm_service])[0]
            llm_service = self.resolve_dependencies(llm_service_cls)
        elif config.get("use_llm", False):
            llm_service = self.resolve_dependencies(LiteLLMService)

        # Inject llm service into artifact_dict so it can be picked up by processors, etc.
        artifact_dict["llm_service"] = llm_service
        self.llm_service = llm_service

        self.artifact_dict = artifact_dict
        self.renderer = renderer

        processor_list = self.initialize_processors(processor_list)
        self.processor_list = processor_list

        self.layout_builder_class = LayoutBuilder
        if self.use_llm:
            self.layout_builder_class = LLMLayoutBuilder

    def build_document(self, filepath: str):
        provider_cls = provider_from_filepath(filepath)
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)
        provider = provider_cls(filepath, self.config)
        document = DocumentBuilder(self.config)(provider, layout_builder, line_builder, ocr_builder)
        structure_builder_cls = self.resolve_dependencies(StructureBuilder)
        structure_builder_cls(document)

        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str):
        document = self.build_document(filepath)
        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)
