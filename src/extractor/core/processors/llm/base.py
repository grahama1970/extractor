#!/usr/bin/env python3
"""
Base LLM Processor - Foundation for all LLM-based processors.

This module provides a base class for processors that use Large Language Models
to enhance document extraction. It handles common LLM interaction patterns.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from loguru import logger
import os
import asyncio


async def call_claude_subprocess(
    prompt: str, image_path: Optional[str] = None, timeout: int = 30, use_ultrathink: bool = False
) -> str:
    """
    Call Claude CLI using proper subprocess with correct syntax.

    Args:
        prompt: The prompt to send to Claude
        image_path: Optional path to image file (will be included in prompt)
        timeout: Timeout in seconds
        use_ultrathink: Whether to prefix prompt with 'ultrathink:'

    Returns:
        Claude's response as string
    """
    # Build the full prompt
    full_prompt = prompt
    if image_path and os.path.exists(image_path):
        # Include image path in the prompt for Claude to analyze
        full_prompt = f"Please analyze the image at {image_path}\n\n{prompt}"

    if use_ultrathink:
        full_prompt = f"ultrathink: {full_prompt}"

    # Set up environment with proper PATH
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin:/usr/local/bin:/home/graham/.bun/bin:" + env.get("PATH", "")
    env["BUN_INSTALL"] = "/home/graham/.bun"

    # Use correct claude -p syntax (NOT --print)
    cmd = ["/home/graham/.bun/bin/claude", "-p", "--dangerously-skip-permissions"]

    try:
        # Create subprocess with proper stream handling
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Send prompt and get response
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=full_prompt.encode()), timeout=timeout
        )

        if proc.returncode == 0 and stdout:
            return stdout.decode().strip()
        else:
            error_msg = stderr.decode() if stderr else "No error message"
            logger.error(f"Claude subprocess failed: {error_msg}")
            return ""

    except asyncio.TimeoutError:
        logger.error(f"Claude subprocess timed out after {timeout}s")
        if proc:
            proc.terminate()
            await proc.wait()
        return ""
    except Exception as e:
        logger.error(f"Claude subprocess error: {e}")
        return ""


def call_claude_subprocess_sync(
    prompt: str, image_path: Optional[str] = None, timeout: int = 30, use_ultrathink: bool = False
) -> str:
    """
    Synchronous version of call_claude_subprocess.
    """
    import asyncio

    return asyncio.run(call_claude_subprocess(prompt, image_path, timeout, use_ultrathink))


class BaseLLMProcessor(ABC):
    """Base class for LLM-based processors."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the base LLM processor.

        Args:
            config: LLM configuration including model, cache settings, etc.
        """
        self.config = config or {}
        self.name = "BaseLLMProcessor"
        self.llm_service = None
        self._initialize_llm_service()

    def _initialize_llm_service(self):
        """Initialize the LLM service if configuration is provided."""
        if self.config.get("litellm_model"):
            try:
                from extractor.core.services.litellm import LiteLLMService

                self.llm_service = LiteLLMService(self.config)
                logger.info(f"Initialized LLM service with model: {self.config['litellm_model']}")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM service: {e}")
                self.llm_service = None
        else:
            logger.debug("No LLM model configured, processor will run without LLM enhancement")

    @abstractmethod
    def process(self, *args, **kwargs) -> Any:
        """
        Process the input data. Must be implemented by subclasses.

        Returns:
            Processed result
        """
        pass

    async def _call_llm(
        self,
        prompt: str,
        image: Any = None,
        block: Any = None,
        response_schema: Any = None,
        max_retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        Call the LLM service with standard error handling.

        Args:
            prompt: The prompt for the LLM
            image: Optional image to analyze
            block: Optional block context
            response_schema: Optional Pydantic schema for structured output
            max_retries: Maximum number of retry attempts

        Returns:
            LLM response as a dictionary, or None if failed
        """
        if not self.llm_service:
            logger.warning("No LLM service available")
            return None

        try:
            response = await call_claude_subprocess(prompt)

            if isinstance(response, dict):
                return response
            elif hasattr(response, "dict"):
                # Handle Pydantic models
                return response.dict()
            else:
                logger.warning(f"Unexpected response type from LLM: {type(response)}")
                return None

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def _extract_text_from_blocks(self, blocks: List[Dict[str, Any]]) -> str:
        """
        Extract combined text from a list of blocks.

        Args:
            blocks: List of block dictionaries

        Returns:
            Combined text string
        """
        texts = []
        for block in blocks:
            text = block.get("text", "") or block.get("html", "")
            if text:
                texts.append(text)
        return "\n".join(texts)

    def _find_blocks_in_region(
        self,
        blocks: List[Dict[str, Any]],
        bbox: List[float],
        page: int = None,
        tolerance: float = 5.0,
    ) -> List[Dict[str, Any]]:
        """
        Find blocks that overlap with a given bounding box region.

        Args:
            blocks: List of blocks to search
            bbox: Bounding box [x0, y0, x1, y1]
            page: Optional page number filter
            tolerance: Pixel tolerance for overlap detection

        Returns:
            List of blocks that overlap with the region
        """
        if not bbox or len(bbox) != 4:
            return []

        overlapping = []
        x0, y0, x1, y1 = bbox

        for block in blocks:
            # Check page if specified
            if page is not None and block.get("page", 0) != page:
                continue

            block_bbox = block.get("bbox", [])
            if not block_bbox or len(block_bbox) != 4:
                continue

            bx0, by0, bx1, by1 = block_bbox

            # Check for overlap with tolerance
            if (
                bx1 + tolerance >= x0
                and bx0 - tolerance <= x1
                and by1 + tolerance >= y0
                and by0 - tolerance <= y1
            ):
                overlapping.append(block)

        return overlapping

    def _confidence_score(self, result: Dict[str, Any]) -> float:
        """
        Calculate a confidence score for the processing result.

        Args:
            result: Processing result dictionary

        Returns:
            Confidence score between 0 and 1
        """
        # Default implementation - can be overridden by subclasses
        if "confidence" in result:
            return float(result["confidence"])
        elif "score" in result:
            return float(result["score"])
        else:
            # Base confidence on whether we got a result
            return 0.8 if result else 0.0
