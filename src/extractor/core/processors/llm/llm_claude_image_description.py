"""
Enhanced Image Description Processor with Claude Integration
Module: llm_claude_image_description.py
Description: Implementation of llm claude image description functionality

Provides enhanced image description using Claude's multimodal capabilities
when Claude features are enabled, falling back to standard LLM processing.
"""

import asyncio
from pathlib import Path
from typing import Annotated, List, Dict, Any, Optional
from loguru import logger

from extractor.core.processors.llm.llm_image_description import LLMImageDescriptionProcessor
from extractor.core.processors.claude_image_describer import (
    ImageDescriptionEngine,
    ImageData,
    ImageType
)
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block
from extractor.core.schema.document import Document


class LLMClaudeImageDescriptionProcessor(LLMImageDescriptionProcessor):
    """
    Enhanced image description processor that uses Claude's multimodal
    capabilities when available, with fallback to standard LLM processing.
    """
    
    use_claude_if_available: Annotated[
        bool,
        "Use Claude's multimodal capabilities for image description if available."
    ] = True
    
    claude_detail_level: Annotated[
        str,
        "Detail level for Claude descriptions: 'brief', 'standard', or 'comprehensive'."
    ] = "comprehensive"
    
    claude_extract_data: Annotated[
        bool,
        "Extract data from charts and tables using Claude."
    ] = True
    
    claude_generate_accessibility: Annotated[
        bool,
        "Generate accessibility descriptions using Claude."
    ] = True
    
    claude_workspace_dir: Annotated[
        Optional[str],
        "Workspace directory for Claude processing."
    ] = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.claude_engine = None
        
        # Check if Claude features are enabled
        if self.use_claude_if_available and self._is_claude_enabled():
            workspace_dir = Path(self.claude_workspace_dir or "/tmp/marker_claude_images")
            workspace_dir.mkdir(parents=True, exist_ok=True)
            self.claude_engine = ImageDescriptionEngine(workspace_dir)
            logger.info("Claude multimodal image description enabled")
    
    def _is_claude_enabled(self) -> bool:
        """Check if Claude features are enabled in configuration."""
        # This would check the global Claude configuration
        # For now, we'll check if the claude command is available
        import subprocess
        try:
            result = subprocess.run(['which', 'claude'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def __call__(self, document: Document):
        """Process images with Claude if available, otherwise use standard processing."""
        if not self.use_llm:
            return
            
        # Check if we should use Claude
        if self.claude_engine and self._should_use_claude(document):
            self._process_with_claude(document)
        else:
            # Fall back to standard processing
            super().__call__(document)
    
    def _should_use_claude(self, document: Document) -> bool:
        """Determine if Claude should be used for this document."""
        # Check if Claude is configured in the document
        if hasattr(document, 'claude_config'):
            claude_config = document.claude_config
            return getattr(claude_config, 'enable_claude_features', False)
        return False
    
    def _process_with_claude(self, document: Document):
        """Process images using Claude's multimodal capabilities."""
        logger.info("Processing images with Claude multimodal capabilities")
        
        # Collect all images to process
        images_to_process = []
        block_mapping = {}  # Map image paths to blocks
        
        for page_idx, page in enumerate(document.pages):
            for block in page.contained_blocks(document, self.block_types):
                # Extract image to temporary file
                try:
                    image_path = self._extract_image_to_file(document, block, page_idx)
                    if image_path:
                        # Determine image type
                        image_type = self._determine_image_type(block, document)
                        
                        # Get surrounding context
                        context = self._get_image_context(block, page, document)
                        
                        # Create ImageData
                        image_data = ImageData(
                            image_path=image_path,
                            image_type=image_type,
                            page_number=page_idx + 1,
                            context=context,
                            caption=getattr(block, 'caption', None),
                            alt_text=getattr(block, 'alt_text', None),
                            bbox=block.polygon.bbox if block.polygon else None
                        )
                        
                        images_to_process.append(image_data)
                        block_mapping[str(image_path)] = block
                        
                except Exception as e:
                    logger.error(f"Failed to extract image for block: {e}")
                    block.update_metadata(llm_error_count=1)
        
        if not images_to_process:
            logger.info("No images to process")
            return
        
        # Submit images to Claude for processing
        try:
            task_id = self.claude_engine.submit_images_sync(
                images=images_to_process,
                detail_level=self.claude_detail_level,
                include_data_extraction=self.claude_extract_data,
                include_accessibility=self.claude_generate_accessibility
            )
            
            # Wait for results
            result = self.claude_engine.get_descriptions_sync(task_id, timeout=300)
            
            if result and result.descriptions:
                logger.info(f"Claude described {len(result.descriptions)} images")
                
                # Apply descriptions to blocks
                for desc in result.descriptions:
                    # Find corresponding block
                    for img_path, block in block_mapping.items():
                        # Match by some criteria (simplified here)
                        if block and desc.description:
                            # Apply the description
                            block.description = desc.description
                            
                            # Add additional metadata
                            metadata = {
                                'claude_confidence': desc.confidence,
                                'image_type': desc.image_type.value,
                                'llm_model': 'claude-3-5-sonnet'
                            }
                            
                            if desc.keywords:
                                metadata['keywords'] = desc.keywords
                            
                            if desc.extracted_data:
                                metadata['extracted_data'] = desc.extracted_data
                                
                            if desc.accessibility_text:
                                block.alt_text = desc.accessibility_text
                                
                            if desc.detected_text:
                                metadata['detected_text'] = desc.detected_text
                                
                            block.update_metadata(**metadata)
                            
                            # Only apply to first matching block
                            break
            else:
                logger.warning("Claude image description failed or timed out")
                # Fall back to standard processing
                super().__call__(document)
                
        except Exception as e:
            logger.error(f"Claude image processing failed: {e}")
            # Fall back to standard processing
            super().__call__(document)
        finally:
            # Clean up temporary image files
            for img_data in images_to_process:
                if img_data.image_path.exists():
                    img_data.image_path.unlink()
    
    def _extract_image_to_file(self, document: Document, block: Block, page_idx: int) -> Optional[Path]:
        """Extract image from block and save to temporary file."""
        import tempfile
        import uuid
        
        # Extract image using parent method
        image_pil = self.extract_image(document, block)
        if not image_pil:
            return None
        
        # Save to temporary file
        temp_dir = Path(tempfile.gettempdir()) / "marker_claude_images"
        temp_dir.mkdir(exist_ok=True)
        
        image_path = temp_dir / f"image_{page_idx}_{uuid.uuid4().hex[:8]}.png"
        image_pil.save(image_path, format='PNG')
        
        return image_path
    
    def _determine_image_type(self, block: Block, document: Document) -> ImageType:
        """Determine the type of image based on context."""
        block_text = block.raw_text(document).lower() if hasattr(block, 'raw_text') else ""
        
        # Check block metadata or surrounding text for clues
        if any(word in block_text for word in ['chart', 'graph', 'plot']):
            return ImageType.CHART
        elif any(word in block_text for word in ['diagram', 'flow', 'architecture']):
            return ImageType.DIAGRAM
        elif any(word in block_text for word in ['table', 'grid']):
            return ImageType.TABLE_IMAGE
        elif any(word in block_text for word in ['equation', 'formula']):
            return ImageType.EQUATION_IMAGE
        elif any(word in block_text for word in ['screenshot', 'screen']):
            return ImageType.SCREENSHOT
        elif block.block_type == BlockTypes.Figure:
            return ImageType.FIGURE
        else:
            return ImageType.UNKNOWN
    
    def _get_image_context(self, image_block: Block, page: Block, document: Document) -> str:
        """Get surrounding text context for an image."""
        context_lines = []
        
        # Find image position in page
        image_idx = None
        page_blocks = list(page.contained_blocks(document))
        for idx, block in enumerate(page_blocks):
            if block.id == image_block.id:
                image_idx = idx
                break
        
        if image_idx is None:
            return ""
        
        # Get text before and after (up to 3 blocks each way)
        for i in range(max(0, image_idx - 3), min(len(page_blocks), image_idx + 4)):
            if i == image_idx:
                continue
            block = page_blocks[i]
            if block.block_type in [BlockTypes.Text, BlockTypes.TextInlineMath]:
                if hasattr(block, 'text'):
                    context_lines.append(block.text)
        
        return " ".join(context_lines)[:500]  # Limit context length
    

# Register the enhanced processor
def register_enhanced_image_processor():
    """Register the enhanced image processor to replace the standard one."""
    from extractor.core.processors import BaseProcessor
    
    # This would be called during initialization if Claude features are enabled
    # The processor would be registered in the processor list
    pass