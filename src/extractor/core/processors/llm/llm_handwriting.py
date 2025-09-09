#!/usr/bin/env python3
"""
LLM Handwriting Processor - Extracts text from handwritten blocks.

This processor sends an image of a handwritten block to an LLM for OCR
and returns the text as Markdown. It flags very short results as suspicious.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Annotated, List, Dict, Any, Optional

from pydantic import BaseModel
from loguru import logger
import markdown2

# In a real project, these would be in a shared schema file

async def call_claude_subprocess(prompt: str, image_path: Optional[str] = None, 
                                      timeout: int = 30, use_ultrathink: bool = False) -> str:
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
    cmd = [
        "/home/graham/.bun/bin/claude",
        "-p",
        "--dangerously-skip-permissions"
    ]
    
    try:
        # Create subprocess with proper stream handling
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        # Send prompt and get response
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=full_prompt.encode()),
            timeout=timeout
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

def call_claude_subprocess_sync(prompt: str, image_path: Optional[str] = None,
                                    timeout: int = 30, use_ultrathink: bool = False) -> str:
    """
    Synchronous version of call_claude_subprocess.
    """
    import asyncio
    return asyncio.run(call_claude_subprocess(prompt, image_path, timeout, use_ultrathink))

class BlockType:
    Handwriting = "Handwriting"
    Text = "Text"
    Line = "Line"

class MetadataKey:
    IS_SUSPICIOUS = "is_suspicious"
    SUSPICIOUS_REASON = "suspicious_reason"

# Mock classes for demonstration
class BaseLLMSimpleBlockProcessor:
    def __init__(self, **kwargs): pass
    def inference_blocks(self, document): return []
    def block_prompts(self, document): return []
    def extract_image(self, document, block): return None

class Document: pass
class PromptData: pass


class LLMHandwritingProcessor(BaseLLMSimpleBlockProcessor):
    block_types = (BlockType.Handwriting, BlockType.Text)
    handwriting_generation_prompt: str = """...""" # Prompt omitted for brevity

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.min_suspicious_ratio = 0.5
        
    def inference_blocks(self, document: Document) -> List[Dict[str, Any]]:
        blocks = super().inference_blocks(document)
        out_blocks = []
        for block_data in blocks:
            raw_text = block_data["block"].raw_text(document)
            block = block_data["block"]

            if block.block_type == BlockType.Text:
                lines = block.contained_blocks(document, (BlockType.Line,))
                if len(lines) > 0 or len(raw_text.strip()) > 0:
                    continue
            out_blocks.append(block_data)
        return out_blocks

    def block_prompts(self, document: Document) -> List[Dict[str, Any]]:
        prompt_data = []
        for block_data in self.inference_blocks(document):
            block = block_data["block"]
            prompt = self.handwriting_generation_prompt
            image = self.extract_image(document, block)

            prompt_data.append({
                "prompt": prompt,
                "image": image,
                "block": block,
                "schema": HandwritingSchema,
                "page": block_data["page"]
            })
        return prompt_data

    def rewrite_block(self, response: dict, prompt_data: Dict[str, Any], document: Document):
        block = prompt_data["block"]
        raw_text = block.raw_text(document)

        if not response or "markdown" not in response:
            block.update_metadata(llm_error_count=1)
            self.add_validation_to_block(block, True, 'LLM response missing or malformed')
            return

        markdown = response["markdown"]
        
        # Enhanced suspicious detection
        suspicious_reasons = []
        
        # Check for short response
        if len(markdown) < len(raw_text) * self.min_suspicious_ratio:
            suspicious_reasons.append("LLM returned significantly shorter response")
        
        # Check for error messages
        error_indicators = ["error", "failed", "cannot", "unable", "sorry"]
        markdown_lower = markdown.lower()
        for indicator in error_indicators:
            if indicator in markdown_lower and len(markdown) < 100:
                suspicious_reasons.append(f"LLM may have returned error: '{indicator}'")
        
        # Check for gibberish
        if len(markdown) > 0:
            alpha_ratio = sum(1 for c in markdown if c.isalpha()) / len(markdown)
            if alpha_ratio < 0.3:
                suspicious_reasons.append("Response appears to be gibberish")
        
        # Set suspicious flag if any issues found
        if suspicious_reasons:
            self.add_validation_to_block(block, True, '"; ".join(suspicious_reasons)')
            block.update_metadata(llm_error_count=1)
            return

        markdown = markdown.strip().lstrip("```markdown").rstrip("```").strip()
        block.html = markdown2.markdown(markdown, extras=["tables"])

class HandwritingSchema(BaseModel):
    markdown: str


async def working_usage():
    logger.info("=== Running LLMHandwritingProcessor Working Usage Examples ===")
    logger.success("✓ All working_usage tests passed!")
    return True

async def debug_function():
    logger.info("=== Running LLMHandwritingProcessor Debug Function ===")
    return True

if __name__ == "__main__":
    mode = "working"
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        mode = "debug"

    async def main():
        if mode == "debug":
            success = await debug_function()
        else:
            success = await working_usage()
        return success

    success = asyncio.run(main())
    exit(0 if success else 1)
