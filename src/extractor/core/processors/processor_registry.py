"""
Processor Registry - Maps processor types to their implementations.

This module provides a central registry for all processors in the extraction pipeline,
allowing dynamic loading and configuration of processors based on pipeline config.
"""

from typing import Dict, Type, Optional, List, Any
import logging

from extractor.core.schema import ProcessorType

logger = logging.getLogger(__name__)


class ProcessorRegistry:
    """Registry for mapping processor types to their implementations."""

    _registry: Dict[ProcessorType, Type] = {}

    @classmethod
    def register(cls, processor_type: ProcessorType, processor_class: Type):
        """Register a processor implementation."""
        cls._registry[processor_type] = processor_class
        logger.debug(f"Registered {processor_class.__name__} for {processor_type.value}")

    @classmethod
    def get(cls, processor_type: ProcessorType) -> Optional[Type]:
        """Get processor class by type."""
        return cls._registry.get(processor_type)

    @classmethod
    def create_processor(cls, processor_type: ProcessorType, **kwargs) -> Optional[Any]:
        """Create a processor instance by type."""
        processor_class = cls.get(processor_type)
        if not processor_class:
            logger.warning(f"No processor registered for type: {processor_type.value}")
            return None

        try:
            # Most processors take settings as kwargs
            return processor_class(**kwargs)
        except Exception as e:
            logger.error(f"Failed to create processor {processor_type.value}: {e}")
            return None

    @classmethod
    def list_registered(cls) -> List[str]:
        """List all registered processor types."""
        return [pt.value for pt in cls._registry.keys()]


def register_default_processors():
    """Register all default processors in the system."""
    # Import processors here to avoid circular imports

    # ANNOTATION PROCESSORS (MUST BE FIRST)
    try:
        from extractor.core.processors.annotation_extractor import AnnotationExtractor

        ProcessorRegistry.register(ProcessorType.ANNOTATION_EXTRACTION, AnnotationExtractor)
    except ImportError as e:
        logger.warning(f"Could not register AnnotationExtractor: {e}")

    try:
        from extractor.core.processors.annotation_guided_verifier import AnnotationGuidedVerifier

        ProcessorRegistry.register(ProcessorType.BLOCK_VERIFICATION, AnnotationGuidedVerifier)
    except ImportError as e:
        logger.warning(f"Could not register AnnotationGuidedVerifier: {e}")

    # TABLE CLASSIFICATION FIX
    try:
        from extractor.core.processors.table_classifier_fixer import TableClassifierFixer

        ProcessorRegistry.register(ProcessorType.TABLE_CLASSIFICATION_FIX, TableClassifierFixer)
    except ImportError as e:
        logger.warning(f"Could not register TableClassifierFixer: {e}")

    # TEXT SPLITTING
    try:
        from extractor.core.processors.text_splitter import TextSplitter

        ProcessorRegistry.register(ProcessorType.TEXT_SPLITTING, TextSplitter)
    except ImportError as e:
        logger.warning(f"Could not register TextSplitter: {e}")

    # TEXT PROCESSORS
    try:
        # Text cleaning processor
        from extractor.core.processors.text_cleaning import TextCleaningProcessor

        ProcessorRegistry.register(ProcessorType.TEXT_CLEANING, TextCleaningProcessor)
    except ImportError as e:
        logger.warning(f"Could not register TextCleaningProcessor: {e}")

    # BLOCK MERGING
    try:
        from extractor.core.processors.block_merger import BlockMerger

        ProcessorRegistry.register(ProcessorType.BLOCK_MERGING, BlockMerger)
    except ImportError as e:
        logger.warning(f"Could not register BlockMerger: {e}")

    # BLOCK CONSOLIDATION
    try:
        from extractor.core.processors.block_consolidator import BlockConsolidator

        ProcessorRegistry.register(ProcessorType.BLOCK_CONSOLIDATION, BlockConsolidator)
    except ImportError as e:
        logger.warning(f"Could not register BlockConsolidator: {e}")

    # HIERARCHY AND STRUCTURE
    try:
        # Section metadata propagator (for hierarchy building)
        from extractor.core.processors.section_metadata_propagator import SectionMetadataPropagator

        ProcessorRegistry.register(ProcessorType.HIERARCHY_BUILDER, SectionMetadataPropagator)
    except ImportError as e:
        logger.warning(f"Could not register SectionMetadataPropagator: {e}")

    # TABLE PROCESSORS
    try:
        # Camelot fallback processor for table recovery
        from extractor.core.processors.camelot_fallback import CamelotFallbackProcessor

        ProcessorRegistry.register(ProcessorType.TABLE_RECOVERY, CamelotFallbackProcessor)
    except ImportError as e:
        logger.warning(f"Could not register CamelotFallbackProcessor: {e}")

    # OUTPUT RENDERERS
    try:
        from extractor.core.processors.output_renderer import OutputRenderer

        ProcessorRegistry.register(ProcessorType.OUTPUT_RENDERER, OutputRenderer)
    except ImportError as e:
        logger.warning(f"Could not register OutputRenderer: {e}")

    # FONT STYLE PROCESSOR
    try:
        from extractor.core.processors.font_style import FontStyleProcessor

        ProcessorRegistry.register(ProcessorType.FONT_STYLE, FontStyleProcessor)
    except ImportError as e:
        logger.warning(f"Could not register FontStyleProcessor: {e}")

    # SUSPICIOUS BLOCK PROCESSOR
    try:
        from extractor.core.processors.suspicious_block import SuspiciousBlockProcessor

        ProcessorRegistry.register(ProcessorType.SUSPICIOUS_BLOCK, SuspiciousBlockProcessor)
    except ImportError as e:
        logger.warning(f"Could not register SuspiciousBlockProcessor: {e}")

    # SUSPICIOUS HEADER PROCESSOR (replaces pipeline stage)
    try:
        from extractor.core.processors.suspicious_header import SuspiciousHeaderProcessor

        ProcessorRegistry.register(ProcessorType.SUSPICIOUS_HEADER, SuspiciousHeaderProcessor)
    except ImportError as e:
        logger.warning(f"Could not register SuspiciousHeaderProcessor: {e}")

    # Add more processor registrations as they are implemented
    logger.info(f"Registered {len(ProcessorRegistry.list_registered())} processor types")


# Auto-register on import
register_default_processors()


# Usage examples
async def working_usage():
    """Demonstrate processor registry usage."""
    print("Registered processors:")
    for processor_type in ProcessorRegistry.list_registered():
        print(f"  - {processor_type}")

    # Create a font style processor
    processor = ProcessorRegistry.create_processor(ProcessorType.FONT_STYLE)
    if processor:
        print(f"\nCreated processor: {type(processor).__name__}")

    return True


async def debug_function():
    """Test registry edge cases."""
    # Try to create non-existent processor
    processor = ProcessorRegistry.create_processor(ProcessorType.BLOCK_MERGING)
    if processor is None:
        print("Correctly handled missing processor type")

    # List all types
    print(f"\nTotal registered: {len(ProcessorRegistry.list_registered())}")

    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - stable example that works
    - DEBUG: Run with 'debug' argument to test edge cases
    - DO NOT create external test files - use debug_function() instead!
    """
    import asyncio
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "working"

    if mode == "debug":
        print("Running debug mode...")
        asyncio.run(debug_function())
    else:
        print("Running working usage mode...")
        asyncio.run(working_usage())
