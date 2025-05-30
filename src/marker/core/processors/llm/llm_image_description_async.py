"""
Async processor for generating image descriptions using LiteLLM's acompletion.
"""
import asyncio
import base64
import io
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import aiohttp
import litellm
from litellm.utils import get_secret
from PIL import Image
from tqdm.asyncio import tqdm_asyncio

from marker.core.schema import BlockTypes
from marker.core.schema.blocks import Block
from marker.core.schema.document import Document
from marker.core.processors import Processor


class DetailLevel(str, Enum):
    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"


class LLMImageDescriptionAsyncProcessor(Processor):
    """
    Processor for generating image descriptions with LiteLLM's acompletion.
    """
    name: str = "llm_image_description_async"
    block_types: List[BlockTypes] = [BlockTypes.Picture, BlockTypes.Figure]
    
    # Configuration options
    litellm_model: str = "vertex_ai/gemini-2.0-flash"  # Updated to Vertex AI Gemini model
    description_detail_level: DetailLevel = DetailLevel.STANDARD
    max_concurrent_images: int = 5  # Max images to process concurrently
    batch_size: int = 10  # Number of images to process in one batch
    
    async def process_images_async(self, document: Document) -> Document:
        """
        Process all images in the document with async batch processing.
        """
        # Find all images in the document
        image_blocks = document.contained_blocks(self.block_types)
        
        if not image_blocks:
            logging.info("No image blocks found in document.")
            return document
            
        logging.info(f"Processing {len(image_blocks)} images using LiteLLM async ({self.litellm_model})...")
        
        semaphore = asyncio.Semaphore(self.max_concurrent_images)
        tasks = []
        
        # Create processing tasks
        for i, block in enumerate(image_blocks):
            task = self.process_image_block_with_semaphore(document, block, semaphore)
            tasks.append(task)
            
            # Process in batches to avoid memory issues
            if len(tasks) >= self.batch_size:
                await self._process_batch(tasks)
                tasks = []
        
        # Process any remaining tasks
        if tasks:
            await self._process_batch(tasks)
        
        logging.info(f"Completed processing {len(image_blocks)} images.")
        return document
    
    async def _process_batch(self, tasks: List[asyncio.Task]):
        """Process a batch of image tasks with a progress bar."""
        if not tasks:
            return
            
        batch_results = []
        for coro in tqdm_asyncio(asyncio.as_completed(tasks), total=len(tasks), desc="Processing images"):
            try:
                result = await coro
                batch_results.append(result)
            except Exception as e:
                logging.error(f"Error processing image: {e}")
    
    async def process_image_block_with_semaphore(self, document: Document, block: Block, semaphore: asyncio.Semaphore):
        """Process an image block using a semaphore to limit concurrency."""
        async with semaphore:
            return await self.process_image_block(document, block)
    
    async def process_image_block(self, document: Document, block: Block) -> Dict[str, Any]:
        """
        Process a single image block and add the description to its caption.
        """
        start_time = time.time()
        try:
            # Get the image
            image = block.get_image(document, highres=True)
            if not image:
                logging.warning(f"No image data for {block.id}")
                return {"block_id": block.id, "success": False, "error": "No image data"}
            
            # Convert image to base64
            img_base64 = self._image_to_base64(image)
            
            # Generate description using LiteLLM's acompletion
            description = await self._generate_description_async(img_base64)
            
            # Update the block with the description
            self._update_block_with_description(block, description)
            
            processing_time = time.time() - start_time
            logging.info(f"Processed {block.id} in {processing_time:.2f}s")
            return {"block_id": block.id, "success": True, "processing_time": processing_time}
            
        except Exception as e:
            processing_time = time.time() - start_time
            logging.error(f"Error processing {block.id}: {e}")
            return {"block_id": block.id, "success": False, "error": str(e), "processing_time": processing_time}
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    def _get_detail_level_prompt(self) -> str:
        """Get the prompt modifier based on the detail level."""
        if self.description_detail_level == DetailLevel.BRIEF:
            return "Briefly describe this image in 1-2 sentences."
        elif self.description_detail_level == DetailLevel.DETAILED:
            return "Provide a detailed description of this image, including all visual elements, layout, and any text content."
        else:  # STANDARD
            return "Describe this image clearly and concisely, mentioning the main visual elements."
    
    async def _generate_description_async(self, base64_image: str) -> str:
        """
        Generate an image description using LiteLLM's acompletion.
        """
        prompt = f"{self._get_detail_level_prompt()} Focus on factual description rather than interpretation."
        
        try:
            response = await litellm.acompletion(
                model=self.litellm_model,
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=500,
                timeout=60  # Increase timeout to 60 seconds for Vertex AI
            )
            
            if response and hasattr(response, 'choices') and response.choices:
                description = response.choices[0].message.content.strip()
                return description
            else:
                logging.warning(f"Unexpected response structure from LiteLLM: {response}")
                return "Image description not available."
                
        except Exception as e:
            logging.error(f"Error generating image description: {e}")
            return "Error generating image description."
    
    def _update_block_with_description(self, block: Block, description: str):
        """Update the block with the generated description."""
        # Different block types might store captions differently
        if hasattr(block, 'caption'):
            # If there's already a caption, enhance it
            if block.caption:
                block.caption = f"{block.caption}\n\nDescription: {description}"
            else:
                block.caption = f"Description: {description}"
        
        # Store in a dedicated description field if available
        if hasattr(block, 'description'):
            block.description = description
            
        # Also store in the block's metadata for consistent access
        if not hasattr(block, 'metadata'):
            block.metadata = {}
        block.metadata['generated_description'] = description
    
    async def aprocess_document(self, document: Document) -> Document:
        """
        Process the document asynchronously using LiteLLM's acompletion.
        """
        return await self.process_images_async(document)
    
    def process_document(self, document: Document) -> Document:
        """
        Process the document synchronously by running the async method in an event loop.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new loop
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(self.process_images_async(document))
            finally:
                new_loop.close()
        else:
            return loop.run_until_complete(self.process_images_async(document))